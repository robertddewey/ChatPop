"""
Tests for avatar consistency between join flows and identity types.

Core rules exercised here:
  - Reserved-username users: User.avatar_url is stable once set. A second join
    that sends an avatar_seed must NOT overwrite the existing User avatar.
  - Reserved-username users with no User.avatar_url: the seed IS used to
    generate and store the avatar on User.
  - Logged-in users acting under an anonymous identity (different username)
    or pure anonymous users: avatar is stored on ChatParticipation directly.
"""

from unittest.mock import patch
from django.test import TestCase
from accounts.models import User
from chats.models import ChatRoom, ChatParticipation
from chats.views import ChatRoomJoinView
import allure


@allure.feature('Avatars')
@allure.story('Join-time avatar assignment')
class JoinTimeAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='alice@example.com',
            password='testpass123',
            reserved_username='alice',
        )
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user,
            access_mode='public',
        )
        self.view = ChatRoomJoinView()

    def _make_participation(self, username, user=None, session_key=None):
        return ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=user,
            username=username,
            session_key=session_key,
            ip_address='127.0.0.1',
            is_anonymous_identity=(user is not None and username.lower() != (user.reserved_username or '').lower()),
        )

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_reserved_user_first_join_stores_user_avatar(self, mock_gen):
        """Reserved user with no existing avatar: seed is honored and saved to User."""
        mock_gen.return_value = 'https://cdn.example.com/new-avatar.png'
        self.assertFalse(self.user.avatar_url)

        part = self._make_participation('alice', user=self.user)
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=self.user, avatar_seed='picked-seed-1'
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, 'https://cdn.example.com/new-avatar.png')
        mock_gen.assert_called_once_with('picked-seed-1')

        # Participation gets the proxy URL
        part.refresh_from_db()
        self.assertEqual(part.avatar_url, f'/api/chats/media/avatars/user/{self.user.id}')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_reserved_user_without_avatar_auto_assigns_from_username(self, mock_gen):
        """Reserved user with no User.avatar_url and no seed from frontend:
        backend auto-assigns a username-seeded avatar (consistent per-username)."""
        mock_gen.return_value = 'https://cdn.example.com/auto-avatar.png'
        self.assertFalse(self.user.avatar_url)

        part = self._make_participation('alice', user=self.user)
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=self.user, avatar_seed=None
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, 'https://cdn.example.com/auto-avatar.png')
        # Seed falls back to participation.username (== reserved_username)
        mock_gen.assert_called_once_with('alice')

        part.refresh_from_db()
        self.assertEqual(part.avatar_url, f'/api/chats/media/avatars/user/{self.user.id}')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_reserved_user_with_existing_avatar_ignores_seed(self, mock_gen):
        """A second reserved-username join with a seed must NOT overwrite the
        existing User.avatar_url — reserved avatars are stable once chosen."""
        self.user.avatar_url = 'https://cdn.example.com/original-avatar.png'
        self.user.save(update_fields=['avatar_url'])

        part = self._make_participation('alice', user=self.user)
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=self.user, avatar_seed='attempted-override-seed'
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, 'https://cdn.example.com/original-avatar.png')
        mock_gen.assert_not_called()

        # Participation still points at the proxy URL (stable regardless)
        part.refresh_from_db()
        self.assertEqual(part.avatar_url, f'/api/chats/media/avatars/user/{self.user.id}')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_reserved_user_existing_avatar_no_seed_no_regenerate(self, mock_gen):
        """No seed + existing User.avatar_url: do nothing new, just set proxy."""
        self.user.avatar_url = 'https://cdn.example.com/original-avatar.png'
        self.user.save(update_fields=['avatar_url'])

        part = self._make_participation('alice', user=self.user)
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=self.user, avatar_seed=None
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, 'https://cdn.example.com/original-avatar.png')
        mock_gen.assert_not_called()
        part.refresh_from_db()
        self.assertEqual(part.avatar_url, f'/api/chats/media/avatars/user/{self.user.id}')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_logged_in_user_anonymous_identity_stores_on_participation(self, mock_gen):
        """A logged-in user joining under an anonymous username gets a direct
        avatar URL on the participation, not on the User."""
        mock_gen.return_value = 'https://cdn.example.com/anon-avatar.png'

        part = self._make_participation('RandomAnon42', user=self.user)
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=self.user, avatar_seed='anon-seed'
        )

        # User.avatar_url untouched
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar_url)

        part.refresh_from_db()
        self.assertEqual(part.avatar_url, 'https://cdn.example.com/anon-avatar.png')
        mock_gen.assert_called_once_with('anon-seed')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_pure_anonymous_user_stores_on_participation(self, mock_gen):
        """A fully anonymous user gets a direct avatar URL on the participation."""
        mock_gen.return_value = 'https://cdn.example.com/anon-avatar.png'

        part = self._make_participation('Guest007', user=None, session_key='abc123')
        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=None, avatar_seed='pure-anon-seed'
        )

        part.refresh_from_db()
        self.assertEqual(part.avatar_url, 'https://cdn.example.com/anon-avatar.png')
        mock_gen.assert_called_once_with('pure-anon-seed')

    @patch('chatpop.utils.media.generate_and_store_avatar')
    def test_anonymous_participation_with_existing_avatar_not_overwritten(self, mock_gen):
        """If a participation already has an avatar_url, don't regenerate
        (anonymous identities are locked to their first-chosen avatar)."""
        part = self._make_participation('Guest007', user=None, session_key='abc123')
        part.avatar_url = 'https://cdn.example.com/locked-anon.png'
        part.save(update_fields=['avatar_url'])

        self.view._generate_avatar_for_participation(
            part, self.chat_room, user=None, avatar_seed='attempted-override-seed'
        )

        part.refresh_from_db()
        self.assertEqual(part.avatar_url, 'https://cdn.example.com/locked-anon.png')
        mock_gen.assert_not_called()
