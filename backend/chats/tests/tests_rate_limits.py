"""
Tests for API rate limiting functionality
"""
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User
from ..models import ChatRoom


class UsernameGenerationRateLimitTests(TestCase):
    """Test rate limiting for username suggestion endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test user (host)
        self.host = User.objects.create_user(
            email='host@example.com',
            password='testpass123'
        )

        # Create test chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )
        self.chat_code = self.chat_room.code

        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    def test_username_suggestion_allows_up_to_20_requests(self):
        """Test that up to 20 username suggestions are allowed per hour"""
        fingerprint = 'test_fingerprint_123'

        # Make 20 requests - all should succeed
        for i in range(20):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                data={'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Request {i+1} failed: {response.data if hasattr(response, 'data') else response.content}"
            )
            self.assertIn('username', response.json())
            self.assertIn('remaining', response.json())
            self.assertEqual(response.json()['remaining'], 20 - (i + 1))

    def test_username_suggestion_blocks_21st_request(self):
        """Test that 21st request is rate limited"""
        fingerprint = 'test_fingerprint_456'

        # Make 20 successful requests
        for _ in range(20):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 21st request should be blocked
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('limit reached', data['error'].lower())
        self.assertEqual(data['remaining'], 0)

    def test_rate_limit_is_per_fingerprint(self):
        """Test that rate limits are isolated per fingerprint"""
        fingerprint1 = 'fingerprint_user1'
        fingerprint2 = 'fingerprint_user2'

        # Use up rate limit for fingerprint1
        for _ in range(20):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint1},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # fingerprint1 should be blocked
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint1},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # fingerprint2 should still work
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint2},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rate_limit_is_per_chat(self):
        """Test that rate limits are isolated per chat room"""
        fingerprint = 'shared_fingerprint'

        # Create second chat room
        chat_room2 = ChatRoom.objects.create(
            name='Second Chat',
            host=self.host,
            access_mode='public'
        )

        # Use up rate limit for first chat
        for _ in range(20):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # First chat should be blocked
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Second chat should still work (separate rate limit)
        response = self.client.post(
            f'/api/chats/{chat_room2.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rate_limit_fallback_to_ip_when_no_fingerprint(self):
        """Test that IP-based rate limiting works when fingerprint is missing"""
        # Don't provide fingerprint - should use IP

        # Make 20 requests without fingerprint
        for i in range(20):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {},  # No fingerprint
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 21st request should be blocked (using same IP)
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_rate_limit_counter_increments_correctly(self):
        """Test that remaining counter decrements correctly"""
        fingerprint = 'counter_test_fp'

        # First request: 19 remaining
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['remaining'], 19)

        # Make 4 more requests (total: 5 requests, 15 remaining)
        for _ in range(4):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
        # After 5th request: 15 remaining
        self.assertEqual(response.json()['remaining'], 15)

        # 20th request: 0 remaining
        for _ in range(14):
            self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.json()['remaining'], 0)

    def test_rate_limit_error_message_format(self):
        """Test that rate limit error has correct format"""
        fingerprint = 'error_msg_test'

        # Exhaust rate limit
        for _ in range(20):
            self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

        # Get rate limit error
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        data = response.json()

        # Verify error structure
        self.assertIn('error', data)
        self.assertIn('remaining', data)
        self.assertIsInstance(data['error'], str)
        self.assertIsInstance(data['remaining'], int)
        self.assertIn('20', data['error'])  # Mentions the limit
        self.assertIn('hour', data['error'].lower())  # Mentions time window

    def test_rate_limit_only_increments_on_successful_generation(self):
        """Test that rate limit counter only increments on successful username generation"""
        fingerprint = 'success_only_test'

        # Make successful requests
        for i in range(5):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.json()['remaining'], 20 - (i + 1))

        # Verify count is at 5
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.json()['remaining'], 14)

    def test_rate_limit_applies_to_nonexistent_chat(self):
        """Test that rate limiting still applies even for non-existent chat codes"""
        fingerprint = 'nonexistent_chat_test'

        # Try to get username for non-existent chat
        response = self.client.post(
            '/api/chats/INVALID_CODE/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        # Should get 404, not rate limit
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_different_fingerprints_independent_limits(self):
        """Test that different fingerprints have completely independent rate limits"""
        fp1, fp2, fp3 = 'fp1', 'fp2', 'fp3'

        # Use 10 from fp1
        for _ in range(10):
            self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fp1},
                format='json'
            )

        # Use 5 from fp2
        for _ in range(5):
            self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fp2},
                format='json'
            )

        # Use 15 from fp3
        for _ in range(15):
            self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fp3},
                format='json'
            )

        # Check remaining counts are correct
        response1 = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fp1},
            format='json'
        )
        self.assertEqual(response1.json()['remaining'], 9)

        response2 = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fp2},
            format='json'
        )
        self.assertEqual(response2.json()['remaining'], 14)

        response3 = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fp3},
            format='json'
        )
        self.assertEqual(response3.json()['remaining'], 4)

    def test_rate_limit_cache_key_format(self):
        """Test that rate limit uses correct cache key format"""
        fingerprint = 'cache_key_test'
        expected_key = f"username_suggest_limit:{self.chat_code}:{fingerprint}"

        # Make a request
        self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        # Verify cache key exists and has correct value
        count = cache.get(expected_key)
        self.assertIsNotNone(count)
        self.assertEqual(count, 1)

        # Make another request
        self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        # Verify count incremented
        count = cache.get(expected_key)
        self.assertEqual(count, 2)

    def test_rate_limit_edge_case_exactly_20_requests(self):
        """Test edge case: exactly 20 requests (last allowed request)"""
        fingerprint = 'edge_case_20'

        # Make exactly 20 requests
        for i in range(19):
            response = self.client.post(
                f'/api/chats/{self.chat_code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 20th request should succeed with 0 remaining
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['remaining'], 0)

        # 21st should fail
        response = self.client.post(
            f'/api/chats/{self.chat_code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
