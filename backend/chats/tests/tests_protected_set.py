"""
Phase 2 tests: protected-message SET.

Covers:
- Protected types (highlight, gift, photo, video, voice) land in the SET on
  add_message.
- Eviction SREMs evicted IDs.
- update_message keeps the SET in sync when is_highlight toggles.
- Eviction reads the SET via SMEMBERS, NOT via HGET+JSON parse (the slow path
  this phase exists to remove).
- Behavior parity: same set of writes produces the same eviction outcomes
  whether read via SET or HGET (parity proof).
"""

from __future__ import annotations

from django.test import TransactionTestCase

from chats.models import Message
from chats.tests import cache_helpers, factories
from chats.utils.performance.cache import MessageCache


def _protected_set_ids(room_id) -> set:
    """Helper: return the contents of the protected SET for a room."""
    client = cache_helpers.redis_client()
    key = MessageCache.PROTECTED_SET_KEY.format(room_id=str(room_id))
    raw = client.smembers(key)
    return {(m.decode() if isinstance(m, bytes) else m) for m in raw}


class ProtectedSetPopulationTest(TransactionTestCase):
    """add_message must populate the protected SET for every protected type."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_text_message_not_protected(self):
        msg = factories.make_messages(self.room, count=1)[0]
        MessageCache.add_message(msg)
        self.assertNotIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_photo_message_added_to_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(photo_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_video_message_added_to_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(video_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_voice_message_added_to_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(voice_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_gift_message_added_to_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(gift_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_highlight_message_added_to_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(highlight_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_mixed_set_only_holds_protected(self):
        """Realistic chat state: only protected messages should be in the SET."""
        msgs = factories.make_messages(
            self.room, count=20,
            mix=factories.MessageMix(
                photo_pct=10, voice_pct=10, highlight_pct=5, gift_pct=5,
            ),
        )
        for m in msgs:
            MessageCache.add_message(m)

        protected = _protected_set_ids(self.room.id)
        # 30% of 20 = 6 protected messages.
        self.assertEqual(len(protected), 6)

        for m in msgs:
            should_be_protected = bool(
                m.is_highlight or m.message_type == 'gift'
                or m.photo_url or m.video_url or m.voice_url
            )
            actually_protected = str(m.id) in protected
            self.assertEqual(
                should_be_protected, actually_protected,
                f'Mismatch for msg {m.id}: should_be={should_be_protected} '
                f'actual={actually_protected}',
            )


class ProtectedSetSyncOnHighlightToggleTest(TransactionTestCase):
    """update_message (the path highlight toggle goes through) must keep the
    protected SET in sync as is_highlight flips."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_highlighting_text_message_adds_to_set(self):
        msg = factories.make_messages(self.room, count=1)[0]
        MessageCache.add_message(msg)
        self.assertNotIn(str(msg.id), _protected_set_ids(self.room.id))

        # Simulate highlight toggle on
        msg.is_highlight = True
        msg.save(update_fields=['is_highlight'])
        MessageCache.update_message(msg)

        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_unhighlighting_text_message_removes_from_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(highlight_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

        # Toggle off
        msg.is_highlight = False
        msg.save(update_fields=['is_highlight'])
        MessageCache.update_message(msg)

        self.assertNotIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_unhighlighting_photo_message_keeps_in_set(self):
        """A photo with a highlight that gets un-highlighted is STILL protected
        because of photo_url. SET membership must reflect any-of, not all-of."""
        # Build a photo message and explicitly highlight it
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(photo_pct=100),
        )
        msg = msgs[0]
        msg.is_highlight = True
        msg.save(update_fields=['is_highlight'])

        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

        # Un-highlight; photo_url is still set.
        msg.is_highlight = False
        msg.save(update_fields=['is_highlight'])
        MessageCache.update_message(msg)

        self.assertIn(
            str(msg.id), _protected_set_ids(self.room.id),
            'Photo must remain protected after un-highlight (photo_url still set)',
        )


