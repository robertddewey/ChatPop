"""
Tests for RoomNotificationCache — per-room "has new content" indicators.

Covers the visited-gate semantics: a user only sees a notification marker for
a room after they have visited it at least once AND new content has since
arrived. New joiners do not see markers for rooms they have never opened.
"""

import uuid
from django.test import TransactionTestCase
from django.core.cache import cache
from chats.utils.performance.cache import RoomNotificationCache
import allure


@allure.feature('Room Notifications')
@allure.story('Visited-gated unseen markers')
class RoomNotificationCacheTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.room_id = str(uuid.uuid4())
        self.alice = str(uuid.uuid4())
        self.bob = str(uuid.uuid4())
        self.carol = str(uuid.uuid4())

    def tearDown(self):
        cache.clear()

    def test_new_user_sees_no_markers_with_prior_activity(self):
        """A user who has never visited any room sees no markers, even if
        prior activity has populated the seen sets for other users."""
        # Bob and others have existing activity in every FAB room
        for room_type in RoomNotificationCache.FAB_ROOMS:
            RoomNotificationCache.mark_new_content(self.room_id, room_type, actor_user_id=self.bob)

        # Carol joins fresh and has never opened any room
        result = RoomNotificationCache.has_unseen(self.room_id, self.carol)
        self.assertEqual(result, {rt: False for rt in RoomNotificationCache.FAB_ROOMS})

    def test_visited_then_new_content_shows_marker(self):
        """After visiting a room, a subsequent new message triggers a marker."""
        RoomNotificationCache.mark_seen(self.room_id, 'photo', self.alice)
        RoomNotificationCache.mark_new_content(self.room_id, 'photo', actor_user_id=self.bob)

        result = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('photo',))
        self.assertTrue(result['photo'])

    def test_visited_without_new_content_no_marker(self):
        """Visiting a room with no subsequent activity shows no marker."""
        RoomNotificationCache.mark_seen(self.room_id, 'photo', self.alice)

        result = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('photo',))
        self.assertFalse(result['photo'])

    def test_never_visited_new_content_still_no_marker(self):
        """New content in a room a user has never visited does NOT show a marker."""
        RoomNotificationCache.mark_new_content(self.room_id, 'video', actor_user_id=self.bob)

        result = RoomNotificationCache.has_unseen(self.room_id, self.carol, room_types=('video',))
        self.assertFalse(result['video'])

    def test_actor_does_not_see_own_marker(self):
        """The sender of new content is in the seen set and gets no marker,
        regardless of visited state."""
        RoomNotificationCache.mark_seen(self.room_id, 'gifts', self.bob)
        RoomNotificationCache.mark_new_content(self.room_id, 'gifts', actor_user_id=self.bob)

        result = RoomNotificationCache.has_unseen(self.room_id, self.bob, room_types=('gifts',))
        self.assertFalse(result['gifts'])

    def test_reopening_room_clears_marker(self):
        """Opening a room after new content clears that room's marker."""
        RoomNotificationCache.mark_seen(self.room_id, 'focus', self.alice)
        RoomNotificationCache.mark_new_content(self.room_id, 'focus', actor_user_id=self.bob)
        # Alice has a marker here
        pre = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('focus',))
        self.assertTrue(pre['focus'])

        # Alice opens focus again
        RoomNotificationCache.mark_seen(self.room_id, 'focus', self.alice)
        post = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('focus',))
        self.assertFalse(post['focus'])

    def test_mixed_rooms_only_visited_show_markers(self):
        """A user who has visited some rooms but not others: new content in
        both rooms only produces a marker for the visited one."""
        RoomNotificationCache.mark_seen(self.room_id, 'photo', self.alice)
        # Alice has NOT visited 'video'
        RoomNotificationCache.mark_new_content(self.room_id, 'photo', actor_user_id=self.bob)
        RoomNotificationCache.mark_new_content(self.room_id, 'video', actor_user_id=self.bob)

        result = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('photo', 'video'))
        self.assertTrue(result['photo'])
        self.assertFalse(result['video'])

    def test_visited_set_persists_across_new_content(self):
        """mark_new_content must not wipe the visited set — otherwise a user
        who visited a room would stop getting markers after activity there."""
        RoomNotificationCache.mark_seen(self.room_id, 'audio', self.alice)
        # Multiple rounds of new content
        for _ in range(3):
            RoomNotificationCache.mark_new_content(self.room_id, 'audio', actor_user_id=self.bob)

        result = RoomNotificationCache.has_unseen(self.room_id, self.alice, room_types=('audio',))
        self.assertTrue(result['audio'])
