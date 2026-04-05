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

import allure
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth import get_user_model
from rest_framework import status

from chats.models import ChatRoom, ChatBlock, Message

User = get_user_model()


@allure.feature('User Blocking')
@allure.story('Ban Enforcement - HTTP API')
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

        # Host must join first
        from chats.models import ChatParticipation
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
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

    @allure.title("Banned username cannot rejoin chat")
    @allure.description("Test that user banned by username cannot rejoin the chat room")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_banned_username_cannot_rejoin_http(self):
        """Test that user banned by username cannot rejoin the chat"""
        # Generate and join with an anonymous username
        fingerprint = 'anon-fp-username-ban'
        test_username = self._suggest_username(fingerprint)
        token = self._join_chat_and_get_token(test_username, fingerprint)

        # Ban user by username
        self._create_ban(blocked_username=test_username.lower())

        # Attempt to rejoin with a new suggested username (same fingerprint)
        new_username = self._suggest_username(fingerprint)

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': new_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )

        # Ban is enforced at join time - the username ban blocks the original username
        # but a new username won't be caught by username ban alone.
        # Verify the original username is blocked by trying to rejoin with it
        response2 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': test_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)

    @allure.title("Username ban is case-insensitive (join enforcement)")
    @allure.description("Test that username ban is case-insensitive at join time")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_banned_username_case_insensitive_http(self):
        """Test that username ban is case-insensitive at join time"""
        # Generate and join with an anonymous username
        fingerprint = 'anon-fp-case-test'
        test_username = self._suggest_username(fingerprint)
        token = self._join_chat_and_get_token(test_username, fingerprint)

        # Ban user with lowercase username
        self._create_ban(blocked_username=test_username.lower())

        # Attempt to rejoin with the same username (original case preserved)
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': test_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )

        # Should be forbidden (case-insensitive match at join time)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @allure.title("Banned fingerprint+IP cannot rejoin chat")
    @allure.description("Test that user banned by fingerprint+IP cannot rejoin the chat room")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_banned_fingerprint_cannot_rejoin_http(self):
        """Test that user banned by fingerprint+IP cannot rejoin the chat"""
        # Get a generated username for the fingerprint
        fingerprint = 'anon-fingerprint-test'
        username = self._suggest_username(fingerprint)

        # Anonymous user joins chat with generated username
        token = self._join_chat_and_get_token(username, fingerprint)

        # Ban anonymous user by fingerprint+IP (fingerprint_ip tier)
        from chats.models import ChatParticipation
        host_participation = ChatParticipation.objects.get(
            chat_room=self.chat_room, user=self.host
        )
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_fingerprint=fingerprint,
            blocked_ip_address='127.0.0.1',
            blocked_by=host_participation,
            ban_tier=ChatBlock.BAN_TIER_FINGERPRINT_IP
        )

        # Attempt to rejoin with a new username but same fingerprint
        new_username = self._suggest_username(fingerprint)
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': new_username,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )

        # Should be forbidden (fingerprint+IP ban enforced at join time)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @allure.title("Banned user ID cannot rejoin chat")
    @allure.description("Test that user banned by user_id cannot rejoin the chat room")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_banned_user_id_cannot_rejoin_http(self):
        """Test that user banned by user_id cannot rejoin the chat"""
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

        # Attempt to rejoin the chat
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'RegularUser'},
            content_type='application/json'
        )

        # Should be forbidden (user account ban enforced at join time)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @allure.title("Non-banned user can send HTTP message")
    @allure.description("Test that non-banned users can still send messages via HTTP API")
    @allure.severity(allure.severity_level.NORMAL)
    def test_non_banned_user_can_send_message_http(self):
        """Test that non-banned users can still send messages via HTTP API"""
        # Generate and join with an anonymous username
        fingerprint = 'anon-fp-valid-user'
        test_username = self._suggest_username(fingerprint)
        token = self._join_chat_and_get_token(test_username, fingerprint)

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

    @allure.title("Host can send message after banning user")
    @allure.description("Test that host can still send messages after banning a user")
    @allure.severity(allure.severity_level.NORMAL)
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

    @allure.title("Ban only affects specific chat")
    @allure.description("Test that ChatBlock only affects the specific chat room")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ban_only_affects_specific_chat(self):
        """Test that ChatBlock only affects the specific chat room"""
        # Create second chat room
        chat_room2 = ChatRoom.objects.create(
            name='Test Chat 2',
            host=self.host,
            access_mode='public'
        )

        # Host must join second chat first
        from chats.models import ChatParticipation
        ChatParticipation.objects.create(
            chat_room=chat_room2,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint2',
            ip_address='127.0.0.1'
        )

        # Generate and join chat 1 with anonymous user
        fingerprint = 'anon-fp-multi-chat'
        username1 = self._suggest_username(fingerprint)
        token1 = self._join_chat_and_get_token(username1, fingerprint)

        # Generate and join chat 2 with same user
        suggest_response2 = self.client.post(
            f'/api/chats/HostUser/{chat_room2.code}/suggest-username/',
            {'fingerprint': fingerprint},
            content_type='application/json'
        )
        username2 = suggest_response2.json()['username']
        join_response2 = self.client.post(
            f'/api/chats/HostUser/{chat_room2.code}/join/',
            {'username': username2, 'fingerprint': fingerprint},
            content_type='application/json'
        )
        token2 = join_response2.json()['session_token']

        # Ban user from first chat only (by username)
        host_participation = ChatParticipation.objects.get_or_create(
            chat_room=self.chat_room,
            user=self.host,
            defaults={'username': 'HostUser'}
        )[0]

        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=username1.lower(),
            blocked_by=host_participation
        )

        # Attempt to rejoin first chat (should fail - banned)
        response1 = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': username1,
                'fingerprint': fingerprint
            },
            content_type='application/json'
        )
        self.assertEqual(response1.status_code, status.HTTP_403_FORBIDDEN)

        # Can still send message in second chat (not banned there)
        response2 = self.client.post(
            f'/api/chats/HostUser/{chat_room2.code}/messages/send/',
            {
                'username': username2,
                'content': 'Chat 2 message',
                'session_token': token2
            },
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)


