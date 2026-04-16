"""
Phase 4 tests: batch eviction.

Trim only fires when the timeline exceeds `cap + EVICTION_BATCH_SIZE`, then
evicts a batch at once. Tests cover:
- Sub-threshold overflow does NOT trim (cache may exceed cap by up to batch_size).
- At-threshold overflow DOES trim, bringing the cache back to cap.
- Protected messages still survive the batched eviction.
- Force-eviction still works under saturation.
- Eviction operations are pipelined into ≤ a small number of round-trips.
"""

from __future__ import annotations

from constance import config
from django.test import TransactionTestCase

from chats.tests import cache_helpers, factories
from chats.utils.performance.cache import MessageCache


class BatchEvictionThresholdTest(TransactionTestCase):
    """Trim triggers only when total > cap + EVICTION_BATCH_SIZE."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()
        self._original_cap = config.REDIS_CACHE_MAX_COUNT

    def tearDown(self):
        config.REDIS_CACHE_MAX_COUNT = self._original_cap
        cache_helpers.flush_cache()

    def test_overflow_below_batch_size_does_not_trim(self):
        """cap=10, batch=100. Add 50 messages — well over cap but under
        cap+batch — no eviction should fire. Cache holds all 50."""
        config.REDIS_CACHE_MAX_COUNT = 10
        # batch is a class constant (100); 10 + 100 = 110 trim threshold

        msgs = factories.make_messages(self.room, count=50)
        for m in msgs:
            MessageCache.add_message(m)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(
            snap['timeline_size'], 50,
            'Timeline trimmed prematurely — batch threshold should have prevented this',
        )

    def test_overflow_at_batch_threshold_triggers_trim(self):
        """cap=10, batch=100. Add 111 messages (cap + batch + 1). Trim fires
        and brings cache back down to cap (10)."""
        config.REDIS_CACHE_MAX_COUNT = 10

        msgs = factories.make_messages(self.room, count=111)
        for m in msgs:
            MessageCache.add_message(m)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(
            snap['timeline_size'], 10,
            'Trim did not bring cache back down to cap',
        )

    def test_overflow_grows_until_threshold_then_collapses(self):
        """Watch the timeline size grow past cap and only collapse when batch
        threshold is crossed. Confirms the staircase pattern, not a smooth trim."""
        config.REDIS_CACHE_MAX_COUNT = 10
        msgs = factories.make_messages(self.room, count=120)

        # Add up to cap (10) — timeline = 10.
        for m in msgs[:10]:
            MessageCache.add_message(m)
        self.assertEqual(cache_helpers.inspect_room(self.room.id)['timeline_size'], 10)

        # Add up to cap + batch (110) — still no trim, timeline grows.
        for m in msgs[10:110]:
            MessageCache.add_message(m)
        self.assertEqual(
            cache_helpers.inspect_room(self.room.id)['timeline_size'], 110,
            'Cache should grow up to cap+batch_size before trimming',
        )

        # Add 1 more — crosses threshold, trim fires, back down to cap.
        MessageCache.add_message(msgs[110])
        self.assertEqual(
            cache_helpers.inspect_room(self.room.id)['timeline_size'], 10,
            'Crossing threshold should trim back to cap',
        )


class BatchEvictionProtectionTest(TransactionTestCase):
    """Batch eviction must still respect protection."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()
        self._original_cap = config.REDIS_CACHE_MAX_COUNT

    def tearDown(self):
        config.REDIS_CACHE_MAX_COUNT = self._original_cap
        cache_helpers.flush_cache()

    def test_protected_media_survives_batch_eviction(self):
        """cap=10, batch=100. 5 photos + 106 text crosses threshold (cap+batch=110).
        After trim fires: overflow = 111 - 10 = 101 evictions, all 5 photos
        survive (protected), and we end up at exactly cap (10)."""
        config.REDIS_CACHE_MAX_COUNT = 10

        photos = factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(photo_pct=100),
        )
        # 106 text messages timestamped AFTER the photos so eviction sees the
        # photos as oldest candidates. 5 + 106 = 111, just over threshold (110).
        from datetime import timedelta
        from django.utils import timezone
        text_start = timezone.now() + timedelta(minutes=5)
        texts = factories.make_messages(
            self.room, count=106, start_time=text_start,
        )

        for m in photos + texts:
            MessageCache.add_message(m)

        snap = cache_helpers.inspect_room(self.room.id)
        # Trim brings us back down to cap (10) — overflow=101 was evicted.
        self.assertEqual(snap['timeline_size'], 10)
        self.assertEqual(
            snap['photo_index_size'], 5,
            'Photos were evicted by batch eviction despite being protected',
        )

        data_ids = set(cache_helpers.msg_data_ids(self.room.id))
        for p in photos:
            self.assertIn(str(p.id), data_ids)

    def test_force_eviction_still_works_for_all_protected(self):
        """cap=5, batch=100. Add 106 photos (all protected) — just over
        threshold. Once trim fires, force-eviction must take oldest photos
        to bring cache back to cap (5)."""
        config.REDIS_CACHE_MAX_COUNT = 5

        photos = factories.make_messages(
            self.room, count=106, mix=factories.MessageMix(photo_pct=100),
        )
        for m in photos:
            MessageCache.add_message(m)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(
            snap['timeline_size'], 5,
            'Force eviction did not enforce cap when all messages are protected',
        )
        # The 5 NEWEST photos must survive.
        data_ids = set(cache_helpers.msg_data_ids(self.room.id))
        for p in photos[-5:]:
            self.assertIn(str(p.id), data_ids, f'Newest photo {p.id} missing')
        for p in photos[:-5]:
            self.assertNotIn(str(p.id), data_ids, f'Old photo {p.id} should be evicted')

    def test_size_never_exceeds_cap_plus_batch(self):
        """Invariant: at all times, timeline_size <= cap + batch_size.
        This is the formal contract of the batched semantics."""
        config.REDIS_CACHE_MAX_COUNT = 10
        ceiling = 10 + MessageCache.EVICTION_BATCH_SIZE

        msgs = factories.make_messages(self.room, count=300)
        max_seen = 0
        for m in msgs:
            MessageCache.add_message(m)
            size = cache_helpers.inspect_room(self.room.id)['timeline_size']
            max_seen = max(max_seen, size)
            self.assertLessEqual(
                size, ceiling,
                f'Cache reached size {size}, exceeding cap+batch={ceiling}',
            )

        # And we should have actually exercised the boundary at some point.
        self.assertGreater(
            max_seen, 10,
            'Test never exercised over-cap behavior — too few writes',
        )


