"""
Phase 5 tests: bulk-pipelined hydration.

The hydration path used to call `add_message` once per matching Postgres row,
each its own round-trip. For 5000 messages that's 5000 RTTs and a multi-second
cliff on first filter-room read. The new path queues every message's writes
onto ONE pipeline and executes once.

Tests cover:
- All matching messages land in msg_data + timeline + correct media index.
- Hydration completes in a small bounded number of round-trips, regardless
  of message count.
- Cap is respected (stops at REDIS_CACHE_MAX_COUNT most recent).
- Hydration flag prevents repeat work.
- Hydrating one media type does not pollute another type's index.
- All indexes/sets remain consistent after bulk hydration.
"""

from __future__ import annotations

from datetime import timedelta

from constance import config
from django.test import TransactionTestCase
from django.utils import timezone

from chats.tests import cache_helpers, factories
from chats.utils.performance.cache import MessageCache


class BulkHydrationCorrectnessTest(TransactionTestCase):
    """The pipeline-batched path must produce the same end state as the old
    serial-loop path."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_hydrates_all_matching_photos_to_index_and_data(self):
        factories.make_messages(
            self.room, count=20, mix=factories.MessageMix(photo_pct=100),
        )

        photos = MessageCache.get_photo_messages(self.room.id, limit=50)
        self.assertEqual(len(photos), 20)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['photo_index_size'], 20)
        self.assertEqual(snap['msg_data_size'], 20)
        self.assertEqual(snap['timeline_size'], 20)

    def test_hydrates_all_voice_messages(self):
        factories.make_messages(
            self.room, count=11, mix=factories.MessageMix(voice_pct=100),
        )
        audios = MessageCache.get_audio_messages(self.room.id, limit=50)
        self.assertEqual(len(audios), 11)

    def test_hydration_keeps_protected_set_in_sync(self):
        """Bulk-hydrated photos must end up in the protected SET."""
        msgs = factories.make_messages(
            self.room, count=15, mix=factories.MessageMix(photo_pct=100),
        )
        MessageCache.get_photo_messages(self.room.id)

        client = cache_helpers.redis_client()
        protected_key = MessageCache.PROTECTED_SET_KEY.format(room_id=str(self.room.id))
        members = client.smembers(protected_key)
        member_ids = {(m.decode() if isinstance(m, bytes) else m) for m in members}

        for m in msgs:
            self.assertIn(str(m.id), member_ids)

    def test_hydration_keeps_index_registry_in_sync(self):
        """Hydrating photos must register the photo index key."""
        factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(photo_pct=100),
        )
        MessageCache.get_photo_messages(self.room.id)

        client = cache_helpers.redis_client()
        registry_key = MessageCache.IDX_KEYS_REGISTRY.format(room_id=str(self.room.id))
        members = client.smembers(registry_key)
        member_keys = {(m.decode() if isinstance(m, bytes) else m) for m in members}

        self.assertIn(
            f'room:{self.room.id}:idx:photo', member_keys,
        )

    def test_hydration_indexes_are_consistent_after_run(self):
        """Full consistency check: every ID in every index must exist in msg_data."""
        factories.make_messages(
            self.room, count=30,
            mix=factories.MessageMix(photo_pct=50, voice_pct=20),
        )
        MessageCache.get_photo_messages(self.room.id)
        MessageCache.get_audio_messages(self.room.id)
        cache_helpers.assert_indexes_consistent(self.room.id)

    def test_hydrating_photo_does_not_populate_audio_index(self):
        """Hydrating one type must NOT pollute another type's index."""
        factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(photo_pct=100),
        )
        MessageCache.get_photo_messages(self.room.id)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['photo_index_size'], 5)
        self.assertEqual(snap['audio_index_size'], 0)
        self.assertEqual(snap['video_index_size'], 0)


