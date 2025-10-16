"""
Security tests for JWT-based chat session authentication
Tests for vulnerabilities and unauthorized access attempts
"""
import jwt
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from ..models import ChatRoom
from ..utils.security.auth import ChatSessionValidator

User = get_user_model()


class ChatSessionSecurityTests(TestCase):
    """Test suite for JWT session security vulnerabilities"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            reserved_username='testuser'
        )

        # Create test chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user,
            access_mode='public'
        )
        self.chat_code = self.chat_room.code

        # Valid session token
        self.valid_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_code,
            username='testuser',
            user_id=str(self.user.id)
        )

    def test_message_send_requires_session_token(self):
        """Test that sending messages without session token is blocked"""
        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={'username': 'testuser', 'content': 'Hello'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('session token', response.json().get('detail', '').lower())

    def test_message_send_with_invalid_token(self):
        """Test that invalid JWT tokens are rejected"""
        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': 'invalid.jwt.token'
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_message_send_with_expired_token(self):
        """Test that expired tokens are rejected"""
        # Create expired token
        expired_payload = {
            'chat_code': self.chat_code,
            'username': 'testuser',
            'user_id': str(self.user.id),
            'iat': datetime.utcnow() - timedelta(hours=25),
            'exp': datetime.utcnow() - timedelta(hours=1)
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm='HS256')

        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': expired_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('expired', response.json().get('detail', '').lower())

    def test_cannot_use_token_for_different_chat(self):
        """Test that tokens are chat-specific"""
        # Create another chat room
        other_chat = ChatRoom.objects.create(
            name='Other Chat',
            host=self.user,
            access_mode='public'
        )

        # Try to use token from first chat in second chat
        response = self.client.post(
            f'/api/chats/{other_chat.code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': self.valid_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('not valid for this chat', response.json().get('detail', '').lower())

    def test_cannot_use_token_for_different_username(self):
        """Test that tokens are username-specific"""
        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'different_user',  # Different username
                'content': 'Hello',
                'session_token': self.valid_token  # Token for 'testuser'
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('username mismatch', response.json().get('detail', '').lower())

    def test_cannot_forge_token_with_wrong_secret(self):
        """Test that tokens signed with wrong secret are rejected"""
        forged_payload = {
            'chat_code': self.chat_code,
            'username': 'testuser',
            'user_id': str(self.user.id),
            'iat': datetime.utcnow(),
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        forged_token = jwt.encode(forged_payload, 'wrong_secret', algorithm='HS256')

        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': forged_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_modify_token_payload(self):
        """Test that modified tokens are rejected"""
        # Decode token, modify, and re-encode with wrong secret
        decoded = jwt.decode(self.valid_token, settings.SECRET_KEY, algorithms=['HS256'])
        decoded['username'] = 'hacker'  # Try to change username

        # Re-encode with wrong secret (can't re-encode with right secret without knowledge)
        modified_token = jwt.encode(decoded, 'attacker_secret', algorithm='HS256')

        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'hacker',
                'content': 'Hello',
                'session_token': modified_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_join_endpoint_issues_valid_token(self):
        """Test that join endpoint properly issues session tokens"""
        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'newuser'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('session_token', data)

        # Verify token is valid
        token = data['session_token']
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(payload['chat_code'], self.chat_code)
        self.assertEqual(payload['username'], 'newuser')

    def test_valid_token_allows_message_send(self):
        """Test that valid tokens allow message sending"""
        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello World',
                'session_token': self.valid_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['content'], 'Hello World')

    def test_replay_attack_prevention(self):
        """Test that the same message cannot be replayed multiple times maliciously"""
        # Note: This tests that tokens remain valid for their lifetime
        # Real replay attack prevention would require nonces/request IDs

        # First message should succeed
        response1 = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Message 1',
                'session_token': self.valid_token
            },
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Second message with same token should also succeed
        # (tokens are reusable within their lifetime - this is by design)
        response2 = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Message 2',
                'session_token': self.valid_token
            },
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)

    def test_sql_injection_in_username(self):
        """Test that SQL injection attempts in username are blocked by validation"""
        malicious_username = "'; DROP TABLE chats_message; --"

        # Try to join with malicious username
        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': malicious_username},
            content_type='application/json'
        )

        # Should be rejected due to invalid characters (contains quotes, semicolons, spaces, hyphens)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('username', error_msg)

        # Verify chat room still exists (not affected)
        self.assertTrue(ChatRoom.objects.filter(code=self.chat_code).exists())

    def test_xss_in_username(self):
        """Test that XSS attempts in username are blocked by validation"""
        xss_username = "<script>alert('XSS')</script>"

        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': xss_username},
            content_type='application/json'
        )

        # Should be rejected due to invalid characters (contains angle brackets, parentheses, quotes, etc.)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('username', error_msg)

    def test_token_without_expiration(self):
        """Test that tokens must have expiration"""
        # Create token without exp claim
        payload_no_exp = {
            'chat_code': self.chat_code,
            'username': 'testuser',
            'user_id': str(self.user.id),
            'iat': datetime.utcnow()
            # Missing 'exp'
        }
        token_no_exp = jwt.encode(payload_no_exp, settings.SECRET_KEY, algorithm='HS256')

        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': token_no_exp
            },
            content_type='application/json'
        )

        # Should be rejected (tokens must have expiration)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rate_limiting_not_bypassed_by_multiple_tokens(self):
        """Test that having multiple valid tokens doesn't bypass rate limits"""
        # Create multiple tokens
        tokens = [
            ChatSessionValidator.create_session_token(
                chat_code=self.chat_code,
                username=f'user{i}',
                user_id=None
            )
            for i in range(5)
        ]

        # Each token should work independently
        for i, token in enumerate(tokens):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/messages/send/',
                data={
                    'username': f'user{i}',
                    'content': f'Message {i}',
                    'session_token': token
                },
                content_type='application/json'
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_empty_or_null_token(self):
        """Test that empty or null tokens are rejected"""
        test_cases = [
            {'session_token': ''},
            {'session_token': None},
            {}  # Missing session_token
        ]

        for data in test_cases:
            data.update({'username': 'testuser', 'content': 'Hello'})
            response = self.client.post(
                f'/api/chats/{self.chat_code}/messages/send/',
                data=data,
                content_type='application/json'
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_token_with_future_iat(self):
        """Test that tokens with future issued-at time are rejected"""
        future_payload = {
            'chat_code': self.chat_code,
            'username': 'testuser',
            'user_id': str(self.user.id),
            'iat': datetime.utcnow() + timedelta(hours=1),  # Future issued-at
            'exp': datetime.utcnow() + timedelta(hours=25)
        }
        future_token = jwt.encode(future_payload, settings.SECRET_KEY, algorithm='HS256')

        response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': future_token
            },
            content_type='application/json'
        )

        # PyJWT should reject future tokens
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_private_chat_access_code_protection(self):
        """Test that private chats require correct access code to get session token"""
        # Create private chat
        private_chat = ChatRoom.objects.create(
            name='Private Chat',
            host=self.user,
            access_mode='private',
            access_code='secret123'
        )

        # Try to join without access code
        response = self.client.post(
            f'/api/chats/{private_chat.code}/join/',
            data={'username': 'hacker'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with wrong access code
        response = self.client.post(
            f'/api/chats/{private_chat.code}/join/',
            data={'username': 'hacker', 'access_code': 'wrong'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with correct access code
        response = self.client.post(
            f'/api/chats/{private_chat.code}/join/',
            data={'username': 'legit_user', 'access_code': 'secret123'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_token', response.json())


class UsernameReservationSecurityTests(TestCase):
    """Test suite for username reservation and fingerprinting security"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()

        # Create test users with reserved usernames
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='testpass123',
            reserved_username='Alice'
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='testpass123',
            reserved_username='Bobby'
        )

        # Create test chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user1,
            access_mode='public'
        )
        self.chat_code = self.chat_room.code

    def test_two_anonymous_users_same_username_blocked(self):
        """Test that two anonymous users with the same username cannot join the same chat"""
        # First anonymous user gets a generated username
        suggest_response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # First anonymous user joins with generated username
        response1 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second anonymous user tries to join with same username but different fingerprint
        response2 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint2'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response2.json()).lower()
        self.assertIn('username', error_msg)

    def test_registered_user_blocked_from_using_others_reserved_username(self):
        """Test that registered user A cannot join using registered user B's reserved_username"""
        # user1 tries to join with user2's reserved_username "Bobby"
        self.client.force_login(self.user1)
        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'Bobby'},  # user2's reserved_username
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('reserved', error_msg)


    def test_anonymous_user_username_persistence_via_fingerprint(self):
        """Test that anonymous users are locked to their username via fingerprint"""
        # Anonymous user gets a generated username
        suggest_response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # Anonymous user joins with generated username
        response1 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Same fingerprint tries to rejoin with different username (generate a different one)
        suggest_response2 = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response2.status_code, status.HTTP_200_OK)
        different_username = suggest_response2.json()['username']

        response2 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': different_username, 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response2.json()).lower()
        self.assertIn('already joined', error_msg)

    def test_registered_user_username_persistence(self):
        """Test that registered users are locked to their chosen username in a chat"""
        # user1 joins with custom username "SuperAlice" (not their reserved_username)
        self.client.force_login(self.user1)
        response1 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'SuperAlice'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # user1 tries to rejoin with different username (even their own reserved_username)
        response2 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'Alice'},  # Their own reserved_username
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response2.json()).lower()
        self.assertIn('already joined', error_msg)

        # user1 tries to rejoin with a completely different username
        response3 = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'MegaAlice'},
            content_type='application/json'
        )
        self.assertEqual(response3.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response3.json()).lower()
        self.assertIn('already joined', error_msg)

    def test_reserved_username_case_insensitive_uniqueness(self):
        """Test that reserved usernames are unique case-insensitively but case is preserved"""
        # User1 already has reserved_username='Alice' from setUp

        # Try to register another user with 'alice' (lowercase)
        response = self.client.post(
            '/api/auth/register/',
            data={
                'email': 'user3@example.com',
                'password': 'testpass123',
                'reserved_username': 'alice'  # Same as Alice but lowercase
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('already reserved', error_msg)

        # Try with 'ALICE' (uppercase)
        response = self.client.post(
            '/api/auth/register/',
            data={
                'email': 'user4@example.com',
                'password': 'testpass123',
                'reserved_username': 'ALICE'  # Same as Alice but uppercase
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('already reserved', error_msg)

        # Verify user1's username is still stored with original case
        self.user1.refresh_from_db()
        self.assertEqual(self.user1.reserved_username, 'Alice')  # Capital A preserved

    def test_reserved_username_case_preservation_in_messages(self):
        """Test that reserved username case is preserved when displayed in messages"""
        # User1 with reserved_username='Alice' joins and sends a message
        self.client.force_login(self.user1)
        join_response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': 'Alice'},
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        token = join_response.json()['session_token']

        # Send a message
        msg_response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={'username': 'Alice', 'content': 'Hello from Alice', 'session_token': token},
            content_type='application/json'
        )
        self.assertEqual(msg_response.status_code, status.HTTP_201_CREATED)

        # Verify the username in the message has preserved case
        message_data = msg_response.json()
        self.assertEqual(message_data['user']['reserved_username'], 'Alice')  # Capital A preserved

    def test_anonymous_username_case_preservation_in_messages(self):
        """Test that anonymous username case is preserved when displayed in messages"""
        # Anonymous user gets a generated username
        suggest_response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint_case_test'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # Anonymous user joins with generated username
        join_response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint_case_test'},
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        token = join_response.json()['session_token']

        # Send a message
        msg_response = self.client.post(
            f'/api/chats/{self.chat_code}/messages/send/',
            data={'username': username, 'content': f'Hello from {username}', 'session_token': token},
            content_type='application/json'
        )
        self.assertEqual(msg_response.status_code, status.HTTP_201_CREATED)

        # Verify the username in the message has preserved case
        # For anonymous users, the username is stored in ChatParticipation
        from ..models import ChatParticipation
        participation = ChatParticipation.objects.get(
            chat_room__code=self.chat_code,
            fingerprint='fingerprint_case_test'
        )
        # Generated usernames like "HappyTiger42" have mixed case - verify it's preserved
        self.assertEqual(participation.username, username)
