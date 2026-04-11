"""
Tests for the broadcast sticky system.

The broadcast sticky allows the host to pin ONE message to the top sticky slot,
independent of the highlight system.
"""
from django.test import TestCase, Client
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework import status
from ..models import ChatRoom, Message, ChatParticipation, ChatBlock
from ..utils.security.auth import ChatSessionValidator

User = get_user_model()


class BroadcastStickyTests(TestCase):
    """Test suite for broadcast sticky functionality."""

    def setUp(self):
        cache.clear()
        self.client = Client()

        # Create host
        self.host = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='hostuser'
        )

        # Create regular user
        self.regular_user = User.objects.create_user(
            email='regular@example.com',
            password='testpass123',
            reserved_username='regularuser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )
        self.code = self.chat_room.code

        # Host joins
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='hostuser',
            fingerprint='host_fp'
        )

        # Regular user joins
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.regular_user,
            username='regularuser',
            fingerprint='regular_fp'
        )

        # Create messages
        self.host_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='hostuser',
            user=self.host,
            content='Host message',
            is_from_host=True,
        )
        self.regular_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='regularuser',
            user=self.regular_user,
            content='Regular message',
        )
        self.regular_msg2 = Message.objects.create(
            chat_room=self.chat_room,
            username='regularuser',
            user=self.regular_user,
            content='Another regular message',
        )

        # Generate session tokens
        self.host_token = ChatSessionValidator.create_session_token(
            chat_code=self.code,
            username='hostuser',
            user_id=str(self.host.id),
            fingerprint='host_fp',
        )
        self.regular_token = ChatSessionValidator.create_session_token(
            chat_code=self.code,
            username='regularuser',
            user_id=str(self.regular_user.id),
            fingerprint='regular_fp',
        )

    def _broadcast_url(self, message_id):
        return f'/api/chats/hostuser/{self.code}/messages/{message_id}/broadcast-sticky/'

    def test_host_can_broadcast_message(self):
        """Host can set a broadcast sticky."""
        resp = self.client.post(
            self._broadcast_url(self.regular_msg.id),
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['action'], 'broadcast')
        self.assertEqual(resp.json()['message_id'], str(self.regular_msg.id))

        self.chat_room.refresh_from_db()
        self.assertEqual(self.chat_room.broadcast_message_id, self.regular_msg.id)

    def test_host_can_unbroadcast_message(self):
        """Host can clear a broadcast sticky by toggling the same message."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        resp = self.client.post(
            self._broadcast_url(self.regular_msg.id),
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['action'], 'unbroadcast')

        self.chat_room.refresh_from_db()
        self.assertIsNone(self.chat_room.broadcast_message_id)

    def test_broadcast_replaces_existing(self):
        """Broadcasting a new message replaces the old broadcast."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        resp = self.client.post(
            self._broadcast_url(self.regular_msg2.id),
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['action'], 'broadcast')

        self.chat_room.refresh_from_db()
        self.assertEqual(self.chat_room.broadcast_message_id, self.regular_msg2.id)

    def test_non_host_cannot_broadcast(self):
        """Regular user cannot toggle broadcast sticky."""
        resp = self.client.post(
            self._broadcast_url(self.regular_msg.id),
            {'session_token': self.regular_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_messages_api_returns_broadcast_message(self):
        """The messages API returns the broadcast_message field."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        resp = self.client.get(
            f'/api/chats/hostuser/{self.code}/messages/',
            {'session_token': self.host_token},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn('broadcast_message', data)
        self.assertIsNotNone(data['broadcast_message'])
        self.assertEqual(data['broadcast_message']['id'], str(self.regular_msg.id))

    def test_messages_api_returns_null_when_no_broadcast(self):
        """The messages API returns null broadcast_message when none set."""
        resp = self.client.get(
            f'/api/chats/hostuser/{self.code}/messages/',
            {'session_token': self.host_token},
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertIn('broadcast_message', data)
        self.assertIsNone(data['broadcast_message'])

    def test_highlight_does_not_affect_sticky(self):
        """Highlighting a message does NOT change the broadcast sticky."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        # Highlight a different message
        resp = self.client.post(
            f'/api/chats/hostuser/{self.code}/messages/{self.regular_msg2.id}/highlight/',
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Broadcast should be unchanged
        self.chat_room.refresh_from_db()
        self.assertEqual(self.chat_room.broadcast_message_id, self.regular_msg.id)

    def test_delete_cascade_clears_broadcast(self):
        """Deleting the broadcast message clears the broadcast."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        # Host deletes the broadcast message
        self.client.force_login(self.host)
        resp = self.client.post(
            f'/api/chats/hostuser/{self.code}/messages/{self.regular_msg.id}/delete/',
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.chat_room.refresh_from_db()
        self.assertIsNone(self.chat_room.broadcast_message_id)

    def test_ban_cascade_clears_broadcast(self):
        """Banning a user whose message is broadcast clears the broadcast."""
        self.chat_room.broadcast_message = self.regular_msg
        self.chat_room.save(update_fields=['broadcast_message'])

        # Host bans the regular user
        self.client.force_login(self.host)
        resp = self.client.post(
            f'/api/chats/hostuser/{self.code}/block-user/',
            {
                'session_token': self.host_token,
                'username': 'regularuser',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.chat_room.refresh_from_db()
        self.assertIsNone(self.chat_room.broadcast_message_id)

    def test_session_token_required(self):
        """Broadcast endpoint requires session token."""
        resp = self.client.post(
            self._broadcast_url(self.regular_msg.id),
            {},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_deleted_message_cannot_be_broadcast(self):
        """Cannot broadcast a deleted message."""
        self.regular_msg.is_deleted = True
        self.regular_msg.save(update_fields=['is_deleted'])

        resp = self.client.post(
            self._broadcast_url(self.regular_msg.id),
            {'session_token': self.host_token},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