class BulkHydrationFlagTest(TransactionTestCase):
    """Hydration is one-shot per room/type — flag must prevent repeats."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_second_call_does_not_re_hydrate(self):
        """Once hydrated, subsequent get_photo_messages must NOT issue the
        photo-lookup Postgres query again."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(photo_pct=100),
        )
        # First call hydrates.
        MessageCache.get_photo_messages(self.room.id)

        # Second call: count Postgres queries against the Message table.
        with CaptureQueriesContext(connection) as ctx:
            MessageCache.get_photo_messages(self.room.id)

        photo_queries = [
            q for q in ctx.captured_queries
            if 'chats_message' in q['sql'].lower() and 'photo_url' in q['sql'].lower()
        ]
        self.assertEqual(
            len(photo_queries), 0,
            f'Hydration ran twice — found {len(photo_queries)} photo queries',
        )


class BulkHydrationCapTest(TransactionTestCase):
    """Hydration must cap at REDIS_CACHE_MAX_COUNT — most recent only."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()
        self._original_cap = config.REDIS_CACHE_MAX_COUNT

    def tearDown(self):
        config.REDIS_CACHE_MAX_COUNT = self._original_cap
        cache_helpers.flush_cache()

    def test_cap_enforced_on_hydration(self):
        """Cap=20, but 50 photos exist in DB — only the 20 newest should
        come back from the photo room."""
        config.REDIS_CACHE_MAX_COUNT = 20

        # 50 photos, oldest first.
        old_start = timezone.now() - timedelta(days=2)
        msgs = factories.make_messages(
            self.room, count=50,
            mix=factories.MessageMix(photo_pct=100),
            start_time=old_start,
            step_seconds=60,
        )

        photos = MessageCache.get_photo_messages(self.room.id, limit=50)
        self.assertEqual(len(photos), 20)

        # The 20 returned must be the NEWEST 20 (msgs[30..49]).
        returned_ids = {p['id'] for p in photos}
        expected_ids = {str(m.id) for m in msgs[-20:]}
        self.assertEqual(returned_ids, expected_ids)


class BulkHydrationPerformanceTest(TransactionTestCase):
    """The whole point of Phase 5: hydration must use a single pipeline,
    not N round-trips."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_hydration_completes_in_few_round_trips(self):
        """Hydrate 100 photos. Total RTTs (during hydration only) should be
        small — ideally 1 (the bulk pipeline). Allow up to 5 to absorb
        EXISTS check + read-side ZRANGEBYSCORE + HMGET for the response."""
        factories.make_messages(
            self.room, count=100, mix=factories.MessageMix(photo_pct=100),
        )

        with cache_helpers.count_redis_rtts() as rtts:
            MessageCache.get_photo_messages(self.room.id, limit=200)

        self.assertLessEqual(
            rtts.rtt_count, 10,
            f'Hydration of 100 photos used {rtts.rtt_count} round-trips — '
            'expected ~5 (one pipeline). Bulk-pipeline path may be broken.',
        )

    def test_hydration_of_5000_messages_is_not_5000_rtts(self):
        """Direct regression guard against the old per-message-pipeline path:
        hydrating 5000 messages must NOT issue thousands of round-trips."""
        factories.make_messages(
            self.room, count=5000, mix=factories.MessageMix(photo_pct=100),
        )

        with cache_helpers.count_redis_rtts() as rtts:
            MessageCache.get_photo_messages(self.room.id, limit=10)

        self.assertLess(
            rtts.rtt_count, 100,
            f'Hydration of 5000 photos used {rtts.rtt_count} round-trips — '
            'should be ~5. Per-message round-trip is back.',
        )


