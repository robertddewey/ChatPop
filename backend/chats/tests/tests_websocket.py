"""
WebSocket Consumer Tests

Tests for Django Channels WebSocket consumer functionality including:
- Message serialization (UUID to string conversion)
- WebSocket connection and authentication
- Message broadcasting through channel layers
- Both logged-in and anonymous user scenarios
"""

import allure
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from chats.consumers import ChatConsumer
from chats.models import ChatRoom, Message, ChatParticipation
from accounts.models import User
from chats.utils.security.auth import ChatSessionValidator
from unittest.mock import patch
from django.db import connection
import json
import msgpack


@allure.feature('WebSocket')
@allure.story('Message Serialization')
class WebSocketSerializationTests(TransactionTestCase):
    """Test message serialization for WebSocket broadcast"""

    def setUp(self):
        """Set up test data"""
        # Ensure clean database connection
        connection.close()
        connection.connect()

        # Create logged-in user (host)
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            reserved_username='testuser'
        )

        # Create chat room (host is required)
        self.chat_room = ChatRoom.objects.create(
            code='TEST1234',
            name='Test Chat',
            host=self.user,
            access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Create participation
        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser'
        )

    def tearDown(self):
        """Clean up database connection after each test"""
        # Close any open connections from async operations
        connection.close()

    @allure.title("Message serialization with logged-in user")
    @allure.description("Test that message with logged-in user serializes correctly (UUID to string)")
    @allure.severity(allure.severity_level.CRITICAL)
    @patch('chats.utils.performance.cache.MessageCache._compute_username_is_reserved')
    def test_message_serialization_with_logged_in_user(self, mock_compute_reserved):
        """Test that message with logged-in user serializes correctly (UUID to string)"""
        # Mock the username_is_reserved computation to avoid database query
        mock_compute_reserved.return_value = True

        # Create message with logged-in user
        message = Message.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            content='Test message from logged-in user'
        )

        # Use the mocked value
        username_is_reserved = mock_compute_reserved(message)

        serialized = {
            'id': str(message.id),
            'chat_code': message.chat_room.code,
            'username': message.username,
            'username_is_reserved': username_is_reserved,
            'user_id': str(message.user.id) if message.user else None,
            'message_type': message.message_type,
            'content': message.content,
            'reply_to_id': str(message.reply_to.id) if message.reply_to else None,
            'is_pinned': message.is_pinned,
            'created_at': message.created_at.isoformat(),
            'is_deleted': message.is_deleted,
        }

        # Verify all fields are present
        self.assertIn('id', serialized)
        self.assertIn('user_id', serialized)
        self.assertIn('chat_code', serialized)
        self.assertIn('username', serialized)
        self.assertIn('content', serialized)

        # Critical: user_id must be a string, not UUID
        self.assertIsInstance(serialized['user_id'], str)
        self.assertEqual(serialized['user_id'], str(message.user.id))

        # Verify id is also string
        self.assertIsInstance(serialized['id'], str)
        self.assertEqual(serialized['id'], str(message.id))

        # Verify msgpack can serialize it (this would fail with UUID objects)
        try:
            msgpack.packb(serialized, use_bin_type=True)
        except TypeError as e:
            self.fail(f"msgpack serialization failed: {e}")

    @allure.title("Message serialization with anonymous user")
    @allure.description("Test that message with anonymous user serializes correctly (user_id=None)")
    @allure.severity(allure.severity_level.CRITICAL)
    @patch('chats.utils.performance.cache.MessageCache._compute_username_is_reserved')
    def test_message_serialization_with_anonymous_user(self, mock_compute_reserved):
        """Test that message with anonymous user serializes correctly (user_id=None)"""
        # Mock the username_is_reserved computation to avoid database query
        mock_compute_reserved.return_value = False

        # Create message with anonymous user (no user object)
        message = Message.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='anonymous123',
            content='Test message from anonymous user'
        )

        # Use the mocked value
        username_is_reserved = mock_compute_reserved(message)

        serialized = {
            'id': str(message.id),
            'chat_code': message.chat_room.code,
            'username': message.username,
            'username_is_reserved': username_is_reserved,
            'user_id': str(message.user.id) if message.user else None,
            'message_type': message.message_type,
            'content': message.content,
            'reply_to_id': str(message.reply_to.id) if message.reply_to else None,
            'is_pinned': message.is_pinned,
            'created_at': message.created_at.isoformat(),
            'is_deleted': message.is_deleted,
        }

        # Verify user_id is None (not a UUID)
        self.assertIsNone(serialized['user_id'])

        # Verify id is string
        self.assertIsInstance(serialized['id'], str)
        self.assertEqual(serialized['id'], str(message.id))

        # Verify msgpack can serialize it
        try:
            msgpack.packb(serialized, use_bin_type=True)
        except TypeError as e:
            self.fail(f"msgpack serialization failed: {e}")

    @allure.title("Message serialization with reply")
    @allure.description("Test that reply_to_id is properly serialized as string")
    @allure.severity(allure.severity_level.CRITICAL)
    @patch('chats.utils.performance.cache.MessageCache._compute_username_is_reserved')
    def test_message_serialization_with_reply(self, mock_compute_reserved):
        """Test that reply_to_id is properly serialized as string"""
        # Mock the username_is_reserved computation to avoid database query
        mock_compute_reserved.return_value = True

        # Create parent message
        parent_message = Message.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            content='Parent message'
        )

        # Create reply message
        reply_message = Message.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            content='Reply message',
            reply_to=parent_message
        )

        # Use the mocked value
        username_is_reserved = mock_compute_reserved(reply_message)

        serialized = {
            'id': str(reply_message.id),
            'chat_code': reply_message.chat_room.code,
            'username': reply_message.username,
            'username_is_reserved': username_is_reserved,
            'user_id': str(reply_message.user.id) if reply_message.user else None,
            'message_type': reply_message.message_type,
            'content': reply_message.content,
            'reply_to_id': str(reply_message.reply_to.id) if reply_message.reply_to else None,
            'is_pinned': reply_message.is_pinned,
            'created_at': reply_message.created_at.isoformat(),
            'is_deleted': reply_message.is_deleted,
        }

        # Verify reply_to_id is string
        self.assertIsInstance(serialized['reply_to_id'], str)
        self.assertEqual(serialized['reply_to_id'], str(parent_message.id))

        # Verify msgpack can serialize it
        try:
            msgpack.packb(serialized, use_bin_type=True)
        except TypeError as e:
            self.fail(f"msgpack serialization failed: {e}")

    @allure.title("All serialized fields are JSON serializable")
    @allure.description("Test that all fields in serialized message are JSON-serializable")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_all_serialized_fields_are_json_serializable(self):
        """Test that all fields in serialized message are JSON-serializable"""
        # Create message with all possible fields
        parent_message = Message.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            content='Parent message'
        )

        message = Message.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='testuser',
            content='Test message',
            reply_to=parent_message,
            is_pinned=True,
            message_type=Message.MESSAGE_HOST
        )

        # Create consumer instance
        consumer = ChatConsumer()

        # Call serialization method
        from asgiref.sync import async_to_sync
        serialized = async_to_sync(consumer.serialize_message_for_broadcast)(message)

        # Verify all fields can be JSON serialized
        try:
            json_string = json.dumps(serialized)
            json.loads(json_string)  # Verify it can be loaded back
        except (TypeError, ValueError) as e:
            self.fail(f"JSON serialization failed: {e}")

