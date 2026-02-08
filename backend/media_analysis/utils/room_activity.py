"""
Room activity utility for ranking suggestions by active participants.

Queries unique users who sent messages in the last 24 hours,
with Redis caching to reduce database load.
"""

import logging
from datetime import timedelta
from typing import Dict, List, Set

from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache configuration
ACTIVE_USERS_CACHE_PREFIX = "room_active_users_24h"
ACTIVE_USERS_CACHE_TTL = 300  # 5 minutes in seconds


def get_active_users_for_rooms(room_ids: List[str]) -> Dict[str, int]:
    """
    Get count of unique users who sent messages in last 24 hours for each room.

    Uses Redis caching with 5-minute TTL to reduce database load.
    Batch fetches from cache, then queries DB for cache misses.

    Args:
        room_ids: List of ChatRoom UUIDs (as strings)

    Returns:
        Dict mapping room_id -> active_user_count
        Rooms not found or with no activity return 0

    Example:
        >>> counts = get_active_users_for_rooms(['uuid1', 'uuid2', 'uuid3'])
        >>> counts
        {'uuid1': 5, 'uuid2': 0, 'uuid3': 12}
    """
    if not room_ids:
        return {}

    # Deduplicate room IDs
    unique_room_ids = list(set(room_ids))

    # Build cache keys
    cache_keys = {
        room_id: f"{ACTIVE_USERS_CACHE_PREFIX}:{room_id}"
        for room_id in unique_room_ids
    }

    # Batch fetch from cache
    cached_values = cache.get_many(list(cache_keys.values()))

    # Separate hits and misses
    results: Dict[str, int] = {}
    cache_misses: Set[str] = set()

    for room_id in unique_room_ids:
        cache_key = cache_keys[room_id]
        if cache_key in cached_values:
            results[room_id] = cached_values[cache_key]
        else:
            cache_misses.add(room_id)

    if cache_misses:
        logger.debug(
            f"Active users cache: {len(results)} hits, {len(cache_misses)} misses"
        )

        # Query DB for cache misses
        db_results = _query_active_users(list(cache_misses))

        # Store in cache and add to results
        cache_to_set = {}
        for room_id in cache_misses:
            count = db_results.get(room_id, 0)
            results[room_id] = count
            cache_to_set[cache_keys[room_id]] = count

        # Batch set cache
        cache.set_many(cache_to_set, timeout=ACTIVE_USERS_CACHE_TTL)

    return results


def _query_active_users(room_ids: List[str]) -> Dict[str, int]:
    """
    Query database for unique users who sent messages in last 24 hours.

    Args:
        room_ids: List of ChatRoom UUIDs to query

    Returns:
        Dict mapping room_id -> active_user_count
    """
    from chats.models import Message

    if not room_ids:
        return {}

    # Calculate 24 hours ago
    cutoff_time = timezone.now() - timedelta(hours=24)

    # Query: COUNT(DISTINCT username) GROUP BY chat_room_id
    # Using username since anonymous users don't have user_id
    active_counts = (
        Message.objects.filter(
            chat_room_id__in=room_ids,
            created_at__gte=cutoff_time,
            is_deleted=False  # Don't count deleted messages
        )
        .values('chat_room_id')
        .annotate(active_users=Count('username', distinct=True))
    )

    # Convert to dict with string keys
    results = {
        str(row['chat_room_id']): row['active_users']
        for row in active_counts
    }

    logger.debug(f"Queried active users for {len(room_ids)} rooms: {results}")

    return results


def invalidate_room_activity_cache(room_id: str) -> None:
    """
    Invalidate the active users cache for a specific room.

    Call this when a new message is sent to ensure fresh counts.
    Optional optimization - cache will naturally expire after TTL.

    Args:
        room_id: ChatRoom UUID to invalidate
    """
    cache_key = f"{ACTIVE_USERS_CACHE_PREFIX}:{room_id}"
    cache.delete(cache_key)
    logger.debug(f"Invalidated active users cache for room {room_id}")
