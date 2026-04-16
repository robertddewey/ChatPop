"""
Smoke tests for chats.tests.factories and chats.tests.cache_helpers.

These are infrastructure tests — they validate the test utilities themselves,
not production code. If these fail, every other test that uses the factories
is probably broken too.
"""

from __future__ import annotations

import time

from django.test import TransactionTestCase

from chats.models import ChatParticipation, ChatRoom, Message
from chats.tests import cache_helpers, factories


class FactoryBasicsTest(TransactionTestCase):
    """Single-row builders return valid, persisted objects."""

    def test_make_user_persists_and_sets_defaults(self):
        user = factories.make_user()
        self.assertIsNotNone(user.id)
        self.assertTrue(user.email.endswith('@example.com'))
        self.assertTrue(user.reserved_username.startswith('User'))

    def test_make_room_creates_host_implicitly(self):
        room = factories.make_room()
        self.assertIsNotNone(room.id)
        self.assertIsNotNone(room.host)
        self.assertEqual(room.access_mode, 'public')

    def test_make_room_with_explicit_host(self):
        host = factories.make_user(reserved_username='HostUser')
        room = factories.make_room(host=host, name='Custom Name')
        self.assertEqual(room.host, host)
        self.assertEqual(room.name, 'Custom Name')

    def test_make_participation_links_to_user(self):
        user = factories.make_user(reserved_username='Alice')
        room = factories.make_room(host=user)
        p = factories.make_participation(room, 'Alice', user=user)
        self.assertEqual(p.chat_room, room)
        self.assertEqual(p.username, 'Alice')
        self.assertEqual(p.user, user)
        self.assertFalse(p.is_spotlight)


class MakeMessagesTest(TransactionTestCase):
    """Bulk message builder: counts, ordering, type distribution."""

    def setUp(self):
        self.room = factories.make_room()

    def test_empty_count_returns_empty_list(self):
        result = factories.make_messages(self.room, count=0)
        self.assertEqual(result, [])
        self.assertEqual(Message.objects.filter(chat_room=self.room).count(), 0)

    def test_count_matches_db(self):
        factories.make_messages(self.room, count=25)
        self.assertEqual(Message.objects.filter(chat_room=self.room).count(), 25)

    def test_timestamps_are_monotonically_increasing(self):
        msgs = factories.make_messages(self.room, count=10, step_seconds=1)
        persisted = list(
            Message.objects.filter(chat_room=self.room).order_by('created_at')
        )
        self.assertEqual(len(persisted), 10)
        for i in range(1, len(persisted)):
            self.assertGreater(persisted[i].created_at, persisted[i - 1].created_at)

    def test_mix_produces_expected_type_distribution(self):
        # 100 messages with 10% photo, 5% video, 5% voice, 5% gift, 5% highlight
        mix = factories.MessageMix(
            photo_pct=10, video_pct=5, voice_pct=5, gift_pct=5, highlight_pct=5,
        )
        msgs = factories.make_messages(self.room, count=100, mix=mix)
        counts = factories.count_by_kind(msgs)

        # Deterministic walking-modulo distribution, so counts are exact.
        self.assertEqual(counts['photo'], 10)
        self.assertEqual(counts['video'], 5)
        self.assertEqual(counts['voice'], 5)
        self.assertEqual(counts['gift'], 5)
        self.assertEqual(counts['highlight'], 5)
        self.assertEqual(counts['text'], 70)

    def test_photo_kind_sets_photo_fields(self):
        mix = factories.MessageMix(photo_pct=100)
        msgs = factories.make_messages(self.room, count=3, mix=mix)
        for m in msgs:
            self.assertTrue(m.photo_url)
            self.assertEqual(m.photo_width, 1080)
            self.assertIsNone(m.voice_url)
            self.assertEqual(m.message_type, 'normal')

    def test_voice_kind_includes_decimal_duration(self):
        """Regression guard for the voice_duration Decimal serialization bug.
        Voice messages MUST carry a Decimal duration so tests that exercise
        _serialize_message actually cover the Decimal path."""
        from decimal import Decimal

        mix = factories.MessageMix(voice_pct=100)
        msgs = factories.make_messages(self.room, count=2, mix=mix)
        for m in msgs:
            self.assertTrue(m.voice_url)
            self.assertIsInstance(m.voice_duration, Decimal)

    def test_mix_rejects_over_100_percent(self):
        with self.assertRaises(ValueError):
            factories.MessageMix(photo_pct=60, video_pct=60)

    def test_bulk_creation_is_fast(self):
        """Target per plan: seed 5000 messages in <3 seconds on local hardware.
        This is a performance guard — if someone accidentally removes bulk_create
        or adds a per-row signal, this test catches it.
        """
        start = time.time()
        factories.make_messages(self.room, count=5000)
        elapsed = time.time() - start
        self.assertLess(
            elapsed, 5.0,
            f'make_messages(count=5000) took {elapsed:.2f}s — factories are no longer bulk'
        )
        self.assertEqual(Message.objects.filter(chat_room=self.room).count(), 5000)


class CacheHelpersTest(TransactionTestCase):
    """Smoke-test the cache inspection helpers against a known room state."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_inspect_empty_room(self):
        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['timeline_size'], 0)
        self.assertEqual(snap['msg_data_size'], 0)

    def test_inspect_after_writes(self):
        msgs = factories.make_messages(
            self.room, count=5,
            mix=factories.MessageMix(photo_pct=40),  # 2 of 5 photos
        )
        cache_helpers.hydrate_room(self.room.id, msgs)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['timeline_size'], 5)
        self.assertEqual(snap['msg_data_size'], 5)
        self.assertEqual(snap['photo_index_size'], 2)

    def test_assert_indexes_consistent_passes_on_healthy_room(self):
        msgs = factories.make_messages(
            self.room, count=10,
            mix=factories.MessageMix(photo_pct=20, highlight_pct=10),
        )
        cache_helpers.hydrate_room(self.room.id, msgs)
        # Should not raise.
        cache_helpers.assert_indexes_consistent(self.room.id)

    def test_assert_indexes_consistent_detects_orphan(self):
        """Manually corrupt the state: ZADD an index key with a msg_id that
        isn't in msg_data. The consistency check should fail."""
        from chats.utils.performance.cache import MessageCache

        client = cache_helpers.redis_client()
        bad_key = MessageCache.PHOTO_INDEX_KEY.format(room_id=str(self.room.id))
        client.zadd(bad_key, {'nonexistent-id': 1234567890.0})

        with self.assertRaises(AssertionError) as ctx:
            cache_helpers.assert_indexes_consistent(self.room.id)
        self.assertIn('PHOTO_INDEX_KEY', str(ctx.exception))

    def test_count_redis_ops_tallies_commands(self):
        from chats.utils.performance.cache import MessageCache

        msgs = factories.make_messages(self.room, count=1)
        with cache_helpers.count_redis_ops() as counter:
            MessageCache.add_message(msgs[0])
        # add_message uses a pipeline with HSET + EXPIRE + ZADD + EXPIRE + focus index ops.
        # Exact count depends on message fields, but it should be clearly > 0.
        self.assertGreater(counter.total(), 0)

    def test_count_redis_rtts_distinguishes_pipelined_from_standalone(self):
        """A single pipeline of N commands should count as 1 RTT, not N."""
        client = cache_helpers.redis_client()
        with cache_helpers.count_redis_rtts() as rtts:
            pipe = client.pipeline()
            for i in range(10):
                pipe.set(f'test_key_{i}', i)
            pipe.execute()
        # 10 commands, 1 pipeline.execute() = 1 RTT
        self.assertEqual(rtts.rtt_count, 1)
