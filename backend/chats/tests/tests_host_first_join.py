"""
Tests for host-first join enforcement.

Users should not be able to access or join a chat until the host has joined first.
"""

import allure
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from chats.models import ChatRoom, ChatParticipation

User = get_user_model()


@allure.feature('Chat Access Control')
@allure.story('Host-First Join Enforcement')
class HostFirstJoinTests(TestCase):
    """Test host-first join enforcement"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create host user
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create another user (non-host)
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            reserved_username='OtherUser'
        )

        # Create a chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host_user,
            access_mode=ChatRoom.ACCESS_PUBLIC,
            voice_enabled=True
        )

    @allure.title("Non-host cannot get chat details before host joins")
    @allure.description("Non-host users should get 404 when trying to get chat details before host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_host_cannot_get_chat_details_before_host_joins(self):
        """Non-host users should get 404 when trying to get chat details before host joins"""
        # Authenticate as non-host user
        self.client.force_authenticate(user=self.other_user)

        # Try to get chat details
        response = self.client.get(f'/api/chats/HostUser/{self.chat_room.code}/')

        # Should return 404 (chat not found)
        self.assertEqual(response.status_code, 404)

    @allure.title("Non-host cannot join before host joins")
    @allure.description("Non-host users should get 404 when trying to join before host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_host_cannot_join_before_host_joins(self):
        """Non-host users should get 404 when trying to join before host joins"""
        # Authenticate as non-host user
        self.client.force_authenticate(user=self.other_user)

        # Try to join chat
        response = self.client.post(f'/api/chats/HostUser/{self.chat_room.code}/join/', {
            'username': 'TestUser',
            'fingerprint': 'test-fingerprint-123'
        })

        # Should return 404 (chat not found)
        self.assertEqual(response.status_code, 404)

    @allure.title("Anonymous user cannot get chat details before host joins")
    @allure.description("Anonymous users should get 404 when trying to get chat details before host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_user_cannot_get_chat_details_before_host_joins(self):
        """Anonymous users should get 404 when trying to get chat details before host joins"""
        # No authentication (anonymous user)

        # Try to get chat details
        response = self.client.get(f'/api/chats/HostUser/{self.chat_room.code}/')

        # Should return 404 (chat not found)
        self.assertEqual(response.status_code, 404)

    @allure.title("Anonymous user cannot join before host joins")
    @allure.description("Anonymous users should get 404 when trying to join before host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_user_cannot_join_before_host_joins(self):
        """Anonymous users should get 404 when trying to join before host joins"""
        # No authentication (anonymous user)

        # Try to join chat
        response = self.client.post(f'/api/chats/HostUser/{self.chat_room.code}/join/', {
            'username': 'AnonymousUser',
            'fingerprint': 'test-fingerprint-456'
        })

        # Should return 404 (chat not found)
        self.assertEqual(response.status_code, 404)

    @allure.title("Host can get chat details before joining")
    @allure.description("Host should be able to get chat details even before joining")
    @allure.severity(allure.severity_level.NORMAL)
    def test_host_can_get_chat_details_before_joining(self):
        """Host should be able to get chat details even before joining"""
        # Authenticate as host
        self.client.force_authenticate(user=self.host_user)

        # Try to get chat details
        response = self.client.get(f'/api/chats/HostUser/{self.chat_room.code}/')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], self.chat_room.code)

    @allure.title("Host can join first")
    @allure.description("Host should be able to join their own chat")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_host_can_join_first(self):
        """Host should be able to join their own chat"""
        # Authenticate as host
        self.client.force_authenticate(user=self.host_user)

        # Join chat
        response = self.client.post(f'/api/chats/HostUser/{self.chat_room.code}/join/', {
            'username': 'HostUser',
            'fingerprint': 'host-fingerprint'
        }, format='json')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertIn('session_token', response.data)
        self.assertEqual(response.data['username'], 'HostUser')

        # Verify ChatParticipation was created
        participation = ChatParticipation.objects.filter(
            chat_room=self.chat_room,
            user=self.host_user
        ).first()
        self.assertIsNotNone(participation)
        self.assertEqual(participation.username, 'HostUser')

    @allure.title("Non-host can get chat details after host joins")
    @allure.description("Non-host users should be able to get chat details after host joins")
    @allure.severity(allure.severity_level.NORMAL)
    def test_non_host_can_get_chat_details_after_host_joins(self):
        """Non-host users should be able to get chat details after host joins"""
        # Host joins first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host-fingerprint'
        )

        # Authenticate as non-host user
        self.client.force_authenticate(user=self.other_user)

        # Try to get chat details
        response = self.client.get(f'/api/chats/HostUser/{self.chat_room.code}/')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], self.chat_room.code)

    @allure.title("Non-host can join after host joins")
    @allure.description("Non-host users should be able to join after host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_non_host_can_join_after_host_joins(self):
        """Non-host users should be able to join after host joins"""
        # Host joins first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host-fingerprint'
        )

        # Authenticate as non-host user
        self.client.force_authenticate(user=self.other_user)

        # Try to join chat
        response = self.client.post(f'/api/chats/HostUser/{self.chat_room.code}/join/', {
            'username': 'OtherUser',
            'fingerprint': 'other-fingerprint'
        }, format='json')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertIn('session_token', response.data)
        self.assertEqual(response.data['username'], 'OtherUser')

        # Verify ChatParticipation was created
        participation = ChatParticipation.objects.filter(
            chat_room=self.chat_room,
            user=self.other_user
        ).first()
        self.assertIsNotNone(participation)
        self.assertEqual(participation.username, 'OtherUser')

    @allure.title("Anonymous user can get chat details after host joins")
    @allure.description("Anonymous users should be able to get chat details after host joins")
    @allure.severity(allure.severity_level.NORMAL)
    def test_anonymous_user_can_get_chat_details_after_host_joins(self):
        """Anonymous users should be able to get chat details after host joins"""
        # Host joins first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host-fingerprint'
        )

        # No authentication (anonymous user)

        # Try to get chat details
        response = self.client.get(f'/api/chats/HostUser/{self.chat_room.code}/')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['code'], self.chat_room.code)

    @allure.title("Anonymous user can join after host joins")
    @allure.description("Anonymous users should be able to join after host joins")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_user_can_join_after_host_joins(self):
        """Anonymous users should be able to join after host joins"""
        # Host joins first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser',
            fingerprint='host-fingerprint'
        )

        # Create a dummy username generation record for anonymous user
        # This is required for anonymous users to join (see SECURITY CHECK 0 in views.py)
        from django.core.cache import cache
        test_fingerprint = 'anonymous-fingerprint'
        test_username = 'AnonymousUser'
        generated_key = f"username:generated_for_fingerprint:{test_fingerprint}"
        cache.set(generated_key, {test_username}, 3600)

        # No authentication (anonymous user)

        # Try to join chat
        response = self.client.post(f'/api/chats/HostUser/{self.chat_room.code}/join/', {
            'username': test_username,
            'fingerprint': test_fingerprint
        }, format='json')

        # Should succeed
        self.assertEqual(response.status_code, 200)
        self.assertIn('session_token', response.data)
        self.assertEqual(response.data['username'], test_username)

        # Verify ChatParticipation was created
        participation = ChatParticipation.objects.filter(
            chat_room=self.chat_room,
            fingerprint=test_fingerprint,
            user__isnull=True
        ).first()
        self.assertIsNotNone(participation)
        self.assertEqual(participation.username, test_username)
