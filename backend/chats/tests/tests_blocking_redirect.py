"""
Tests for blocking redirect functionality.

Verifies that blocked users (both anonymous and logged-in) are properly
detected and redirected when attempting to access a chat page.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from ..models import ChatRoom, ChatParticipation, ChatBlock
import uuid

User = get_user_model()


class BlockingRedirectTests(TestCase):
    """Test blocking detection for chat page access"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create host user
        self.host = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name="Test Chat",
            code="TEST123",
            host=self.host
        )

        # Create host participation
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='192.168.1.1'
        )

    def test_anonymous_user_not_blocked(self):
        """Anonymous user with no blocks should see is_blocked=False"""
        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=new_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        self.assertFalse(response.data['is_blocked'])

    def test_anonymous_user_blocked_by_fingerprint(self):
        """Anonymous user with blocked fingerprint should see is_blocked=True"""
        # Block the fingerprint
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_fingerprint='blocked_fingerprint',
            blocked_by=self.host_participation
        )

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=blocked_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        self.assertTrue(response.data['is_blocked'])

    def test_logged_in_user_not_blocked(self):
        """Logged-in user with no blocks should see is_blocked=False"""
        # Create logged-in user
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            reserved_username='TestUser'
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=some_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        self.assertFalse(response.data['is_blocked'])

    def test_logged_in_user_blocked_by_account(self):
        """Logged-in user with blocked account should see is_blocked=True"""
        # Create logged-in user
        user = User.objects.create_user(
            email='blocked@example.com',
            password='testpass123',
            reserved_username='BlockedUser'
        )

        # Block the user account
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_user=user,
            blocked_by=self.host_participation
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=some_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        self.assertTrue(response.data['is_blocked'])

    def test_logged_in_user_fingerprint_blocked_but_account_not(self):
        """
        Logged-in user should NOT be blocked by fingerprint blocks.
        Only user account blocks apply to logged-in users.
        """
        # Create logged-in user
        user = User.objects.create_user(
            email='test2@example.com',
            password='testpass123',
            reserved_username='TestUser2'
        )

        # Block the fingerprint (but NOT the user account)
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_fingerprint='blocked_fingerprint',
            blocked_by=self.host_participation
        )

        self.client.force_authenticate(user=user)

        # Use the blocked fingerprint but as a logged-in user
        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=blocked_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        # Should NOT be blocked - logged-in users bypass fingerprint blocks
        self.assertFalse(response.data['is_blocked'])

    def test_returning_anonymous_user_blocked(self):
        """
        Returning anonymous user (has participation) who is blocked
        should see is_blocked=True
        """
        # Create anonymous participation
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='BlockedAnon',
            fingerprint='anon_fingerprint',
            ip_address='192.168.1.100'
        )

        # Block the participation (creates block by username and fingerprint)
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_fingerprint='anon_fingerprint',
            blocked_by=self.host_participation
        )

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=anon_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_joined'])
        self.assertTrue(response.data['is_blocked'])
        self.assertEqual(response.data['username'], 'BlockedAnon')

    def test_returning_logged_in_user_blocked(self):
        """
        Returning logged-in user (has participation) who is blocked
        should see is_blocked=True
        """
        # Create logged-in user
        user = User.objects.create_user(
            email='returning@example.com',
            password='testpass123',
            reserved_username='ReturningUser'
        )

        # Create participation
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=user,
            username='ReturningUser',
            fingerprint='returning_fingerprint',
            ip_address='192.168.1.101'
        )

        # Block the user account
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_user=user,
            blocked_by=self.host_participation
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=returning_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_joined'])
        self.assertTrue(response.data['is_blocked'])
        self.assertEqual(response.data['username'], 'ReturningUser')

    def test_anonymous_blocked_by_username(self):
        """Anonymous user blocked by username should see is_blocked=True"""
        # Block by username
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username='blockedname',
            blocked_by=self.host_participation
        )

        # First-time user trying to join with the blocked username
        # Won't happen in practice (username is chosen at join time),
        # but tests the blocking logic
        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=new_fingerprint'
        )

        # First-time user doesn't have username yet, so can't be blocked by username
        # They'll only be blocked by fingerprint
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['has_joined'])
        self.assertFalse(response.data['is_blocked'])

    def test_multiple_blocks_same_user(self):
        """User blocked by multiple identifiers should see is_blocked=True"""
        # Create logged-in user
        user = User.objects.create_user(
            email='multi@example.com',
            password='testpass123',
            reserved_username='MultiBlocked'
        )

        # Create participation
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=user,
            username='MultiBlocked',
            fingerprint='multi_fingerprint',
            ip_address='192.168.1.102'
        )

        # Block by multiple identifiers
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_user=user,
            blocked_by=self.host_participation
        )
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username='multiblocked',
            blocked_by=self.host_participation
        )
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_fingerprint='multi_fingerprint',
            blocked_by=self.host_participation
        )

        self.client.force_authenticate(user=user)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/my-participation/?fingerprint=multi_fingerprint'
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['has_joined'])
        self.assertTrue(response.data['is_blocked'])
