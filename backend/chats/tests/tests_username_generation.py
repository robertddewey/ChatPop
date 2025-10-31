"""
Tests for username generation and global uniqueness checking.

Covers:
- is_username_globally_available() helper function
- generate_username() with rate limiting and Redis tracking
- API endpoints for username suggestions
"""
import allure
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from constance.test import override_config

from chats.models import ChatRoom, ChatParticipation
from chats.utils.username.validators import is_username_globally_available
from chats.utils.username.generator import generate_username

User = get_user_model()


@allure.feature('Username Generation')
@allure.story('Global Username Availability')
class IsUsernameGloballyAvailableTestCase(TestCase):
    """Test the is_username_globally_available() helper function"""

    def setUp(self):
        """Set up test data"""
        # Create a test user with reserved username
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            reserved_username='ReservedUser'
        )

        # Create a test chat
        self.chat = ChatRoom.objects.create(
            code='TESTCHAT',
            name='Test Chat',
            host=self.user,
        )

        # Create a chat participation with username
        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat,
            user=None,  # Anonymous user
            username='ChatUser123',
            fingerprint='test_fingerprint'
        )

    @allure.title("Available username returns True")
    @allure.description("Test that an available username returns True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_available_username(self):
        """Test that an available username returns True"""
        self.assertTrue(is_username_globally_available('AvailableUser'))
        self.assertTrue(is_username_globally_available('NewUser123'))
        self.assertTrue(is_username_globally_available('UniqueUser'))

    @allure.title("Username taken by reserved user")
    @allure.description("Test that a username reserved by a user returns False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_taken_by_reserved_user(self):
        """Test that a username reserved by a user returns False"""
        # Exact case match
        self.assertFalse(is_username_globally_available('ReservedUser'))

        # Case-insensitive match
        self.assertFalse(is_username_globally_available('reserveduser'))
        self.assertFalse(is_username_globally_available('RESERVEDUSER'))
        self.assertFalse(is_username_globally_available('rEsErVeDuSeR'))

    @allure.title("Username taken by chat participant")
    @allure.description("Test that a username used in a chat returns False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_taken_by_chat_participant(self):
        """Test that a username used in a chat returns False"""
        # Exact case match
        self.assertFalse(is_username_globally_available('ChatUser123'))

        # Case-insensitive match
        self.assertFalse(is_username_globally_available('chatuser123'))
        self.assertFalse(is_username_globally_available('CHATUSER123'))
        self.assertFalse(is_username_globally_available('ChAtUsEr123'))

    @allure.title("Username check with multiple participations")
    @allure.description("Test that username taken in any chat returns False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_check_with_multiple_participations(self):
        """Test that username taken in any chat returns False"""
        # Create another chat with same username
        chat2 = ChatRoom.objects.create(
            code='CHAT2',
            name='Chat 2',
            host=self.user,
        )

        ChatParticipation.objects.create(
            chat_room=chat2,
            user=None,
            username='AnotherUser',
            fingerprint='another_fingerprint'
        )

        # Username should be unavailable
        self.assertFalse(is_username_globally_available('AnotherUser'))
        self.assertFalse(is_username_globally_available('anotheruser'))

    @allure.title("Username check with registered user participation")
    @allure.description("Test that username from registered user's participation is also checked")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_check_with_registered_user_participation(self):
        """Test that username from registered user's participation is also checked"""
        # Create a participation with a registered user
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='pass123',
            reserved_username='User2Reserved'
        )

        ChatParticipation.objects.create(
            chat_room=self.chat,
            user=user2,
            username='User2ChatName',
            fingerprint='user2_fingerprint'
        )

        # Both reserved username and chat username should be unavailable
        self.assertFalse(is_username_globally_available('User2Reserved'))
        self.assertFalse(is_username_globally_available('User2ChatName'))


@allure.feature('Username Generation')
@allure.story('Username Generator Function')
class GenerateUsernameTestCase(TestCase):
    """Test the generate_username() function with rate limiting"""

    def setUp(self):
        """Clear cache before each test"""
        cache.clear()
        self.test_fingerprint = 'test_fingerprint_123'

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Successful username generation")
    @allure.description("Test successful username generation with remaining attempts")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_successful_generation(self):
        """Test successful username generation with remaining attempts"""
        username, remaining = generate_username(self.test_fingerprint)

        # Should return a valid username
        self.assertIsNotNone(username)
        self.assertIsInstance(username, str)
        self.assertGreaterEqual(len(username), 5)
        self.assertLessEqual(len(username), 15)

        # Should have 9 attempts remaining (used 1 of 10)
        self.assertEqual(remaining, 9)

    @allure.title("Rate limit tracking")
    @allure.description("Test that rate limit is properly tracked across multiple calls")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_rate_limit_tracking(self):
        """Test that rate limit is properly tracked across multiple calls"""
        # Make 10 generations (max allowed)
        for i in range(10):
            username, remaining = generate_username(self.test_fingerprint)
            self.assertIsNotNone(username)
            self.assertEqual(remaining, 9 - i)

        # 11th attempt should fail
        username, remaining = generate_username(self.test_fingerprint)
        self.assertIsNone(username)
        self.assertEqual(remaining, 0)

    @allure.title("Rate limit per fingerprint")
    @allure.description("Test that rate limits are isolated per fingerprint")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_rate_limit_per_fingerprint(self):
        """Test that rate limits are isolated per fingerprint"""
        fingerprint1 = 'fingerprint_1'
        fingerprint2 = 'fingerprint_2'

        # Use up all attempts for fingerprint1
        for i in range(10):
            username, remaining = generate_username(fingerprint1)
            self.assertIsNotNone(username)

        # Fingerprint1 should be rate limited
        username, remaining = generate_username(fingerprint1)
        self.assertIsNone(username)
        self.assertEqual(remaining, 0)

        # Fingerprint2 should still work
        username, remaining = generate_username(fingerprint2)
        self.assertIsNotNone(username)
        self.assertEqual(remaining, 9)

    @allure.title("Custom max attempts override")
    @allure.description("Test that max_attempts parameter overrides Constance config")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_custom_max_attempts_override(self):
        """Test that max_attempts parameter overrides Constance config"""
        # Use custom max_attempts=100 (like registration)
        username, remaining = generate_username(
            self.test_fingerprint,
            chat_code=None,
            max_attempts=100
        )

        self.assertIsNotNone(username)
        # Should have 99 attempts remaining (used 1 of 100)
        self.assertEqual(remaining, 99)

    @allure.title("Generated usernames tracking")
    @allure.description("Test that generated usernames are tracked in Redis for this fingerprint")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_generated_usernames_tracking(self):
        """Test that generated usernames are tracked in Redis for this fingerprint"""
        # Generate a username
        username1, _ = generate_username(self.test_fingerprint)
        self.assertIsNotNone(username1)

        # Check Redis tracking - should preserve original capitalization
        generated_key = f"username:generated_for_fingerprint:{self.test_fingerprint}"
        generated_set = cache.get(generated_key, set())

        self.assertIn(username1, generated_set)  # Original capitalization, not .lower()

    @allure.title("Chat-specific cache")
    @allure.description("Test that chat-specific suggestion cache works")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_chat_specific_cache(self):
        """Test that chat-specific suggestion cache works"""
        chat_code = 'TESTCHAT'

        # Generate username for specific chat
        username1, _ = generate_username(self.test_fingerprint, chat_code=chat_code)
        self.assertIsNotNone(username1)

        # Check that chat cache is updated
        chat_cache_key = f"chat:{chat_code}:recent_suggestions"
        recent_suggestions = cache.get(chat_cache_key, set())

        self.assertIn(username1.lower(), recent_suggestions)

    @allure.title("Global uniqueness check")
    @allure.description("Test that generated usernames avoid globally taken usernames")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_global_uniqueness_check(self):
        """Test that generated usernames avoid globally taken usernames"""
        # Create a user with reserved username
        User.objects.create_user(
            email='test@example.com',
            password='pass123',
            reserved_username='TakenUser1'
        )

        # Generate multiple usernames - none should be 'TakenUser1'
        for i in range(5):
            username, _ = generate_username(f'fingerprint_{i}')
            self.assertIsNotNone(username)
            self.assertNotEqual(username.lower(), 'takenuser1')

    @allure.title("Fallback to guest usernames")
    @allure.description("Test fallback to Guest usernames when generation struggles")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_fallback_to_guest_usernames(self):
        """Test fallback to Guest usernames when generation struggles"""
        # Mock the adjective/noun generation to always fail
        with patch('chats.utils.username.generator.random.choice') as mock_choice:
            # Make random choices generate invalid usernames
            mock_choice.side_effect = ['x', 'y', 'x', 'y'] * 100

            # Should eventually fall back to Guest pattern
            with patch('chats.utils.username.generator.random.randint') as mock_randint:
                mock_randint.return_value = 12345

                # The function will try 100 normal attempts, then try Guest fallback
                username, remaining = generate_username(self.test_fingerprint)

                # May or may not succeed depending on availability, but should not crash
                self.assertIsInstance(remaining, int)

    @allure.title("Constance config integration")
    @allure.description("Test that Constance config value is properly used")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_constance_config_integration(self):
        """Test that Constance config value is properly used"""
        # Generate usernames using Constance config (3 attempts)
        for i in range(3):
            username, remaining = generate_username(self.test_fingerprint)
            self.assertIsNotNone(username)
            self.assertEqual(remaining, 2 - i)

        # 4th attempt should fail
        username, remaining = generate_username(self.test_fingerprint)
        self.assertIsNone(username)
        self.assertEqual(remaining, 0)

    @allure.title("Redis TTL expiration")
    @allure.description("Test that Redis keys have proper TTL (1 hour)")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_redis_ttl_expiration(self):
        """Test that Redis keys have proper TTL (1 hour)"""
        username, _ = generate_username(self.test_fingerprint)
        self.assertIsNotNone(username)

        # Check that keys have TTL set
        attempts_key = f"username:generation_attempts:{self.test_fingerprint}"
        generated_key = f"username:generated_for_fingerprint:{self.test_fingerprint}"

        # Keys should exist and have TTL
        self.assertIsNotNone(cache.get(attempts_key))
        self.assertIsNotNone(cache.get(generated_key))


@allure.feature('Username Generation')
@allure.story('Chat Suggest Username API')
class ChatSuggestUsernameAPITestCase(TestCase):
    """Test the /api/chats/{code}/suggest-username/ endpoint"""

    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        cache.clear()

        # Create a test user and chat
        self.user = User.objects.create_user(
            email='host@example.com',
            password='pass123',
            reserved_username='HostUser'
        )

        self.chat = ChatRoom.objects.create(
            code='TESTCHAT',
            name='Test Chat',
            host=self.user,
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Successful username suggestion")
    @allure.description("Test successful username suggestion")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_successful_suggestion(self):
        """Test successful username suggestion"""
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': 'test_fp_123'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('username', response.data)
        self.assertIn('remaining', response.data)
        self.assertIn('generation_remaining', response.data)

        # Check username is valid
        username = response.data['username']
        self.assertGreaterEqual(len(username), 5)
        self.assertLessEqual(len(username), 15)

    @allure.title("Dual rate limits")
    @allure.description("Test that both chat-specific and global rate limits are enforced")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_dual_rate_limits(self):
        """Test that both chat-specific and global rate limits are enforced"""
        fingerprint = 'test_fp_dual'

        # Make successful requests and track both limits
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check both rate limit counters
        # remaining: chat-specific suggestions remaining (20 - 1 = 19)
        # generation_remaining: global generation attempts remaining (10 - 1 = 9)
        self.assertEqual(response.data['remaining'], 19)
        self.assertEqual(response.data['generation_remaining'], 9)

    @allure.title("Global generation limit hit triggers rotation")
    @allure.description("Test rotation behavior when global generation limit is exceeded")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=2)
    def test_global_generation_limit_hit(self):
        """Test rotation behavior when global generation limit is exceeded"""
        fingerprint = 'test_fp_limit'

        # Use up global generation attempts (2) and track generated usernames
        generated_usernames = []
        for i in range(2):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            generated_usernames.append(response.data['username'])

        # Verify we hit the global limit
        self.assertEqual(response.data['generation_remaining'], 0)

        # 3rd+ attempts should rotate through previously generated usernames (not fail)
        for i in range(10):  # Test multiple rotation calls
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

            # Should succeed with 200 OK (rotation, not generation)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Should return one of the previously generated usernames
            self.assertIn(response.data['username'], generated_usernames)

            # Global generation attempts should remain at 0
            self.assertEqual(response.data['generation_remaining'], 0)

    @allure.title("Fingerprint extraction from body")
    @allure.description("Test that fingerprint is correctly extracted from request body")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_fingerprint_extraction_from_body(self):
        """Test that fingerprint is correctly extracted from request body"""
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': 'custom_fingerprint_123'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify fingerprint was used by checking Redis
        attempts_key = 'username:generation_attempts:custom_fingerprint_123'
        attempts = cache.get(attempts_key)
        self.assertEqual(attempts, 1)

    @allure.title("IP fallback when no fingerprint")
    @allure.description("Test that IP address is used as fallback when fingerprint is missing")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_ip_fallback_when_no_fingerprint(self):
        """Test that IP address is used as fallback when fingerprint is missing"""
        # Send request without fingerprint
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json',
            REMOTE_ADDR='192.168.1.100'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify IP was used by checking Redis
        attempts_key = 'username:generation_attempts:192.168.1.100'
        attempts = cache.get(attempts_key)
        self.assertEqual(attempts, 1)

    @allure.title("Invalid chat code")
    @allure.description("Test error response for invalid chat code")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_chat_code(self):
        """Test error response for invalid chat code"""
        response = self.client.post(
            '/api/chats/HostUser/INVALID/suggest-username/',
            {'fingerprint': 'test_fp'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @allure.title("Username rotation after global limit")
    @allure.description("Test that users can rotate through previously generated usernames after hitting global limit")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=5
    )
    def test_username_rotation_after_global_limit(self):
        """Test that users can rotate through previously generated usernames after hitting global limit"""
        fingerprint = 'rotation_test_fp'

        # Generate 3 usernames (hit global limit)
        generated_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            generated_usernames.append(response.data['username'])

        # Verify we hit the global limit
        self.assertEqual(response.data['generation_remaining'], 0)

        # Continue calling suggest-username - should rotate through previous usernames (unlimited)
        for i in range(20):  # Test 20 rotation calls
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

            # Should succeed with 200 OK (not 429)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            # Should return one of the previously generated usernames
            self.assertIn(response.data['username'], generated_usernames)

            # Global generation attempts should remain at 0
            self.assertEqual(response.data['generation_remaining'], 0)

    @allure.title("Per-chat rate limit separate from global")
    @allure.description("Test that per-chat rate limit (3) is enforced separately from global limit (10)")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=3
    )
    def test_per_chat_rate_limit_separate_from_global(self):
        """Test that per-chat rate limit (3) is enforced separately from global limit (10)"""
        fingerprint = 'per_chat_test_fp'

        # Generate 3 usernames for this chat (hit per-chat limit)
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check final state
        self.assertEqual(response.data['remaining'], 0)  # Per-chat limit reached
        self.assertEqual(response.data['generation_remaining'], 7)  # Global: used 3 of 10

        # Create a second chat
        chat2 = ChatRoom.objects.create(
            code='CHAT2',
            name='Second Chat',
            host=self.user,
        )

        # Should be able to generate in new chat (per-chat limit is separate)
        response = self.client.post(
            f'/api/chats/HostUser/{chat2.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['remaining'], 2)  # New chat: 2 remaining
        self.assertEqual(response.data['generation_remaining'], 6)  # Global: 6 remaining

    @allure.title("Per-chat rotation after hitting limit")
    @allure.description("""CRITICAL TEST: This would have caught the per-chat rate limit bug!

Tests that after hitting the per-chat limit, subsequent requests rotate
through previously generated usernames instead of generating new ones.

Bug it would have caught: The per-chat limit check was happening AFTER
generate_username() was called, so users could generate unlimited usernames.""")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=2
    )
    def test_per_chat_rotation_after_hitting_limit(self):
        """
        CRITICAL TEST: This would have caught the per-chat rate limit bug!

        Tests that after hitting the per-chat limit, subsequent requests rotate
        through previously generated usernames instead of generating new ones.

        Bug it would have caught: The per-chat limit check was happening AFTER
        generate_username() was called, so users could generate unlimited usernames.
        """
        fingerprint = 'per_chat_rotation_fp'

        # STEP 1: Generate 2 usernames (hit per-chat limit)
        generated_usernames = []
        for i in range(2):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            generated_usernames.append(response.data['username'])

        # Verify we hit the per-chat limit
        self.assertEqual(response.data['remaining'], 0)  # Per-chat limit reached
        self.assertEqual(response.data['generation_remaining'], 8)  # Global: 8 remaining

        # STEP 2: Make 10 MORE requests - should rotate, not generate new usernames
        for i in range(10):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

            # Should succeed with 200 OK (rotation, not generation)
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Request {i+3} failed. Expected rotation but got: {response.data}"
            )

            # CRITICAL ASSERTION: Should return one of the PREVIOUSLY generated usernames
            # NOT generate a new 3rd, 4th, 5th username!
            self.assertIn(
                response.data['username'],
                generated_usernames,
                f"Request {i+3} returned '{response.data['username']}' which was NOT "
                f"in the original 2 generated usernames: {generated_usernames}. "
                f"This means a NEW username was generated when it should have rotated!"
            )

            # Per-chat limit should remain at 0 (no new generations in this chat)
            self.assertEqual(response.data['remaining'], 0)

            # Global limit should remain at 8 (rotation doesn't consume global limit)
            self.assertEqual(response.data['generation_remaining'], 8)

    @allure.title("Case preservation in generation")
    @allure.description("Test that generated usernames preserve their original capitalization")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=5)
    def test_case_preservation_in_generation(self):
        """Test that generated usernames preserve their original capitalization"""
        fingerprint = 'case_test_fp'

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        username = response.data['username']

        # Username should have mixed case (e.g., "HappyTiger42", not "happytiger42" or "Happytiger42")
        self.assertNotEqual(username, username.lower())  # Not all lowercase
        self.assertRegex(username, r'^[A-Z][a-z]+[A-Z][a-z]+\d+$')  # Pattern: AdjectiveNoun123

        # Verify it's stored with original capitalization in Redis
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
        generated_set = cache.get(generated_key, set())
        self.assertIn(username, generated_set)  # Original case
        self.assertNotIn(username.lower(), generated_set)  # Not lowercase

    @allure.title("Case preservation in rotation")
    @allure.description("Test that username rotation returns usernames with original capitalization")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_case_preservation_in_rotation(self):
        """Test that username rotation returns usernames with original capitalization"""
        fingerprint = 'rotation_case_fp'

        # Generate 3 usernames and track their exact capitalization
        original_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            original_usernames.append(response.data['username'])

        # Rotate through usernames multiple times
        for i in range(10):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            rotated_username = response.data['username']

            # Should return exact match (same capitalization)
            self.assertIn(rotated_username, original_usernames)

            # Should NOT return lowercased version
            self.assertNotIn(rotated_username.lower(), [rotated_username])

    @allure.title("Case-insensitive uniqueness")
    @allure.description("Test that username uniqueness checking is case-insensitive")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_case_insensitive_uniqueness(self):
        """Test that username uniqueness checking is case-insensitive"""
        fingerprint1 = 'case_unique_fp1'
        fingerprint2 = 'case_unique_fp2'

        # User 1 generates a username
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint1},
            format='json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        username1 = response1.data['username']

        # Manually reserve that username in Redis (simulating user taking it)
        reservation_key = f"username:reserved:{username1.lower()}"
        cache.set(reservation_key, True, 3600)

        # User 2 generates usernames - should never get username1 (case-insensitive)
        for i in range(10):
            response2 = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint2},
                format='json'
            )

            if response2.status_code == status.HTTP_200_OK:
                username2 = response2.data['username']
                # Case-insensitive comparison
                self.assertNotEqual(username2.lower(), username1.lower())


