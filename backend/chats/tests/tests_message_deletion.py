"""
Tests for message deletion feature.

Tests cover:
- Authorization (only host can delete messages)
- Soft delete (is_deleted flag, not physical deletion)
- Cache invalidation (Redis cache clearing)
- WebSocket broadcasting
- Edge cases (already deleted, non-existent message)
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock, AsyncMock
from chats.models import ChatRoom, Message, ChatParticipation
from chats.redis_cache import MessageCache
from chats.security import ChatSessionValidator
import json

User = get_user_model()


class MessageDeletionAuthorizationTests(TestCase):
    """Test authorization rules for message deletion"""

    def setUp(self):
        # Create users
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )
        self.participant_user = User.objects.create_user(
            email='participant@example.com',
            password='testpass123',
            reserved_username='ParticipantUser'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='testpass123',
            reserved_username='OtherUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            code='TEST123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        # Create participations
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser'
        )
        self.host_session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=str(self.host_user.id)
        )

        self.participant_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.participant_user,
            username='ParticipantUser'
        )
        self.participant_session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='ParticipantUser',
            user_id=str(self.participant_user.id)
        )

        # Create a test message from participant
        self.message = Message.objects.create(
            chat_room=self.chat_room,
            username='ParticipantUser',
            user=self.participant_user,
            content='Test message to delete',
            message_type='normal'
        )

        self.client = APIClient()

    def test_host_can_delete_message(self):
        """Test that chat host can delete any message"""
        self.client.force_authenticate(user=self.host_user)

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.host_session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

        # Verify message is soft-deleted
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_deleted)

    def test_participant_cannot_delete_message(self):
        """Test that non-host participant cannot delete messages"""
        self.client.force_authenticate(user=self.participant_user)

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.participant_session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify message is NOT deleted
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)

    def test_unauthenticated_user_cannot_delete_message(self):
        """Test that unauthenticated user cannot delete messages"""
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': 'fake-token'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify message is NOT deleted
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_deleted)

    def test_missing_session_token_rejected(self):
        """Test that request without session token is rejected"""
        self.client.force_authenticate(user=self.host_user)

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {}  # No session_token

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('session token', response.data['detail'].lower())

    def test_invalid_session_token_rejected(self):
        """Test that invalid session token is rejected"""
        self.client.force_authenticate(user=self.host_user)

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': 'invalid-token-12345'}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_from_different_chat_cannot_delete(self):
        """Test that host of different chat cannot delete messages"""
        # Create another chat with other_user as host
        other_chat = ChatRoom.objects.create(
            name='Other Chat',
            code='OTHER123',
            host=self.other_user,
            access_mode='public',
            is_active=True
        )

        other_participation = ChatParticipation.objects.create(
            chat_room=other_chat,
            user=self.other_user,
            username='OtherUser'
        )
        other_session_token = ChatSessionValidator.create_session_token(
            chat_code=other_chat.code,
            username='OtherUser',
            user_id=str(self.other_user.id)
        )

        self.client.force_authenticate(user=self.other_user)

        # Try to delete message from the original chat
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': other_session_token}

        response = self.client.post(url, data, format='json')

        # Should fail because session token is for wrong chat
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class MessageSoftDeletionTests(TestCase):
    """Test that messages are soft-deleted, not physically deleted"""

    def setUp(self):
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            code='TEST123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser'
        )
        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=str(self.host_user.id)
        )

        self.message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Message to soft delete',
            message_type='normal'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.host_user)

    def test_message_not_physically_deleted(self):
        """Test that message still exists in database after deletion"""
        message_id = self.message.id

        url = f'/api/chats/{self.chat_room.code}/messages/{message_id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Message should still exist in database
        self.assertTrue(Message.objects.filter(id=message_id).exists())

        # But should be marked as deleted
        deleted_message = Message.objects.get(id=message_id)
        self.assertTrue(deleted_message.is_deleted)

    def test_is_deleted_flag_set_to_true(self):
        """Test that is_deleted flag is set to True"""
        self.assertFalse(self.message.is_deleted)  # Initially False

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.message.refresh_from_db()
        self.assertTrue(self.message.is_deleted)

    def test_message_content_preserved_after_deletion(self):
        """Test that message content and metadata are preserved"""
        original_content = self.message.content
        original_username = self.message.username
        original_created_at = self.message.created_at

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.message.refresh_from_db()

        # All original data should be preserved
        self.assertEqual(self.message.content, original_content)
        self.assertEqual(self.message.username, original_username)
        self.assertEqual(self.message.created_at, original_created_at)
        self.assertTrue(self.message.is_deleted)

    def test_already_deleted_message_returns_success(self):
        """Test that deleting already-deleted message returns success"""
        # First deletion
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        response1 = self.client.post(url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Second deletion of same message
        response2 = self.client.post(url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertTrue(response2.data.get('already_deleted', False))

    def test_deleted_message_count_preserved(self):
        """Test that deleting messages doesn't reduce message count"""
        initial_count = Message.objects.filter(chat_room=self.chat_room).count()

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        self.client.post(url, data, format='json')

        final_count = Message.objects.filter(chat_room=self.chat_room).count()

        # Count should remain the same (soft delete)
        self.assertEqual(initial_count, final_count)


