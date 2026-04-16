"""
Regression tests for the cache bugs fixed during the photo-room investigation
on 2026-04-15. Each test pins down a specific failure mode so it cannot return
silently.

Bugs covered:
1. voice_duration was a Decimal and json.dumps blew up, making add_message
   silently return False for any message that touched _serialize_message.
2. _fetch_from_db's inline serializer was missing photo_url, video_url,
   video_duration, video_thumbnail_url, is_highlight, gift_recipient,
   is_gift_acknowledged — so the Postgres fallback path stripped media.
3. _hydrate_media_index originally scanned the bounded msg_data hash and
   missed older media that had aged out of the recent-message window.
4. add_message swallowed every exception silently; bug #1 lived in the dark
   for that reason. Now logs at ERROR with a stack trace.
5. Highlight Room was sorted by created_at, so messages appeared in send-order
   rather than highlight-order. Score now uses highlighted_at.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.test import TransactionTestCase
from django.utils import timezone

from chats.models import Message
from chats.tests import cache_helpers, factories
from chats.utils.performance.cache import MessageCache


class VoiceDurationDecimalRegressionTest(TransactionTestCase):
    """Bug #1: voice_duration as Decimal made every add_message fail silently."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_voice_message_round_trips_through_cache(self):
        """A message with a non-null voice_duration (Decimal) must serialize,
        cache, and deserialize without raising. voice_duration comes back as
        float (the cache layer's chosen JSON-friendly representation)."""
        voice_msgs = factories.make_messages(
            self.room, count=1,
            mix=factories.MessageMix(voice_pct=100),
        )
        msg = voice_msgs[0]
        # Sanity check: the factory does carry a Decimal duration.
        self.assertIsInstance(msg.voice_duration, Decimal)

        result = MessageCache.add_message(msg)
        self.assertTrue(
            result,
            'add_message returned False — voice_duration Decimal serialization '
            'is broken again',
        )

        cached = MessageCache.get_messages(self.room.id, limit=10)
        self.assertEqual(len(cached), 1)
        self.assertIsNotNone(cached[0]['voice_duration'])
        self.assertIsInstance(
            cached[0]['voice_duration'], float,
            'voice_duration should round-trip as float, not as a Decimal or string',
        )
        # Approximately 6.73 (factory default), allow float wobble.
        self.assertAlmostEqual(cached[0]['voice_duration'], 6.73, places=2)


class FetchFromDbMediaFieldsRegressionTest(TransactionTestCase):
    """Bug #2: Postgres fallback inline serializer dropped media fields.

    Direct unit test of the serializer used in MessageListView._fetch_from_db
    is awkward because the method is heavily entangled with request context.
    Instead, test the canonical serializer (MessageCache._serialize_message)
    that fetch_from_db now delegates to: every required field must be present
    in its output for each media type.
    """

    REQUIRED_KEYS = {
        'photo_url', 'photo_width', 'photo_height',
        'video_url', 'video_duration', 'video_thumbnail_url',
        'video_width', 'video_height',
        'voice_url', 'voice_duration', 'voice_waveform',
        'is_highlight', 'gift_recipient', 'is_gift_acknowledged',
        'message_type', 'reply_to_id', 'reply_to_message',
    }

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def test_serializer_includes_all_required_fields_for_photo(self):
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(photo_pct=100),
        )
        data = MessageCache._serialize_message(msgs[0])
        missing = self.REQUIRED_KEYS - set(data.keys())
        self.assertFalse(
            missing,
            f'Serializer is missing keys for photo message: {missing}',
        )
        self.assertTrue(data['photo_url'])

    def test_serializer_includes_all_required_fields_for_video(self):
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(video_pct=100),
        )
        data = MessageCache._serialize_message(msgs[0])
        missing = self.REQUIRED_KEYS - set(data.keys())
        self.assertFalse(missing, f'Serializer missing keys for video: {missing}')
        self.assertTrue(data['video_url'])
        self.assertIsNotNone(data['video_duration'])
        self.assertTrue(data['video_thumbnail_url'])

    def test_serializer_includes_all_required_fields_for_voice(self):
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(voice_pct=100),
        )
        data = MessageCache._serialize_message(msgs[0])
        missing = self.REQUIRED_KEYS - set(data.keys())
        self.assertFalse(missing, f'Serializer missing keys for voice: {missing}')
        self.assertTrue(data['voice_url'])
        self.assertIsNotNone(data['voice_duration'])

    def test_serializer_includes_is_highlight_for_highlighted_message(self):
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(highlight_pct=100),
        )
        data = MessageCache._serialize_message(msgs[0])
        self.assertTrue(data['is_highlight'])