class HighlightHydrationCorrectnessTest(TransactionTestCase):
    """Highlight room hydration mirrors media hydration: one bulk pipeline
    seeds msg_data + timeline + highlight index + protected SET."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_hydrates_all_highlights(self):
        msgs = factories.make_messages(
            self.room, count=20, mix=factories.MessageMix(highlight_pct=100),
        )

        highlights = MessageCache.get_highlight_messages(self.room.id, limit=50)
        self.assertEqual(len(highlights), 20)

        snap = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap['highlight_index_size'], 20)
        self.assertEqual(snap['msg_data_size'], 20)
        self.assertEqual(snap['timeline_size'], 20)

    def test_hydration_keeps_protected_set_in_sync(self):
        msgs = factories.make_messages(
            self.room, count=10, mix=factories.MessageMix(highlight_pct=100),
        )
        MessageCache.get_highlight_messages(self.room.id)

        client = cache_helpers.redis_client()
        protected_key = MessageCache.PROTECTED_SET_KEY.format(room_id=str(self.room.id))
        members = client.smembers(protected_key)
        member_ids = {(m.decode() if isinstance(m, bytes) else m) for m in members}
        for m in msgs:
            self.assertIn(str(m.id), member_ids)

    def test_hydration_keeps_index_registry_in_sync(self):
        factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(highlight_pct=100),
        )
        MessageCache.get_highlight_messages(self.room.id)

        client = cache_helpers.redis_client()
        registry_key = MessageCache.IDX_KEYS_REGISTRY.format(room_id=str(self.room.id))
        members = client.smembers(registry_key)
        member_keys = {(m.decode() if isinstance(m, bytes) else m) for m in members}
        self.assertIn(f'room:{self.room.id}:idx:highlight', member_keys)

    def test_hydration_indexes_are_consistent_after_run(self):
        factories.make_messages(
            self.room, count=15, mix=factories.MessageMix(highlight_pct=100),
        )
        MessageCache.get_highlight_messages(self.room.id)
        cache_helpers.assert_indexes_consistent(self.room.id)

    def test_old_highlights_outside_msg_data_appear_after_hydration(self):
        """Pre-existing highlights in Postgres that have NEVER been written to
        the cache must surface in the highlight room on first request."""
        from datetime import timedelta
        from django.utils import timezone

        old_start = timezone.now() - timedelta(days=10)
        factories.make_messages(
            self.room, count=30, mix=factories.MessageMix(highlight_pct=100),
            start_time=old_start, step_seconds=60,
        )

        snap_before = cache_helpers.inspect_room(self.room.id)
        self.assertEqual(snap_before['highlight_index_size'], 0)

        result = MessageCache.get_highlight_messages(self.room.id, limit=100)
        self.assertEqual(len(result), 30)


class HighlightHydrationFlagTest(TransactionTestCase):
    """Hydration is one-shot per room — flag must prevent repeats."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_second_call_does_not_re_hydrate(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        factories.make_messages(
            self.room, count=5, mix=factories.MessageMix(highlight_pct=100),
        )
        MessageCache.get_highlight_messages(self.room.id)

        with CaptureQueriesContext(connection) as ctx:
            MessageCache.get_highlight_messages(self.room.id)

        highlight_queries = [
            q for q in ctx.captured_queries
            if 'chats_message' in q['sql'].lower() and 'is_highlight' in q['sql'].lower()
        ]
        self.assertEqual(
            len(highlight_queries), 0,
            f'Hydration ran twice — found {len(highlight_queries)} highlight queries',
        )


class HighlightHydrationCapTest(TransactionTestCase):
    """Hydration must cap at REDIS_CACHE_MAX_COUNT."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()
        self._original_cap = config.REDIS_CACHE_MAX_COUNT

    def tearDown(self):
        config.REDIS_CACHE_MAX_COUNT = self._original_cap
        cache_helpers.flush_cache()

    def test_cap_enforced_on_hydration(self):
        """Cap=10, but 25 highlights exist in DB — hydration loads only 10
        (the most recently highlighted ones)."""
        config.REDIS_CACHE_MAX_COUNT = 10

        from datetime import timedelta
        from django.utils import timezone

        old_start = timezone.now() - timedelta(days=2)
        msgs = factories.make_messages(
            self.room, count=25, mix=factories.MessageMix(highlight_pct=100),
            start_time=old_start, step_seconds=60,
        )

        highlights = MessageCache.get_highlight_messages(self.room.id, limit=100)
        self.assertEqual(len(highlights), 10)

        # The 10 returned must be the NEWEST 10 by highlighted_at.
        returned_ids = {h['id'] for h in highlights}
        expected_ids = {str(m.id) for m in msgs[-10:]}
        self.assertEqual(returned_ids, expected_ids)


class HighlightHydrationPerformanceTest(TransactionTestCase):
    """Hydration must use a single bulk pipeline."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_hydration_completes_in_few_round_trips(self):
        factories.make_messages(
            self.room, count=100, mix=factories.MessageMix(highlight_pct=100),
        )

        with cache_helpers.count_redis_rtts() as rtts:
            MessageCache.get_highlight_messages(self.room.id, limit=200)

        self.assertLessEqual(
            rtts.rtt_count, 10,
            f'Hydration of 100 highlights used {rtts.rtt_count} round-trips — '
            'expected ~5 (one bulk pipeline).',
        )


