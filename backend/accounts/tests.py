"""
Registration Tests

Tests for user registration functionality.
Users can register with either:
1. A custom typed username (any valid username)
2. A username generated via the suggest-username endpoint

Note: The "must use generated username" security is ONLY enforced for anonymous chat joining,
NOT for registration. Registered users can choose any valid username for their account.
"""

import json
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from accounts.models import User


class RegistrationTests(TestCase):
    """
    Test user registration with both custom and generated usernames.
    """

    def setUp(self):
        """Set up test client and clear Redis cache"""
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        """Clean up Redis cache after each test"""
        cache.clear()

    def test_registration_with_custom_username_succeeds(self):
        """Test that users can register with any valid custom username"""
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'CustomUser99'
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 201, f"Registration failed: {response.json()}")
        data = response.json()
        self.assertIn('user', data)
        self.assertIn('token', data)
        self.assertEqual(data['user']['reserved_username'], 'CustomUser99')

        # Verify user was created in database
        user = User.objects.get(email='testuser@example.com')
        self.assertEqual(user.reserved_username, 'CustomUser99')

    def test_registration_with_generated_username_succeeds(self):
        """Test that registration also works when using a generated username"""
        fingerprint = 'test_registration_fp_001'

        # Step 1: Generate a username via the suggest-username endpoint
        suggest_response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        username = suggest_response.json()['username']

        # Step 2: Register with the generated username
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username,
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 201, f"Registration failed: {response.json()}")
        data = response.json()
        self.assertIn('user', data)
        self.assertIn('token', data)
        self.assertEqual(data['user']['reserved_username'], username)

        # Verify user was created in database
        user = User.objects.get(email='testuser@example.com')
        self.assertEqual(user.reserved_username, username)

    def test_registration_without_username_succeeds(self):
        """Test that registration without providing a username succeeds with empty string"""
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!'
                # No reserved_username provided
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['user']['reserved_username'], '')

    def test_multiple_registrations_with_different_usernames(self):
        """Test that multiple users can register with different usernames"""
        # Register first user
        response_1 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user1@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'User1'
            }),
            content_type='application/json'
        )
        self.assertEqual(response_1.status_code, 201)

        # Register second user with different username
        response_2 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user2@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'User2'
            }),
            content_type='application/json'
        )
        self.assertEqual(response_2.status_code, 201)

        # Verify both users were created
        self.assertTrue(User.objects.filter(email='user1@example.com').exists())
        self.assertTrue(User.objects.filter(email='user2@example.com').exists())

    def test_registration_preserves_other_validations(self):
        """Test that registration still enforces other validations (email, password, etc.)"""
        # Test 1: Invalid email
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'invalid-email',
                'password': 'SecurePass123!',
                'reserved_username': 'ValidUser99'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

        # Test 2: Weak password
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'test@example.com',
                'password': 'weak',  # Too short
                'reserved_username': 'ValidUser99'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_registration_username_case_insensitive_uniqueness(self):
        """Test that username uniqueness check is case-insensitive"""
        # Register first user
        response_1 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user1@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'TestUser99'
            }),
            content_type='application/json'
        )
        self.assertEqual(response_1.status_code, 201)

        # Try to register second user with same username but different case
        response_2 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user2@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'testuser99'  # Different case
            }),
            content_type='application/json'
        )

        # Should be rejected (username already taken)
        self.assertEqual(response_2.status_code, 400)
        self.assertIn('reserved_username', response_2.json())

    def test_registration_duplicate_username_rejected(self):
        """Test that duplicate usernames are rejected"""
        # Register first user
        response_1 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user1@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'DuplicateUser'
            }),
            content_type='application/json'
        )
        self.assertEqual(response_1.status_code, 201)

        # Try to register second user with same username
        response_2 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user2@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'DuplicateUser'
            }),
            content_type='application/json'
        )

        # Should be rejected
        self.assertEqual(response_2.status_code, 400)
        self.assertIn('reserved_username', response_2.json())


class UsernameAvailabilityCheckTests(TestCase):
    """Test the /api/auth/check-username/ endpoint"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()

        # Create an existing user
        self.existing_user = User.objects.create_user(
            email='existing@example.com',
            password='TestPass123!',
            reserved_username='ExistingUser99'
        )

    def test_check_available_username(self):
        """Test checking an available username"""
        response = self.client.get('/api/auth/check-username/', {'username': 'AvailableUser99'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['available'])
        self.assertIn('available', data['message'].lower())

    def test_check_taken_username(self):
        """Test checking a taken username"""
        response = self.client.get('/api/auth/check-username/', {'username': 'ExistingUser99'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['available'])
        self.assertIn('taken', data['message'].lower())

    def test_check_username_case_insensitive(self):
        """Test that username check is case-insensitive"""
        response = self.client.get('/api/auth/check-username/', {'username': 'existinguser99'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['available'])  # Should detect as taken (case-insensitive)

    def test_check_profane_username(self):
        """Test that profane usernames are rejected"""
        response = self.client.get('/api/auth/check-username/', {'username': 'FuckYou123'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['available'])
        # Check for either 'profanity' or 'prohibited' in the error message
        message_lower = data['message'].lower()
        self.assertTrue('profanity' in message_lower or 'prohibited' in message_lower or 'not allowed' in message_lower)

    def test_check_empty_username(self):
        """Test that empty username is rejected"""
        response = self.client.get('/api/auth/check-username/', {'username': ''})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['available'])
        self.assertIn('required', data['message'].lower())
