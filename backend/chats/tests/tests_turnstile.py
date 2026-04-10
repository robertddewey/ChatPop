"""
Tests for Cloudflare Turnstile bot detection decorator and session verification.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class TurnstileDecoratorTests(TestCase):
    """Test the @require_turnstile decorator behavior (session-based)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='')
    def test_decorator_is_noop_when_secret_key_empty(self):
        """Decorator passes through when CLOUDFLARE_TURNSTILE_SECRET_KEY is empty."""
        response = self.client.post(
            '/api/auth/suggest-username/', {},
            format='json'
        )
        # Should not be 403 (Turnstile bypassed)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    def test_decorator_rejects_unverified_session(self):
        """Decorator returns 403 when session is not verified."""
        response = self.client.post(
            '/api/auth/suggest-username/', {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('error', response.json())
        self.assertEqual(response.json()['error'], 'Human verification required')

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    def test_decorator_allows_verified_session(self):
        """Decorator passes through when session has turnstile_verified flag."""
        # Create a session by making a request first
        self.client.get('/api/auth/check-username/', {'username': 'test_user'})
        # Set the session flag
        session = self.client.session
        session['turnstile_verified'] = True
        session.save()

        response = self.client.post(
            '/api/auth/suggest-username/', {},
            format='json'
        )
        # Should not be 403
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class VerifyHumanViewTests(TestCase):
    """Test the /api/auth/verify-human/ endpoint."""

    def setUp(self):
        self.client = APIClient()

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='')
    def test_noop_when_no_secret_key(self):
        """Returns verified=True immediately when CLOUDFLARE_TURNSTILE_SECRET_KEY is empty."""
        response = self.client.post('/api/auth/verify-human/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['verified'])

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='')
    def test_already_verified_session(self):
        """Returns already_verified=True when session is already verified."""
        # First call sets the session flag (no secret key = auto-verify)
        self.client.post('/api/auth/verify-human/', {}, format='json')
        # Second call should return already_verified
        response = self.client.post('/api/auth/verify-human/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['verified'])
        self.assertTrue(response.json()['already_verified'])

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    def test_missing_token_returns_400(self):
        """Returns 400 when no token is provided and Turnstile is configured."""
        response = self.client.post('/api/auth/verify-human/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()['verified'])
        self.assertEqual(response.json()['error'], 'Token required')

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    @patch('accounts.views.verify_turnstile_token')
    def test_valid_token_verifies_session(self, mock_verify):
        """Sets session flag when Cloudflare returns success."""
        mock_verify.return_value = True

        response = self.client.post(
            '/api/auth/verify-human/',
            {'turnstile_token': 'valid-token'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['verified'])

        # Session should now be verified — subsequent protected calls should pass
        session = self.client.session
        self.assertTrue(session.get('turnstile_verified'))

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    @patch('accounts.views.verify_turnstile_token')
    def test_invalid_token_returns_403(self, mock_verify):
        """Returns 403 when Cloudflare returns failure."""
        mock_verify.return_value = False

        response = self.client.post(
            '/api/auth/verify-human/',
            {'turnstile_token': 'invalid-token'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.json()['verified'])

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    @patch('accounts.views.verify_turnstile_token')
    def test_verified_session_bypasses_decorator(self, mock_verify):
        """After verify-human succeeds, protected endpoints pass without per-request token."""
        mock_verify.return_value = True

        # Verify human first
        self.client.post(
            '/api/auth/verify-human/',
            {'turnstile_token': 'valid-token'},
            format='json'
        )

        # Now call a protected endpoint — should pass
        response = self.client.post(
            '/api/auth/suggest-username/', {},
            format='json'
        )
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret-key')
    @patch('accounts.views.verify_turnstile_token')
    def test_already_verified_with_secret_key(self, mock_verify):
        """Returns already_verified=True when session was previously verified via token."""
        mock_verify.return_value = True

        # First call verifies with token
        self.client.post(
            '/api/auth/verify-human/',
            {'turnstile_token': 'valid-token'},
            format='json'
        )

        # Second call (no token needed) should return already_verified
        response = self.client.post(
            '/api/auth/verify-human/', {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()['verified'])
        self.assertTrue(response.json()['already_verified'])


class TurnstileVerificationTests(TestCase):
    """Test the verify_turnstile_token function."""

    @patch('chats.utils.turnstile.requests.post')
    def test_successful_verification(self, mock_post):
        """Test successful token verification with Cloudflare."""
        from chats.utils.turnstile import verify_turnstile_token

        mock_response = MagicMock()
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response

        with self.settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret'):
            result = verify_turnstile_token('test-token', '127.0.0.1')

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('chats.utils.turnstile.requests.post')
    def test_failed_verification(self, mock_post):
        """Test failed token verification with Cloudflare."""
        from chats.utils.turnstile import verify_turnstile_token

        mock_response = MagicMock()
        mock_response.json.return_value = {'success': False, 'error-codes': ['invalid-input-response']}
        mock_post.return_value = mock_response

        with self.settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret'):
            result = verify_turnstile_token('bad-token', '127.0.0.1')

        self.assertFalse(result)

    @patch('chats.utils.turnstile.requests.post')
    def test_network_error_fails_open(self, mock_post):
        """Test that network errors fail open (allow request through)."""
        from chats.utils.turnstile import verify_turnstile_token

        mock_post.side_effect = Exception('Network error')

        with self.settings(CLOUDFLARE_TURNSTILE_SECRET_KEY='test-secret'):
            result = verify_turnstile_token('test-token', '127.0.0.1')

        # Should fail open — don't block users if Cloudflare is down
        self.assertTrue(result)

    def test_noop_when_no_secret_key(self):
        """Test that verification is a no-op when secret key is empty."""
        from chats.utils.turnstile import verify_turnstile_token

        with self.settings(CLOUDFLARE_TURNSTILE_SECRET_KEY=''):
            result = verify_turnstile_token('any-token', '127.0.0.1')

        self.assertTrue(result)