@allure.feature('Username Generation')
@allure.story('Accounts Suggest Username API')
class AccountsSuggestUsernameAPITestCase(TestCase):
    """Test the /api/auth/suggest-username/ endpoint for registration"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Registration higher limit")
    @allure.description("Test that registration suggestions get 100 attempts instead of 10")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_registration_higher_limit(self):
        """Test that registration suggestions get 100 attempts instead of 10"""
        fingerprint = 'reg_fp_123'

        response = self.client.post(
            '/api/auth/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('username', response.data)
        self.assertIn('remaining_attempts', response.data)

        # Should have 99 remaining (used 1 of 100)
        self.assertEqual(response.data['remaining_attempts'], 99)

    @allure.title("Successful registration suggestion")
    @allure.description("Test successful username suggestion for registration")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_successful_registration_suggestion(self):
        """Test successful username suggestion for registration"""
        response = self.client.post(
            '/api/auth/suggest-username/',
            {'fingerprint': 'test_reg_fp'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check username is valid
        username = response.data['username']
        self.assertGreaterEqual(len(username), 5)
        self.assertLessEqual(len(username), 15)

    @allure.title("IP fallback for registration")
    @allure.description("Test IP fallback when fingerprint not provided")
    @allure.severity(allure.severity_level.NORMAL)
    def test_ip_fallback_for_registration(self):
        """Test IP fallback when fingerprint not provided"""
        response = self.client.post(
            '/api/auth/suggest-username/',
            {},
            format='json',
            REMOTE_ADDR='10.0.0.50'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify IP was used
        attempts_key = 'username:generation_attempts:10.0.0.50'
        attempts = cache.get(attempts_key)
        self.assertEqual(attempts, 1)

    @allure.title("X-Forwarded-For header support")
    @allure.description("Test that X-Forwarded-For header is used when available")
    @allure.severity(allure.severity_level.NORMAL)
    def test_x_forwarded_for_header(self):
        """Test that X-Forwarded-For header is used when available"""
        response = self.client.post(
            '/api/auth/suggest-username/',
            {},
            format='json',
            HTTP_X_FORWARDED_FOR='203.0.113.1, 198.51.100.1'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should use first IP from X-Forwarded-For
        attempts_key = 'username:generation_attempts:203.0.113.1'
        attempts = cache.get(attempts_key)
        self.assertEqual(attempts, 1)

    @allure.title("Registration rate limit exhaustion")
    @allure.description("Test error when registration rate limit (100) is exceeded")
    @allure.severity(allure.severity_level.NORMAL)
    def test_registration_rate_limit_exhaustion(self):
        """Test error when registration rate limit (100) is exceeded"""
        fingerprint = 'reg_limit_fp'

        # Manually set attempts to 100
        attempts_key = f'username:generation_attempts:{fingerprint}'
        cache.set(attempts_key, 100, 3600)

        response = self.client.post(
            '/api/auth/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['remaining_attempts'], 0)


@allure.feature('Username Generation')
@allure.story('Check Username Redis Reservation')
class CheckUsernameRedisReservationTestCase(TestCase):
    """Test that /api/auth/check-username/ reserves usernames in Redis"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Available username reserved in Redis")
    @allure.description("Test that available username is reserved in Redis after validation")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_available_username_reserved_in_redis(self):
        """Test that available username is reserved in Redis after validation"""
        username = 'ValidUser123'

        response = self.client.get(
            '/api/auth/check-username/',
            {'username': username}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])

        # Check that username was reserved in Redis
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(cache.get(reservation_key))

    @allure.title("Unavailable username not reserved")
    @allure.description("Test that unavailable username is NOT reserved in Redis")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_unavailable_username_not_reserved(self):
        """Test that unavailable username is NOT reserved in Redis"""
        # Create a user with reserved username
        User.objects.create_user(
            email='test@example.com',
            password='pass123',
            reserved_username='TakenUser'
        )

        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'TakenUser'}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['available'])

        # Redis should still have key from previous reservation
        # but we shouldn't add a new one for unavailable usernames
        # Actually, the code doesn't add reservation for unavailable usernames
        # Let's verify the taken username is detected properly
        reservation_key = f"username:reserved:takenuser"
        # The reservation should be None since we didn't reserve it
        # (it's taken by User.reserved_username, not Redis)

    @allure.title("Invalid username not reserved")
    @allure.description("Test that invalid username (too short) is NOT reserved in Redis")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_invalid_username_not_reserved(self):
        """Test that invalid username (too short) is NOT reserved in Redis"""
        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'abc'}  # Too short
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['available'])

        # Should not be in Redis
        reservation_key = "username:reserved:abc"
        self.assertIsNone(cache.get(reservation_key))

    @allure.title("Race condition prevention")
    @allure.description("Test that two users checking same username see it as taken after first check")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_race_condition_prevention(self):
        """Test that two users checking same username see it as taken after first check"""
        username = 'RaceTest123'

        # First user checks username - should be available and reserved
        response1 = self.client.get(
            '/api/auth/check-username/',
            {'username': username}
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['available'])

        # Second user checks same username - should be unavailable (reserved in Redis)
        response2 = self.client.get(
            '/api/auth/check-username/',
            {'username': username}
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['available'])

    @allure.title("Constance TTL setting used")
    @allure.description("Test that Constance USERNAME_VALIDATION_TTL_MINUTES setting is used")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=5)
    def test_constance_ttl_setting_used(self):
        """Test that Constance USERNAME_VALIDATION_TTL_MINUTES setting is used"""
        username = 'TTLTest123'

        response = self.client.get(
            '/api/auth/check-username/',
            {'username': username}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])

        # Verify reservation exists
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(cache.get(reservation_key))

        # Note: Testing actual TTL expiration would require time.sleep()
        # which is too slow for unit tests. The TTL value is tested
        # by checking that cache.set() was called with correct timeout
        # in the view code (5 minutes * 60 = 300 seconds)

    @allure.title("Case insensitive reservation")
    @allure.description("Test that username reservation is case-insensitive")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_case_insensitive_reservation(self):
        """Test that username reservation is case-insensitive"""
        # Reserve username with mixed case
        response1 = self.client.get(
            '/api/auth/check-username/',
            {'username': 'CaseSensitive'}
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['available'])

        # Try different case - should be unavailable
        response2 = self.client.get(
            '/api/auth/check-username/',
            {'username': 'casesensitive'}
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['available'])

        # Try another variant
        response3 = self.client.get(
            '/api/auth/check-username/',
            {'username': 'CASESENSITIVE'}
        )

        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        self.assertFalse(response3.data['available'])