class MessageCacheInvalidationTests(TestCase):
    """Test that Redis cache is properly invalidated on deletion"""

    def setUp(self):
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            code='TEST123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser'
        )
        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=str(self.host_user.id)
        )

        self.message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Cached message',
            message_type='normal'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.host_user)

    @patch('chats.views.MessageCache.remove_message')
    def test_cache_remove_called_on_deletion(self, mock_remove_message):
        """Test that MessageCache.remove_message is called"""
        mock_remove_message.return_value = True

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify cache removal was called with correct parameters
        mock_remove_message.assert_called_once_with(
            self.chat_room.code,
            str(self.message.id)
        )

    def test_cache_invalidation_removes_message_from_messages_cache(self):
        """Test that message is removed from main messages cache"""
        # Add message to cache
        MessageCache.add_message(self.message)

        # Verify it's in cache
        cached_messages = MessageCache.get_messages(self.chat_room.code, limit=50)
        message_ids = [msg['id'] for msg in cached_messages]
        self.assertIn(str(self.message.id), message_ids)

        # Delete message
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        self.client.post(url, data, format='json')

        # Verify it's removed from cache
        cached_messages_after = MessageCache.get_messages(self.chat_room.code, limit=50)
        message_ids_after = [msg['id'] for msg in cached_messages_after]
        self.assertNotIn(str(self.message.id), message_ids_after)

    def test_cache_invalidation_removes_message_from_pinned_cache(self):
        """Test that pinned message is removed from pinned cache"""
        from django.utils import timezone
        from datetime import timedelta

        # Pin the message with pinned_until timestamp
        self.message.is_pinned = True
        self.message.pinned_until = timezone.now() + timedelta(hours=1)
        self.message.save()

        # Add to pinned cache
        MessageCache.add_pinned_message(self.message)

        # Verify it's in pinned cache
        pinned_messages = MessageCache.get_pinned_messages(self.chat_room.code)
        pinned_ids = [msg['id'] for msg in pinned_messages]
        self.assertIn(str(self.message.id), pinned_ids)

        # Delete message
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        self.client.post(url, data, format='json')

        # Verify it's removed from pinned cache
        pinned_messages_after = MessageCache.get_pinned_messages(self.chat_room.code)
        pinned_ids_after = [msg['id'] for msg in pinned_messages_after]
        self.assertNotIn(str(self.message.id), pinned_ids_after)

    def test_cache_invalidation_removes_reactions_cache(self):
        """Test that message reactions are removed from cache"""
        # Add message to cache
        MessageCache.add_message(self.message)

        # Add reactions to cache
        reactions = [
            {'emoji': '👍', 'count': 5},
            {'emoji': '❤️', 'count': 3}
        ]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message.id),
            reactions
        )

        # Verify reactions are in cache
        cached_reactions = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message.id)
        )
        self.assertEqual(len(cached_reactions), 2)

        # Delete message
        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        self.client.post(url, data, format='json')

        # Verify reactions cache is cleared
        cached_reactions_after = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message.id)
        )
        self.assertEqual(len(cached_reactions_after), 0)


