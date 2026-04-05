"""
Integration tests for the complete username generation and join flow.

These tests catch bugs that unit tests miss by testing the FULL user journey:
1. suggest-username API → 2. join API with that username → 3. rotation → 4. join again

CRITICAL: These tests would have caught the case-sensitivity bug in ChatRoomJoinView
where the security check failed to handle case-preserved usernames from Redis.
"""
import allure
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from constance.test import override_config

from chats.models import ChatRoom, ChatParticipation

User = get_user_model()


@allure.feature('Username Generation')
@allure.story('Generation to Join Flow')
class UsernameGenerationToJoinFlowTestCase(TestCase):
    """
    Test the complete flow from username generation to joining a chat.

    This catches integration bugs that unit tests miss, such as:
    - Case preservation through the entire flow
    - Security check compatibility with case-preserved usernames
    - Join validation with generated usernames
    """

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

        # Host must join first to allow anonymous users to join
        ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.user,
            username='HostUser',
            fingerprint='host_fingerprint'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Suggest username then join preserves case")
    @allure.description("""CRITICAL TEST: This would have caught the case-sensitivity bug.

Tests that a username suggested by the API can be used to join the chat
with its original capitalization preserved (e.g., "HappyTiger42" not "happytiger42").

Bug it catches: ChatRoomJoinView security check was doing:
    if username.lower() not in generated_usernames
But generated_usernames contained "HappyTiger42", so checking for
"happytiger42" would fail.""")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_suggest_username_then_join_preserves_case(self):
        """
        CRITICAL TEST: This would have caught the case-sensitivity bug.

        Tests that a username suggested by the API can be used to join the chat
        with its original capitalization preserved (e.g., "HappyTiger42" not "happytiger42").

        Bug it catches: ChatRoomJoinView security check was doing:
            if username.lower() not in generated_usernames
        But generated_usernames contained "HappyTiger42", so checking for
        "happytiger42" would fail.
        """
        # STEP 1: Suggest a username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )

        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        suggested_username = suggest_response.data['username']

        # Verify it has mixed case (e.g., "HappyTiger42")
        self.assertRegex(suggested_username, r'^[A-Z][a-z]+[A-Z][a-z]+\d+$')
        self.assertNotEqual(suggested_username, suggested_username.lower())

        # STEP 2: Try to join with the EXACT suggested username (original case)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': suggested_username,  # Original case: "HappyTiger42"
            },
            format='json'
        )

        # This is where the bug manifested: join would fail with 400 Bad Request
        # because the security check couldn't find "happytiger42" in ["HappyTiger42"]
        self.assertEqual(
            join_response.status_code,
            status.HTTP_200_OK,
            f"Failed to join with suggested username '{suggested_username}'. "
            f"Error: {join_response.data if join_response.status_code != 200 else 'None'}"
        )

        # Verify participation was created with original capitalization
        session_key = self.client.session.session_key
        participation = ChatParticipation.objects.get(
            chat_room=self.chat,
            session_key=session_key
        )
        self.assertEqual(participation.username, suggested_username)
        self.assertNotEqual(participation.username, suggested_username.lower())

    @allure.title("Join rejects username not generated for session")
    @allure.description("Test that the security check rejects usernames that weren't generated for this specific session")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_join_rejects_username_not_generated_for_session(self):
        """
        Test that the security check rejects usernames that weren't generated
        for this specific session.
        """
        # Use two separate clients (different sessions)
        client1 = APIClient()
        client2 = APIClient()

        # User 1 generates a username
        suggest_response = client1.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username1 = suggest_response.data['username']

        # User 2 tries to join with User 1's username (should fail)
        join_response = client2.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username1,  # User 1's username
            },
            format='json'
        )

        # Should be rejected by security check
        self.assertEqual(join_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid username', str(join_response.data))

    @allure.title("Case insensitive join with different case")
    @allure.description("Test that attempting to join with a different case of a generated username still works (case-insensitive matching)")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_case_insensitive_join_attempt_with_different_case(self):
        """
        Test that attempting to join with a different case of a generated username
        still works (case-insensitive matching).
        """
        # Generate username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )
        username = suggest_response.data['username']  # e.g., "HappyTiger42"

        # Try to join with lowercase version
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username.lower(),  # e.g., "happytiger42"
            },
            format='json'
        )

        # Should succeed (case-insensitive validation in serializer)
        # Note: The serializer normalizes the username before storage
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)