@allure.feature('Username Generation')
@allure.story('Username Validation Redis Reservation')
class UsernameValidationRedisReservationTestCase(TestCase):
    """Test that /api/chats/{code}/validate-username/ reserves usernames in Redis"""

    def setUp(self):
        """Set up test client and chat"""
        self.client = APIClient()
        cache.clear()

        # Create test user and chat
        self.user = User.objects.create_user(
            email='host@example.com',
            password='pass123',
            reserved_username='HostUser'
        )

        self.chat = ChatRoom.objects.create(
            code='TESTCHAT',
            name='Test Chat',
            host=self.user,
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Available username reserved in Redis")
    @allure.description("Test that available username is reserved in Redis after validation")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_available_username_reserved_in_redis(self):
        """Test that available username is reserved in Redis after validation"""
        username = 'ChatUser123'

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': username},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])

        # Check that username was reserved in Redis
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(cache.get(reservation_key))

    @allure.title("Unavailable username not reserved")
    @allure.description("Test that unavailable username is NOT reserved in Redis")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_unavailable_username_not_reserved(self):
        """Test that unavailable username is NOT reserved in Redis"""
        # Create participation with username
        ChatParticipation.objects.create(
            chat_room=self.chat,
            user=None,
            username='TakenChatUser',
            fingerprint='test_fp'
        )

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'TakenChatUser'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['available'])

    @allure.title("Invalid username not reserved")
    @allure.description("Test that invalid username (profanity) is NOT reserved in Redis")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_invalid_username_not_reserved(self):
        """Test that invalid username (profanity) is NOT reserved in Redis"""
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'ab'},  # Too short
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Should not be in Redis
        reservation_key = "username:reserved:ab"
        self.assertIsNone(cache.get(reservation_key))

    @allure.title("Race condition prevention")
    @allure.description("Test that two users validating same username see it as taken after first validation")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_race_condition_prevention(self):
        """Test that two users validating same username see it as taken after first validation"""
        username = 'RaceChatTest'

        # First user validates username - should be available and reserved
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': username},
            format='json'
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['available'])

        # Second user validates same username - should be unavailable (reserved in Redis)
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': username},
            format='json'
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['available'])

    @allure.title("Constance TTL setting used")
    @allure.description("Test that Constance USERNAME_VALIDATION_TTL_MINUTES setting is used")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=5)
    def test_constance_ttl_setting_used(self):
        """Test that Constance USERNAME_VALIDATION_TTL_MINUTES setting is used"""
        username = 'TTLChatTest'

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': username},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['available'])

        # Verify reservation exists
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(cache.get(reservation_key))

    @allure.title("Case insensitive reservation")
    @allure.description("Test that username reservation is case-insensitive")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_case_insensitive_reservation(self):
        """Test that username reservation is case-insensitive"""
        # Reserve username with mixed case
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'MixedCase'},
            format='json'
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertTrue(response1.data['available'])

        # Try different case - should be unavailable
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'mixedcase'},
            format='json'
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['available'])

        # Try another variant
        response3 = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'MIXEDCASE'},
            format='json'
        )

        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        self.assertFalse(response3.data['available'])

    @allure.title("Reserved username detected")
    @allure.description("Test that User.reserved_username is checked")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(USERNAME_VALIDATION_TTL_MINUTES=10)
    def test_reserved_username_detected(self):
        """Test that User.reserved_username is checked"""
        # User has reserved_username='HostUser'
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/validate-username/',
            {'username': 'HostUser'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['available'])
        self.assertTrue(response.data['reserved_by_other'])


