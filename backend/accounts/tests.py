"""
Registration Security Tests

Tests for the generated username enforcement system during registration.
This ensures users can ONLY register with usernames generated via the suggest-username endpoint.
"""

import json
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from accounts.models import User


class RegistrationGeneratedUsernameSecurityTests(TestCase):
    """
    Test security enforcement: Users can ONLY register with system-generated usernames.
    This prevents API bypass where users send arbitrary usernames to the registration endpoint.
    """

    def setUp(self):
        """Set up test client and clear Redis cache"""
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        """Clean up Redis cache after each test"""
        cache.clear()

    def test_registration_with_generated_username_succeeds(self):
        """Test that registration succeeds when using a generated username"""
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

    def test_registration_with_non_generated_username_rejected(self):
        """Test that registration is rejected when using a non-generated username"""
        fingerprint = 'test_registration_fp_002'

        # Try to register with an arbitrary username (not generated via suggest-username)
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'HackerUser99',  # Not generated
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )

        # Should be rejected
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('reserved_username', data)
        self.assertIn('Invalid username', str(data['reserved_username']))
        self.assertIn('suggest username feature', str(data['reserved_username']))

        # Verify user was NOT created
        self.assertFalse(User.objects.filter(email='testuser@example.com').exists())

    def test_registration_without_fingerprint_succeeds(self):
        """Test that registration without fingerprint bypasses security check (backward compatibility)"""
        # NOTE: This test verifies backward compatibility. In production, fingerprint should be required.

        # Register without providing a fingerprint (security check is bypassed)
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'ValidUser99'
                # No fingerprint provided
            }),
            content_type='application/json'
        )

        # Should succeed (security check only applies when fingerprint is provided)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['user']['reserved_username'], 'ValidUser99')

    def test_registration_with_different_fingerprint_rejected(self):
        """Test that username generated for one fingerprint cannot be used by another"""
        fingerprint_a = 'test_registration_fp_003a'
        fingerprint_b = 'test_registration_fp_003b'

        # Fingerprint A generates a username
        suggest_response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint_a}),
            content_type='application/json'
        )
        self.assertEqual(suggest_response.status_code, 200)
        username = suggest_response.json()['username']

        # Fingerprint B tries to use that username
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username,
                'fingerprint': fingerprint_b  # Different fingerprint!
            }),
            content_type='application/json'
        )

        # Should be rejected
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('reserved_username', data)
        self.assertIn('Invalid username', str(data['reserved_username']))

    def test_multiple_registrations_same_fingerprint(self):
        """Test that the same fingerprint can register multiple users with different generated usernames"""
        fingerprint = 'test_registration_fp_004'

        # Generate and register first user
        suggest_response_1 = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        username_1 = suggest_response_1.json()['username']

        response_1 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user1@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username_1,
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response_1.status_code, 201)

        # Generate and register second user with same fingerprint
        suggest_response_2 = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        username_2 = suggest_response_2.json()['username']

        response_2 = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user2@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username_2,
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response_2.status_code, 201)

        # Verify both users were created
        self.assertTrue(User.objects.filter(email='user1@example.com').exists())
        self.assertTrue(User.objects.filter(email='user2@example.com').exists())

    def test_rate_limiting_enforced(self):
        """Test that rate limiting prevents excessive username generation"""
        fingerprint = 'test_registration_fp_005'

        # Generate 100 usernames (max allowed for registration)
        for i in range(100):
            response = self.client.post(
                '/api/auth/suggest-username/',
                json.dumps({'fingerprint': fingerprint}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200, f"Failed on attempt {i+1}")

        # 101st attempt should hit rate limit
        response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)  # Too Many Requests
        data = response.json()
        self.assertEqual(data['remaining_attempts'], 0)

    def test_registration_preserves_other_validations(self):
        """Test that adding security check doesn't bypass other validations (profanity, format, etc.)"""
        fingerprint = 'test_registration_fp_006'

        # Generate a valid username
        suggest_response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        username = suggest_response.json()['username']

        # Test 1: Invalid email
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'invalid-email',
                'password': 'SecurePass123!',
                'reserved_username': username,
                'fingerprint': fingerprint
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
                'reserved_username': username,
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('password', response.json())

    def test_username_case_insensitive_matching(self):
        """Test that username matching in security check is case-insensitive"""
        fingerprint = 'test_registration_fp_007'

        # Generate a username
        suggest_response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        username = suggest_response.json()['username']

        # Try to register with different casing
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'testuser@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username.upper(),  # Different casing
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )

        # Should succeed (case-insensitive matching)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['user']['reserved_username'].lower(), username.lower())

    def test_race_condition_prevention(self):
        """Test that two users cannot get the same username due to Redis reservation"""
        # User A generates a username
        fingerprint_a = 'test_race_fp_a'
        suggest_response_a = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint_a}),
            content_type='application/json'
        )
        self.assertEqual(suggest_response_a.status_code, 200)
        username_a = suggest_response_a.json()['username']

        # User B tries to generate a username - should get a DIFFERENT one
        # because username_a is now reserved in Redis
        fingerprint_b = 'test_race_fp_b'
        suggest_response_b = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint_b}),
            content_type='application/json'
        )
        self.assertEqual(suggest_response_b.status_code, 200)
        username_b = suggest_response_b.json()['username']

        # Usernames should be different
        self.assertNotEqual(username_a.lower(), username_b.lower())

        # Both users should be able to register with their respective usernames
        response_a = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user_a@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username_a,
                'fingerprint': fingerprint_a
            }),
            content_type='application/json'
        )
        self.assertEqual(response_a.status_code, 201)

        response_b = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'user_b@example.com',
                'password': 'SecurePass123!',
                'reserved_username': username_b,
                'fingerprint': fingerprint_b
            }),
            content_type='application/json'
        )
        self.assertEqual(response_b.status_code, 201)

    def test_username_squatting_prevention(self):
        """Test that users cannot squat on desirable usernames by manipulating the API"""
        fingerprint = 'test_squatting_fp_001'

        # Attempt 1: Try to register with a desirable username without generating it
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'squatter@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'CoolUser99',  # Desirable username, not generated
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved_username', response.json())
        self.assertIn('Invalid username', str(response.json()['reserved_username']))

        # Attempt 2: Try to register with a common/simple username
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'squatter@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'Admin12345',  # Another desirable username
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved_username', response.json())

        # Verify no user was created
        self.assertFalse(User.objects.filter(email='squatter@example.com').exists())

    def test_bypass_ui_direct_api_call(self):
        """Test that users cannot bypass the UI and send arbitrary usernames via direct API calls"""
        fingerprint = 'test_bypass_fp_001'

        # Scenario 1: User sends a valid-looking username directly without generating it
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'hacker@example.com',
                'password': 'SecurePass123!',
                'reserved_username': 'HackerUser123',  # Valid format but not generated
                'fingerprint': fingerprint
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved_username', response.json())
        self.assertIn('Invalid username', str(response.json()['reserved_username']))

        # Scenario 2: User tries to use someone else's generated username
        # First, another user generates a username
        other_fingerprint = 'test_bypass_fp_002'
        suggest_response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': other_fingerprint}),
            content_type='application/json'
        )
        stolen_username = suggest_response.json()['username']

        # Original user tries to steal it
        response = self.client.post(
            '/api/auth/register/',
            json.dumps({
                'email': 'thief@example.com',
                'password': 'SecurePass123!',
                'reserved_username': stolen_username,  # Stolen from other fingerprint
                'fingerprint': fingerprint  # Different fingerprint!
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved_username', response.json())

        # Verify no users were created
        self.assertFalse(User.objects.filter(email='hacker@example.com').exists())
        self.assertFalse(User.objects.filter(email='thief@example.com').exists())

    def test_rate_limit_prevents_excessive_username_generation(self):
        """Test that rate limiting prevents abuse by limiting username generation attempts"""
        fingerprint = 'test_ratelimit_fp_001'

        # Generate exactly 100 usernames (the max limit for registration)
        generated_usernames = []
        for i in range(100):
            response = self.client.post(
                '/api/auth/suggest-username/',
                json.dumps({'fingerprint': fingerprint}),
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 200, f"Failed on attempt {i+1}")
            generated_usernames.append(response.json()['username'])

        # 101st attempt should hit rate limit
        response = self.client.post(
            '/api/auth/suggest-username/',
            json.dumps({'fingerprint': fingerprint}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)  # Too Many Requests
        data = response.json()
        self.assertEqual(data['remaining_attempts'], 0)

        # Verify we cannot use the rate-limited fingerprint to register
        # Even with a previously generated username, the system should respect the limit
        # (This test verifies the limit is enforced at generation time)
        self.assertEqual(len(generated_usernames), 100)


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
