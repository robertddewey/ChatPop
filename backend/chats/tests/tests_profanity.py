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
        response = self.client.post(
            f'/api/chats/{self.chat.code}/join/',
            {
                'username': 'Alice_Smith',
                'fingerprint': 'test_fp_456'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    def test_join_with_profane_username_rejected(self):
        """Test that joining with profane username is rejected"""
        response = self.client.post(
            f'/api/chats/{self.chat.code}/join/',
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
            f'/api/chats/{self.chat.code}/join/',
            {
                'username': 'f_u_c_k_99',
                'fingerprint': 'test_fp_101'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_join_with_legitimate_word_containing_substring(self):
        """Test that legitimate words with banned substrings are allowed"""
        response = self.client.post(
            f'/api/chats/{self.chat.code}/join/',
            {
                'username': 'password123',
                'fingerprint': 'test_fp_102'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class CheckUsernameProfanityTests(TestCase):
    """
    Test profanity filtering in check-username endpoint (registration modal)
    """

    def test_check_clean_username(self):
        """Test that clean username passes check"""
        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'GoodUser123'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('available'))
        self.assertEqual(data.get('message'), 'Username is available')

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

    def test_check_legitimate_word_with_substring(self):
        """Test that legitimate words with banned substrings pass check"""
        response = self.client.get(
            '/api/auth/check-username/',
            {'username': 'password123'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('available'))


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

    def test_validate_clean_username(self):
        """Test that clean username passes validation"""
        response = self.client.post(
            f'/api/chats/{self.chat.code}/validate-username/',
            {
                'username': 'GoodUser123',
                'fingerprint': 'test-fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('available'))

    def test_validate_profane_username_rejected(self):
        """Test that profane username is rejected during validation"""
        response = self.client.post(
            f'/api/chats/{self.chat.code}/validate-username/',
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
            f'/api/chats/{self.chat.code}/validate-username/',
            {
                'username': 'f_u_c_k_99',
                'fingerprint': 'test-fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data.get('available'))

    def test_validate_legitimate_word_with_substring(self):
        """Test that legitimate words with banned substrings pass validation"""
        response = self.client.post(
            f'/api/chats/{self.chat.code}/validate-username/',
            {
                'username': 'password123',
                'fingerprint': 'test-fingerprint'
            },
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('available'))


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
        # Generate 10 usernames and check they're all clean (below rate limit of 20/hour)
        for _ in range(10):
            response = self.client.post(
                f'/api/chats/{self.chat.code}/suggest-username/',
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
            f'/api/chats/{self.chat.code}/suggest-username/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('username', data)
        self.assertIsInstance(data['username'], str)
        self.assertGreater(len(data['username']), 0)