class HighlightRoomLimitAndPaginationTest(TransactionTestCase):
    """Behavior pinning for the >50-highlights case.

    Setup: 60 highlights total, with `highlighted_at` in NON-chronological
    order relative to `created_at`. Specifically, the OLDEST message
    (by created_at) is the NEWEST highlight (most recently starred).
    This catches sort-by-created_at regressions.

    Verifies:
    - First page (limit=50) returns the 50 most-RECENTLY-STARRED highlights,
      not the 50 most-RECENTLY-SENT.
    - Within the page, messages are ordered by highlighted_at ascending
      (oldest highlight at top of page, newest highlight at bottom).
    - Pagination via `before_timestamp` walks BACKWARD by highlighted_at,
      surfacing the older 10 starred messages.
    - The dropped 10 are exactly the 10 OLDEST-by-highlighted_at, regardless
      of their created_at.
    """

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def _make_highlight(self, room, created_at, highlighted_at, content):
        """Helper: create one highlighted message with explicit timestamps."""
        from chats.models import Message
        import uuid
        m = Message.objects.create(
            id=uuid.uuid4(),
            chat_room=room,
            username='Alice',
            content=content,
            is_highlight=True,
        )
        # bypass auto_now on save to set timestamps explicitly
        Message.objects.filter(pk=m.pk).update(
            created_at=created_at,
            highlighted_at=highlighted_at,
        )
        m.refresh_from_db()
        return m

    def test_first_page_returns_most_recently_starred_50(self):
        """60 highlights, request 50 → API returns 50 with the highest
        highlighted_at, NOT the 50 with the highest created_at."""
        # Create 60 highlights. Send-order matches index 0..59 (oldest..newest).
        # Star-order is REVERSED — message[0] (oldest sent) is starred LAST.
        base_created = timezone.now() - timedelta(days=10)
        base_highlighted = timezone.now() - timedelta(hours=2)

        msgs = []
        for i in range(60):
            m = self._make_highlight(
                room=self.room,
                created_at=base_created + timedelta(seconds=i),
                # Reverse: msg[0] highlighted last, msg[59] highlighted first.
                highlighted_at=base_highlighted + timedelta(seconds=(60 - i)),
                content=f'msg {i}',
            )
            msgs.append(m)

        result = MessageCache.get_highlight_messages(self.room.id, limit=50)
        self.assertEqual(len(result), 50)

        # The 50 returned are the 50 MOST-RECENTLY-STARRED.
        # In our setup, that's msgs[0..49] (they were highlighted last).
        returned_ids = {r['id'] for r in result}
        expected_ids = {str(m.id) for m in msgs[:50]}
        self.assertEqual(
            returned_ids, expected_ids,
            'First page must contain the 50 most-recently-starred messages, '
            'NOT the 50 most-recently-sent',
        )

        # The 10 EXCLUDED are msgs[50..59] — the OLDEST highlights despite
        # being the NEWEST messages.
        excluded_ids = {str(m.id) for m in msgs[50:]}
        self.assertEqual(
            returned_ids & excluded_ids, set(),
            'Newest-sent messages must NOT appear in first page when their '
            'highlighted_at is older than the 50th-most-recent highlight',
        )

    def test_first_page_is_ordered_oldest_highlight_first(self):
        """Within the first page, position [0] is the OLDEST highlight in the
        page and position [-1] is the NEWEST (so it scrolls naturally with
        the user's most-recent action at the bottom)."""
        base_created = timezone.now() - timedelta(days=10)
        base_highlighted = timezone.now() - timedelta(hours=2)
        msgs = []
        for i in range(60):
            m = self._make_highlight(
                room=self.room,
                created_at=base_created + timedelta(seconds=i),
                highlighted_at=base_highlighted + timedelta(seconds=(60 - i)),
                content=f'msg {i}',
            )
            msgs.append(m)

        result = MessageCache.get_highlight_messages(self.room.id, limit=50)

        # Within the page, highlighted_at must be monotonically increasing.
        from datetime import datetime
        prev_ts = None
        for r in result:
            ts = datetime.fromisoformat(r['highlighted_at']).timestamp()
            if prev_ts is not None:
                self.assertGreaterEqual(
                    ts, prev_ts,
                    'Highlight room must be sorted by highlighted_at ascending',
                )
            prev_ts = ts

    def test_pagination_walks_backward_by_highlighted_at(self):
        """After the first page (50 most recent highlights), pagination by
        before_timestamp = oldest-page-highlighted_at returns the older 10.
        Asserts the boundary uses highlighted_at, not created_at."""
        base_created = timezone.now() - timedelta(days=10)
        base_highlighted = timezone.now() - timedelta(hours=2)
        msgs = []
        for i in range(60):
            m = self._make_highlight(
                room=self.room,
                created_at=base_created + timedelta(seconds=i),
                highlighted_at=base_highlighted + timedelta(seconds=(60 - i)),
                content=f'msg {i}',
            )
            msgs.append(m)

        # First page.
        page1 = MessageCache.get_highlight_messages(self.room.id, limit=50)
        self.assertEqual(len(page1), 50)

        # Frontend would extract page1[0]'s highlighted_at as the boundary
        # for pagination — emulate that here.
        from datetime import datetime
        oldest_in_page1 = datetime.fromisoformat(
            page1[0]['highlighted_at']
        ).timestamp()

        # Second page.
        page2 = MessageCache.get_highlight_messages(
            self.room.id, limit=50, before_timestamp=oldest_in_page1,
        )
        self.assertEqual(
            len(page2), 10,
            'Second page must contain the 10 highlights older than the first page',
        )

        # The 10 returned must be exactly the OLDEST-by-highlighted_at messages
        # (msgs[50..59] in our setup).
        page2_ids = {r['id'] for r in page2}
        expected_ids = {str(m.id) for m in msgs[50:]}
        self.assertEqual(
            page2_ids, expected_ids,
            'Pagination must return the older-by-highlighted_at messages, '
            'NOT older-by-created_at',
        )

        # And no overlap with page 1.
        page1_ids = {r['id'] for r in page1}
        self.assertEqual(
            page1_ids & page2_ids, set(),
            'Pages must not overlap — boundary handling is buggy',
        )

    def test_old_message_starred_today_appears_at_bottom_of_page(self):
        """The classic case: a message sent days ago, starred just now.
        It should be the LAST entry in the highlight room (newest highlight)
        even though its created_at is the oldest."""
        # Setup: 5 highlights with normal timeline, plus 1 ANCIENT message
        # starred just now.
        from django.utils import timezone as tz

        base_h = tz.now() - timedelta(hours=5)
        msgs = []
        for i in range(5):
            m = self._make_highlight(
                room=self.room,
                created_at=tz.now() - timedelta(hours=4 - i),
                highlighted_at=base_h + timedelta(minutes=i * 30),
                content=f'recent msg {i}',
            )
            msgs.append(m)

        # The ancient message: created 10 days ago, starred 1 minute ago.
        ancient = self._make_highlight(
            room=self.room,
            created_at=tz.now() - timedelta(days=10),
            highlighted_at=tz.now() - timedelta(minutes=1),
            content='ancient message',
        )

        result = MessageCache.get_highlight_messages(self.room.id, limit=50)
        self.assertEqual(len(result), 6)

        # Ancient must be LAST (most recent highlight), despite being the
        # OLDEST message by created_at.
        self.assertEqual(
            result[-1]['id'], str(ancient.id),
            'An old message starred recently must appear at the BOTTOM of '
            'the highlight room (most recent highlight position)',
        )
