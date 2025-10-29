"""
Tests for username profanity filtering
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from chats.utils.username.validators import validate_username
from chats.utils.username.profanity import is_username_allowed, ValidationResult


class UsernameProfanityCheckTests(TestCase):
    """
    Test the profanity checker module directly.
    These tests mirror the built-in tests in username_profanity_check.py
    """

    def test_clean_usernames_allowed(self):
        """Test that clean usernames are allowed"""
        clean_usernames = [
            "Alice_Smith",
            "Bob12345",
            "Charlie99",
            "DavidJones",
            "Emma_Watson",
        ]
        for username in clean_usernames:
            result = is_username_allowed(username)
            self.assertTrue(result.allowed, f"{username} should be allowed but got: {result.reason}")

    def test_obvious_profanity_blocked(self):
        """Test that obvious profanity is blocked"""
        profane_usernames = [
            "fuck123",
            "shithead",
            "asshole99",
        ]
        for username in profane_usernames:
            result = is_username_allowed(username)
            self.assertFalse(result.allowed, f"{username} should be blocked")
            self.assertIsNotNone(result.reason)

    def test_leet_speak_variants_blocked(self):
        """Test that leet speak variants are blocked"""
        leet_variants = [
            "fUcK123",  # Case variation
            "f_u_c_k",  # Separators
            "fu__ck",   # Extra separators
        ]
        for username in leet_variants:
            result = is_username_allowed(username)
            self.assertFalse(result.allowed, f"{username} should be blocked as leet speak variant")

    def test_legitimate_words_with_banned_substrings_allowed(self):
        """Test that legitimate words containing banned substrings are allowed"""
        legitimate_usernames = [
            "password123",     # Contains 'ass'
            "assistant99",     # Contains 'ass'
            "compass_user",    # Contains 'ass'
            "titan_gamer",     # Contains 'tit'
        ]
        for username in legitimate_usernames:
            result = is_username_allowed(username)
            self.assertTrue(result.allowed, f"{username} should be allowed but got: {result.reason}")

    def test_check_result_structure(self):
        """Test that ValidationResult has correct structure"""
        # Allowed username
        result = is_username_allowed("Alice_Smith")
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.allowed)
        self.assertIsNone(result.reason)

        # Blocked username
        result = is_username_allowed("fuck123")
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.allowed)
        self.assertIsNotNone(result.reason)
        self.assertIsInstance(result.reason, str)


class ValidatorProfanityIntegrationTests(TestCase):
    """
    Test profanity filtering integration with validate_username()
    """

    def test_clean_username_passes_validation(self):
        """Test that clean usernames pass validation with profanity check enabled"""
        clean_usernames = [
            "Alice_Smith",
            "Bob12345",
            "Charlie99",
        ]
        for username in clean_usernames:
            try:
                result = validate_username(username, skip_badwords_check=False)
                self.assertEqual(result, username)
            except ValidationError:
                self.fail(f"{username} should pass validation")

    def test_profane_username_fails_validation(self):
        """Test that profane usernames fail validation with profanity check enabled"""
        profane_usernames = [
            "fuck123",
            "shithead",
            "asshole99",
        ]
        for username in profane_usernames:
            with self.assertRaises(ValidationError) as cm:
                validate_username(username, skip_badwords_check=False)
            self.assertIn("not allowed", str(cm.exception).lower())

    def test_skip_badwords_check_bypasses_profanity_filter(self):
        """Test that skip_badwords_check=True bypasses profanity filtering"""
        # This would normally be blocked, but skip_badwords_check=True should allow it
        username = "fuck123"
        try:
            result = validate_username(username, skip_badwords_check=True)
            self.assertEqual(result, username)
        except ValidationError as e:
            # Should only fail on format validation (length/characters), not profanity
            self.assertNotIn("not allowed", str(e).lower())

    def test_legitimate_words_pass_validation(self):
        """Test that legitimate words with banned substrings pass validation"""
        legitimate_usernames = [
            "password123",
            "assistant99",
            "compass_user",
        ]
        for username in legitimate_usernames:
            try:
                result = validate_username(username, skip_badwords_check=False)
                self.assertEqual(result, username)
            except ValidationError:
                self.fail(f"{username} should pass validation")


class ChatJoinProfanityTests(TestCase):
    """
    Test profanity filtering in the chat join API endpoint
    """

    def setUp(self):
        """Create a test chat room"""
        from chats.models import ChatRoom
        from accounts.models import User

        # Create a test user to be the host
        self.user = User.objects.create_user(
            email='testhost@example.com',
            password='TestPass123!'
        )

        self.chat = ChatRoom.objects.create(
            name="Test Chat",
            host=self.user,
            access_mode='public'
        )

    def test_join_with_clean_username(self):
        """Test joining a chat with a clean username"""
        fingerprint = 'test_fp_456'

        # Step 1: Generate a valid username
        suggest_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
            {
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        username = suggest_response.json()['username']

        # Step 2: Join with the generated username
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_join_with_profane_username_rejected(self):
        """Test that joining with profane username is rejected"""
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': 'fuck123',
                'fingerprint': 'test_fp_789'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json())

    def test_join_with_leet_speak_profanity_rejected(self):
        """Test that leet speak profanity is rejected"""
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': 'f_u_c_k_99',
                'fingerprint': 'test_fp_101'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_join_with_legitimate_word_containing_substring(self):
        """Test that legitimate words with banned substrings are allowed"""
        fingerprint = 'test_fp_102'

        # Step 1: Generate a valid username
        suggest_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
            {
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        username = suggest_response.json()['username']

        # Step 2: Join with the generated username (should succeed)
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class CheckUsernameProfanityTests(TestCase):
    """
    Test profanity filtering in check-username endpoint (registration modal)
    """

    def test_check_profane_username_rejected(self):
        """Test that profane username is rejected during check"""
        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'asshole99'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('available'))
        self.assertIn('not allowed', data.get('message').lower())

    def test_check_leet_speak_profanity_rejected(self):
        """Test that leet speak profanity is rejected during check"""
        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'f_u_c_k_99'}
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('available'))


class UserRegistrationProfanityTests(TestCase):
    """
    Test profanity filtering in user registration
    """

    def test_register_with_clean_reserved_username(self):
        """Test registering with a clean reserved username"""
        response = self.client.post(
            '/api/auth/register/',
            data={
                'email': 'alice@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'AliceSmith99'  # Reserved usernames: alphanumeric only (no underscores)
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)

    def test_register_with_profane_reserved_username_rejected(self):
        """Test that registering with profane reserved username is rejected"""
        response = self.client.post(
            '/api/auth/register/',
            {
                'email': 'test@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'fuck123'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved_username', response.json())

    def test_register_without_reserved_username(self):
        """Test that registration without reserved username works"""
        response = self.client.post(
            '/api/auth/register/',
            {
                'email': 'nouser@example.com',
                'password': 'SecurePass123!'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 201)


class UsernameValidationProfanityTests(TestCase):
    """
    Test profanity filtering in username validation endpoint
    """

    def setUp(self):
        """Create a test chat room"""
        from chats.models import ChatRoom
        from accounts.models import User

        # Create a test user to be the host
        self.user = User.objects.create_user(
            email='validationhost@example.com',
            password='TestPass123!'
        )

        self.chat = ChatRoom.objects.create(
            name="Test Chat",
            host=self.user,
            access_mode='public'
        )

    def test_validate_profane_username_rejected(self):
        """Test that profane username is rejected during validation"""
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/validate-username/',
            {
                'username': 'fuck123',
                'fingerprint': 'test-fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('available'))
        self.assertIn('error', data)

    def test_validate_leet_speak_profanity_rejected(self):
        """Test that leet speak profanity is rejected during validation"""
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/validate-username/',
            {
                'username': 'f_u_c_k_99',
                'fingerprint': 'test-fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('available'))


class SuggestUsernameProfanityTests(TestCase):
    """
    Test that suggested usernames skip profanity filtering
    """

    def setUp(self):
        """Create a test chat room"""
        from chats.models import ChatRoom
        from accounts.models import User

        # Create a test user to be the host
        self.user = User.objects.create_user(
            email='suggesthost@example.com',
            password='TestPass123!'
        )

        self.chat = ChatRoom.objects.create(
            name="Test Chat",
            host=self.user,
            access_mode='public'
        )

    def test_suggested_usernames_are_clean(self):
        """Test that suggested usernames are always clean (don't contain profanity)"""
        # Generate 5 usernames with unique fingerprints (well below rate limit of 10/hour per fingerprint)
        for i in range(5):
            response = self.client.post(
                f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
                {
                    'fingerprint': f'test_profanity_fp_{i}'
                },
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            username = data.get('username')

            # Verify the suggested username would pass profanity check
            result = is_username_allowed(username)
            self.assertTrue(
                result.allowed,
                f"Suggested username '{username}' failed profanity check: {result.reason}"
            )

    def test_suggested_username_endpoint_success(self):
        """Test that suggest-username endpoint returns valid username"""
        response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
            {
                'fingerprint': 'test_endpoint_success_fp'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('username', data)
        self.assertIsInstance(data['username'], str)
        self.assertGreater(len(data['username']), 0)


class GeneratedUsernameSecurityTests(TestCase):
    """
    Test security enforcement: Anonymous users can ONLY use system-generated usernames.
    This prevents API bypass where users send arbitrary usernames.
    """

    def setUp(self):
        """Create a test chat room and authenticated user"""
        from chats.models import ChatRoom
        from accounts.models import User

        # Create a test user to be the host
        self.host_user = User.objects.create_user(
            email='securityhost@example.com',
            password='TestPass123!'
        )

        self.chat = ChatRoom.objects.create(
            name="Security Test Chat",
            host=self.host_user,
            access_mode='public'
        )

        # Create a registered user with a reserved username (max 15 chars)
        self.registered_user = User.objects.create_user(
            email='registered@example.com',
            password='TestPass123!',
            reserved_username='RegUser99'
        )

    def test_anonymous_user_with_generated_username_can_join(self):
        """Test that anonymous users can join with a system-generated username"""
        fingerprint = 'test_security_fp_1'

        # Step 1: Get a generated username
        suggest_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
            {
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        suggested_username = suggest_response.json()['username']

        # Step 2: Join with the generated username (should succeed)
        join_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': suggested_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, 200)
        data = join_response.json()
        self.assertIn('session_token', data)
        self.assertEqual(data['username'], suggested_username)

    def test_anonymous_user_with_non_generated_username_rejected(self):
        """Test that anonymous users CANNOT join with arbitrary (non-generated) usernames"""
        fingerprint = 'test_security_fp_2'

        # Try to join with a username that was NOT generated by the system
        arbitrary_username = 'ArbitraryUser99'

        join_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': arbitrary_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, 400)
        data = join_response.json()
        # DRF returns ValidationError as a list when raised with a string
        self.assertIsInstance(data, list)
        error_message = str(data[0]).lower()
        self.assertIn('suggest username', error_message)

    def test_authenticated_user_can_use_reserved_username(self):
        """Test that authenticated users can still use their reserved usernames"""
        # Log in as the registered user
        self.client.force_login(self.registered_user)

        # Join with reserved username (should succeed)
        join_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': self.registered_user.reserved_username,
                'fingerprint': 'test_security_fp_3'  # Fingerprint provided but user is authenticated
            },
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, 200)
        data = join_response.json()
        self.assertIn('session_token', data)
        self.assertEqual(data['username'], self.registered_user.reserved_username)

    def test_existing_participant_can_rejoin_with_same_username(self):
        """Test that existing participants can rejoin with their existing username"""
        from chats.models import ChatParticipation

        fingerprint = 'test_security_fp_4'
        username = 'ExistingUser99'

        # Step 1: Create an existing participation (simulate previous join)
        participation = ChatParticipation.objects.create(
            chat_room=self.chat,
            username=username,
            fingerprint=fingerprint,
            user=None,  # Anonymous user
            is_active=True
        )

        # Step 2: Try to rejoin with the same username and fingerprint (should succeed)
        rejoin_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(rejoin_response.status_code, 200)
        data = rejoin_response.json()
        self.assertIn('session_token', data)
        self.assertEqual(data['username'], username)

    def test_anonymous_user_cannot_use_another_fingerprints_generated_username(self):
        """Test that anonymous users cannot use usernames generated for different fingerprints"""
        fingerprint_a = 'test_security_fp_5a'
        fingerprint_b = 'test_security_fp_5b'

        # Step 1: Generate username for fingerprint A
        suggest_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/suggest-username/',
            {
                'fingerprint': fingerprint_a
            },
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        username_for_a = suggest_response.json()['username']

        # Step 2: Try to join with username_for_a using fingerprint B (should fail)
        join_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': username_for_a,
                'fingerprint': fingerprint_b
            },
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, 400)
        data = join_response.json()
        # DRF returns ValidationError as a list
        self.assertIsInstance(data, list)
        error_message = str(data[0]).lower()
        self.assertIn('suggest username', error_message)

    def test_security_check_only_applies_to_new_anonymous_participations(self):
        """Test that security check is only applied to NEW anonymous participations, not rejoins"""
        from chats.models import ChatParticipation

        fingerprint = 'test_security_fp_6'
        username = 'RejoiningUser99'

        # Step 1: Create an existing participation with an arbitrary username
        # (This simulates a user who joined before the security check was implemented)
        participation = ChatParticipation.objects.create(
            chat_room=self.chat,
            username=username,
            fingerprint=fingerprint,
            user=None,
            is_active=True
        )

        # Step 2: Rejoin with the same username (should succeed even if not in generated cache)
        rejoin_response = self.client.post(
            f'/api/chats/RegUser99/{self.chat.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(rejoin_response.status_code, 200)
        data = rejoin_response.json()
        self.assertEqual(data['username'], username)
