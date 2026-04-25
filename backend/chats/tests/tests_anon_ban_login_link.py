"""
Tests for ban-evasion prevention when an anonymous-banned user logs in.

Scenario the fix protects against:
  1. User joins a chat anonymously, gets banned. ChatBlock has
     blocked_user=NULL (anon had no User FK at the time of ban).
  2. User logs in to a registered account from the same browser session.
  3. /my-participation/ refuses to claim the banned session-anon. Without
     the fix, the registered identity (different username, no user-account
     ban) would be free to post — escaping the ban.
  4. Fix: when the claim is refused due to a ban that matches this session,
     back-fill blocked_user on the matching ChatBlock so the ban now
     applies to the user's account in this chat.
"""

import allure
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from chats.models import ChatRoom, ChatParticipation, ChatBlock

User = get_user_model()


@allure.feature('User Blocking')
@allure.story('Anon ban survives login')
class AnonBanSurvivesLoginTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email='host@test.com',
            password='hostpass123',
            reserved_username='HostUser',
        )
        self.chat_room = ChatRoom.objects.create(
            host=self.host,
            code='ABCDEF',
            access_mode=ChatRoom.ACCESS_PUBLIC,
        )
        self.host_participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            is_anonymous_identity=False,
        )
        self.robert = User.objects.create_user(
            email='robert@test.com',
            password='robpass123',
            reserved_username='Robert',
        )
        self.url = f'/api/chats/HostUser/{self.chat_room.code}/my-participation/'

    def _establish_session(self, client):
        """Make a request to populate Django's session, return session_key."""
        client.get(self.url)
        return client.session.session_key

    def test_blocked_user_backfilled_when_banned_anon_session_logs_in(self):
        """When a session-anon is banned and the same session later logs in,
        the matching ChatBlock should back-fill blocked_user so the ban
        applies to the user's account in this chat."""
        client = APIClient()
        session_key = self._establish_session(client)

        # Anon participation in this session.
        anon = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='BetaAnvil244',
            session_key=session_key,
            fingerprint='fp-xyz',
            ip_address='127.0.0.1',
            is_anonymous_identity=False,
        )

        # Ban created when the anon had no user FK.
        block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=anon.username.lower(),
            blocked_user=None,
            blocked_session_key=session_key,
            blocked_fingerprint=anon.fingerprint,
            blocked_ip_address=anon.ip_address,
            ban_tier=ChatBlock.BAN_TIER_SESSION,
            blocked_by=self.host_participation,
        )

        # Same session now logs in as Robert and hits /my-participation/.
        client.force_authenticate(user=self.robert)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # ChatBlock should now have blocked_user=Robert.
        block.refresh_from_db()
        self.assertEqual(
            block.blocked_user_id, self.robert.id,
            "blocked_user should be back-filled with the logged-in user "
            "so the ban applies to the user's account."
        )

    def test_other_users_unaffected(self):
        """Back-fill must only touch ban rows tied to THIS session, not
        unrelated bans for other anons."""
        client = APIClient()
        my_session_key = self._establish_session(client)

        my_anon = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='BetaAnvil244',
            session_key=my_session_key,
            fingerprint='fp-mine',
            ip_address='127.0.0.1',
            is_anonymous_identity=False,
        )
        my_block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=my_anon.username.lower(),
            blocked_user=None,
            blocked_session_key=my_session_key,
            blocked_fingerprint=my_anon.fingerprint,
            blocked_ip_address=my_anon.ip_address,
            ban_tier=ChatBlock.BAN_TIER_SESSION,
            blocked_by=self.host_participation,
        )

        # An unrelated banned anon on a totally different session.
        unrelated_anon = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='OtherAnon999',
            session_key='session-other',
            fingerprint='fp-other',
            ip_address='10.0.0.1',
            is_anonymous_identity=False,
        )
        unrelated_block = ChatBlock.objects.create(
            chat_room=self.chat_room,
            blocked_username=unrelated_anon.username.lower(),
            blocked_user=None,
            blocked_session_key=unrelated_anon.session_key,
            blocked_fingerprint=unrelated_anon.fingerprint,
            blocked_ip_address=unrelated_anon.ip_address,
            ban_tier=ChatBlock.BAN_TIER_SESSION,
            blocked_by=self.host_participation,
        )

        client.force_authenticate(user=self.robert)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        my_block.refresh_from_db()
        unrelated_block.refresh_from_db()
        self.assertEqual(my_block.blocked_user_id, self.robert.id,
                         "Robert's own banned anon should back-fill to Robert.")
        self.assertIsNone(unrelated_block.blocked_user_id,
                          "An unrelated banned anon must NOT be back-filled.")

    def test_unbanned_anon_is_still_claimed_normally(self):
        """Sanity check — the back-fill only fires for banned anons; clean
        anons still get linked to the user as before."""
        client = APIClient()
        session_key = self._establish_session(client)

        anon = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=None,
            username='HappyClover12',
            session_key=session_key,
            fingerprint='fp-clean',
            ip_address='127.0.0.1',
            is_anonymous_identity=False,
        )

        client.force_authenticate(user=self.robert)
        resp = client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        anon.refresh_from_db()
        self.assertEqual(anon.user_id, self.robert.id, "Clean anon should be claimed.")
        self.assertTrue(anon.is_anonymous_identity, "Claimed anon should be flagged as anonymous identity.")
