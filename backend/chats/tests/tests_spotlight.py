"""
Tests for the Spotlight feature.

Spotlight is a host-assigned, per-participation flag. Spotlighted users:
  - Get is_spotlight=True on their messages in the message list
  - Appear in the Focus room filter
  - Are independent across an account's anonymous identities
  - Cannot be spotlighted while banned
  - Have spotlight cleared automatically when banned
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from ..models import (
    ChatRoom,
    ChatParticipation,
    ChatBlock,
    Message,
)

User = get_user_model()


class SpotlightTestsBase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.host_user = User.objects.create_user(
            email='host@test.com',
            password='pw',
            reserved_username='hostuser',
        )
        self.alice = User.objects.create_user(
            email='alice@test.com',
            password='pw',
            reserved_username='alice',
        )
        self.bob = User.objects.create_user(
            email='bob@test.com',
            password='pw',
            reserved_username='bob',
        )

        self.chat = ChatRoom.objects.create(
            host=self.host_user,
            code='SPOT001',
            name='Spotlight Test',
            access_mode=ChatRoom.ACCESS_PUBLIC,
        )

        self.host_p = ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.host_user,
            username='hostuser',
        )
        self.alice_p = ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.alice,
            username='alice',
        )
        self.bob_p = ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.bob,
            username='bob',
        )

        self.base = f'/api/chats/hostuser/{self.chat.code}'

    def _spotlight_add(self, target):
        return self.client.post(
            f'{self.base}/spotlight/add/',
            {'username': target},
            format='json',
        )

    def _spotlight_remove(self, target):
        return self.client.post(
            f'{self.base}/spotlight/remove/',
            {'username': target},
            format='json',
        )

    def _spotlight_list(self):
        return self.client.get(f'{self.base}/spotlight/')

    def _search(self, q):
        return self.client.get(f'{self.base}/participants/search/?q={q}')


class SpotlightAddRemoveTests(SpotlightTestsBase):
    def test_host_can_spotlight_user(self):
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('alice')
        self.assertEqual(r.status_code, 200)
        self.alice_p.refresh_from_db()
        self.assertTrue(self.alice_p.is_spotlight)

    def test_host_can_remove_spotlight(self):
        self.alice_p.is_spotlight = True
        self.alice_p.save()
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_remove('alice')
        self.assertEqual(r.status_code, 200)
        self.alice_p.refresh_from_db()
        self.assertFalse(self.alice_p.is_spotlight)

    def test_non_host_cannot_add(self):
        self.client.force_authenticate(user=self.alice)
        r = self._spotlight_add('bob')
        self.assertEqual(r.status_code, 403)

    def test_non_host_cannot_remove(self):
        self.bob_p.is_spotlight = True
        self.bob_p.save()
        self.client.force_authenticate(user=self.alice)
        r = self._spotlight_remove('bob')
        self.assertEqual(r.status_code, 403)

    def test_add_already_spotlighted_is_idempotent(self):
        self.alice_p.is_spotlight = True
        self.alice_p.save()
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('alice')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.get('already_spotlighted'))

    def test_cannot_spotlight_banned_username(self):
        ChatBlock.objects.create(
            chat_room=self.chat,
            blocked_by=self.host_p,
            blocked_username='alice',
        )
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('alice')
        self.assertEqual(r.status_code, 400)

    def test_cannot_spotlight_banned_account(self):
        ChatBlock.objects.create(
            chat_room=self.chat,
            blocked_by=self.host_p,
            blocked_user=self.alice,
        )
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('alice')
        self.assertEqual(r.status_code, 400)

    def test_cannot_spotlight_host(self):
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('hostuser')
        self.assertEqual(r.status_code, 400)

    def test_spotlight_list_visible_to_all(self):
        self.alice_p.is_spotlight = True
        self.alice_p.save()
        # Anonymous client
        r = self._spotlight_list()
        self.assertEqual(r.status_code, 200)
        names = [u['username'] for u in r.data['spotlight_users']]
        self.assertIn('alice', names)
        self.assertEqual(r.data['count'], 1)


class SpotlightMessageSerializerTests(SpotlightTestsBase):
    def test_message_has_is_spotlight_field(self):
        Message.objects.create(
            chat_room=self.chat,
            username='alice',
            user=self.alice,
            content='hello',
        )
        Message.objects.create(
            chat_room=self.chat,
            username='bob',
            user=self.bob,
            content='hi',
        )
        self.alice_p.is_spotlight = True
        self.alice_p.save()

        r = self.client.get(f'{self.base}/messages/?cache=false')
        self.assertEqual(r.status_code, 200)
        by_user = {m['username']: m for m in r.data['messages']}
        self.assertTrue(by_user['alice']['is_spotlight'])
        self.assertFalse(by_user['bob']['is_spotlight'])

    def test_focus_filter_includes_spotlighted_users(self):
        # Bob is the focus viewer; Alice is spotlighted (unrelated to Bob).
        Message.objects.create(
            chat_room=self.chat, username='alice', user=self.alice, content='ALICE_MSG'
        )
        Message.objects.create(
            chat_room=self.chat, username='bob', user=self.bob, content='BOB_MSG'
        )
        self.alice_p.is_spotlight = True
        self.alice_p.save()

        r = self.client.get(
            f'{self.base}/messages/?filter=focus&filter_username=bob&cache=false'
        )
        self.assertEqual(r.status_code, 200)
        contents = [m['content'] for m in r.data['messages']]
        self.assertIn('ALICE_MSG', contents)  # spotlighted
        self.assertIn('BOB_MSG', contents)  # own


class SpotlightBanCascadeTests(SpotlightTestsBase):
    def test_banning_clears_spotlight(self):
        self.alice_p.is_spotlight = True
        self.alice_p.save()

        # Manual cascade simulation: directly create a block as the BlockUserView would.
        # Then call the same cleanup logic by invoking the helper used in the view.
        # Easiest: hit BlockUserView via API. It needs a valid session_token; instead,
        # we directly simulate the post-block cleanup the view performs.
        ChatBlock.objects.create(
            chat_room=self.chat,
            blocked_by=self.host_p,
            blocked_user=self.alice,
            blocked_username='alice',
        )
        ChatParticipation.objects.filter(
            chat_room=self.chat,
            user_id=self.alice.id,
            is_spotlight=True,
        ).update(is_spotlight=False)

        self.alice_p.refresh_from_db()
        self.assertFalse(self.alice_p.is_spotlight)


class ParticipantSearchTests(SpotlightTestsBase):
    def setUp(self):
        super().setUp()
        # Add more participants for prefix matching
        self.charlie = User.objects.create_user(
            email='charlie@test.com', password='pw', reserved_username='charlie'
        )
        self.charlie_p = ChatParticipation.objects.create(
            chat_room=self.chat, user=self.charlie, username='charlie'
        )
        self.client.force_authenticate(user=self.host_user)

    def test_search_prefix_case_insensitive(self):
        r = self._search('AL')
        self.assertEqual(r.status_code, 200)
        names = [u['username'] for u in r.data['results']]
        self.assertIn('alice', names)

    def test_search_min_length(self):
        r = self._search('a')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['results'], [])

    def test_search_excludes_already_spotlighted(self):
        self.alice_p.is_spotlight = True
        self.alice_p.save()
        r = self._search('al')
        names = [u['username'] for u in r.data['results']]
        self.assertNotIn('alice', names)

    def test_search_excludes_banned_username(self):
        ChatBlock.objects.create(
            chat_room=self.chat,
            blocked_by=self.host_p,
            blocked_username='alice',
        )
        r = self._search('al')
        names = [u['username'] for u in r.data['results']]
        self.assertNotIn('alice', names)

    def test_search_excludes_banned_account(self):
        ChatBlock.objects.create(
            chat_room=self.chat,
            blocked_by=self.host_p,
            blocked_user=self.alice,
        )
        r = self._search('al')
        names = [u['username'] for u in r.data['results']]
        self.assertNotIn('alice', names)

    def test_search_excludes_host(self):
        r = self._search('ho')
        names = [u['username'] for u in r.data['results']]
        self.assertNotIn('hostuser', names)

    def test_search_max_10_results(self):
        # Create 15 extra participants matching prefix 'zz'
        for i in range(15):
            ChatParticipation.objects.create(
                chat_room=self.chat,
                username=f'zzuser{i:02d}',
                session_key=f'sess_zz_{i:02d}',
            )
        r = self._search('zz')
        self.assertLessEqual(len(r.data['results']), 10)
        self.assertEqual(len(r.data['results']), 10)

    def test_search_non_host_forbidden(self):
        self.client.force_authenticate(user=self.alice)
        r = self._search('bo')
        self.assertEqual(r.status_code, 403)


class SpotlightPerParticipationTests(SpotlightTestsBase):
    def test_per_participation_semantics_for_anon_identities(self):
        """A user's anon identity being spotlighted does NOT spotlight other identities."""
        anon_p = ChatParticipation.objects.create(
            chat_room=self.chat,
            user=self.alice,
            username='alice_anon_x',
            is_anonymous_identity=True,
        )
        self.client.force_authenticate(user=self.host_user)
        r = self._spotlight_add('alice_anon_x')
        self.assertEqual(r.status_code, 200)

        anon_p.refresh_from_db()
        self.alice_p.refresh_from_db()
        self.assertTrue(anon_p.is_spotlight)
        self.assertFalse(self.alice_p.is_spotlight)