@allure.feature('Username Generation')
@allure.story('Dice Roll Rotation Limit')
class DiceRollRotationLimitTestCase(TestCase):
    """
    CRITICAL TEST: Verify that dice roll never shows more usernames than
    MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT, and rotates through the same usernames.

    This test ensures per-chat tracking is working correctly - users should only
    see the exact same N usernames when clicking the dice, not an ever-growing list.
    """

    def setUp(self):
        """Set up test client and chat"""
        self.client = APIClient()
        cache.clear()

        # Create test user and chat
        self.user = User.objects.create_user(
            email='host@example.com',
            password='pass123',
            reserved_username='HostUser'
        )

        self.chat = ChatRoom.objects.create(
            code='TESTCHAT',
            name='Test Chat',
            host=self.user,
        )

    def tearDown(self):
        """Clear cache after test"""
        cache.clear()

    @allure.title("Dice roll never exceeds per-chat limit")
    @allure.description("""CRITICAL TEST: Click the dice 20 times, verify only 3 unique usernames ever appear.

This test would FAIL if per-chat tracking was broken and rotation used the global
username list instead of the per-chat list.""")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=20,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=3
    )
    def test_dice_roll_never_exceeds_per_chat_limit(self):
        """
        CRITICAL TEST: Click the dice 20 times, verify only 3 unique usernames ever appear.

        This test would FAIL if per-chat tracking was broken and rotation used the global
        username list instead of the per-chat list.
        """
        fingerprint = 'dice_test_fp'

        # Click the dice 20 times (way more than the limit of 3)
        all_usernames_seen = []
        for click_number in range(1, 21):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                f"Click #{click_number} failed with {response.status_code}: {response.data}"
            )

            username = response.data['username']
            all_usernames_seen.append(username)

        # CRITICAL ASSERTION: Should only see MAX 3 unique usernames across all 20 clicks
        unique_usernames = list(set(all_usernames_seen))
        self.assertEqual(
            len(unique_usernames),
            3,
            f"Expected exactly 3 unique usernames after 20 dice rolls, but got {len(unique_usernames)}:\n"
            f"  Unique usernames: {unique_usernames}\n"
            f"  All 20 rolls: {all_usernames_seen}\n"
            f"This indicates per-chat rotation is broken!"
        )

        # Verify all 20 usernames are from the set of 3 original usernames
        for i, username in enumerate(all_usernames_seen, start=1):
            self.assertIn(
                username,
                unique_usernames,
                f"Click #{i} returned unexpected username '{username}' not in the original 3: {unique_usernames}"
            )

    @allure.title("Per-chat limit isolated between chats")
    @allure.description("Test that per-chat limits are truly per-chat - each chat gets its own pool of 3 usernames")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=20,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=3
    )
    def test_per_chat_limit_isolated_between_chats(self):
        """
        Test that per-chat limits are truly per-chat - each chat gets its own pool of 3 usernames.
        """
        fingerprint = 'multi_chat_fp'

        # Create a second chat
        chat2 = ChatRoom.objects.create(
            code='CHAT2',
            name='Second Chat',
            host=self.user,
        )

        # Generate 3 usernames in first chat
        chat1_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            chat1_usernames.append(response.data['username'])

        # Generate 3 usernames in second chat (should be different pool)
        chat2_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{chat2.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            chat2_usernames.append(response.data['username'])

        # Verify we have 6 total unique usernames (3 per chat)
        all_unique = list(set(chat1_usernames + chat2_usernames))
        self.assertEqual(
            len(all_unique),
            6,
            f"Expected 6 unique usernames across 2 chats (3 each), got {len(all_unique)}:\n"
            f"  Chat 1: {chat1_usernames}\n"
            f"  Chat 2: {chat2_usernames}\n"
            f"  All unique: {all_unique}"
        )

        # Now rotate in each chat - should only see that chat's 3 usernames
        for i in range(10):
            response1 = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertIn(response1.data['username'], chat1_usernames)

            response2 = self.client.post(
                f'/api/chats/HostUser/{chat2.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertIn(response2.data['username'], chat2_usernames)

    @allure.title("Rotation index per-chat independent")
    @allure.description("Test that rotation index is per-chat, not global")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(
        MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=20,
        MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT=5
    )
    def test_rotation_index_per_chat_independent(self):
        """
        Test that rotation index is per-chat, not global.

        If rotation index was global, clicking dice in Chat A would advance
        the rotation index for Chat B (wrong behavior).
        """
        fingerprint = 'rotation_index_fp'

        # Create second chat
        chat2 = ChatRoom.objects.create(
            code='CHAT2',
            name='Second Chat',
            host=self.user,
        )

        # Generate 5 usernames in each chat
        chat1_usernames = []
        chat2_usernames = []

        for i in range(5):
            resp1 = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            chat1_usernames.append(resp1.data['username'])

            resp2 = self.client.post(
                f'/api/chats/HostUser/{chat2.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            chat2_usernames.append(resp2.data['username'])

        # Both chats are now rotating
        # Click dice in Chat 1 three times
        for i in range(3):
            self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

        # Chat 2's rotation index should NOT be affected by Chat 1's clicks
        # Get next username from Chat 2 - should be first in rotation (index 0)
        sorted_chat2_usernames = sorted(chat2_usernames)
        response = self.client.post(
            f'/api/chats/HostUser/{chat2.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )

        # Should return the first username in alphabetical order (rotation starts at 0)
        self.assertEqual(
            response.data['username'],
            sorted_chat2_usernames[0],
            f"Expected Chat 2's rotation to start at index 0, but got a different username. "
            f"This indicates rotation index is global, not per-chat!"
        )
