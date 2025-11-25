"""
Tests for Redis-based rate limiting functionality.

Tests the rate limiting system that tracks upload attempts per hour
using Redis cache, with different limits for authenticated vs anonymous users.
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
            fingerprint='test-fp',
            ip_address='192.168.1.1'
        )

        self.assertTrue(allowed)
        self.assertEqual(count, 0)
        self.assertGreater(limit, 0)

    @override_settings(
        CONSTANCE_CONFIG={
            'PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED': (20, 'Max uploads per hour for authenticated users'),
        }
    )
    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_blocks_after_limit_exceeded(self, mock_config):
        """Test that 21st request is blocked for authenticated users (limit=20)."""
        # Configure mock config
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED = 20
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_ANONYMOUS = 5

        user_id = self.user.id
        fingerprint = 'test-fp'
        ip_address = '192.168.1.1'

        # Simulate 20 uploads (up to limit)
        for i in range(20):
            allowed, count, limit = check_rate_limit(user_id, fingerprint, ip_address)
            self.assertTrue(allowed)
            increment_rate_limit(user_id, fingerprint, ip_address)

        # 21st request should be blocked
        allowed, count, limit = check_rate_limit(user_id, fingerprint, ip_address)
        self.assertFalse(allowed)
        self.assertEqual(count, 20)
        self.assertEqual(limit, 20)

    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_blocks_anonymous_after_5_requests(self, mock_config):
        """Test that 6th request is blocked for anonymous users (limit=5)."""
        # Configure mock config
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED = 20
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_ANONYMOUS = 5

        user_id = None  # Anonymous
        fingerprint = 'anon-fp'
        ip_address = '192.168.1.2'

        # Simulate 5 uploads (up to limit)
        for i in range(5):
            allowed, count, limit = check_rate_limit(user_id, fingerprint, ip_address)
            self.assertTrue(allowed)
            increment_rate_limit(user_id, fingerprint, ip_address)

        # 6th request should be blocked
        allowed, count, limit = check_rate_limit(user_id, fingerprint, ip_address)
        self.assertFalse(allowed)
        self.assertEqual(count, 5)
        self.assertEqual(limit, 5)

    def test_rate_limit_key_prioritizes_user_id(self):
        """Test that user ID takes precedence in rate limit key generation."""
        key = get_rate_limit_key(
            user_id=123,
            fingerprint='test-fp',
            ip_address='192.168.1.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:user:123')
        self.assertNotIn('fp:', key)
        self.assertNotIn('ip:', key)

    def test_rate_limit_key_falls_back_to_fingerprint(self):
        """Test that fingerprint is used when no user ID is provided."""
        key = get_rate_limit_key(
            user_id=None,
            fingerprint='test-fp-456',
            ip_address='192.168.1.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:fp:test-fp-456')
        self.assertNotIn('user:', key)
        self.assertNotIn('ip:', key)

    def test_rate_limit_key_falls_back_to_ip(self):
        """Test that IP address is used when no user ID or fingerprint is provided."""
        key = get_rate_limit_key(
            user_id=None,
            fingerprint=None,
            ip_address='10.0.0.1'
        )

        self.assertEqual(key, 'media_analysis:rate_limit:ip:10.0.0.1')
        self.assertNotIn('user:', key)
        self.assertNotIn('fp:', key)

    @patch('media_analysis.utils.rate_limit.config')
    def test_rate_limit_isolated_per_user(self, mock_config):
        """Test that different users have separate rate limits."""
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED = 20
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_ANONYMOUS = 5

        # Create second user
        user2 = User.objects.create_user(
            email='test2@example.com',
            password='testpass123'
        )

        # Upload 20 times for user1 (hit limit)
        for i in range(20):
            increment_rate_limit(self.user.id, 'fp1', '192.168.1.1')

        # User1 should be blocked
        allowed1, count1, limit1 = check_rate_limit(self.user.id, 'fp1', '192.168.1.1')
        self.assertFalse(allowed1)

        # User2 should still be allowed (separate limit)
        allowed2, count2, limit2 = check_rate_limit(user2.id, 'fp2', '192.168.1.2')
        self.assertTrue(allowed2)
        self.assertEqual(count2, 0)

    def test_get_client_identifier_from_authenticated_request(self):
        """Test extraction of client identifiers from authenticated request."""
        django_request = self.factory.post('/test/', {'fingerprint': 'test-fp'})
        django_request.user = self.user
        django_request.META['REMOTE_ADDR'] = '192.168.1.1'

        # Wrap in DRF Request to enable .data attribute
        request = Request(django_request)
        # DRF Request needs user set explicitly when wrapping Django request
        request._user = self.user

        user_id, fingerprint, ip_address = get_client_identifier(request)

        self.assertEqual(user_id, self.user.id)
        self.assertEqual(fingerprint, 'test-fp')
        self.assertEqual(ip_address, '192.168.1.1')

    def test_get_client_identifier_from_anonymous_request(self):
        """Test extraction of client identifiers from anonymous request."""
        django_request = self.factory.post('/test/', {'fingerprint': 'anon-fp'})
        django_request.user = Mock(is_authenticated=False)
        django_request.META['REMOTE_ADDR'] = '10.0.0.1'

        # Wrap in DRF Request to enable .data attribute
        request = Request(django_request)

        user_id, fingerprint, ip_address = get_client_identifier(request)

        self.assertIsNone(user_id)
        self.assertEqual(fingerprint, 'anon-fp')
        self.assertEqual(ip_address, '10.0.0.1')

    def test_get_client_identifier_with_x_forwarded_for(self):
        """Test that X-Forwarded-For header is used if present (proxy/load balancer)."""
        request = self.factory.post('/test/')
        request.user = Mock(is_authenticated=False)
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.195, 70.41.3.18'
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        user_id, fingerprint, ip_address = get_client_identifier(request)

        # Should use first IP from X-Forwarded-For
        self.assertEqual(ip_address, '203.0.113.195')

    @patch('media_analysis.utils.rate_limit.config')
    def test_get_remaining_uploads(self, mock_config):
        """Test calculation of remaining uploads."""
        mock_config.PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED = 20

        user_id = self.user.id
        fingerprint = 'test-fp'
        ip_address = '192.168.1.1'

        # No uploads yet
        remaining, used, limit = get_remaining_uploads(user_id, fingerprint, ip_address)
        self.assertEqual(remaining, 20)
        self.assertEqual(used, 0)
        self.assertEqual(limit, 20)

        # After 5 uploads
        for i in range(5):
            increment_rate_limit(user_id, fingerprint, ip_address)

        remaining, used, limit = get_remaining_uploads(user_id, fingerprint, ip_address)
        self.assertEqual(remaining, 15)
        self.assertEqual(used, 5)
        self.assertEqual(limit, 20)
