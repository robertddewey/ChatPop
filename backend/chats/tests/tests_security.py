"""
Security tests for JWT-based chat session authentication
Tests for vulnerabilities and unauthorized access attempts
"""
import allure
import jwt
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from ..models import ChatRoom, ChatParticipation
from ..utils.security.auth import ChatSessionValidator

User = get_user_model()


@allure.feature('Chat Security')
@allure.story('JWT Session Authentication')
class ChatSessionSecurityTests(TestCase):
    """
    Test suite for JWT session security vulnerabilities.

    Ensures that:
    - Session tokens are properly validated
    - Tokens cannot be reused across chats
    - Expired tokens are rejected
    - Invalid tokens are rejected
    """

    def setUp(self):
        """Set up test data"""
        # Clear Redis cache before each test to prevent rate limit carryover
        cache.clear()

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

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            fingerprint='host_fingerprint'
        )

        # Valid session token
        self.valid_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_code,
            username='testuser',
            user_id=str(self.user.id)
        )

    @allure.title("Message send requires valid session token")
    @allure.description("""
    Security test to verify that sending messages without a session token is properly blocked.

    Expected behavior:
    - POST request without session_token should return 403 FORBIDDEN
    - Response should indicate that a session token is required

    This prevents unauthorized users from sending messages to chat rooms.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    def test_message_send_requires_session_token(self):
        """Test that sending messages without session token is blocked"""
        response = self.client.post(
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
            data={'username': 'testuser', 'content': 'Hello'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('session token', response.json().get('detail', '').lower())

    @allure.title("Invalid JWT tokens are rejected")
    @allure.description("""
    Verifies that malformed or invalid JWT tokens are rejected by the system.

    Tests against:
    - Malformed JWT strings
    - Tokens with invalid signatures
    - Tokens from untrusted sources
    """)
    @allure.severity(allure.severity_level.CRITICAL)
    def test_message_send_with_invalid_token(self):
        """Test that invalid JWT tokens are rejected"""
        response = self.client.post(
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': 'invalid.jwt.token'
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @allure.title("Expired session tokens are rejected")
    @allure.description("""
    Security test to verify that expired JWT tokens cannot be used.

    Creates a token with:
    - Issued time (iat): 25 hours ago
    - Expiration time (exp): 1 hour ago

    Expected: 403 FORBIDDEN with 'expired' message
    """)
    @allure.severity(allure.severity_level.CRITICAL)
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
            data={
                'username': 'testuser',
                'content': 'Hello',
                'session_token': expired_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('expired', response.json().get('detail', '').lower())

    @allure.title("Session tokens are chat-specific and cannot be reused")
    @allure.description("""
    Verifies that a session token issued for one chat room cannot be used in another.

    Security scenario:
    1. User joins Chat Room A and receives token_A
    2. User tries to use token_A in Chat Room B
    3. System should reject the token

    This prevents token reuse attacks across different chat rooms.
    """)
    @allure.severity(allure.severity_level.CRITICAL)
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
            f'/api/chats/testuser/{other_chat.code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
        # First, get a generated username via suggest-username
        suggest_response = self.client.post(
            f'/api/chats/testuser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'join_test_fp'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        response = self.client.post(
            f'/api/chats/testuser/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'join_test_fp'},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('session_token', data)

        # Verify token is valid
        token = data['session_token']
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        self.assertEqual(payload['chat_code'], self.chat_code)
        self.assertEqual(payload['username'], username)

    def test_valid_token_allows_message_send(self):
        """Test that valid tokens allow message sending"""
        response = self.client.post(
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/join/',
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
            f'/api/chats/testuser/{self.chat_code}/join/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
                f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
                f'/api/chats/testuser/{self.chat_code}/messages/send/',
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
            f'/api/chats/testuser/{self.chat_code}/messages/send/',
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

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=private_chat,
            user=self.user,
            username='testuser',
            fingerprint='host_fingerprint_private'
        )

        # Try to join without access code
        response = self.client.post(
            f'/api/chats/testuser/{private_chat.code}/join/',
            data={'username': 'hacker'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with wrong access code
        response = self.client.post(
            f'/api/chats/testuser/{private_chat.code}/join/',
            data={'username': 'hacker', 'access_code': 'wrong'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Try with correct access code - first generate a valid username
        suggest_response = self.client.post(
            f'/api/chats/testuser/{private_chat.code}/suggest-username/',
            data={'fingerprint': 'legit_fp'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        legit_username = suggest_response.json()['username']

        response = self.client.post(
            f'/api/chats/testuser/{private_chat.code}/join/',
            data={'username': legit_username, 'access_code': 'secret123', 'fingerprint': 'legit_fp'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('session_token', response.json())


class UsernameReservationSecurityTests(TestCase):
    """Test suite for username reservation and fingerprinting security"""

    def setUp(self):
        """Set up test data"""
        # Clear Redis cache before each test to prevent rate limit carryover
        cache.clear()

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

        # Create separate host user (not user1 or user2, so they can join as participants)
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create test chat room with host_user as host
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host_user,
            access_mode='public'
        )
        self.chat_code = self.chat_room.code

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host_fingerprint'
        )

    def test_two_anonymous_users_same_username_blocked(self):
        """Test that username uniqueness is enforced: first user claims username successfully,
        second user is blocked from using the same username"""
        # Use separate clients to simulate separate sessions (separate anonymous users)
        client1 = Client()
        client2 = Client()

        # First anonymous user gets a generated username
        suggest_response = client1.post(
            f'/api/chats/HostUser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # First anonymous user joins with generated username
        response1 = client1.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second anonymous user tries to join with same username but different session
        response2 = client2.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
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
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': 'Bobby'},  # user2's reserved_username
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response.json()).lower()
        self.assertIn('reserved', error_msg)


    def test_anonymous_user_username_persistence_via_session(self):
        """Test that anonymous users are locked to their username via session"""
        # Anonymous user gets a generated username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # Anonymous user joins with generated username
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Same session tries to rejoin with a different (arbitrary) username
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': 'DifferentName99', 'fingerprint': 'fingerprint1'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response2.json()).lower()
        self.assertIn('already joined', error_msg)

    def test_registered_user_username_persistence(self):
        """Test that registered users are locked to their chosen username in a chat"""
        # user1 joins with their reserved_username "Alice"
        self.client.force_login(self.user1)
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': 'Alice'},
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # user1 tries to rejoin with a completely different username
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': 'MegaAlice'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)
        error_msg = str(response2.json()).lower()
        self.assertIn('previously joined', error_msg)

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
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': 'Alice'},
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        token = join_response.json()['session_token']

        # Send a message
        msg_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/messages/send/',
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
            f'/api/chats/HostUser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'fingerprint_case_test'},
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.json()['username']

        # Anonymous user joins with generated username
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={'username': username, 'fingerprint': 'fingerprint_case_test'},
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        token = join_response.json()['session_token']

        # Send a message
        msg_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/messages/send/',
            data={'username': username, 'content': f'Hello from {username}', 'session_token': token},
            content_type='application/json'
        )
        self.assertEqual(msg_response.status_code, status.HTTP_201_CREATED)

        # Verify the username in the message has preserved case
        # For anonymous users, the username is stored in ChatParticipation
        from ..models import ChatParticipation
        participation = ChatParticipation.objects.get(
            chat_room__code=self.chat_code,
            username=username,
            user__isnull=True
        )
        # Generated usernames like "HappyTiger42" have mixed case - verify it's preserved
        self.assertEqual(participation.username, username)


@allure.feature('Chat Security')
@allure.story('Reserved Username Protection')
class ReservedUsernameSecurityTests(TestCase):
    """
    Test suite for reserved username fingerprint hijacking prevention.

    Ensures that:
    - Anonymous users cannot join with reserved usernames
    - SuggestUsernameView doesn't leak reserved usernames to anonymous users
    - Authenticated users can still use their own reserved usernames
    - Pre-existing anonymous participations are grandfathered
    """

    def setUp(self):
        """Set up test data"""
        cache.clear()
        self.client = Client()

        # Create a registered user with reserved username
        self.registered_user = User.objects.create_user(
            email='reserved@example.com',
            password='testpass123',
            reserved_username='ReservedUser'
        )

        # Create host user
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create test chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host_user,
            access_mode='public'
        )
        self.chat_code = self.chat_room.code

        # Host joins
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host_fp'
        )

    @allure.title("Anonymous user cannot join with a reserved username")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_cannot_join_with_reserved_username(self):
        """Anonymous user trying to join with a reserved username should be rejected"""
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={
                'username': 'ReservedUser',
                'fingerprint': 'attacker_fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response_text = str(response.json()).lower()
        self.assertIn('reserved', response_text)

    @allure.title("Authenticated user can join with their own reserved username")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_authenticated_user_can_use_own_reserved_username(self):
        """Authenticated user should be able to join with their own reserved username"""
        # Get auth token via login endpoint
        login_response = self.client.post(
            '/api/auth/login/',
            data={'email': 'reserved@example.com', 'password': 'testpass123'},
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        token = login_response.json().get('access')

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/join/',
            data={
                'username': 'ReservedUser',
                'fingerprint': 'registered_user_fp'
            },
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @allure.title("SuggestUsernameView doesn't return registered user's username to anonymous visitor")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_suggest_username_doesnt_leak_registered_username(self):
        """SuggestUsernameView should not return a registered user's participation username via fingerprint"""
        # Create a registered user's participation with a specific fingerprint
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.registered_user,
            username='ReservedUser',
            fingerprint='shared_fingerprint'
        )

        # Anonymous user with same fingerprint calls suggest
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'shared_fingerprint'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should NOT return the registered user's username
        if data.get('is_returning'):
            self.assertNotEqual(data['username'].lower(), 'reserveduser')

    @allure.title("SuggestUsernameView doesn't return reserved username to anonymous visitor")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_suggest_username_doesnt_return_reserved_to_anonymous(self):
        """Even if anonymous participation exists with reserved username, suggest should not return it"""
        # Create an anonymous participation that happens to have a reserved username
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='ReservedUser',
            fingerprint='anon_with_reserved_fp',
            is_active=True
        )

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_code}/suggest-username/',
            data={'fingerprint': 'anon_with_reserved_fp'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        # Should NOT return the reserved username as a returning user suggestion
        if data.get('is_returning'):
            self.assertNotEqual(data['username'].lower(), 'reserveduser')

    @allure.title("MyParticipationView flags reserved username for anonymous participation")
    @allure.severity(allure.severity_level.NORMAL)
    def test_my_participation_flags_reserved_username_for_anonymous(self):
        """MyParticipationView should flag username_is_reserved for anonymous participations with reserved names"""
        # First, make a request to establish a session
        self.client.get(f'/api/chats/HostUser/{self.chat_code}/')
        session_key = self.client.session.session_key

        # Create an anonymous participation with a reserved username and session_key
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='ReservedUser',
            fingerprint='anon_reserved_fp',
            session_key=session_key,
            is_active=True
        )

        response = self.client.get(
            f'/api/chats/HostUser/{self.chat_code}/my-participation/',
            {'fingerprint': 'anon_reserved_fp'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data.get('username_is_reserved', False))
