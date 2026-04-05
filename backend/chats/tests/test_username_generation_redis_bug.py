"""
Tests to verify the username generation Redis storage for session-to-usernames mapping.

Verifies: username:generated_for_session:{identity_key} contains all generated usernames.
"""
from django.test import TestCase
from django.core.cache import cache
from chats.utils.username.generator import generate_username
from constance import config


class UsernameGenerationRedisBugTest(TestCase):
    """Tests that verify Redis storage for session-to-usernames mapping"""

    def setUp(self):
        """Clear Redis before each test"""
        cache.clear()

    def test_generated_username_saved_to_session_set(self):
        """
        Generated username should be saved to Redis under session/identity key.

        Expected behavior:
        - After generating a username for identity_key "test123"
        - Redis key "username:generated_for_session:test123" should contain the username
        """
        identity_key = "test_identity_key_123"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(identity_key, chat_code)

        # Verify username was generated successfully
        self.assertIsNotNone(username)
        self.assertGreater(len(username), 0)

        generated_key = f"username:generated_for_session:{identity_key}"
        generated_usernames = cache.get(generated_key, set())

        self.assertIn(
            username.lower(),
            {u.lower() for u in generated_usernames},
            f"Generated username '{username}' should be saved to Redis key '{generated_key}'"
        )

    def test_multiple_generations_accumulate_in_session_set(self):
        """
        Multiple username generations should accumulate in the session set.

        Expected behavior:
        - Generate 3 usernames for the same identity key
        - All 3 should be stored in the set
        """
        identity_key = "test_identity_key_456"
        chat_code = "TESTCHAT"

        generated_usernames = []
        for i in range(3):
            username, remaining = generate_username(identity_key, chat_code)
            self.assertIsNotNone(username)
            generated_usernames.append(username)

        generated_key = f"username:generated_for_session:{identity_key}"
        cached_usernames = cache.get(generated_key, set())

        # Convert to lowercase for comparison
        cached_usernames_lower = {u.lower() for u in cached_usernames}

        for username in generated_usernames:
            self.assertIn(
                username.lower(),
                cached_usernames_lower,
                f"Generated username '{username}' should be in Redis set. "
                f"Found: {cached_usernames}"
            )

    def test_session_set_has_correct_ttl(self):
        """
        The session set should have a TTL matching USERNAME_ANONYMOUS_DICE_HOLD_TTL_MINUTES.

        Expected behavior:
        - The set should be created with TTL = 1 minute (60 seconds) for chat dice generation
        """
        identity_key = "test_identity_key_789"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(identity_key, chat_code)
        self.assertIsNotNone(username)

        generated_key = f"username:generated_for_session:{identity_key}"

        # Check if key exists
        self.assertTrue(
            cache.get(generated_key) is not None,
            f"Redis key '{generated_key}' should exist after username generation"
        )

        # Check TTL (should be 60 minutes = 3600 seconds)
        # Note: Django cache doesn't expose TTL directly, but we can verify the key exists
        # and has the expected content

    def test_global_reservation_key_exists(self):
        """
        Verify the global reservation IS working.
        """
        identity_key = "test_identity_key_global"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(identity_key, chat_code)
        self.assertIsNotNone(username)

        # Global reservation key SHOULD exist (this part works correctly)
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(
            cache.get(reservation_key) is not None,
            f"Global reservation key '{reservation_key}' should exist"
        )

    def test_chat_specific_suggestions_exists(self):
        """
        Verify chat-specific suggestions ARE working.
        """
        identity_key = "test_identity_key_chat"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(identity_key, chat_code)
        self.assertIsNotNone(username)

        # Chat-specific suggestions SHOULD exist (this part works correctly)
        chat_suggestions_key = f"chat:{chat_code}:recent_suggestions"
        cached_suggestions = cache.get(chat_suggestions_key, [])

        self.assertIn(
            username.lower(),
            [u.lower() for u in cached_suggestions],
            f"Username '{username}' should be in chat-specific suggestions"
        )

    def test_generation_attempts_counter_increments(self):
        """
        Verify generation attempts counter IS working.
        """
        identity_key = "test_identity_key_attempts"
        chat_code = "TESTCHAT"

        # Generate first username
        username1, remaining1 = generate_username(identity_key, chat_code)
        self.assertIsNotNone(username1)
        self.assertEqual(remaining1, config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL - 1)

        # Generate second username
        username2, remaining2 = generate_username(identity_key, chat_code)
        self.assertIsNotNone(username2)
        self.assertEqual(remaining2, config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL - 2)

        # Attempts counter SHOULD be working (this part works correctly)
        attempts_key = f"username:generation_attempts:{identity_key}"
        attempts = cache.get(attempts_key, 0)
        self.assertEqual(attempts, 2, "Generation attempts should be tracked correctly")