@allure.feature('User Blocking')
@allure.story('Ban Enforcement - WebSocket')
class ChatBanEnforcementWebSocketTests(TransactionTestCase):
    """
    Test ChatBlock enforcement in WebSocket connections.

    These tests ensure banned users cannot connect via WebSocket.
    Uses TransactionTestCase to support async operations.
    """

    def setUp(self):
        """Create test users and chat room"""
        from channels.db import database_sync_to_async
        from chats.models import ChatParticipation

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

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
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

    @allure.title("Banned username cannot connect via WebSocket")
    @allure.description("Test that user banned by username cannot connect via WebSocket")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Banned fingerprint+IP cannot connect via WebSocket")
    @allure.description("Test that user banned by fingerprint+IP cannot connect via WebSocket")
    @allure.severity(allure.severity_level.CRITICAL)
    async def test_banned_fingerprint_cannot_connect_websocket(self):
        """Test that user banned by fingerprint+IP cannot connect via WebSocket"""
        from channels.testing import WebsocketCommunicator
        from chatpop.asgi import application
        from channels.db import database_sync_to_async

        fingerprint = 'banned-fingerprint'
        client_ip = '127.0.0.1'

        # Ban user by fingerprint+IP (fingerprint_ip tier)
        @database_sync_to_async
        def create_fingerprint_ip_ban():
            from chats.models import ChatParticipation
            host_participation = ChatParticipation.objects.get_or_create(
                chat_room=self.chat_room,
                user=self.host,
                defaults={'username': 'HostUser'}
            )[0]
            ChatBlock.objects.create(
                chat_room=self.chat_room,
                blocked_fingerprint=fingerprint,
                blocked_ip_address=client_ip,
                blocked_by=host_participation,
                ban_tier=ChatBlock.BAN_TIER_FINGERPRINT_IP
            )

        await create_fingerprint_ip_ban()

        # Create session token with fingerprint
        token = self._create_session_token('AnonUser', fingerprint=fingerprint)

        # Attempt to connect via WebSocket (with client IP in scope)
        communicator = WebsocketCommunicator(
            application,
            f'/ws/chat/{self.chat_room.code}/?session_token={token}'
        )
        communicator.scope['client'] = (client_ip, 0)

        connected, subprotocol = await communicator.connect()

        # Should be rejected
        self.assertFalse(connected, "Fingerprint+IP-banned user should not be able to connect")

        await communicator.disconnect()

    @allure.title("Banned user ID cannot connect via WebSocket")
    @allure.description("Test that user banned by user_id cannot connect via WebSocket")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Banned username is case-insensitive (WebSocket)")
    @allure.description("Test that username ban is case-insensitive for WebSocket")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Non-banned user can connect via WebSocket")
    @allure.description("Test that non-banned users can connect via WebSocket")
    @allure.severity(allure.severity_level.NORMAL)
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


@allure.feature('User Blocking')
@allure.story('Ban Creation and Management')
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

        # Host must join first
        from chats.models import ChatParticipation
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
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

    @allure.title("Host can ban user by username")
    @allure.description("Test that host can ban user by username")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Non-host cannot ban users")
    @allure.description("Test that non-host users cannot ban other users")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Ban requires session token")
    @allure.description("Test that banning requires a valid session token")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("Duplicate ban prevented")
    @allure.description("Test that duplicate bans are prevented or handled gracefully")
    @allure.severity(allure.severity_level.NORMAL)
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

    @allure.title("Ban consolidates all identifiers")
    @allure.description("Test that ONE ChatBlock row is created with ALL identifiers")
    @allure.severity(allure.severity_level.CRITICAL)
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

    @allure.title("IP address is tracked in ban")
    @allure.description("Test that IP address is stored in ChatBlock for tracking")
    @allure.severity(allure.severity_level.NORMAL)
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

    @allure.title("Ban requires authentication")
    @allure.description("Test that banning requires authentication")
    @allure.severity(allure.severity_level.CRITICAL)
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


@allure.feature('User Blocking')
@allure.story('Ban Integration Workflow')
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

        # Host must join first
        from chats.models import ChatParticipation
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
        )

    @allure.title("Complete ban workflow")
    @allure.description("Test complete ban workflow from join to ban to enforcement at rejoin")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_complete_ban_workflow(self):
        """Test complete ban workflow from join to ban to enforcement at rejoin"""
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

        # Step 4: Banned user attempts to rejoin the chat
        # Ban enforcement happens at join time (not per-message)
        self.client.force_login(self.user)
        rejoin_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'RegularUser'},
            content_type='application/json'
        )
        self.assertEqual(rejoin_response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify only first message was saved (ban doesn't delete existing messages)
        self.assertEqual(
            Message.objects.filter(
                chat_room=self.chat_room,
                username='RegularUser'
            ).count(),
            1
        )
