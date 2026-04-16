"""
Phase 3 tests: known-index registry.

Replaces `scan_iter` on `idx:*` with an explicit Redis SET of touched index
keys, read via SMEMBERS. Tests cover:
- Registry is populated with every index `add_message` touches.
- Per-user focus indexes for distinct senders all land in the registry.
- Eviction reads the registry instead of scan_iter (mocking scan_iter to raise
  proves the new path is active).
- All indexes the registry tracks get cleaned during eviction (no orphan IDs).
"""

from __future__ import annotations

from unittest import mock

from django.test import TransactionTestCase

from chats.tests import cache_helpers, factories
from chats.utils.performance.cache import MessageCache


def _registry_keys(room_id) -> set:
    """Return the contents of the index registry SET for a room."""
    client = cache_helpers.redis_client()
    key = MessageCache.IDX_KEYS_REGISTRY.format(room_id=str(room_id))
    raw = client.smembers(key)
    return {(m.decode() if isinstance(m, bytes) else m) for m in raw}


class IndexRegistryPopulationTest(TransactionTestCase):
    """add_message must register every idx:* key it writes."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_text_message_registers_focus_only(self):
        msg = factories.make_messages(self.room, count=1, usernames=['Alice'])[0]
        MessageCache.add_message(msg)
        registry = _registry_keys(self.room.id)
        # Plain text from Alice -> only the per-user focus index.
        self.assertIn(
            f'room:{self.room.id}:idx:focus:alice', registry,
        )
        # Nothing else for a plain text message.
        self.assertEqual(len(registry), 1)

    def test_photo_registers_focus_and_photo(self):
        msg = factories.make_messages(
            self.room, count=1, usernames=['Bob'],
            mix=factories.MessageMix(photo_pct=100),
        )[0]
        MessageCache.add_message(msg)
        registry = _registry_keys(self.room.id)
        self.assertIn(f'room:{self.room.id}:idx:focus:bob', registry)
        self.assertIn(f'room:{self.room.id}:idx:photo', registry)

    def test_voice_registers_focus_and_audio(self):
        msg = factories.make_messages(
            self.room, count=1, usernames=['Carol'],
            mix=factories.MessageMix(voice_pct=100),
        )[0]
        MessageCache.add_message(msg)
        registry = _registry_keys(self.room.id)
        self.assertIn(f'room:{self.room.id}:idx:focus:carol', registry)
        self.assertIn(f'room:{self.room.id}:idx:audio', registry)

    def test_highlight_registers_highlight_index(self):
        msg = factories.make_messages(
            self.room, count=1, usernames=['Dave'],
            mix=factories.MessageMix(highlight_pct=100),
        )[0]
        MessageCache.add_message(msg)
        registry = _registry_keys(self.room.id)
        self.assertIn(f'room:{self.room.id}:idx:highlight', registry)

    def test_gift_registers_gifts_indexes(self):
        msg = factories.make_messages(
            self.room, count=1, usernames=['Eve'],
            mix=factories.MessageMix(gift_pct=100),
        )[0]
        MessageCache.add_message(msg)
        registry = _registry_keys(self.room.id)
        self.assertIn(f'room:{self.room.id}:idx:gifts', registry)
        self.assertIn(f'room:{self.room.id}:idx:gifts:eve', registry)

    def test_distinct_users_each_get_focus_index_registered(self):
        """10 unique senders must produce 10 focus:{user} indexes, all registered."""
        usernames = [f'User{i}' for i in range(10)]
        msgs = factories.make_messages(
            self.room, count=10, usernames=usernames,
        )
        for m in msgs:
            MessageCache.add_message(m)

        registry = _registry_keys(self.room.id)
        for u in usernames:
            self.assertIn(
                f'room:{self.room.id}:idx:focus:{u.lower()}', registry,
                f'Focus index for {u} not registered',
            )

    def test_add_to_highlight_index_registers_key(self):
        """Highlighting an existing message via add_to_highlight_index (the path
        the host's highlight toggle uses) must also register the highlight key."""
        msg = factories.make_messages(self.room, count=1)[0]
        MessageCache.add_message(msg)
        # Plain text — highlight index not registered yet.
        self.assertNotIn(
            f'room:{self.room.id}:idx:highlight', _registry_keys(self.room.id),
        )

        # Now host highlights it.
        MessageCache.add_to_highlight_index(msg)
        self.assertIn(
            f'room:{self.room.id}:idx:highlight', _registry_keys(self.room.id),
        )


class EvictionUsesRegistryNotScanIterTest(TransactionTestCase):
    """The whole point of Phase 3: eviction must NOT call scan_iter on the
    keyspace. It must SMEMBERS the registry."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_eviction_succeeds_when_scan_iter_would_raise(self):
        """If we patch redis_client.scan_iter to raise, eviction must still
        succeed — proving it's no longer using scan_iter. Uses
        strict_cap_eviction so trim fires on the very next overflow."""
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 5
        try:
            with cache_helpers.strict_cap_eviction():
                # Fill cap with messages that touch a few indexes (text + 1 photo).
                msgs = factories.make_messages(
                    self.room, count=5, mix=factories.MessageMix(photo_pct=20),
                )
                for m in msgs:
                    MessageCache.add_message(m)

                # Now the next add will overflow and trigger eviction.
                extra = factories.make_messages(self.room, count=1)[0]

                # Patch scan_iter to raise — if eviction calls it, the test fails.
                client = cache_helpers.redis_client()
                with mock.patch.object(
                    client, 'scan_iter',
                    side_effect=AssertionError('scan_iter must not be called by eviction'),
                ):
                    # add_message itself must not raise.
                    result = MessageCache.add_message(extra)
                    self.assertTrue(result, 'add_message returned False')

            # Eviction did happen — verify cap is enforced.
            snap = cache_helpers.inspect_room(self.room.id)
            self.assertEqual(snap['timeline_size'], 5)
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap

    def test_remove_message_succeeds_when_scan_iter_would_raise(self):
        """Same guarantee for remove_message (soft delete path)."""
        msgs = factories.make_messages(
            self.room, count=3, mix=factories.MessageMix(photo_pct=100),
        )
        for m in msgs:
            MessageCache.add_message(m)

        client = cache_helpers.redis_client()
        with mock.patch.object(
            client, 'scan_iter',
            side_effect=AssertionError('scan_iter must not be called by remove_message'),
        ):
            removed = MessageCache.remove_message(self.room.id, str(msgs[0].id))
            self.assertTrue(removed)

        # And the photo index is properly cleaned.
        photo_idx = cache_helpers.index_ids(self.room.id, 'PHOTO_INDEX_KEY')
        self.assertNotIn(str(msgs[0].id), photo_idx)


class EvictionCleansAllRegisteredIndexesTest(TransactionTestCase):
    """Behavior parity: after eviction, no idx:* contains an evicted ID.
    Catches the case where the registry misses an index that was actually
    touched by add_message."""

    def setUp(self):
        cache_helpers.flush_cache()
        self.room = factories.make_room()

    def tearDown(self):
        cache_helpers.flush_cache()

    def test_eviction_leaves_no_orphan_index_entries(self):
        from constance import config

        original_cap = config.REDIS_CACHE_MAX_COUNT
        config.REDIS_CACHE_MAX_COUNT = 10
        try:
            # Mix of types so multiple indexes get populated.
            msgs = factories.make_messages(
                self.room, count=10, usernames=['Alice', 'Bob'],
                mix=factories.MessageMix(
                    photo_pct=20, voice_pct=10, highlight_pct=10, gift_pct=10,
                ),
            )
            for m in msgs:
                MessageCache.add_message(m)

            # Force eviction by adding text past the cap.
            extras = factories.make_messages(
                self.room, count=5, usernames=['Alice', 'Bob'],
            )
            for m in extras:
                MessageCache.add_message(m)

            # The consistency helper checks that no global index references
            # an ID outside msg_data — exactly what we want.
            cache_helpers.assert_indexes_consistent(self.room.id)
        finally:
            config.REDIS_CACHE_MAX_COUNT = original_cap