class HydrationFindsMessagesOutsideMsgDataTest(TransactionTestCase):
    """Bug #3: hydration scanned msg_data instead of Postgres, so older media
    that had aged out of the bounded recent-messages window was invisible
    to the photo/video/audio rooms.
    """

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_old_photos_outside_msg_data_window_appear_after_hydration(self):
        """Setup: 50 recent text messages + 10 photos all created earlier.
        Only the recent text lands in msg_data via normal cache writes.
        First call to get_photo_messages must hydrate from Postgres and
        return all 10 photos, regardless of whether they were in msg_data."""

        # 10 old photos, timestamps well before the recent text.
        old_start = timezone.now() - timedelta(days=2)
        factories.make_messages(
            self.room, count=10,
            mix=factories.MessageMix(photo_pct=100),
            start_time=old_start,
            step_seconds=60,
        )

        # 50 recent text messages, written through add_message so they
        # populate msg_data (simulating organic chat traffic).
        recent_start = timezone.now() - timedelta(minutes=10)
        recent_msgs = factories.make_messages(
            self.room, count=50,
            mix=factories.MessageMix(),  # 100% text
            start_time=recent_start,
            step_seconds=1,
        )
        for msg in recent_msgs:
            MessageCache.add_message(msg)

        # At this point msg_data has 50 entries (text), no photos.
        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['msg_data_size'], 50)
        self.assertEqual(snap['photo_index_size'], 0)

        # Photo room request triggers hydration — must return all 10 old photos.
        photos = MessageCache.get_photo_messages(self.room.id, limit=50)
        self.assertEqual(
            len(photos), 10,
            f'Expected 10 photos after hydration, got {len(photos)}. '
            'Hydration may be scanning msg_data again instead of Postgres.',
        )
        # Sanity: every returned message has a photo_url.
        for p in photos:
            self.assertTrue(p['photo_url'], f'Photo {p["id"]} missing photo_url')

    def test_hydration_is_idempotent(self):
        """A second call to get_photo_messages should NOT re-hydrate (the
        hydrated:{type} flag prevents redundant Postgres scans)."""
        factories.make_messages(
            self.room, count=5,
            mix=factories.MessageMix(photo_pct=100),
        )
        # First call hydrates.
        MessageCache.get_photo_messages(self.room.id)

        # Second call: count Postgres queries to confirm we don't re-scan.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            MessageCache.get_photo_messages(self.room.id)

        # The hydration query is the only Postgres hit it would make. After
        # the first hydration, subsequent calls should issue zero photo-lookup
        # queries against the Message table.
        photo_queries = [
            q for q in ctx.captured_queries
            if 'chats_message' in q['sql'].lower() and 'photo_url' in q['sql'].lower()
        ]
        self.assertEqual(
            len(photo_queries), 0,
            f'Hydration ran twice — found {len(photo_queries)} photo lookup queries',
        )


class AddMessageErrorLoggingRegressionTest(TransactionTestCase):
    """Bug #4: add_message swallowed every exception silently. Now must log
    at ERROR level with a stack trace so future serialization regressions
    are immediately visible.
    """

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_add_message_logs_at_error_when_serialization_fails(self):
        """Force a failure inside add_message and assert ERROR log is emitted
        with the exception class included."""

        msgs = factories.make_messages(self.room, count=1)
        msg = msgs[0]

        # Patch _serialize_message to raise so add_message's except block fires.
        import unittest.mock as mock

        with self.assertLogs(
            'chats.utils.performance.cache', level='ERROR'
        ) as log_ctx:
            with mock.patch.object(
                MessageCache, '_serialize_message',
                side_effect=ValueError('synthetic serialization failure'),
            ):
                result = MessageCache.add_message(msg)

        # add_message must still return False (don't crash on cache failure).
        self.assertFalse(result)

        # And it must have logged at ERROR with the exception class name.
        log_output = '\n'.join(log_ctx.output)
        self.assertIn('add_message failed', log_output)
        self.assertIn('ValueError', log_output)