class MessageDeletionWebSocketTests(TestCase):
    """Test WebSocket broadcasting for message deletion"""

    def setUp(self):
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            code='TEST123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser'
        )
        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=str(self.host_user.id)
        )

        self.message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Message with WebSocket',
            message_type='normal'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.host_user)

    @patch('channels.layers.get_channel_layer')
    def test_websocket_broadcast_called_on_deletion(self, mock_get_channel_layer):
        """Test that WebSocket broadcast is sent when message is deleted"""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify channel layer was used
        mock_get_channel_layer.assert_called_once()

        # Verify group_send was called with correct parameters
        mock_channel_layer.group_send.assert_called_once()
        call_args = mock_channel_layer.group_send.call_args

        # Check group name
        self.assertEqual(call_args[0][0], f'chat_{self.chat_room.code}')

        # Check message structure
        message_data = call_args[0][1]
        self.assertEqual(message_data['type'], 'message_deleted')
        self.assertEqual(message_data['message_id'], str(self.message.id))

    @patch('channels.layers.get_channel_layer')
    def test_websocket_message_includes_correct_message_id(self, mock_get_channel_layer):
        """Test that WebSocket message contains correct message ID"""
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        url = f'/api/chats/{self.chat_room.code}/messages/{self.message.id}/delete/'
        data = {'session_token': self.session_token}

        self.client.post(url, data, format='json')

        call_args = mock_channel_layer.group_send.call_args
        message_data = call_args[0][1]

        self.assertEqual(message_data['message_id'], str(self.message.id))


class MessageDeletionEdgeCasesTests(TestCase):
    """Test edge cases and error handling"""

    def setUp(self):
        self.host_user = User.objects.create_user(
            email='host@example.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            code='TEST123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host_user,
            username='HostUser'
        )
        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=str(self.host_user.id)
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.host_user)

    def test_delete_nonexistent_message_returns_404(self):
        """Test that deleting non-existent message returns 404"""
        fake_uuid = 'a' * 8 + '-' + 'b' * 4 + '-' + 'c' * 4 + '-' + 'd' * 4 + '-' + 'e' * 12

        url = f'/api/chats/{self.chat_room.code}/messages/{fake_uuid}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_message_from_wrong_chat_returns_404(self):
        """Test that message from different chat returns 404"""
        # Create another chat
        other_chat = ChatRoom.objects.create(
            name='Other Chat',
            code='OTHER123',
            host=self.host_user,
            access_mode='public',
            is_active=True
        )

        # Create message in OTHER chat
        other_message = Message.objects.create(
            chat_room=other_chat,
            username='HostUser',
            user=self.host_user,
            content='Message in other chat',
            message_type='normal'
        )

        # Try to delete it using TEST123 chat code
        url = f'/api/chats/{self.chat_room.code}/messages/{other_message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify message was NOT deleted
        other_message.refresh_from_db()
        self.assertFalse(other_message.is_deleted)

    def test_delete_from_inactive_chat_returns_404(self):
        """Test that deleting from inactive chat returns 404"""
        # Make chat inactive
        self.chat_room.is_active = False
        self.chat_room.save()

        message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Message in inactive chat',
            message_type='normal'
        )

        url = f'/api/chats/{self.chat_room.code}/messages/{message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_includes_message_id(self):
        """Test that successful response includes message ID"""
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Test message',
            message_type='normal'
        )

        url = f'/api/chats/{self.chat_room.code}/messages/{message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message_id'], str(message.id))
        self.assertTrue(response.data['success'])

    @patch('chats.views.MessageCache.remove_message')
    def test_deletion_succeeds_even_if_cache_removal_fails(self, mock_remove_message):
        """Test that message deletion succeeds even if cache removal fails"""
        # Make cache removal fail
        mock_remove_message.return_value = False

        message = Message.objects.create(
            chat_room=self.chat_room,
            username='HostUser',
            user=self.host_user,
            content='Test message',
            message_type='normal'
        )

        url = f'/api/chats/{self.chat_room.code}/messages/{message.id}/delete/'
        data = {'session_token': self.session_token}

        response = self.client.post(url, data, format='json')

        # Should still succeed (cache failure is not critical)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Message should still be deleted
        message.refresh_from_db()
        self.assertTrue(message.is_deleted)
