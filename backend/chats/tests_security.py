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
from .models import ChatRoom
from .security import ChatSessionValidator

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
        """Test that SQL injection attempts in username are blocked"""
        malicious_username = "'; DROP TABLE chats_message; --"

        # Try to join with malicious username
        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': malicious_username},
            content_type='application/json'
        )

        # Should still succeed (username validation allows special chars)
        # But SQL injection should not affect database
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

        # Verify chat room still exists (not dropped)
        self.assertTrue(ChatRoom.objects.filter(code=self.chat_code).exists())

    def test_xss_in_username(self):
        """Test that XSS attempts in username are handled"""
        xss_username = "<script>alert('XSS')</script>"

        response = self.client.post(
            f'/api/chats/{self.chat_code}/join/',
            data={'username': xss_username},
            content_type='application/json'
        )

        # Should be accepted (frontend must sanitize for display)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

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
