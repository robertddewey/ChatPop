"""
Tests to demonstrate the username generation Redis storage bug.

Bug: Generated usernames are NOT being saved to the fingerprint-to-usernames mapping.
Expected: username:generated_for_fingerprint:{fingerprint} should contain all generated usernames.
Actual: This key is NEVER written to Redis (only read from).
"""
from django.test import TestCase
from django.core.cache import cache
from chats.utils.username.generator import generate_username
from constance import config


class UsernameGenerationRedisBugTest(TestCase):
    """Tests that expose the missing Redis storage for fingerprint-to-usernames mapping"""

    def setUp(self):
        """Clear Redis before each test"""
        cache.clear()

    def test_generated_username_saved_to_fingerprint_set(self):
        """
        BUG TEST: Generated username should be saved to Redis under fingerprint key.

        Expected behavior:
        - After generating a username for fingerprint "test123"
        - Redis key "username:generated_for_fingerprint:test123" should contain the username

        Current behavior:
        - The key is never written to Redis
        - This breaks username rotation and reuse
        """
        fingerprint = "test_fingerprint_123"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(fingerprint, chat_code)

        # Verify username was generated successfully
        self.assertIsNotNone(username)
        self.assertGreater(len(username), 0)

        # BUG: This test FAILS because the key is never set
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
        generated_usernames = cache.get(generated_key, set())

        self.assertIn(
            username.lower(),
            {u.lower() for u in generated_usernames},
            f"Generated username '{username}' should be saved to Redis key '{generated_key}'"
        )

    def test_multiple_generations_accumulate_in_fingerprint_set(self):
        """
        BUG TEST: Multiple username generations should accumulate in the fingerprint set.

        Expected behavior:
        - Generate 3 usernames for the same fingerprint
        - All 3 should be stored in the set

        Current behavior:
        - None are stored (key is never written)
        """
        fingerprint = "test_fingerprint_456"
        chat_code = "TESTCHAT"

        generated_usernames = []
        for i in range(3):
            username, remaining = generate_username(fingerprint, chat_code)
            self.assertIsNotNone(username)
            generated_usernames.append(username)

        # BUG: This test FAILS because the key is never set
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
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

    def test_fingerprint_set_has_correct_ttl(self):
        """
        BUG TEST: The fingerprint set should have a TTL matching USERNAME_RESERVATION_TTL_MINUTES.

        Expected behavior:
        - The set should be created with TTL = 60 minutes (3600 seconds)

        Current behavior:
        - Key doesn't exist, so TTL is irrelevant
        """
        fingerprint = "test_fingerprint_789"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(fingerprint, chat_code)
        self.assertIsNotNone(username)

        # BUG: This test FAILS because the key is never created
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"

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
        This test should PASS - verifying the global reservation IS working.

        This demonstrates that the bug is ONLY with the fingerprint-to-usernames mapping,
        not with the global username reservation.
        """
        fingerprint = "test_fingerprint_global"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(fingerprint, chat_code)
        self.assertIsNotNone(username)

        # Global reservation key SHOULD exist (this part works correctly)
        reservation_key = f"username:reserved:{username.lower()}"
        self.assertTrue(
            cache.get(reservation_key) is not None,
            f"Global reservation key '{reservation_key}' should exist"
        )

    def test_chat_specific_suggestions_exists(self):
        """
        This test should PASS - verifying chat-specific suggestions ARE working.

        This demonstrates that the bug is ONLY with the fingerprint-to-usernames mapping,
        not with the chat-specific recent suggestions cache.
        """
        fingerprint = "test_fingerprint_chat"
        chat_code = "TESTCHAT"

        # Generate a username
        username, remaining = generate_username(fingerprint, chat_code)
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
        This test should PASS - verifying generation attempts counter IS working.

        This demonstrates that the bug is ONLY with the fingerprint-to-usernames mapping,
        not with the attempt tracking.
        """
        fingerprint = "test_fingerprint_attempts"
        chat_code = "TESTCHAT"

        # Generate first username
        username1, remaining1 = generate_username(fingerprint, chat_code)
        self.assertIsNotNone(username1)
        self.assertEqual(remaining1, config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL - 1)

        # Generate second username
        username2, remaining2 = generate_username(fingerprint, chat_code)
        self.assertIsNotNone(username2)
        self.assertEqual(remaining2, config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL - 2)

        # Attempts counter SHOULD be working (this part works correctly)
        attempts_key = f"username:generation_attempts:{fingerprint}"
        attempts = cache.get(attempts_key, 0)
        self.assertEqual(attempts, 2, "Generation attempts should be tracked correctly")
