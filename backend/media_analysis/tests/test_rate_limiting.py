"""
Tests for Redis-based rate limiting functionality.

Tests the rate limiting system that tracks upload attempts per hour
using Redis cache, with different limits for authenticated vs anonymous users.
Includes session-based rate limiting for anonymous users and global rate limits.
"""
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.request import Request
from rest_framework import status

from media_analysis.utils.rate_limit import (
    get_rate_limit_key,
    check_rate_limit,
    increment_rate_limit,
    get_client_identifier,
    get_remaining_uploads,
    check_global_rate_limit,
    increment_global_rate_limit,
    get_global_rate_limit_key,
)

User = get_user_model()


class RateLimitingTests(TestCase):
    """Test suite for rate limiting functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Clear Redis cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    def test_rate_limit_allows_first_request(self):
        """Test that the first request is always allowed."""
        allowed, count, limit = check_rate_limit(
            user_id=self.user.id,
            session_key=None,
            ip_address='192.168.1.1'
        )

        self.assertTrue(allowed)
        self.assertEqual(count, 0)
        self.assertGreater(limit, 0)

    @override_settings(
        CONSTANCE_CONFIG={
            'PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR': (20, 'Max uploads per hour for authenticated users'),
        }
    )
    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_blocks_after_limit_exceeded(self, mock_config):
        """Test that 21st request is blocked for authenticated users (limit=20)."""
        mock_config.PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR = 20
        mock_config.PHOTO_ANALYSIS_SESSION_LIMIT_PER_HOUR = 5

        user_id = self.user.id
        session_key = None
        ip_address = '192.168.1.1'

        # Simulate 20 uploads (up to limit)
        for i in range(20):
            allowed, count, limit = check_rate_limit(user_id, session_key, ip_address)
            self.assertTrue(allowed)
            increment_rate_limit(user_id, session_key, ip_address)

        # 21st request should be blocked
        allowed, count, limit = check_rate_limit(user_id, session_key, ip_address)
        self.assertFalse(allowed)
        self.assertEqual(count, 20)
        self.assertEqual(limit, 20)

    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_blocks_anonymous_after_5_requests(self, mock_config):
        """Test that 6th request is blocked for anonymous users (limit=5)."""
        mock_config.PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR = 20
        mock_config.PHOTO_ANALYSIS_SESSION_LIMIT_PER_HOUR = 5

        user_id = None  # Anonymous
        session_key = 'test-session-key-abc123'
        ip_address = '192.168.1.2'

        # Simulate 5 uploads (up to limit)
        for i in range(5):
            allowed, count, limit = check_rate_limit(user_id, session_key, ip_address)
            self.assertTrue(allowed)
            increment_rate_limit(user_id, session_key, ip_address)

        # 6th request should be blocked
        allowed, count, limit = check_rate_limit(user_id, session_key, ip_address)
        self.assertFalse(allowed)
        self.assertEqual(count, 5)
        self.assertEqual(limit, 5)

    def test_rate_limit_key_prioritizes_user_id(self):
        """Test that user ID takes precedence in rate limit key generation."""
        key = get_rate_limit_key(
            user_id=123,
            session_key=None,
            ip_address='192.168.1.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:user:123')
        self.assertNotIn('ip:', key)
        self.assertNotIn('session:', key)

    def test_rate_limit_key_uses_session_for_anonymous(self):
        """Test that session key is used for anonymous users when available."""
        key = get_rate_limit_key(
            user_id=None,
            session_key='abc123sessionkey',
            ip_address='10.0.0.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:session:abc123sessionkey')
        self.assertNotIn('user:', key)
        self.assertNotIn('ip:', key)

    def test_rate_limit_key_falls_back_to_ip(self):
        """Test that IP address is used when no user ID or session key is provided."""
        key = get_rate_limit_key(
            user_id=None,
            session_key=None,
            ip_address='10.0.0.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:ip:10.0.0.1')
        self.assertNotIn('user:', key)
        self.assertNotIn('session:', key)

    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_isolated_per_user(self, mock_config):
        """Test that different users have separate rate limits."""
        mock_config.PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR = 20
        mock_config.PHOTO_ANALYSIS_SESSION_LIMIT_PER_HOUR = 5

        # Create second user
        user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123'
        )

        # Upload 20 times for user1 (hit limit)
        for i in range(20):
            increment_rate_limit(self.user.id, None, '192.168.1.1')

        # User1 should be blocked
        allowed1, count1, limit1 = check_rate_limit(self.user.id, None, '192.168.1.1')
        self.assertFalse(allowed1)

        # User2 should still be allowed (separate limit)
        allowed2, count2, limit2 = check_rate_limit(user2.id, None, '192.168.1.2')
        self.assertTrue(allowed2)
        self.assertEqual(count2, 0)

    def test_get_client_identifier_from_authenticated_request(self):
        """Test extraction of client identifiers from authenticated request."""
        django_request = self.factory.post('/test/')
        django_request.user = self.user
        django_request.META['REMOTE_ADDR'] = '192.168.1.1'

        # Wrap in DRF Request to enable .data attribute
        request = Request(django_request)
        request._user = self.user

        user_id, session_key, ip_address = get_client_identifier(request)

        self.assertEqual(user_id, self.user.id)
        self.assertIsNone(session_key)
        self.assertEqual(ip_address, '192.168.1.1')

    def test_get_client_identifier_returns_three_values(self):
        """Test that get_client_identifier returns a 3-tuple."""
        django_request = self.factory.post('/test/')
        django_request.user = self.user
        django_request.META['REMOTE_ADDR'] = '192.168.1.1'

        request = Request(django_request)
        request._user = self.user

        result = get_client_identifier(request)
        self.assertEqual(len(result), 3)

    def test_get_client_identifier_from_anonymous_request(self):
        """Test extraction of client identifiers from anonymous request."""
        django_request = self.factory.post('/test/')
        django_request.user = Mock(is_authenticated=False)
        django_request.META['REMOTE_ADDR'] = '10.0.0.1'
        # Mock session for anonymous users
        mock_session = Mock()
        mock_session.session_key = 'anon-session-key-xyz'
        django_request.session = mock_session

        # Wrap in DRF Request to enable .data attribute
        request = Request(django_request)

        user_id, session_key, ip_address = get_client_identifier(request)

        self.assertIsNone(user_id)
        self.assertEqual(session_key, 'anon-session-key-xyz')
        self.assertEqual(ip_address, '10.0.0.1')

    def test_get_client_identifier_creates_session_for_anonymous(self):
        """Test that session is created for anonymous users without one."""
        django_request = self.factory.post('/test/')
        django_request.user = Mock(is_authenticated=False)
        django_request.META['REMOTE_ADDR'] = '10.0.0.1'
        # Mock session without existing key
        mock_session = Mock()
        mock_session.session_key = None

        def create_session():
            mock_session.session_key = 'newly-created-session'

        mock_session.create = create_session
        django_request.session = mock_session

        request = Request(django_request)

        user_id, session_key, ip_address = get_client_identifier(request)

        self.assertIsNone(user_id)
        self.assertEqual(session_key, 'newly-created-session')

    def test_get_client_identifier_with_x_forwarded_for(self):
        """Test that X-Forwarded-For header is used if present (proxy/load balancer)."""
        request = self.factory.post('/test/')
        request.user = Mock(is_authenticated=False)
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.195, 70.41.3.18'
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        # Mock session
        mock_session = Mock()
        mock_session.session_key = 'some-session-key'
        request.session = mock_session

        user_id, session_key, ip_address = get_client_identifier(request)

        # Should use first IP from X-Forwarded-For
        self.assertEqual(ip_address, '203.0.113.195')

    @patch('media_analysis.utils.rate_limit.config')
    def test_get_remaining_uploads(self, mock_config):
        """Test calculation of remaining uploads."""
        mock_config.PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR = 20

        user_id = self.user.id
        session_key = None
        ip_address = '192.168.1.1'

        # No uploads yet
        remaining, used, limit = get_remaining_uploads(user_id, session_key, ip_address)
        self.assertEqual(remaining, 20)
        self.assertEqual(used, 0)
        self.assertEqual(limit, 20)

        # After 5 uploads
        for i in range(5):
            increment_rate_limit(user_id, session_key, ip_address)

        remaining, used, limit = get_remaining_uploads(user_id, session_key, ip_address)
        self.assertEqual(remaining, 15)
        self.assertEqual(used, 5)
        self.assertEqual(limit, 20)


class GlobalRateLimitingTests(TestCase):
    """Test suite for global (cross-user) rate limiting."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('media_analysis.utils.rate_limit.config')
    def test_global_rate_limit_allows_under_limit(self, mock_config):
        """Test that requests are allowed when under global limit."""
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_HOUR = 500
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_DAY = 5000

        allowed, reason = check_global_rate_limit('photo')
        self.assertTrue(allowed)
        self.assertEqual(reason, '')

    @patch('media_analysis.utils.rate_limit.config')
    def test_global_rate_limit_blocks_at_hourly_limit(self, mock_config):
        """Test that global hourly limit blocks requests."""
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_HOUR = 3
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_DAY = 5000

        # Increment to reach limit
        for _ in range(3):
            increment_global_rate_limit('photo')

        allowed, reason = check_global_rate_limit('photo')
        self.assertFalse(allowed)
        self.assertIn('capacity', reason)

    @patch('media_analysis.utils.rate_limit.config')
    def test_global_rate_limit_blocks_at_daily_limit(self, mock_config):
        """Test that global daily limit blocks requests."""
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_HOUR = 500
        mock_config.PHOTO_ANALYSIS_GLOBAL_LIMIT_PER_DAY = 3

        # Increment to reach daily limit
        for _ in range(3):
            increment_global_rate_limit('photo')

        allowed, reason = check_global_rate_limit('photo')
        self.assertFalse(allowed)
        self.assertIn('Daily', reason)

    def test_global_increment_creates_counters(self):
        """Test that global increment creates both hourly and daily counters."""
        increment_global_rate_limit('photo')

        hourly_key = get_global_rate_limit_key('photo', 'hourly')
        daily_key = get_global_rate_limit_key('photo', 'daily')

        self.assertEqual(cache.get(hourly_key), 1)
        self.assertEqual(cache.get(daily_key), 1)

    def test_global_services_are_isolated(self):
        """Test that different services have separate global limits."""
        for _ in range(5):
            increment_global_rate_limit('photo')

        hourly_key_photo = get_global_rate_limit_key('photo', 'hourly')
        hourly_key_music = get_global_rate_limit_key('music', 'hourly')

        self.assertEqual(cache.get(hourly_key_photo), 5)
        self.assertIsNone(cache.get(hourly_key_music))
