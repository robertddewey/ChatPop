"""
Redis cache test helpers.

Utilities for inspecting and manipulating the Redis state used by MessageCache
so tests can make targeted assertions without reaching into cache internals.

Intended usage:
- `flush_cache()` — full Redis DB flush; call in setUp / tearDown.
- `inspect_room(room_id)` — snapshot of all cache structures for one room.
- `count_redis_ops(client)` — context manager that tallies Redis commands.
- `assert_indexes_consistent(room_id)` — every ID in every index points to an
  existing msg_data entry; timeline and msg_data agree on membership.

These helpers deliberately use the same key templates as `MessageCache`, but
via explicit references rather than re-implementing them, so changes in cache.py
surface as import-time failures instead of silent test drift.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Callable, Dict, List, Optional

from django.core.cache import cache

from chats.utils.performance.cache import MessageCache


# ---------------------------------------------------------------------------
# Redis lifecycle
# ---------------------------------------------------------------------------


def flush_cache() -> None:
    """Clear every key in the configured Redis cache. Call in setUp/tearDown."""
    cache.clear()


def redis_client():
    """Return the raw Redis client MessageCache uses. Prefer this over django-redis
    wrappers so tests see the same view of the world as production code."""
    return MessageCache._get_redis_client()


# ---------------------------------------------------------------------------
# Snapshot / inspection
# ---------------------------------------------------------------------------


def inspect_room(room_id) -> Dict[str, object]:
    """Return a dict snapshot of cache structures for `room_id`.

    Useful in assertions: `snap = inspect_room(room.id); assert snap['timeline_size'] == 5000`.
    """
    rid = str(room_id)
    client = redis_client()

    timeline_key = MessageCache.TIMELINE_KEY.format(room_id=rid)
    msg_data_key = MessageCache.MSG_DATA_KEY.format(room_id=rid)

    return {
        'timeline_size': client.zcard(timeline_key),
        'msg_data_size': client.hlen(msg_data_key),
        'photo_index_size': client.zcard(MessageCache.PHOTO_INDEX_KEY.format(room_id=rid)),
        'video_index_size': client.zcard(MessageCache.VIDEO_INDEX_KEY.format(room_id=rid)),
        'audio_index_size': client.zcard(MessageCache.AUDIO_INDEX_KEY.format(room_id=rid)),
        'gifts_index_size': client.zcard(MessageCache.GIFTS_INDEX_KEY.format(room_id=rid)),
        'highlight_index_size': client.zcard(MessageCache.HIGHLIGHT_INDEX_KEY.format(room_id=rid)),
        'host_index_size': client.zcard(MessageCache.HOST_INDEX_KEY.format(room_id=rid)),
    }


def timeline_ids(room_id) -> List[str]:
    """Return the list of message IDs currently in the timeline, oldest first."""
    rid = str(room_id)
    raw = redis_client().zrange(MessageCache.TIMELINE_KEY.format(room_id=rid), 0, -1)
    return [m.decode() if isinstance(m, bytes) else m for m in raw]


def msg_data_ids(room_id) -> List[str]:
    """Return message IDs present in the msg_data hash."""
    rid = str(room_id)
    raw = redis_client().hkeys(MessageCache.MSG_DATA_KEY.format(room_id=rid))
    return [m.decode() if isinstance(m, bytes) else m for m in raw]


def index_ids(room_id, index_attr: str, **fmt_kwargs) -> List[str]:
    """Return IDs in a named index (e.g. 'PHOTO_INDEX_KEY', 'FOCUS_INDEX_KEY').

    Extra kwargs are forwarded to str.format for per-user indexes:
        index_ids(room.id, 'FOCUS_INDEX_KEY', username='alice')
    """
    key_template = getattr(MessageCache, index_attr)
    key = key_template.format(room_id=str(room_id), **fmt_kwargs)
    raw = redis_client().zrange(key, 0, -1)
    return [m.decode() if isinstance(m, bytes) else m for m in raw]


# ---------------------------------------------------------------------------
# Consistency assertion
# ---------------------------------------------------------------------------


def assert_indexes_consistent(room_id) -> None:
    """Raise AssertionError if any index points to an ID missing from msg_data.

    Also checks that timeline ⊆ msg_data (timeline shouldn't have orphan IDs).
    Does NOT check the reverse (msg_data may have IDs not in every index — that's
    normal for filter indexes that only hold a subset).
    """
    rid = str(room_id)
    data_ids = set(msg_data_ids(rid))

    # Timeline must be a subset of msg_data.
    tl = set(timeline_ids(rid))
    orphans = tl - data_ids
    if orphans:
        raise AssertionError(
            f'Timeline has {len(orphans)} IDs not in msg_data for room {rid}: '
            f'{sorted(orphans)[:5]}...'
        )

    # Every global index's members must be in msg_data.
    for attr in ('PHOTO_INDEX_KEY', 'VIDEO_INDEX_KEY', 'AUDIO_INDEX_KEY',
                 'GIFTS_INDEX_KEY', 'HIGHLIGHT_INDEX_KEY', 'HOST_INDEX_KEY'):
        idx = set(index_ids(rid, attr))
        orphans = idx - data_ids
        if orphans:
            raise AssertionError(
                f'Index {attr} has {len(orphans)} IDs not in msg_data for room {rid}: '
                f'{sorted(orphans)[:5]}...'
            )


# ---------------------------------------------------------------------------
# Redis op counter
# ---------------------------------------------------------------------------


class RedisOpCounter:
    """Count Redis commands issued during a block.

    Uses monkey-patching of the client instance: wraps `execute_command` and
    `pipeline().execute` to tally commands. Thread-safe via a per-instance lock.

    Usage:
        with count_redis_ops() as counts:
            MessageCache.add_message(msg)
        assert counts.total() < 20
        assert counts.by_command.get('HGET', 0) == 0
    """

    def __init__(self):
        self.total_count = 0
        self.by_command: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._patches: List[Callable] = []

    def _tally(self, command: str):
        with self._lock:
            self.total_count += 1
            self.by_command[command] = self.by_command.get(command, 0) + 1

    def total(self) -> int:
        return self.total_count


@contextlib.contextmanager
def count_redis_ops():
    """Context manager: tally Redis commands during the block.

    Yields a RedisOpCounter. Wraps both direct `execute_command` calls and
    pipeline command accumulation so pipelined ops are counted individually
    (which is what you usually want: a pipeline of 100 ZADDs is 100 ops
    in one round-trip).
    """
    counter = RedisOpCounter()
    client = redis_client()

    original_execute_command = client.execute_command

    def patched_execute_command(*args, **kwargs):
        if args:
            counter._tally(str(args[0]).upper())
        return original_execute_command(*args, **kwargs)

    client.execute_command = patched_execute_command  # type: ignore[method-assign]

    # Patch Pipeline.execute_command too — pipelines accumulate commands via
    # this method and flush on .execute(). Count each queued command.
    from redis.client import Pipeline

    original_pipe_execute_command = Pipeline.execute_command

    def patched_pipe_execute_command(self, *args, **kwargs):
        if args:
            counter._tally(str(args[0]).upper())
        return original_pipe_execute_command(self, *args, **kwargs)

    Pipeline.execute_command = patched_pipe_execute_command  # type: ignore[method-assign]

    try:
        yield counter
    finally:
        client.execute_command = original_execute_command  # type: ignore[method-assign]
        Pipeline.execute_command = original_pipe_execute_command  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Redis round-trip counter (different from op counter)
# ---------------------------------------------------------------------------


class RedisRTTCounter:
    """Count Redis round-trips (network transmissions) during a block.

    A single `execute_command` is one RTT. A pipeline with 100 commands is still
    one RTT (one `.execute()` call). Use this to assert pipelining, e.g.
    "hydration should take <=5 RTTs regardless of how many messages".
    """

    def __init__(self):
        self.rtt_count = 0
        self._lock = threading.Lock()

    def _tally(self):
        with self._lock:
            self.rtt_count += 1


@contextlib.contextmanager
def count_redis_rtts():
    """Context manager: tally Redis round-trips during the block.

    Yields a RedisRTTCounter. Each `execute_command` and each `pipeline.execute()`
    counts as one RTT. Batched pipelines are one RTT no matter how many commands.
    """
    counter = RedisRTTCounter()
    client = redis_client()

    original_execute_command = client.execute_command

    def patched_execute_command(*args, **kwargs):
        counter._tally()
        return original_execute_command(*args, **kwargs)

    client.execute_command = patched_execute_command  # type: ignore[method-assign]

    from redis.client import Pipeline

    original_pipe_execute = Pipeline.execute

    def patched_pipe_execute(self, *args, **kwargs):
        counter._tally()
        return original_pipe_execute(self, *args, **kwargs)

    Pipeline.execute = patched_pipe_execute  # type: ignore[method-assign]

    try:
        yield counter
    finally:
        client.execute_command = original_execute_command  # type: ignore[method-assign]
        Pipeline.execute = original_pipe_execute  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Convenience: bulk-load messages into Redis
# ---------------------------------------------------------------------------


def hydrate_room(room_id, messages) -> None:
    """Run a list of Message instances through MessageCache.add_message.

    Convenience for tests that want "these messages exist in Redis" without
    depending on which cache path they come from. Slower than a bespoke
    pipeline — use only for setup of a hundred or so messages. For large
    fixtures, write to Redis directly via the client.
    """
    for msg in messages:
        MessageCache.add_message(msg)


@contextlib.contextmanager
def strict_cap_eviction():
    """Temporarily disable batched eviction so tests can assert exact-cap
    behavior. Sets EVICTION_BATCH_SIZE to 0 so trim fires the moment the
    timeline exceeds cap.

    Use in tests that interrogate single-message eviction precisely.
    Tests that exercise batch behavior should NOT use this — they should
    work with the production batching semantics.
    """
    original = MessageCache.EVICTION_BATCH_SIZE
    MessageCache.EVICTION_BATCH_SIZE = 0
    try:
        yield
    finally:
        MessageCache.EVICTION_BATCH_SIZE = original
