"""
Comprehensive tests for user blocking functionality.

Test coverage:
- ChatBlock model creation and validation
- Blocking utility functions (block/unblock/check/list)
- API endpoints (block/unblock/list blocked users)
- Join enforcement (blocked users cannot join)
- Self-block prevention
- Host-only permissions
- Multiple identifier blocking (username, fingerprint, user account)
- Case-insensitive username matching
- Block expiration
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from ..models import ChatRoom, ChatParticipation, ChatBlock
from ..utils.security.blocking import (
    block_participation,
    check_if_blocked,
    unblock_participation,
    get_blocked_users
)

User = get_user_model()


class ChatBlockModelTests(TestCase):
    """Tests for the ChatBlock model"""

    def setUp(self):
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )
        self.chat_room = ChatRoom.objects.create(
            host=self.host,
            code='TEST123',
            access_mode=ChatRoom.ACCESS_PUBLIC
        )
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser'
        )

    def test_create_username_block(self):
        """Test creating a block for a username"""
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='baduser'
        )
        self.assertEqual(block.blocked_username, 'baduser')
        self.assertEqual(block.chat_room, self.chat_room)
        self.assertEqual(block.blocked_by, self.host_participation)

    def test_create_fingerprint_block(self):
        """Test creating a block for a fingerprint"""
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_fingerprint='abc123fingerprint'
        )
        self.assertEqual(block.blocked_fingerprint, 'abc123fingerprint')

    def test_create_user_account_block(self):
        """Test creating a block for a user account"""
        blocked_user = User.objects.create_user(
            email='blocked@test.com',
            password='testpass123'
        )
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_user=blocked_user
        )
        self.assertEqual(block.blocked_user, blocked_user)

    def test_unique_constraint_username(self):
        """Test that duplicate username blocks are prevented"""
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='baduser'
        )
        # Attempting to create duplicate should fail due to unique constraint
        with self.assertRaises(Exception):
            ChatBlock.objects.create(
                chat_room=self.chat_room,
                blocked_by=self.host_participation,
                blocked_username='baduser'
            )

    def test_block_with_expiration(self):
        """Test creating a timed block with expiration"""
        expires_at = timezone.now() + timedelta(hours=24)
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='tempblock',
            expires_at=expires_at
        )
        self.assertIsNotNone(block.expires_at)
        self.assertTrue(block.expires_at > timezone.now())

    def test_block_with_reason(self):
        """Test creating a block with a reason note"""
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='spammer',
            reason='Sending spam messages repeatedly'
        )
        self.assertEqual(block.reason, 'Sending spam messages repeatedly')


class BlockingUtilityTests(TestCase):
    """Tests for blocking utility functions"""

    def setUp(self):
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )
        self.chat_room = ChatRoom.objects.create(
            host=self.host,
            code='TEST123',
            access_mode=ChatRoom.ACCESS_PUBLIC
        )
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser'
        )

    def test_block_participation_creates_blocks(self):
        """Test that blocking creates a consolidated block with all identifiers"""
        # Create a participation with username and fingerprint
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='BadUser',
            fingerprint='abc123'
        )

        block = block_participation(
            chat_room=self.chat_room,
            participation=participation,
            blocked_by=self.host_participation
        )

        # Should create 1 consolidated block with both username and fingerprint
        self.assertIsInstance(block, ChatBlock)
        self.assertEqual(block.blocked_username, 'baduser')  # Stored in lowercase
        self.assertEqual(block.blocked_fingerprint, 'abc123')
        self.assertEqual(ChatBlock.objects.filter(chat_room=self.chat_room).count(), 1)

    def test_block_participation_with_user_account(self):
        """Test blocking a registered user creates consolidated block with user account"""
        blocked_user = User.objects.create_user(
            email='blocked@test.com',
            password='testpass123',
            reserved_username='BlockedUser'
        )
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=blocked_user,
            username='BlockedUser',
            fingerprint='xyz789'
        )

        block = block_participation(
            chat_room=self.chat_room,
            participation=participation,
            blocked_by=self.host_participation
        )

        # Should create 1 consolidated block with username, user account, AND fingerprint
        # NOTE: Fingerprint IS STORED but NOT ENFORCED for logged-in users (see check_if_blocked line 118)
        # This allows tracking while preventing false positives if multiple users share same device
        self.assertIsInstance(block, ChatBlock)
        self.assertEqual(block.blocked_username, 'blockeduser')  # Stored in lowercase
        self.assertEqual(block.blocked_user, blocked_user)
        self.assertEqual(block.blocked_fingerprint, 'xyz789')  # Stored for tracking

    def test_block_participation_prevents_self_block(self):
        """Test that users cannot block themselves"""
        with self.assertRaises(ValueError) as context:
            block_participation(
                chat_room=self.chat_room,
                participation=self.host_participation,
                blocked_by=self.host_participation
            )
        self.assertIn('Cannot block yourself', str(context.exception))

    def test_block_participation_requires_host(self):
        """Test that only host can block users"""
        non_host = User.objects.create_user(
            email='user@test.com',
            password='testpass123'
        )
        non_host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=non_host,
            username='RegularUser'
        )
        target_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='TargetUser'
        )

        with self.assertRaises(ValueError) as context:
            block_participation(
                chat_room=self.chat_room,
                participation=target_participation,
                blocked_by=non_host_participation
            )
        self.assertIn('Only the host can block users', str(context.exception))

    def test_check_if_blocked_by_username(self):
        """Test checking if a username is blocked"""
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='baduser'
        )

        is_blocked, message = check_if_blocked(
            chat_room=self.chat_room,
            username='baduser'
        )
        self.assertTrue(is_blocked)
        self.assertEqual(message, 'You have been blocked from this chat.')

    def test_check_if_blocked_case_insensitive(self):
        """Test that username blocking is case-insensitive"""
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='baduser'
        )

        # Check with different case
        is_blocked, _ = check_if_blocked(
            chat_room=self.chat_room,
            username='BadUser'
        )
        self.assertTrue(is_blocked)

    def test_check_if_blocked_by_fingerprint(self):
        """Test checking if a fingerprint is blocked"""
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_fingerprint='abc123'
        )

        is_blocked, _ = check_if_blocked(
            chat_room=self.chat_room,
            fingerprint='abc123'
        )
        self.assertTrue(is_blocked)

    def test_check_if_blocked_by_user_account(self):
        """Test checking if a user account is blocked"""
        blocked_user = User.objects.create_user(
            email='blocked@test.com',
            password='testpass123'
        )
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_user=blocked_user
        )

        is_blocked, _ = check_if_blocked(
            chat_room=self.chat_room,
            user=blocked_user
        )
        self.assertTrue(is_blocked)

    def test_check_if_blocked_by_ip_address(self):
        """Test that IP address blocking is NOT enforced yet (tracking only)"""
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_ip_address='192.168.1.100'
        )

        # IP blocking is disabled - users should NOT be blocked by IP address yet
        is_blocked, _ = check_if_blocked(
            chat_room=self.chat_room,
            ip_address='192.168.1.100'
        )
        self.assertFalse(is_blocked)  # Should NOT be blocked (tracking only, not enforced)

    def test_block_participation_stores_ip_address(self):
        """Test that blocking a user stores their IP address"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='UserWithIP',
            fingerprint='fp123',
            ip_address='10.0.0.50'
        )

        block = block_participation(
            chat_room=self.chat_room,
            participation=participation,
            blocked_by=self.host_participation,
            ip_address='10.0.0.50'
        )

        # Verify IP address was stored in the consolidated block
        self.assertEqual(block.blocked_ip_address, '10.0.0.50')
        self.assertEqual(block.blocked_username, 'userwithip')
        self.assertEqual(block.blocked_fingerprint, 'fp123')

    def test_check_if_not_blocked(self):
        """Test that non-blocked users pass the check"""
        is_blocked, message = check_if_blocked(
            chat_room=self.chat_room,
            username='gooduser'
        )
        self.assertFalse(is_blocked)
        self.assertIsNone(message)

    def test_check_if_blocked_expired(self):
        """Test that expired blocks are ignored"""
        expires_at = timezone.now() - timedelta(hours=1)  # Already expired
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='tempblock',
            expires_at=expires_at
        )

        is_blocked, _ = check_if_blocked(
            chat_room=self.chat_room,
            username='tempblock'
        )
        self.assertFalse(is_blocked)

    def test_unblock_participation(self):
        """Test unblocking removes the consolidated block for a participation"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='BlockedUser',
            fingerprint='abc123'
        )

        # Block the user
        block_participation(
            chat_room=self.chat_room,
            participation=participation,
            blocked_by=self.host_participation
        )

        # Verify consolidated block exists
        self.assertEqual(ChatBlock.objects.filter(chat_room=self.chat_room).count(), 1)

        # Unblock
        count = unblock_participation(self.chat_room, participation)
        self.assertEqual(count, 1)  # Should remove 1 consolidated block
        self.assertEqual(ChatBlock.objects.filter(chat_room=self.chat_room).count(), 0)

    def test_get_blocked_users(self):
        """Test retrieving list of blocked users"""
        # Block two users
        participation1 = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='BadUser1',
            fingerprint='fp1'
        )
        participation2 = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='BadUser2',
            fingerprint='fp2'
        )

        block_participation(
            chat_room=self.chat_room,
            participation=participation1,
            blocked_by=self.host_participation
        )
        block_participation(
            chat_room=self.chat_room,
            participation=participation2,
            blocked_by=self.host_participation
        )

        blocked_users = get_blocked_users(self.chat_room)
        # With consolidated blocks: 1 ChatBlock row per user
        # get_blocked_users returns 1 entry per ChatBlock row
        # So we get 2 entries total (one per blocked user)
        self.assertEqual(len(blocked_users), 2)

        # Verify we have both users represented
        # Note: usernames are stored in lowercase by block_participation()
        usernames = [u['username'] for u in blocked_users if u['username']]
        self.assertIn('baduser1', usernames)
        self.assertIn('baduser2', usernames)

        # Verify each entry has blocked_identifiers list with multiple identifiers
        for user in blocked_users:
            self.assertIn('blocked_identifiers', user)
            self.assertIsInstance(user['blocked_identifiers'], list)
            # Each user should have username and fingerprint blocked
            self.assertGreater(len(user['blocked_identifiers']), 0)


class BlockingAPITests(TestCase):
    """Tests for blocking API endpoints"""

    def setUp(self):
        from ..utils.security.auth import ChatSessionValidator

        self.client = APIClient()
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )
        self.chat_room = ChatRoom.objects.create(
            host=self.host,
            code='TEST123',
            access_mode=ChatRoom.ACCESS_PUBLIC
        )
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser'
        )
        # Create session token for host
        self.host_session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='HostUser',
            user_id=self.host.id
        )

    def test_block_user_endpoint_requires_auth(self):
        """Test that block endpoint requires session token"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='TargetUser'
        )

        # Request without session_token should fail
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {'participation_id': str(participation.id)},
            format='json'
        )
        # BlockUserView returns 400 Bad Request when session_token is missing
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_block_user_endpoint_success(self):
        """Test successfully blocking a user via API"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='BadUser',
            fingerprint='abc123'
        )

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'participation_id': str(participation.id),
                'session_token': self.host_session_token
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('block_id', response.data)
        self.assertIn('blocked_identifiers', response.data)
        # Verify both username and fingerprint were blocked
        self.assertIn('username', response.data['blocked_identifiers'])
        self.assertIn('fingerprint', response.data['blocked_identifiers'])

        # Verify consolidated block was created
        self.assertEqual(ChatBlock.objects.filter(chat_room=self.chat_room).count(), 1)

        # NOTE: We do NOT check is_active=False here because:
        # The new architecture keeps participation.is_active unchanged during blocking
        # ChatBlock table is the source of truth for blocking, not is_active flag
        # This allows MyParticipationView to return is_blocked=true for proper UI display

    def test_block_user_endpoint_requires_host(self):
        """Test that only host can use block endpoint"""
        from ..utils.security.auth import ChatSessionValidator

        non_host = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='RegularUser'
        )
        # Create participation for non-host
        non_host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=non_host,
            username='RegularUser'
        )
        # Create session token for non-host
        non_host_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat_room.code,
            username='RegularUser',
            user_id=non_host.id
        )

        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='TargetUser'
        )

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/block-user/',
            {
                'participation_id': str(participation.id),
                'session_token': non_host_token
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unblock_user_endpoint_success(self):
        """Test successfully unblocking a user via API"""
        self.client.force_authenticate(user=self.host)

        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='UnblockMe',
            fingerprint='xyz789',
            is_active=False
        )

        # Create consolidated block manually
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username='unblockme',  # Lowercase
            blocked_fingerprint='xyz789'
        )

        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/unblock/',
            {'participation_id': str(participation.id)},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['blocks_removed'], 1)  # 1 consolidated block removed

        # Verify block was removed
        self.assertEqual(ChatBlock.objects.filter(chat_room=self.chat_room).count(), 0)

        # Verify participation was reactivated
        participation.refresh_from_db()
        self.assertTrue(participation.is_active)

    def test_blocked_users_list_endpoint(self):
        """Test listing blocked users via API"""
        self.client.force_authenticate(user=self.host)

        # Block some users
        participation1 = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='Blocked1'
        )
        participation2 = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            username='Blocked2'
        )

        block_participation(
            chat_room=self.chat_room,
            participation=participation1,
            blocked_by=self.host_participation
        )
        block_participation(
            chat_room=self.chat_room,
            participation=participation2,
            blocked_by=self.host_participation
        )

        response = self.client.get(
            f'/api/chats/HostUser/{self.chat_room.code}/blocked-users/'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['blocked_users']), 2)


class JoinEnforcementTests(TestCase):
    """Tests for blocking enforcement at join time"""

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='HostUser'
        )
        self.chat_room = ChatRoom.objects.create(
            host=self.host,
            code='TEST123',
            access_mode=ChatRoom.ACCESS_PUBLIC
        )
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def test_blocked_username_cannot_join(self):
        """Test that a blocked username cannot join the chat"""
        # Generate a username
        fingerprint = 'blocked_user_fp'
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        blocked_username = suggest_response.data['username']

        # Block that username
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_username=blocked_username.lower()
        )

        # Try to join with blocked username
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': blocked_username,
                'fingerprint': fingerprint
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_blocked_fingerprint_cannot_join(self):
        """Test that a blocked fingerprint cannot join the chat"""
        # Generate a username for this fingerprint
        fingerprint = 'blocked_fingerprint_fp'
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.data['username']

        # Block the fingerprint
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_fingerprint=fingerprint
        )

        # Try to join with blocked fingerprint
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_blocked_user_account_cannot_join(self):
        """Test that a blocked user account cannot join the chat"""
        blocked_user = User.objects.create_user(
            email='blocked@test.com',
            password='testpass123',
            reserved_username='BlockedUser'
        )

        # Block the user account
        ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_by=self.host_participation,
            blocked_user=blocked_user
        )

        # Try to join as blocked user
        self.client.force_authenticate(user=blocked_user)
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {'username': 'BlockedUser'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_blocked_user_can_join(self):
        """Test that non-blocked users can still join"""
        # Generate a username for a non-blocked user
        fingerprint = 'good_user_fp'
        suggest_response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/suggest-username/',
            {'fingerprint': fingerprint},
            format='json'
        )
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        username = suggest_response.data['username']

        # Join without any blocks
        response = self.client.post(
            f'/api/chats/HostUser/{self.chat_room.code}/join/',
            {
                'username': username,
                'fingerprint': fingerprint
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
