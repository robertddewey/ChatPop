"""
Tests for username validators
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from chats.utils.username.validators import validate_username


class UsernameValidatorTestCase(TestCase):
    """Test username validation rules"""

    def test_valid_usernames(self):
        """Test that valid usernames pass validation"""
        valid_usernames = [
            'alice',
            'Alice',
            'ALICE',
            'alice123',
            'alice_123',
            'user_name',
            'user123name',
            '_user_',
            '12345',
            'test_user_1',
            'a1b2c3d4e5f',  # 11 chars
            'abcde',  # exactly 5 chars (minimum)
            'abcdefghijklmno',  # exactly 15 chars (maximum)
        ]

        for username in valid_usernames:
            with self.subTest(username=username):
                # Should not raise ValidationError
                result = validate_username(username)
                self.assertEqual(result, username)

    def test_minimum_length_validation(self):
        """Test that usernames shorter than 5 characters are rejected"""
        short_usernames = [
            ('', 'cannot be empty'),  # Empty username
            ('a', 'at least 5 characters'),
            ('ab', 'at least 5 characters'),
            ('abc', 'at least 5 characters'),
            ('abcd', 'at least 5 characters'),  # 4 chars - just below minimum
        ]

        for username, expected_msg in short_usernames:
            with self.subTest(username=username):
                with self.assertRaises(ValidationError) as cm:
                    validate_username(username)
                self.assertIn(expected_msg, str(cm.exception))

    def test_maximum_length_validation(self):
        """Test that usernames longer than 15 characters are rejected"""
        long_usernames = [
            'abcdefghijklmnop',  # 16 chars
            'this_is_a_very_long_username',
            'a' * 20,
            'user_name_12345678',
        ]

        for username in long_usernames:
            with self.subTest(username=username):
                with self.assertRaises(ValidationError) as cm:
                    validate_username(username)
                self.assertIn('at most 15 characters', str(cm.exception))

    def test_invalid_characters(self):
        """Test that usernames with invalid characters are rejected"""
        invalid_usernames = [
            'alice bob',  # space
            'alice-bob',  # hyphen
            'alice.bob',  # period
            'alice@bob',  # @
            'alice!',  # exclamation
            'alice#bob',  # hash
            'alice$bob',  # dollar
            'alice%bob',  # percent
            'alice&bob',  # ampersand
            'alice*bob',  # asterisk
            'alice+bob',  # plus
            'alice=bob',  # equals
            'alice/bob',  # slash
            'alice\\bob',  # backslash
            'alice|bob',  # pipe
            'alice[bob]',  # brackets
            'alice{bob}',  # braces
            'alice(bob)',  # parentheses
            'alice<bob>',  # angle brackets
            'alice,bob',  # comma
            'alice;bob',  # semicolon
            'alice:bob',  # colon
            'alice"bob',  # quote
            "alice'bob",  # apostrophe
            'alice`bob',  # backtick
            'alice~bob',  # tilde
            'alice?bob',  # question
            'alice\nname',  # newline
            'alice\tname',  # tab
        ]

        for username in invalid_usernames:
            with self.subTest(username=username):
                with self.assertRaises(ValidationError) as cm:
                    validate_username(username)
                self.assertIn('letters, numbers, and underscores', str(cm.exception))

    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is stripped before validation"""
        # These should pass after stripping
        username_with_spaces = '  valid_user  '
        result = validate_username(username_with_spaces)
        self.assertEqual(result, 'valid_user')

        # But spaces in the middle should fail
        with self.assertRaises(ValidationError):
            validate_username('user name')

    def test_empty_and_none_values(self):
        """Test handling of empty and None values"""
        with self.assertRaises(ValidationError) as cm:
            validate_username('')
        self.assertIn('cannot be empty', str(cm.exception))

        with self.assertRaises(ValidationError) as cm:
            validate_username(None)
        self.assertIn('cannot be empty', str(cm.exception))

        with self.assertRaises(ValidationError) as cm:
            validate_username('   ')  # only whitespace - gets stripped then fails min length
        # Whitespace gets stripped, resulting in empty string, which fails min length check
        error = str(cm.exception)
        self.assertTrue('cannot be empty' in error or 'at least 5 characters' in error)

    def test_case_preservation(self):
        """Test that case is preserved"""
        mixed_case = 'AlIcE_123'
        result = validate_username(mixed_case)
        self.assertEqual(result, mixed_case)  # Should preserve original case

    def test_unicode_rejection(self):
        """Test that unicode/emoji characters are rejected"""
        unicode_usernames = [
            'alice😀',  # 7 chars - will fail on emoji
            'josé_name',  # 10 chars - will fail on é
            'müller_abc',  # 11 chars - will fail on ü
            'алиса_name',  # Will fail on cyrillic
            '用户用户用户用',  # Chinese - will fail on characters
            'ユーザーユーザー',  # Japanese - will fail on characters
        ]

        for username in unicode_usernames:
            with self.subTest(username=username):
                with self.assertRaises(ValidationError) as cm:
                    validate_username(username)
                # May fail on length OR invalid chars depending on unicode handling
                error = str(cm.exception)
                self.assertTrue(
                    'letters, numbers, and underscores' in error or 'at least 5 characters' in error,
                    f"Expected validation error for {username}, got: {error}"
                )

    def test_underscore_positions(self):
        """Test that underscores can be at any position"""
        valid_with_underscores = [
            '_alice',  # leading (6 chars)
            'alice_',  # trailing (6 chars)
            '_alice_',  # both (7 chars)
            'alice_bob_c',  # multiple (12 chars)
            '___alice___',  # multiple consecutive (12 chars)
        ]

        for username in valid_with_underscores:
            with self.subTest(username=username):
                result = validate_username(username)
                self.assertEqual(result, username)

    def test_numeric_only_usernames(self):
        """Test that purely numeric usernames are allowed"""
        numeric_usernames = [
            '12345',
            '999999999999999',  # 15 digits
        ]

        for username in numeric_usernames:
            with self.subTest(username=username):
                result = validate_username(username)
                self.assertEqual(result, username)