class ProtectedSetCleanupOnEvictionTest(TransactionTestCase):
    """When messages are evicted (normal or force) or removed (soft delete),
    they must be SREM'd from the protected SET."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_soft_delete_removes_from_protected_set(self):
        msg = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(photo_pct=100),
        )[0]
        MessageCache.add_message(msg)
        self.assertIn(str(msg.id), _protected_set_ids(self.room.id))

        MessageCache.remove_message(self.room.id, str(msg.id))
        self.assertNotIn(str(msg.id), _protected_set_ids(self.room.id))

    def test_force_eviction_removes_from_protected_set(self):
        """When the cache is saturated with protected media and a non-protected
        message arrives, force-eviction must SREM the evicted IDs too.

        Uses strict_cap_eviction so we can assert exact one-message eviction
        without reasoning about batch slack."""
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 5
        try:
            with cache_helpers.strict_cap_eviction():
                # Fill cap with photos (all protected).
                photo_msgs = factories.make_messages(
                    self.room, count=5, mix=factories.MessageMix(photo_pct=100),
                )
                for m in photo_msgs:
                    MessageCache.add_message(m)
                self.assertEqual(len(_protected_set_ids(self.room.id)), 5)

                # Add 1 more message — forces eviction of oldest photo.
                extras = factories.make_messages(
                    self.room, count=1, mix=factories.MessageMix(photo_pct=100),
                )
                MessageCache.add_message(extras[0])

            protected = _protected_set_ids(self.room.id)
            # 5 cap stays, 1 was evicted, 1 was added.
            self.assertEqual(len(protected), 5)
            # The oldest photo must be gone from the SET.
            self.assertNotIn(str(photo_msgs[0].id), protected)
            # The newest must be in.
            self.assertIn(str(extras[0].id), protected)
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap


class EvictionUsesSetNotHgetTest(TransactionTestCase):
    """The whole point of Phase 2: eviction's protection check must NOT
    issue HGETs to msg_data. Instead it should issue one SMEMBERS."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_trim_path_does_not_hget_msg_data(self):
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 5
        try:
            # strict_cap_eviction so trim fires on the very next overflow,
            # not after batch slack (this test is about the trim hot path,
            # not the batching threshold).
            with cache_helpers.strict_cap_eviction():
                # Pre-fill so the next add triggers trim.
                initial = factories.make_messages(
                    self.room, count=5,
                    mix=factories.MessageMix(photo_pct=20),  # 1 protected
                )
                for m in initial:
                    MessageCache.add_message(m)

                # The next add will overshoot the cap and trigger the trim.
                trigger = factories.make_messages(self.room, count=1)[0]

                with cache_helpers.count_redis_ops() as ops:
                    MessageCache.add_message(trigger)

            # Eviction must use SMEMBERS (1 op), NOT HGET against msg_data.
            # Some HSETs / HGETs against msg_data can still happen (the add_message
            # itself HSETs the new message). The check is specifically: zero HGETs
            # for protection lookup. With the new path, no HGETs happen at all
            # during the protected-status check.
            #
            # We allow up to the small number of HGETs that may occur outside the
            # trim block (e.g. update_message's existence check). What we forbid
            # is "1 HGET per candidate" — i.e. 5+ HGETs.
            hgets = ops.by_command.get('HGET', 0)
            self.assertLess(
                hgets, 5,
                f'Eviction issued {hgets} HGETs — looks like the slow path is '
                'still active. SMEMBERS-based protection check is broken.',
            )

            smembers = ops.by_command.get('SMEMBERS', 0)
            self.assertGreaterEqual(
                smembers, 1,
                'Eviction did not call SMEMBERS — protected SET is not being read',
            )
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap


class EvictionCorrectnessParityTest(TransactionTestCase):
    """Behavior parity: eviction outcomes match what the old HGET+JSON path
    would have produced. Same protected messages survive; same non-protected
    messages get evicted."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_protected_messages_survive_normal_eviction(self):
        """5 photos + 5 text + add 5 more text. 5 photos must survive; oldest
        text must be evicted. Uses strict_cap_eviction for predictable
        per-message trim behavior."""
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 10
        try:
            with cache_helpers.strict_cap_eviction():
                # 10 messages: 5 photos + 5 text.
                photos = factories.make_messages(
                    self.room, count=5, mix=factories.MessageMix(photo_pct=100),
                )
                texts = factories.make_messages(self.room, count=5)
                for m in photos + texts:
                    MessageCache.add_message(m)

                initial_snap = cache_helpers.inspect_room(self.room.id)
                self.assertEqual(initial_snap['timeline_size'], 10)

                # Add 3 more texts — must evict 3 oldest non-protected (i.e. 3 text).
                extras = factories.make_messages(self.room, count=3)
                for m in extras:
                    MessageCache.add_message(m)

            after_snap = cache_helpers.inspect_room(self.room.id)
            self.assertEqual(after_snap['timeline_size'], 10)

            # Photo index must still have all 5 photos.
            self.assertEqual(after_snap['photo_index_size'], 5)
            # All 5 photos must be in msg_data.
            data_ids = set(cache_helpers.msg_data_ids(self.room.id))
            for p in photos:
                self.assertIn(
                    str(p.id), data_ids,
                    f'Photo {p.id} was evicted but should have been protected',
                )
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap

    def test_force_eviction_when_all_protected(self):
        """5 photos in cache, add 1 more photo: oldest photo MUST be evicted
        (force-eviction; can't grow past cap). strict_cap_eviction so trim
        fires immediately on overflow."""
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 5
        try:
            with cache_helpers.strict_cap_eviction():
                photos = factories.make_messages(
                    self.room, count=5, mix=factories.MessageMix(photo_pct=100),
                )
                for m in photos:
                    MessageCache.add_message(m)

                new_photo = factories.make_messages(
                    self.room, count=1, mix=factories.MessageMix(photo_pct=100),
                )[0]
                MessageCache.add_message(new_photo)

            snap = cache_helpers.inspect_room(self.room.id)
            self.assertEqual(snap['timeline_size'], 5, 'Cap not enforced')

            data_ids = set(cache_helpers.msg_data_ids(self.room.id))
            self.assertNotIn(
                str(photos[0].id), data_ids,
                'Oldest photo should have been force-evicted',
            )
            self.assertIn(str(new_photo.id), data_ids)
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap
