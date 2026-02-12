"""
Message activity utility for ranking suggestions by chat activity.

Queries message counts for the last 24 hours and within the configurable
activity window, with Redis caching to reduce database load.

The activity window is configurable via Constance setting:
    CHAT_ACTIVITY_WINDOW_MINUTES (default: 10.0)

Cache TTL is automatically set to half the activity window.
"""

import logging
from datetime import timedelta
from typing import Dict, List, NamedTuple

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache configuration
MESSAGE_ACTIVITY_CACHE_PREFIX = "room_msg_activity"


def _get_activity_window_minutes() -> float:
    """Get the activity window from Constance settings."""
    from constance import config
    return float(config.CHAT_ACTIVITY_WINDOW_MINUTES)


def _get_cache_ttl_seconds() -> int:
    """Calculate cache TTL as half the activity window (in seconds)."""
    window_minutes = _get_activity_window_minutes()
    ttl_seconds = (window_minutes / 2) * 60
    return max(1, int(ttl_seconds))  # Minimum 1 second


class MessageActivity(NamedTuple):
    """Message activity counts for a room."""
    messages_24h: int
    messages_10min: int


def get_message_activity_for_rooms(room_ids: List[str]) -> Dict[str, MessageActivity]:
    """
    Get message counts (24h and active window) for each room.

    Uses Redis caching with TTL = activity_window / 2 to reduce database load.
    Batch fetches from cache, then queries DB for cache misses.

    The activity window is configurable via CHAT_ACTIVITY_WINDOW_MINUTES.

    Args:
        room_ids: List of ChatRoom UUIDs (as strings)

    Returns:
        Dict mapping room_id -> MessageActivity(messages_24h, messages_10min)
        Note: messages_10min is named for legacy reasons but uses the
        configurable activity window (default 10 min).
        Rooms not found or with no activity return MessageActivity(0, 0)

    Example:
        >>> counts = get_message_activity_for_rooms(['uuid1', 'uuid2'])
        >>> counts['uuid1'].messages_24h
        47
        >>> counts['uuid1'].messages_10min  # Uses configurable window
        3
    """
    if not room_ids:
        return {}

    # Deduplicate room IDs
    unique_room_ids = list(set(room_ids))

    # Build cache keys
    cache_keys = {
        room_id: f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room_id}"
        for room_id in unique_room_ids
    }

    # Batch fetch from cache
    cached_values = cache.get_many(list(cache_keys.values()))

    # Separate hits and misses
    results: Dict[str, MessageActivity] = {}
    cache_misses: List[str] = []

    for room_id in unique_room_ids:
        cache_key = cache_keys[room_id]
        if cache_key in cached_values:
            cached = cached_values[cache_key]
            results[room_id] = MessageActivity(
                messages_24h=cached.get('messages_24h', 0),
                messages_10min=cached.get('messages_10min', 0)
            )
        else:
            cache_misses.append(room_id)

    if cache_misses:
        logger.debug(
            f"Message activity cache: {len(results)} hits, {len(cache_misses)} misses"
        )

        # Query DB for cache misses
        db_results = _query_message_activity(cache_misses)

        # Store in cache and add to results
        cache_to_set = {}
        for room_id in cache_misses:
            activity = db_results.get(room_id, MessageActivity(0, 0))
            results[room_id] = activity
            cache_to_set[cache_keys[room_id]] = {
                'messages_24h': activity.messages_24h,
                'messages_10min': activity.messages_10min
            }

        # Batch set cache
        cache.set_many(cache_to_set, timeout=_get_cache_ttl_seconds())

    return results


def _query_message_activity(room_ids: List[str]) -> Dict[str, MessageActivity]:
    """
    Query database for message counts in last 24h and within activity window.

    The activity window is configurable via CHAT_ACTIVITY_WINDOW_MINUTES.

    Args:
        room_ids: List of ChatRoom UUIDs to query

    Returns:
        Dict mapping room_id -> MessageActivity
    """
    from chats.models import Message

    if not room_ids:
        return {}

    now = timezone.now()
    cutoff_24h = now - timedelta(hours=24)
    activity_window_minutes = _get_activity_window_minutes()
    cutoff_active = now - timedelta(minutes=activity_window_minutes)

    # Single query with conditional aggregation
    # COUNT all messages in 24h, COUNT FILTER for 10min
    activity_counts = (
        Message.objects.filter(
            chat_room_id__in=room_ids,
            created_at__gte=cutoff_24h,
            is_deleted=False
        )
        .values('chat_room_id')
        .annotate(
            messages_24h=Count('id'),
            messages_10min=Count('id', filter=Q(created_at__gte=cutoff_active))
        )
    )

    # Convert to dict with MessageActivity values
    results = {
        str(row['chat_room_id']): MessageActivity(
            messages_24h=row['messages_24h'],
            messages_10min=row['messages_10min']
        )
        for row in activity_counts
    }

    logger.debug(f"Queried message activity for {len(room_ids)} rooms: {len(results)} with activity")

    return results


def invalidate_message_activity_cache(room_id: str) -> None:
    """
    Invalidate the message activity cache for a specific room.

    Call this when a new message is sent to ensure fresh counts.
    Optional optimization - cache will naturally expire after TTL.

    Args:
        room_id: ChatRoom UUID to invalidate
    """
    cache_key = f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated message activity cache for room {room_id}")