class HydrationAndEvictionMonitoringTest(TransactionTestCase):
    """Phase 1 observability: monitor.log_hydration and monitor.log_eviction
    must fire on the relevant code paths."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_hydration_records_metric(self):
        from chats.utils.performance.monitoring import monitor

        factories.make_messages(
            self.room, count=3, mix=factories.MessageMix(photo_pct=100),
        )

        # Reset metrics to isolate this test's effect.
        monitor.reset_metrics()
        MessageCache.get_photo_messages(self.room.id)

        summary = monitor.get_metrics_summary()
        self.assertGreaterEqual(summary.get('hydration_count', 0), 1)

    def test_eviction_records_metric_when_cap_exceeded(self):
        """Force eviction by writing more than the cap, then assert the
        eviction metric fired at least once."""
        from constance import config
        from chats.utils.performance.monitoring import monitor

        # Lower the cap drastically so we can trigger eviction without writing
        # 5000 messages. Keep this isolated so it doesn't affect other tests.
        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 10

        try:
            msgs = factories.make_messages(
                self.room, count=15, mix=factories.MessageMix(),
            )
            monitor.reset_metrics()
            with cache_helpers.strict_cap_eviction():
                for msg in msgs:
                    MessageCache.add_message(msg)

            summary = monitor.get_metrics_summary()
            self.assertGreaterEqual(
                summary.get('eviction_count', 0), 1,
                'Eviction metric did not fire despite exceeding cap by 5 messages',
            )
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap


class HighlightRoomOrderingRegressionTest(TransactionTestCase):
    """Bug #5: Highlight Room must be ordered by highlighted_at (when the host
    starred the message), not by created_at (when it was originally sent).

    Reproduces the failure: send three messages M1, M2, M3 in chronological
    order. Then highlight in REVERSE order — M3 first, then M1, then M2.
    The Highlight Room must show M3, M1, M2 (highlight order), not M1, M2, M3
    (send order).
    """

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_highlight_index_score_uses_highlighted_at_via_add_message(self):
        """Direct path: when add_message sees an already-highlighted message,
        the highlight index ZADD score must be highlighted_at, not created_at."""
        # Three messages sent in order: M1 (oldest), M2, M3 (newest).
        msgs = factories.make_messages(self.room, count=3)
        m1, m2, m3 = msgs

        # Highlight in reverse: M3 first, then M1, then M2.
        from django.utils import timezone
        from datetime import timedelta
        base = timezone.now() + timedelta(hours=1)
        m3.is_highlight = True
        m3.highlighted_at = base
        m3.save(update_fields=['is_highlight', 'highlighted_at'])
        m1.is_highlight = True
        m1.highlighted_at = base + timedelta(seconds=10)
        m1.save(update_fields=['is_highlight', 'highlighted_at'])
        m2.is_highlight = True
        m2.highlighted_at = base + timedelta(seconds=20)
        m2.save(update_fields=['is_highlight', 'highlighted_at'])

        for m in (m3, m1, m2):
            MessageCache.add_message(m)

        # get_highlight_messages returns oldest-first by score = highlighted_at.
        # So we expect order: M3 (oldest highlight), M1, M2 (newest highlight).
        result = MessageCache.get_highlight_messages(self.room.id)
        result_ids = [r['id'] for r in result]
        expected = [str(m3.id), str(m1.id), str(m2.id)]
        self.assertEqual(
            result_ids, expected,
            'Highlight Room ordering must reflect highlighted_at, not created_at',
        )

    def test_highlight_index_score_uses_highlighted_at_via_toggle_path(self):
        """Toggle path: add a normal message via add_message, then highlight
        it via add_to_highlight_index (the host-toggle code path). The score
        must be highlighted_at."""
        msgs = factories.make_messages(self.room, count=2)
        m_old, m_new = msgs

        # Cache them as plain messages.
        for m in msgs:
            MessageCache.add_message(m)

        # Highlight m_new FIRST (it was sent last, but starred first).
        from django.utils import timezone
        from datetime import timedelta
        base = timezone.now() + timedelta(hours=1)
        m_new.is_highlight = True
        m_new.highlighted_at = base
        m_new.save(update_fields=['is_highlight', 'highlighted_at'])
        MessageCache.update_message(m_new)
        MessageCache.add_to_highlight_index(m_new)

        # Then highlight m_old (sent first, but starred second).
        m_old.is_highlight = True
        m_old.highlighted_at = base + timedelta(seconds=10)
        m_old.save(update_fields=['is_highlight', 'highlighted_at'])
        MessageCache.update_message(m_old)
        MessageCache.add_to_highlight_index(m_old)

        # Highlight room order: m_new first (highlighted earlier), then m_old.
        result = MessageCache.get_highlight_messages(self.room.id)
        result_ids = [r['id'] for r in result]
        self.assertEqual(
            result_ids, [str(m_new.id), str(m_old.id)],
            'add_to_highlight_index (toggle path) must score by highlighted_at',
        )

    def test_legacy_message_without_highlighted_at_falls_back_to_created_at(self):
        """Legacy data may have is_highlight=True but highlighted_at=None.
        Such messages should still appear in the highlight room, scored by
        created_at, rather than disappearing or crashing."""
        # Create a message with is_highlight=True but no highlighted_at.
        msgs = factories.make_messages(
            self.room, count=1, mix=factories.MessageMix(highlight_pct=100),
        )
        legacy = msgs[0]
        legacy.highlighted_at = None  # simulate legacy row
        legacy.save(update_fields=['highlighted_at'])

        # Should not raise and should still be retrievable.
        result = MessageCache.add_message(legacy)
        self.assertTrue(result, 'add_message must handle highlighted_at=None')

        highlights = MessageCache.get_highlight_messages(self.room.id)
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0]['id'], str(legacy.id))


class HighlightRoomNoDuplicatesRegressionTest(TransactionTestCase):
    """Bug: when the highlight cache index used `highlighted_at` as score but
    the partial-hit boundary in views.py used `created_at`, the DB query
    returned messages already in the cache → duplicate IDs in the response →
    React `Encountered two children with the same key` warning in MainChatView.

    Reproduces by creating highlights where `highlighted_at` differs from
    `created_at` (the realistic case — host highlights a message hours after
    it was sent).
    """

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_partial_hit_does_not_return_duplicate_message_ids(self):
        """Hit the API endpoint for the highlight room and assert no duplicate
        IDs in the response, in a setup that triggers partial-hit + boundary
        mismatch."""
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.test import APIClient

        # Build messages with highlighted_at ORDER different from created_at order.
        # M1 sent oldest, highlighted last.
        # M2 sent middle, highlighted first.
        # M3 sent newest, highlighted middle.
        msgs = factories.make_messages(self.room, count=3, step_seconds=60)
        m1, m2, m3 = msgs

        base_h = timezone.now() + timedelta(hours=1)
        m2.is_highlight = True
        m2.highlighted_at = base_h
        m2.save(update_fields=['is_highlight', 'highlighted_at'])

        m3.is_highlight = True
        m3.highlighted_at = base_h + timedelta(seconds=10)
        m3.save(update_fields=['is_highlight', 'highlighted_at'])

        m1.is_highlight = True
        m1.highlighted_at = base_h + timedelta(seconds=20)
        m1.save(update_fields=['is_highlight', 'highlighted_at'])

        # Add through the cache so highlight index gets populated with score = highlighted_at.
        for m in (m1, m2, m3):
            MessageCache.add_message(m)

        # Hit the view via the standard URL pattern. The test room's host has
        # a reserved_username (set by factories.make_user), which is the
        # `username` segment of the chat-specific URL.
        host_username = self.room.host.reserved_username
        client = APIClient()
        response = client.get(
            f'/api/chats/{host_username}/{self.room.code}/messages/?filter=highlight&limit=50',
        )
        self.assertEqual(response.status_code, 200, response.content[:500])

        ids = [m['id'] for m in response.json()['messages']]
        from collections import Counter
        dupes = {k: v for k, v in Counter(ids).items() if v > 1}
        self.assertEqual(
            dupes, {},
            f'Highlight room API returned duplicate IDs: {dupes}',
        )
