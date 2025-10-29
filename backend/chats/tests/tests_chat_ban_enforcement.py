"""
Tests for ChatBlock (host ban) enforcement across WebSocket and HTTP API.

This test suite ensures that banned users cannot bypass the ban through any method:
- WebSocket connection attempts
- WebSocket message sending
- HTTP API message sending

Security Requirements:
1. Banned users MUST NOT be able to connect via WebSocket
2. Banned users MUST NOT be able to send messages via WebSocket (backup check)
3. Banned users MUST NOT be able to send messages via HTTP API (bypass prevention)
4. Ban enforcement MUST work for username, fingerprint, and user_id
5. Username matching MUST be case-insensitive
"""

from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from rest_framework import status

from chats.models import ChatRoom, ChatBlock, Message

User = get_user_model()


class ChatBanEnforcementHTTPTests(TestCase):
    """
    Test ChatBlock enforcement in HTTP API endpoints.

    These tests ensure banned users cannot send messages via direct HTTP API calls.
    """

    def setUp(self):
        """Create test users, chat room"""
        self.client = Client()

        # Create host user
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create regular user
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='RegularUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )

    def _suggest_username(self, fingerprint):
        """Helper method to get a generated username for a fingerprint"""
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/suggest-username/',
            {'fingerprint': fingerprint},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()['username']

    def _join_chat_and_get_token(self, username, fingerprint=None):
        """Helper method to join chat and get session token"""
        data = {'username': username}
        if fingerprint:
            data['fingerprint'] = fingerprint

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            data=data,
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()['session_token']

    def _create_ban(self, blocked_username=None, blocked_fingerprint=None, blocked_user_id=None):
        """Helper method to create a chat ban"""
        from chats.models import ChatParticipation

        # Get or create host participation
        host_participation = ChatParticipation.objects.get_or_create(
            chat_room=self.chat_room,
            user=self.host,
            defaults={'username': 'HostUser'}
        )[0]

        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=blocked_username,
            blocked_fingerprint=blocked_fingerprint,
            blocked_user_id=blocked_user_id,
            blocked_by=host_participation
        )

    def test_banned_username_cannot_send_message_http(self):
        """Test that user banned by username cannot send message via HTTP API"""
        # Use a valid, non-reserved username (no fingerprint = manually entered username)
        test_username = 'TestUser123'

        # User joins chat (no fingerprint allows manually-entered username)
        token = self._join_chat_and_get_token(test_username)

        # Ban user by username
        self._create_ban(blocked_username=test_username)

        # Attempt to send message via HTTP API
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': test_username,
                'content': 'This should be blocked',
                'session_token': token
            },
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('banned', response.json().get('detail', '').lower())

        # Verify message was not saved
        self.assertEqual(
            Message.objects.filter(
                chat_room=self.chat_room,
                username=test_username
            ).count(),
            0
        )

    def test_banned_username_case_insensitive_http(self):
        """Test that username ban is case-insensitive for HTTP API"""
        # Use a valid, non-reserved username (no fingerprint = manually entered username)
        test_username = 'TestUser456'

        # User joins chat (no fingerprint allows manually-entered username)
        token = self._join_chat_and_get_token(test_username)

        # Ban user with lowercase username
        self._create_ban(blocked_username=test_username.lower())  # lowercase

        # Attempt to send message with different case
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': test_username,  # original case
                'content': 'This should be blocked',
                'session_token': token
            },
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('banned', response.json().get('detail', '').lower())

    def test_banned_fingerprint_cannot_send_message_http(self):
        """Test that user banned by fingerprint cannot send message via HTTP API"""
        # Get a generated username for the fingerprint
        fingerprint = 'anon-fingerprint-test'
        username = self._suggest_username(fingerprint)

        # Anonymous user joins chat with generated username
        token = self._join_chat_and_get_token(username, fingerprint)

        # Ban anonymous user by fingerprint
        self._create_ban(blocked_fingerprint=fingerprint)

        # Attempt to send message via HTTP API
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': username,  # Use generated username
                'content': 'This should be blocked',
                'session_token': token
            },
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('banned', response.json().get('detail', '').lower())

    def test_banned_user_id_cannot_send_message_http(self):
        """Test that user banned by user_id cannot send message via HTTP API"""
        # Registered user joins chat
        self.client.force_login(self.user)
        token = self._join_chat_and_get_token('RegularUser')

        # Ban user by user_id
        from chats.models import ChatParticipation
        host_participation = ChatParticipation.objects.get_or_create(
            chat_room=self.chat_room,
            user=self.host,
            defaults={'username': 'HostUser'}
        )[0]

        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_user_id=self.user.id,
            blocked_by=host_participation
        )

        # Attempt to send message via HTTP API
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': 'RegularUser',
                'content': 'This should be blocked',
                'session_token': token
            },
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('banned', response.json().get('detail', '').lower())

    def test_non_banned_user_can_send_message_http(self):
        """Test that non-banned users can still send messages via HTTP API"""
        # Use a valid, non-reserved username (no fingerprint = manually entered username)
        test_username = 'ValidUser789'

        # User joins chat (no fingerprint allows manually-entered username)
        token = self._join_chat_and_get_token(test_username)

        # Do not create any ban

        # Send message via HTTP API
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': test_username,
                'content': 'This should work',
                'session_token': token
            },
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify message was saved
        self.assertEqual(
            Message.objects.filter(
                chat_room=self.chat_room,
                username=test_username,
                content='This should work'
            ).count(),
            1
        )

    def test_host_can_send_message_after_banning_user(self):
        """Test that host can still send messages after banning a user"""
        # Host joins chat
        self.client.force_login(self.host)
        host_token = self._join_chat_and_get_token('HostUser')

        # Ban regular user
        from chats.models import ChatParticipation
        host_participation = ChatParticipation.objects.get_or_create(
            chat_room=self.chat_room,
            user=self.host,
            defaults={'username': 'HostUser'}
        )[0]

        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username='RegularUser',
            blocked_by=host_participation
        )

        # Host sends message
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': 'HostUser',
                'content': 'Host message',
                'session_token': host_token
            },
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_ban_only_affects_specific_chat(self):
        """Test that ChatBlock only affects the specific chat room"""
        # Use a valid, non-reserved username (no fingerprint = manually entered username)
        test_username = 'MultiChat999'

        # Create second chat room
        chat_room2 = ChatRoom.objects.create(
            name='Test Chat 2',
            host=self.host,
            access_mode='public'
        )

        # User joins both chats (no fingerprint allows manually-entered username)
        token1 = self._join_chat_and_get_token(test_username)

        # Join second chat
        token2_response = self.client.post(
            f'/api/chats/HostUser/{chat_room2.code}/join/',
            {'username': test_username},
            content_type='application/json'
        )
        token2 = token2_response.json()['session_token']

        # Ban user from first chat only
        from chats.models import ChatParticipation
        host_participation = ChatParticipation.objects.get_or_create(
            chat_room=self.chat_room,
            user=self.host,
            defaults={'username': 'HostUser'}
        )[0]

        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=test_username,
            blocked_by=host_participation
        )

        # Attempt to send message in first chat (should fail)
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': test_username,
                'content': 'Chat 1 message',
                'session_token': token1
            },
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_403_FORBIDDEN)

        # Attempt to send message in second chat (should succeed)
        response2 = self.client.post(
            f'/api/chats/HostUser/{chat_room2.code}/messages/send/',
            {
                'username': test_username,
                'content': 'Chat 2 message',
                'session_token': token2
            },
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


class ChatBanEnforcementWebSocketTests(TransactionTestCase):
    """
    Test ChatBlock enforcement in WebSocket connections.

    These tests ensure banned users cannot connect via WebSocket.
    Uses TransactionTestCase to support async operations.
    """

    def setUp(self):
        """Create test users and chat room"""
        from channels.db import database_sync_to_async

        # Create host user
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create regular user
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='RegularUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )

    def _create_session_token(self, username, fingerprint=None, user_id=None):
        """Helper to create a session token (sync - not using DB)"""
        from chats.utils.security.auth import ChatSessionValidator
        return ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username=username,
            user_id=user_id,
            fingerprint=fingerprint
        )

    async def _create_ban_async(self, blocked_username=None, blocked_fingerprint=None, blocked_user_id=None):
        """Helper method to create a chat ban (async-safe)"""
        from chats.models import ChatParticipation
        from channels.db import database_sync_to_async

        # Get or create host participation (wrapped in sync_to_async)
        @database_sync_to_async
        def get_host_participation():
            return ChatParticipation.objects.get_or_create(
                chat_room=self.chat_room,
                user=self.host,
                defaults={'username': 'HostUser'}
            )[0]

        host_participation = await get_host_participation()

        # Create ban (wrapped in sync_to_async)
        @database_sync_to_async
        def create_ban():
            return ChatBlock.objects.create(
                chat_room=self.chat_room,
                blocked_username=blocked_username,
                blocked_fingerprint=blocked_fingerprint,
                blocked_user_id=blocked_user_id,
                blocked_by=host_participation
            )

        await create_ban()

    async def test_banned_username_cannot_connect_websocket(self):
        """Test that user banned by username cannot connect via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application

        # Ban user by username
        await self._create_ban_async(blocked_username='testuser123')

        # Create session token for banned user
        token = self._create_session_token('TestUser123')

        # Attempt to connect via WebSocket
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )

        connected, subprotocol = await communicator.connect()

        # Should be rejected (connection refused)
        self.assertFalse(connected, "Banned user should not be able to connect")

        await communicator.disconnect()

    async def test_banned_fingerprint_cannot_connect_websocket(self):
        """Test that user banned by fingerprint cannot connect via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application

        fingerprint = 'banned-fingerprint'

        # Ban user by fingerprint
        await self._create_ban_async(blocked_fingerprint=fingerprint)

        # Create session token with fingerprint
        token = self._create_session_token('AnonUser', fingerprint=fingerprint)

        # Attempt to connect via WebSocket
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )

        connected, subprotocol = await communicator.connect()

        # Should be rejected
        self.assertFalse(connected, "Fingerprint-banned user should not be able to connect")

        await communicator.disconnect()

    async def test_banned_user_id_cannot_connect_websocket(self):
        """Test that user banned by user_id cannot connect via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application

        # Ban user by user_id
        await self._create_ban_async(blocked_user_id=self.user.id)

        # Create session token for banned user
        token = self._create_session_token('RegularUser', user_id=self.user.id)

        # Attempt to connect via WebSocket
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )

        connected, subprotocol = await communicator.connect()

        # Should be rejected
        self.assertFalse(connected, "User ID-banned user should not be able to connect")

        await communicator.disconnect()

    async def test_banned_username_case_insensitive_websocket(self):
        """Test that username ban is case-insensitive for WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application

        # Ban user with lowercase username
        await self._create_ban_async(blocked_username='testuser456')

        # Try to connect with different case
        token = self._create_session_token('TestUser456')

        # Attempt to connect via WebSocket
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )

        connected, subprotocol = await communicator.connect()

        # Should be rejected (case-insensitive match)
        self.assertFalse(connected, "Case-insensitive ban should block connection")

        await communicator.disconnect()

    async def test_non_banned_user_can_connect_websocket(self):
        """Test that non-banned users can connect via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application

        # Do not create any ban

        # Create session token for non-banned user
        token = self._create_session_token('ValidUser')

        # Attempt to connect via WebSocket
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )

        connected, subprotocol = await communicator.connect()

        # Should succeed
        self.assertTrue(connected, "Non-banned user should be able to connect")

        await communicator.disconnect()


class ChatBanCreationTests(TestCase):
    """
    Test ChatBlock creation and management.

    These tests ensure only hosts can ban users and ban records are created correctly.
    """

    def setUp(self):
        """Create test users and chat room"""
        self.client = Client()

        # Create host user
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create regular user
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='RegularUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )

    def _join_chat_and_get_token(self, user, username):
        """Helper method to join chat as authenticated user and get session token"""
        self.client.force_login(user)
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': username},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()['session_token']

    def test_host_can_ban_user_by_username(self):
        """Test that host can ban user by username"""
        # Regular user joins chat first (to create participation record)
        self._join_chat_and_get_token(self.user, 'RegularUser')

        # Host joins chat
        session_token = self._join_chat_and_get_token(self.host, 'HostUser')

        # Host bans the regular user
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                'session_token': session_token
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify ban was created (stored as lowercase)
        self.assertTrue(
            ChatBlock.objects.filter(
                chat_room=self.chat_room,
                blocked_username='regularuser'  # Stored as lowercase
            ).exists()
        )

    def test_non_host_cannot_ban_users(self):
        """Test that non-host users cannot ban other users"""
        # Create another user to be the target of the ban attempt
        other_user = User.objects.create_user(
            email='other@test.com',
            password='testpass123',
            reserved_username='SomeUser'
        )

        # Other user joins chat first (to create participation record)
        self._join_chat_and_get_token(other_user, 'SomeUser')

        # Regular user joins chat
        session_token = self._join_chat_and_get_token(self.user, 'RegularUser')

        # Regular user tries to ban someone
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'SomeUser',
                'session_token': session_token
            },
            content_type='application/json'
        )

        # Should be forbidden (non-host cannot ban)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify ban was NOT created
        self.assertFalse(
            ChatBlock.objects.filter(
                chat_room=self.chat_room,
                blocked_username='someuser'  # Lowercase
            ).exists()
        )

    def test_ban_requires_session_token(self):
        """Test that banning requires a valid session token"""
        self.client.force_login(self.host)

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                # Missing session_token
            },
            content_type='application/json'
        )

        # Should fail
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])

    def test_duplicate_ban_prevented(self):
        """Test that duplicate bans are prevented or handled gracefully"""
        # Regular user joins chat first (to create participation record)
        self._join_chat_and_get_token(self.user, 'RegularUser')

        # Host joins chat
        session_token = self._join_chat_and_get_token(self.host, 'HostUser')

        # Create first ban
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                'session_token': session_token
            },
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Attempt to create duplicate ban
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                'session_token': session_token
            },
            content_type='application/json'
        )

        # Should succeed (idempotent behavior - updates existing block)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Only one ban should exist (stored as lowercase)
        self.assertEqual(
            ChatBlock.objects.filter(
                chat_room=self.chat_room,
                blocked_username='regularuser'  # Lowercase
            ).count(),
            1
        )

    def test_ban_consolidates_all_identifiers(self):
        """Test that ONE ChatBlock row is created with ALL identifiers"""
        from chats.models import ChatParticipation
        from chats.utils.security.blocking import block_participation

        # Regular user joins chat
        self.client.force_login(self.user)
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'RegularUser', 'fingerprint': 'test-fingerprint'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Get the participation
        participation_to_block = ChatParticipation.objects.get(
            chat_room=self.chat_room,
            username='RegularUser'
        )

        # Get host participation
        self.client.force_login(self.host)
        host_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'HostUser'},
            content_type='application/json'
        )
        host_participation = ChatParticipation.objects.get(
            chat_room=self.chat_room,
            user=self.host
        )

        # Create consolidated ban with ALL identifiers
        block = block_participation(
            chat_room=self.chat_room,
            participation=participation_to_block,
            blocked_by=host_participation,
            ip_address='192.168.1.100'
        )

        # Verify only ONE ChatBlock exists with ALL identifiers
        blocks = ChatBlock.objects.filter(chat_room=self.chat_room)
        self.assertEqual(blocks.count(), 1)

        # Verify all identifiers are populated in ONE row
        block = blocks.first()
        self.assertEqual(block.blocked_username, 'regularuser')  # Stored lowercase
        self.assertEqual(block.blocked_fingerprint, 'test-fingerprint')
        self.assertEqual(block.blocked_user, self.user)
        self.assertEqual(block.blocked_ip_address, '192.168.1.100')
        self.assertEqual(block.blocked_by, host_participation)

    def test_ip_address_is_tracked(self):
        """Test that IP address is stored in ChatBlock for tracking"""
        from chats.models import ChatParticipation

        # Host joins chat
        session_token = self._join_chat_and_get_token(self.host, 'HostUser')

        # Get host participation
        host_participation = ChatParticipation.objects.get(
            chat_room=self.chat_room,
            user=self.host
        )

        # Create ban with IP address
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username='baduser',
            blocked_ip_address='10.0.0.42',
            blocked_by=host_participation
        )

        # Verify IP address was tracked
        block = ChatBlock.objects.get(
            chat_room=self.chat_room,
            blocked_username='baduser'
        )
        self.assertEqual(block.blocked_ip_address, '10.0.0.42')

    def test_ban_requires_authentication(self):
        """Test that banning requires authentication"""
        # Try to ban without authentication
        self.client.logout()

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                'session_token': 'fake_token'
            },
            content_type='application/json'
        )

        # Should fail (no authentication or invalid token)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])


class ChatBanIntegrationTests(TestCase):
    """
    Integration tests for complete ban workflow.

    These tests verify the entire flow from ban creation to enforcement.
    """

    def setUp(self):
        """Create test users and chat room"""
        self.client = Client()

        # Create host user
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )

        # Create regular user
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='RegularUser'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host,
            access_mode='public'
        )

    def test_complete_ban_workflow(self):
        """Test complete ban workflow from join to ban to enforcement"""
        # Step 1: User joins chat and sends message successfully
        self.client.force_login(self.user)
        join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'RegularUser'},
            content_type='application/json'
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        user_token = join_response.json()['session_token']

        # User sends first message
        msg_response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': 'RegularUser',
                'content': 'Hello everyone!',
                'session_token': user_token
            },
            content_type='application/json'
        )
        self.assertEqual(msg_response1.status_code, status.HTTP_201_CREATED)

        # Step 2: Host joins chat
        self.client.force_login(self.host)
        host_join_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'HostUser'},
            content_type='application/json'
        )
        self.assertEqual(host_join_response.status_code, status.HTTP_200_OK)
        host_token = host_join_response.json()['session_token']

        # Step 3: Host bans the user
        ban_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'blocked_username': 'RegularUser',
                'session_token': host_token
            },
            content_type='application/json'
        )
        self.assertEqual(ban_response.status_code, status.HTTP_200_OK)

        # Step 4: Banned user attempts to send another message
        self.client.force_login(self.user)
        msg_response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/messages/send/',
            {
                'username': 'RegularUser',
                'content': 'This should be blocked',
                'session_token': user_token
            },
            content_type='application/json'
        )
        self.assertEqual(msg_response2.status_code, status.HTTP_403_FORBIDDEN)

        # Verify only first message was saved
        self.assertEqual(
            Message.objects.filter(
                chat_room=self.chat_room,
                username='RegularUser'
            ).count(),
            1  # Only the first message before ban
        )
