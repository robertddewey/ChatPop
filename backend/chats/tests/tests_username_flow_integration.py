"""
Integration tests for the complete username generation and join flow.

These tests catch bugs that unit tests miss by testing the FULL user journey:
1. suggest-username API → 2. join API with that username → 3. rotation → 4. join again

CRITICAL: These tests would have caught the case-sensitivity bug in ChatRoomJoinView
where the security check failed to handle case-preserved usernames from Redis.
"""
from django.test import TestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from constance.test import override_config

from chats.models import ChatRoom, ChatParticipation

User = get_user_model()


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
        fingerprint = 'test_fp_case_join'

        # STEP 1: Suggest a username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
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
                'fingerprint': fingerprint
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
        participation = ChatParticipation.objects.get(
            chat_room=self.chat,
            fingerprint=fingerprint
        )
        self.assertEqual(participation.username, suggested_username)
        self.assertNotEqual(participation.username, suggested_username.lower())

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_join_rejects_username_not_generated_for_fingerprint(self):
        """
        Test that the security check rejects usernames that weren't generated
        for this specific fingerprint.
        """
        fingerprint1 = 'fp_user1'
        fingerprint2 = 'fp_user2'

        # User 1 generates a username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint1},
            format='json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username1 = suggest_response.data['username']

        # User 2 tries to join with User 1's username (should fail)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username1,  # User 1's username
                'fingerprint': fingerprint2  # User 2's fingerprint
            },
            format='json'
        )

        # Should be rejected by security check
        self.assertEqual(join_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid username', str(join_response.data))

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_case_insensitive_join_attempt_with_different_case(self):
        """
        Test that attempting to join with a different case of a generated username
        still works (case-insensitive matching).
        """
        fingerprint = 'case_insensitive_fp'

        # Generate username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        username = suggest_response.data['username']  # e.g., "HappyTiger42"

        # Try to join with lowercase version
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username.lower(),  # e.g., "happytiger42"
                'fingerprint': fingerprint
            },
            format='json'
        )

        # Should succeed (case-insensitive validation in serializer)
        # Note: The serializer normalizes the username before storage
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)


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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_rotation_no_consecutive_duplicates(self):
        """
        CRITICAL TEST: Ensure rotation never returns the same username consecutively.

        Example of BAD behavior we're testing against:
            Alice, Alice, Alice, Bob, Alice, Carol, ...

        Expected GOOD behavior:
            Alice, Bob, Carol, Alice, Bob, Carol, ...
        """
        fingerprint = 'rotation_no_dupes_fp'

        # STEP 1: Generate 3 usernames (hit global limit)
        generated_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            generated_usernames.append(response.data['username'])

        # STEP 2: Rotate through usernames 15 times and track order
        rotated_sequence = []
        for i in range(15):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=5)
    def test_rotation_preserves_original_capitalization(self):
        """
        Test that rotation returns usernames with their EXACT original capitalization,
        not lowercased or title-cased versions.
        """
        fingerprint = 'rotation_case_fp'

        # Generate 5 usernames and track exact capitalization
        original_usernames = []
        for i in range(5):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            original_usernames.append(response.data['username'])

        # Rotate through usernames 20 times
        for i in range(20):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=3)
    def test_rotation_after_username_becomes_unavailable(self):
        """
        Test that rotation skips usernames that become unavailable
        (e.g., taken by another user).
        """
        fingerprint = 'rotation_availability_fp'

        # Generate 3 usernames
        generated_usernames = []
        for i in range(3):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )
            generated_usernames.append(response.data['username'])

        # Manually create a participation for the second username
        # (simulating another user taking it)
        taken_username = generated_usernames[1]
        ChatParticipation.objects.create(
            chat_room=self.chat,
            username=taken_username,
            fingerprint='another_user_fp',
            user=None
        )

        # Rotate through usernames - should skip the taken one
        rotated_sequence = []
        for i in range(10):
            response = self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=2)
    def test_rotation_then_join_integration(self):
        """
        Test the full flow: generate → rotate → join with rotated username.

        This ensures rotated usernames can successfully be used to join chats.
        """
        fingerprint = 'rotation_join_fp'

        # Generate 2 usernames
        for i in range(2):
            self.client.post(
                f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
                {'fingerprint': fingerprint},
                format='json'
            )

        # Rotate to get a username
        rotate_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        rotated_username = rotate_response.data['username']

        # Try to join with the rotated username
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': rotated_username,
                'fingerprint': fingerprint
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
        participation = ChatParticipation.objects.get(
            chat_room=self.chat,
            fingerprint=fingerprint
        )
        self.assertEqual(participation.username, rotated_username)


class UsernameSecurityChecksIntegrationTestCase(TestCase):
    """
    Test security checks in the join flow that protect against:
    1. API bypass attempts (using usernames not generated for this fingerprint)
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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_cannot_bypass_generation_with_manual_username(self):
        """
        Test that anonymous users cannot manually craft usernames to bypass
        the generation system.
        """
        fingerprint = 'manual_username_fp'

        # Try to join with a manually crafted username (no prior generation)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': 'HackerName123',  # Not generated via API
                'fingerprint': fingerprint
            },
            format='json'
        )

        # Should be rejected by security check
        self.assertEqual(join_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid username', str(join_response.data))

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_case_preserved_username_passes_security_check(self):
        """
        CRITICAL BUG FIX TEST: Verify that usernames with original capitalization
        pass the security check in ChatRoomJoinView.

        This test directly addresses the bug where the security check was:
            if username.lower() not in generated_usernames

        But generated_usernames contained "HappyTiger42", causing false rejections.
        """
        fingerprint = 'security_case_fp'

        # Generate a username
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        username = suggest_response.data['username']

        # Verify it's in Redis with original capitalization
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
        generated_set = cache.get(generated_key, set())
        self.assertIn(username, generated_set)  # Original case
        self.assertNotIn(username.lower(), generated_set)  # NOT lowercase

        # Join with the username (original capitalization)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {
                'username': username,  # e.g., "HappyTiger42"
                'fingerprint': fingerprint
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

    @override_config(MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL=10)
    def test_rejoining_user_bypasses_generation_check(self):
        """
        Test that users who already joined can rejoin without the
        "username must be generated" security check.
        """
        fingerprint = 'rejoin_fp'

        # First, generate and join
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        username = suggest_response.data['username']

        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {'username': username, 'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)

        # Clear Redis (simulate TTL expiration)
        cache.clear()

        # Try to rejoin with the same username
        rejoin_response = self.client.post(
            f'/api/chats/HostUser/{self.chat.code}/join/',
            {'username': username, 'fingerprint': fingerprint},
            format='json'
        )

        # Should succeed even though username is no longer in Redis
        self.assertEqual(
            rejoin_response.status_code,
            status.HTTP_200_OK,
            "Rejoining users should bypass the generation check"
        )