@allure.feature('Username Generation')
@allure.story('Username Rotation')
class UsernameRotationIntegrationTestCase(TestCase):
    """
    Test username rotation through the complete API flow.

    Tests that rotation:
    1. Returns usernames in a predictable order (alphabetically sorted)
    2. Cycles through all available usernames before repeating
    3. Never returns consecutive duplicates
    4. Preserves original capitalization
    """

    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        cache.clear()

        self.user = User.objects.create_user(
            email='host@example.com',
            password='pass123',
            reserved_username='HostUser'
        )

        self.chat = ChatRoom.objects.create(
            code='ROTTEST',
            name='Rotation Test Chat',
            host=self.user,
        )

        # Host must join first to allow anonymous users to join
        ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.user,
            username='HostUser',
            fingerprint='host_fingerprint'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Rotation has no consecutive duplicates")
    @allure.description("""CRITICAL TEST: Ensure rotation never returns the same username consecutively.

Example of BAD behavior we're testing against:
    Alice, Alice, Alice, Bob, Alice, Carol, ...

Expected GOOD behavior:
    Alice, Bob, Carol, Alice, Bob, Carol, ...""")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_rotation_no_consecutive_duplicates(self):
        """
        CRITICAL TEST: Ensure rotation never returns the same username consecutively.

        Example of BAD behavior we're testing against:
            Alice, Alice, Alice, Bob, Alice, Carol, ...

        Expected GOOD behavior:
            Alice, Bob, Carol, Alice, Bob, Carol, ...
        """
        # STEP 1: Generate 3 usernames (hit global limit)
        generated_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            generated_usernames.append(response.data['username'])

        # STEP 2: Rotate through usernames 15 times and track order
        rotated_sequence = []
        for i in range(15):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            rotated_sequence.append(response.data['username'])

        # ASSERTION 1: No consecutive duplicates
        for i in range(len(rotated_sequence) - 1):
            self.assertNotEqual(
                rotated_sequence[i],
                rotated_sequence[i + 1],
                f"Found consecutive duplicate at index {i}: {rotated_sequence[i]}"
            )

        # ASSERTION 2: All usernames should appear in the sequence
        unique_returned = set(rotated_sequence)
        self.assertEqual(
            unique_returned,
            set(generated_usernames),
            "Rotation should cycle through all generated usernames"
        )

        # ASSERTION 3: Sequence should be predictable (alphabetically sorted rotation)
        # After sorting, the rotation should follow a pattern like:
        # [Alice, Bob, Carol, Alice, Bob, Carol, Alice, Bob, Carol, ...]
        sorted_usernames = sorted(generated_usernames)
        for i, username in enumerate(rotated_sequence):
            expected = sorted_usernames[i % len(sorted_usernames)]
            self.assertEqual(
                username,
                expected,
                f"At index {i}, expected {expected} but got {username}"
            )

    @allure.title("Rotation preserves original capitalization")
    @allure.description("Test that rotation returns usernames with their EXACT original capitalization, not lowercased or title-cased versions")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=5)
    def test_rotation_preserves_original_capitalization(self):
        """
        Test that rotation returns usernames with their EXACT original capitalization,
        not lowercased or title-cased versions.
        """
        # Generate 5 usernames and track exact capitalization
        original_usernames = []
        for i in range(5):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            original_usernames.append(response.data['username'])

        # Rotate through usernames 20 times
        for i in range(20):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            rotated_username = response.data['username']

            # Must be an exact match (same capitalization)
            self.assertIn(
                rotated_username,
                original_usernames,
                f"Rotated username '{rotated_username}' doesn't match original capitalization"
            )

            # Should NOT be a lowercased version
            self.assertNotEqual(rotated_username, rotated_username.lower())

    @allure.title("Rotation skips unavailable usernames")
    @allure.description("Test that rotation skips usernames that become unavailable (e.g., taken by another user)")
    @allure.severity(allure.severity_level.NORMAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_rotation_after_username_becomes_unavailable(self):
        """
        Test that rotation skips usernames that become unavailable
        (e.g., taken by another user).
        """
        # Generate 3 usernames
        generated_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            generated_usernames.append(response.data['username'])

        # Manually create a participation for the second username
        # (simulating another user taking it)
        taken_username = generated_usernames[1]
        ChatParticipation.objects.create(
            chat_room=self.chat,
            username=taken_username,
            session_key='another_user_session',
            user=None
        )

        # Rotate through usernames - should skip the taken one
        rotated_sequence = []
        for i in range(10):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            rotated_sequence.append(response.data['username'])

        # The taken username should NOT appear in rotation
        self.assertNotIn(taken_username, rotated_sequence)

        # Only the 2 available usernames should appear
        unique_returned = set(rotated_sequence)
        available_usernames = [u for u in generated_usernames if u != taken_username]
        self.assertEqual(unique_returned, set(available_usernames))

    @allure.title("Rotation then join integration")
    @allure.description("Test the full flow: generate → rotate → join with rotated username. This ensures rotated usernames can successfully be used to join chats")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=2)
    def test_rotation_then_join_integration(self):
        """
        Test the full flow: generate → rotate → join with rotated username.

        This ensures rotated usernames can successfully be used to join chats.
        """
        # Generate 2 usernames
        for i in range(2):
            self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {},
                format='json'
            )

        # Rotate to get a username
        rotate_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )
        rotated_username = rotate_response.data['username']

        # Try to join with the rotated username
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': rotated_username,
            },
            format='json'
        )

        # Should succeed
        self.assertEqual(
            join_response.status_code,
            status.HTTP_200_OK,
            f"Failed to join with rotated username. Error: {join_response.data}"
        )

        # Verify participation
        session_key = self.client.session.session_key
        participation = ChatParticipation.objects.get(
            chat_room=self.chat,
            session_key=session_key
        )
        self.assertEqual(participation.username, rotated_username)


@allure.feature('Username Generation')
@allure.story('Security Checks')
class UsernameSecurityChecksIntegrationTestCase(TestCase):
    """
    Test security checks in the join flow that protect against:
    1. API bypass attempts (using usernames not generated for this session)
    2. Username hijacking (using another user's generated username)
    3. Case manipulation attacks
    """

    def setUp(self):
        """Set up test client and data"""
        self.client = APIClient()
        cache.clear()

        self.user = User.objects.create_user(
            email='host@example.com',
            password='pass123',
            reserved_username='HostUser'
        )

        self.chat = ChatRoom.objects.create(
            code='SECTEST',
            name='Security Test Chat',
            host=self.user,
        )

        # Host must join first to allow anonymous users to join
        ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.user,
            username='HostUser',
            fingerprint='host_fingerprint'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    @allure.title("Cannot bypass generation with manual username")
    @allure.description("Test that anonymous users cannot manually craft usernames to bypass the generation system")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_cannot_bypass_generation_with_manual_username(self):
        """
        Test that anonymous users cannot manually craft usernames to bypass
        the generation system.
        """
        # Try to join with a manually crafted username (no prior generation)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': 'HackerName123',  # Not generated via API
            },
            format='json'
        )

        # Should be rejected by security check
        self.assertEqual(join_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid username', str(join_response.data))

    @allure.title("Case-preserved username passes security check")
    @allure.description("""CRITICAL BUG FIX TEST: Verify that usernames with original capitalization
pass the security check in ChatRoomJoinView.

This test directly addresses the bug where the security check was:
    if username.lower() not in generated_usernames

But generated_usernames contained "HappyTiger42", causing false rejections.""")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_case_preserved_username_passes_security_check(self):
        """
        CRITICAL BUG FIX TEST: Verify that usernames with original capitalization
        pass the security check in ChatRoomJoinView.

        This test directly addresses the bug where the security check was:
            if username.lower() not in generated_usernames

        But generated_usernames contained "HappyTiger42", causing false rejections.
        """
        # Generate a username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )
        username = suggest_response.data['username']

        # Verify it's in Redis with original capitalization
        session_key = self.client.session.session_key
        generated_key = f"username:generated_for_session:{session_key}"
        generated_set = cache.get(generated_key, set())
        self.assertIn(username, generated_set)  # Original case
        self.assertNotIn(username.lower(), generated_set)  # NOT lowercase

        # Join with the username (original capitalization)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username,  # e.g., "HappyTiger42"
            },
            format='json'
        )

        # This is where the bug manifested - the security check would fail
        self.assertEqual(
            join_response.status_code,
            status.HTTP_200_OK,
            f"Security check failed for case-preserved username '{username}'. "
            f"This suggests the security check is not properly handling case-insensitive comparison. "
            f"Error: {join_response.data if join_response.status_code != 200 else 'None'}"
        )

    @allure.title("Rejoining user bypasses generation check")
    @allure.description("Test that users who already joined can rejoin without the 'username must be generated' security check")
    @allure.severity(allure.severity_level.CRITICAL)
    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_rejoining_user_bypasses_generation_check(self):
        """
        Test that users who already joined can rejoin without the
        "username must be generated" security check.
        """
        # First, generate and join
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {},
            format='json'
        )
        username = suggest_response.data['username']

        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {'username': username},
            format='json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)

        # Clear Redis (simulate TTL expiration)
        cache.clear()

        # Try to rejoin with the same username
        rejoin_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {'username': username},
            format='json'
        )

        # Should succeed even though username is no longer in Redis
        self.assertEqual(
            rejoin_response.status_code,
            status.HTTP_200_OK,
            "Rejoining users should bypass the generation check"
        )