class BatchEvictionPerformanceTest(TransactionTestCase):
    """The point of batching: eviction work happens once per batch, not once
    per message. Asserts the trim path issues at most a small number of
    round-trips even when evicting 100 messages at once."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()
        self._original_cap = config.REDIS_CACHE_MAX_COUNT

    def tearDown(self):
        config.REDIS_CACHE_MAX_COUNT = self._original_cap
        cache_helpers.flush_cache()

    def test_batch_eviction_uses_few_round_trips(self):
        """Fill cache to threshold, then add one more to trigger batch trim.
        The triggering write should issue at most ~5 RTTs (add pipeline +
        ZCARD + SMEMBERS protected + SMEMBERS registry + eviction pipeline)."""
        config.REDIS_CACHE_MAX_COUNT = 10

        # Pre-fill to 110 (cap + batch). No trim has fired yet.
        msgs = factories.make_messages(self.room, count=111)
        for m in msgs[:110]:
            MessageCache.add_message(m)

        # The 111th add will push us over threshold — trim fires.
        with cache_helpers.count_redis_rtts() as rtts:
            MessageCache.add_message(msgs[110])

        # Budget: 1 add_message pipeline + 1 ZCARD + 1 ZRANGE + 1 SMEMBERS
        # protected + 1 SMEMBERS registry + 1 eviction pipeline = ~6 RTTs.
        # Allow some headroom.
        self.assertLessEqual(
            rtts.rtt_count, 10,
            f'Batch trim used {rtts.rtt_count} round-trips — too many',
        )
