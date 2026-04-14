"""
Redis message cache utilities for ChatPop.

Implements a hybrid message storage strategy:
- PostgreSQL: Permanent message log (source of truth)
- Redis: Fast cache for recent messages (last 500 or 24 hours)

Architecture (hash + index):
- room:{room_id}:msg_data - Hash (message_id -> JSON) for message data
- room:{room_id}:timeline - Sorted set (timestamp -> message_id) for chronological order
- room:{room_id}:idx:host - Sorted set index for host messages
- room:{room_id}:idx:focus:{username} - Sorted set index for user's focus view
- room:{room_id}:idx:gifts - Sorted set index for all gift messages
- room:{room_id}:idx:gifts:{username} - Sorted set index for user's gifts

Other keys (unchanged):
- room:{room_id}:pinned:{message_id} - Individual pinned message data
- room:{room_id}:pinned_order - Sorted set for pin ordering (score = pin_amount_paid)
- room:{room_id}:reactions:{message_id} - Hash for reaction counts

Note: Uses room UUID (not code) to avoid collisions between
manual rooms with same code owned by different users.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from django.core.cache import cache
from django.conf import settings
from chats.models import Message, ChatParticipation
from .monitoring import monitor


class MessageCache:
    """Redis cache manager for chat messages"""

    # Core data store (hash: message_id -> JSON)
    MSG_DATA_KEY = "room:{room_id}:msg_data"
    # Timeline index (sorted set: score=timestamp, member=message_id)
    TIMELINE_KEY = "room:{room_id}:timeline"

    # Filter indexes (sorted set: score=timestamp, member=message_id)
    HOST_INDEX_KEY = "room:{room_id}:idx:host"
    FOCUS_INDEX_KEY = "room:{room_id}:idx:focus:{username}"
    GIFTS_INDEX_KEY = "room:{room_id}:idx:gifts"
    GIFTS_USER_INDEX_KEY = "room:{room_id}:idx:gifts:{username}"
    HIGHLIGHT_INDEX_KEY = "room:{room_id}:idx:highlight"

    # Legacy key (kept for migration/cleanup reference)
    MESSAGES_KEY = "room:{room_id}:messages"

    # Pinned and reactions (unchanged)
    PINNED_MESSAGE_KEY = "room:{room_id}:pinned:{message_id}"
    PINNED_ORDER_KEY = "room:{room_id}:pinned_order"
    REACTIONS_KEY = "room:{room_id}:reactions:{message_id}"

    @classmethod
    def _get_max_messages(cls) -> int:
        """Get max messages from Constance (dynamic) or fallback to settings (static)"""
        try:
            from constance import config
            return config.REDIS_CACHE_MAX_COUNT
        except:
            return getattr(settings, 'MESSAGE_CACHE_MAX_COUNT', 500)

    @classmethod
    def _get_ttl_hours(cls) -> int:
        """Get TTL hours from Constance (dynamic) or fallback to settings (static)"""
        try:
            from constance import config
            return config.REDIS_CACHE_TTL_HOURS
        except:
            return getattr(settings, 'MESSAGE_CACHE_TTL_HOURS', 24)

    @classmethod
    def _get_redis_client(cls):
        """Get raw Redis client from django-redis"""
        return cache.client.get_client()

    @classmethod
    def _get_avatar_url(cls, message: Message) -> str:
        """
        Get avatar URL for a message.

        ChatParticipation.avatar_url is ALWAYS populated at join time with:
        - Proxy URL for registered users using reserved_username
        - Direct storage URL for anonymous users or different usernames

        Fallback to DiceBear for orphaned/legacy data only.
        """
        from chatpop.utils.media import get_fallback_dicebear_url

        # Look up ChatParticipation - avatar_url should always be populated
        try:
            participation = ChatParticipation.objects.get(
                chat_room=message.chat_room,
                username__iexact=message.username
            )
            if participation.avatar_url:
                return participation.avatar_url
        except ChatParticipation.DoesNotExist:
            pass

        # Fallback to DiceBear for orphaned/legacy data
        return get_fallback_dicebear_url(message.username)

    @classmethod
    def _serialize_message(cls, message: Message, username_is_reserved: bool = False, avatar_url: str = None) -> Dict[str, Any]:
        """
        Serialize a Message instance to JSON-compatible dict.

        Includes username_is_reserved flag for frontend badge display.
        """
        # Build reply_to_message object if there's a reply
        reply_to_message = None
        if message.reply_to:
            reply_username_is_reserved = cls._compute_username_is_reserved(message.reply_to)
            reply_to_message = {
                "id": str(message.reply_to.id),
                "username": message.reply_to.username,
                "content": message.reply_to.content[:100] if message.reply_to.content else "",
                "message_type": message.reply_to.message_type,
                "is_from_host": message.reply_to.is_from_host,
                "username_is_reserved": reply_username_is_reserved,
                "is_pinned": message.reply_to.is_pinned,
            }

        # Get avatar_url if not provided
        if avatar_url is None:
            avatar_url = cls._get_avatar_url(message)

        return {
            "id": str(message.id),
            "chat_code": message.chat_room.code,
            "username": message.username,
            "username_is_reserved": username_is_reserved,
            "user_id": str(message.user.id) if message.user else None,
            "message_type": message.message_type,
            "is_from_host": message.is_from_host,
            "content": message.content,
            "voice_url": message.voice_url,
            "voice_duration": message.voice_duration,
            "voice_waveform": message.voice_waveform,
            "photo_url": message.photo_url,
            "photo_width": message.photo_width,
            "photo_height": message.photo_height,
            "video_url": message.video_url,
            "video_duration": float(message.video_duration) if message.video_duration else None,
            "video_thumbnail_url": message.video_thumbnail_url,
            "video_width": message.video_width,
            "video_height": message.video_height,
            "reply_to_id": str(message.reply_to.id) if message.reply_to else None,
            "reply_to_message": reply_to_message,
            "is_pinned": message.is_pinned,
            "pinned_at": message.pinned_at.isoformat() if message.pinned_at else None,
            "sticky_until": message.sticky_until.isoformat() if message.sticky_until else None,
            "pin_amount_paid": str(message.pin_amount_paid) if message.pin_amount_paid else "0.00",
            "current_pin_amount": str(message.current_pin_amount) if message.current_pin_amount else "0.00",
            "avatar_url": avatar_url,
            "created_at": message.created_at.isoformat(),
            "is_deleted": message.is_deleted,
            "gift_recipient": message.gift_recipient,
            "is_gift_acknowledged": message.is_gift_acknowledged,
            "is_highlight": message.is_highlight,
        }

    @classmethod
    def _compute_username_is_reserved(cls, message: Message) -> bool:
        """
        Compute whether the message's username matches a reserved username.

        This matches the logic in MyParticipationView (views.py:570-573).
        """
        if not message.user or not message.user.reserved_username:
            return False

        # Case-insensitive match
        return message.username.lower() == message.user.reserved_username.lower()

    @classmethod
    def add_message(cls, message: Message) -> bool:
        """
        Add a message to Redis cache with filter index routing.

        Writes to:
        1. Message hash (msg_data) — full JSON
        2. Timeline sorted set — for chronological ordering
        3. Filter indexes — based on message properties

        All operations are pipelined (single network round trip).

        Args:
            message: Message instance (already saved to PostgreSQL)

        Returns:
            True if successfully cached, False otherwise
        """
        start_time = time.time()
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room.id)
            message_id = str(message.id)
            score = message.created_at.timestamp()
            ttl_seconds = cls._get_ttl_hours() * 3600

            # Compute badge status and serialize
            username_is_reserved = cls._compute_username_is_reserved(message)
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Build pipeline for atomic write
            pipe = redis_client.pipeline()

            # 1. HSET message data to hash
            data_key = cls.MSG_DATA_KEY.format(room_id=room_id)
            pipe.hset(data_key, message_id, message_json)
            pipe.expire(data_key, ttl_seconds)

            # 2. ZADD to timeline
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id)
            pipe.zadd(timeline_key, {message_id: score})
            pipe.expire(timeline_key, ttl_seconds)

            # 3. Route to filter indexes
            sender_username = message.username.lower()

            # Host index
            if message.is_from_host:
                host_key = cls.HOST_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(host_key, {message_id: score})
                pipe.expire(host_key, ttl_seconds)

            # Focus index: sender always sees own messages
            focus_key = cls.FOCUS_INDEX_KEY.format(room_id=room_id, username=sender_username)
            pipe.zadd(focus_key, {message_id: score})
            pipe.expire(focus_key, ttl_seconds)

            # Focus index: if reply, add to parent author's focus
            if message.reply_to:
                parent_username = message.reply_to.username.lower()
                if parent_username != sender_username:
                    parent_focus_key = cls.FOCUS_INDEX_KEY.format(room_id=room_id, username=parent_username)
                    pipe.zadd(parent_focus_key, {message_id: score})
                    pipe.expire(parent_focus_key, ttl_seconds)

                    # If host replied to someone, also add the PARENT message to that user's focus
                    # so they see the context of what the host replied to
                    if message.is_from_host:
                        parent_msg_id = str(message.reply_to.id)
                        parent_score = message.reply_to.created_at.timestamp()
                        pipe.zadd(parent_focus_key, {parent_msg_id: parent_score})

            # Highlight index
            if message.is_highlight:
                highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(highlight_key, {message_id: score})
                pipe.expire(highlight_key, ttl_seconds)

            # Gift indexes
            if message.message_type == 'gift':
                gifts_key = cls.GIFTS_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(gifts_key, {message_id: score})
                pipe.expire(gifts_key, ttl_seconds)

                # Per-user gift index: sender
                gifts_sender_key = cls.GIFTS_USER_INDEX_KEY.format(room_id=room_id, username=sender_username)
                pipe.zadd(gifts_sender_key, {message_id: score})
                pipe.expire(gifts_sender_key, ttl_seconds)

                # Per-user gift index: recipient
                if message.gift_recipient:
                    recipient_username = message.gift_recipient.lower()
                    if recipient_username != sender_username:
                        gifts_recipient_key = cls.GIFTS_USER_INDEX_KEY.format(room_id=room_id, username=recipient_username)
                        pipe.zadd(gifts_recipient_key, {message_id: score})
                        pipe.expire(gifts_recipient_key, ttl_seconds)

            pipe.execute()

            # Trim timeline to max (separate operation)
            max_messages = cls._get_max_messages()
            total_messages = redis_client.zcard(timeline_key)
            if total_messages > max_messages:
                # Get IDs being removed so we can clean hash + indexes
                overflow = total_messages - max_messages
                removed_ids = redis_client.zrange(timeline_key, 0, overflow - 1)
                cls._evict_messages(redis_client, room_id, removed_ids)

            # Monitor: Cache write
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_write(room_id, count=1, duration_ms=duration_ms)

            return True

        except Exception as e:
            # Log error but don't crash (PostgreSQL has the data)
            print(f"Redis cache error (add_message): {e}")
            return False

    @classmethod
    def _evict_messages(cls, redis_client, room_id: str, message_ids: list):
        """Remove evicted messages from hash, timeline, and all filter indexes."""
        if not message_ids:
            return
        pipe = redis_client.pipeline()
        data_key = cls.MSG_DATA_KEY.format(room_id=room_id)
        timeline_key = cls.TIMELINE_KEY.format(room_id=room_id)

        for mid_bytes in message_ids:
            mid = mid_bytes.decode() if isinstance(mid_bytes, bytes) else mid_bytes
            pipe.hdel(data_key, mid)
            pipe.zrem(timeline_key, mid)

        # Clean all index keys for this room
        idx_pattern = f"room:{room_id}:idx:*"
        for idx_key in redis_client.scan_iter(match=idx_pattern, count=100):
            for mid_bytes in message_ids:
                mid = mid_bytes.decode() if isinstance(mid_bytes, bytes) else mid_bytes
                pipe.zrem(idx_key, mid)

        pipe.execute()

    @classmethod
    def update_message(cls, message: Message) -> bool:
        """
        Update an existing message in the Redis hash.

        O(1) operation: HGET to check existence, HSET to overwrite.
        Indexes are NOT touched — they store only message IDs and timestamps,
        which don't change on updates (reactions, pins, gift ack, etc.).

        Args:
            message: Message instance with updated data

        Returns:
            True if successfully updated, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room.id)
            message_id = str(message.id)
            data_key = cls.MSG_DATA_KEY.format(room_id=room_id)

            # Check if message exists in hash
            existing = redis_client.hget(data_key, message_id)
            if existing is None:
                # Not in cache — add it (will also write indexes)
                return cls.add_message(message)

            # Compute badge status and serialize
            username_is_reserved = cls._compute_username_is_reserved(message)
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # O(1) overwrite in hash
            redis_client.hset(data_key, message_id, message_json)

            return True

        except Exception as e:
            print(f"Redis cache error (update_message): {e}")
            return False

    @classmethod
    def _fetch_by_ids(cls, redis_client, room_id: str, message_ids: list) -> List[Dict[str, Any]]:
        """
        Fetch message data from hash for a list of message IDs.

        Args:
            redis_client: Redis client
            room_id: Room UUID string
            message_ids: List of message ID strings/bytes (in desired order)

        Returns:
            List of message dicts (preserves input order, skips missing)
        """
        if not message_ids:
            return []

        data_key = cls.MSG_DATA_KEY.format(room_id=room_id)
        # Decode bytes to strings for HMGET
        str_ids = [mid.decode() if isinstance(mid, bytes) else mid for mid in message_ids]
        raw_values = redis_client.hmget(data_key, str_ids)

        messages = []
        for val in raw_values:
            if val is None:
                continue
            try:
                raw = val.decode() if isinstance(val, bytes) else val
                messages.append(json.loads(raw))
            except (json.JSONDecodeError, AttributeError):
                continue
        return messages

    @classmethod
    def get_messages(cls, room_id: Union[str, UUID], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent messages from Redis cache.

        Reads from timeline index → hash lookup.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            limit: Maximum number of messages to return

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id_str)

            # Get last N message IDs from timeline (oldest first)
            message_ids = redis_client.zrange(timeline_key, -limit, -1)

            # Fetch full data from hash
            messages = cls._fetch_by_ids(redis_client, room_id_str, message_ids)

            # Monitor: Cache read
            duration_ms = (time.time() - start_time) * 1000
            hit = len(messages) > 0
            monitor.log_cache_read(
                room_id_str,
                hit=hit,
                count=len(messages),
                duration_ms=duration_ms,
                source='redis'
            )

            return messages

        except Exception as e:
            print(f"Redis cache error (get_messages): {e}")

            # Monitor: Cache read error (miss)
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(
                room_id_str,
                hit=False,
                count=0,
                duration_ms=duration_ms,
                source='redis'
            )

            return []

    @classmethod
    def _get_ids_before(cls, redis_client, index_key: str, before_timestamp: float, limit: int) -> list:
        """
        Get message IDs from an index before a timestamp, newest-first then reversed.

        Returns list of message IDs in chronological order (oldest first).
        """
        # ZREVRANGEBYSCORE: newest-first, exclusive upper bound
        ids = redis_client.zrevrangebyscore(
            index_key,
            max=f'({before_timestamp}',
            min='-inf',
            start=0,
            num=limit
        )
        # Reverse to chronological order
        ids.reverse()
        return ids

    @classmethod
    def get_messages_before(cls, room_id: Union[str, UUID], before_timestamp: float, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get messages before a specific timestamp (for pagination/scroll-up).

        Reads from timeline index → hash lookup.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            before_timestamp: Unix timestamp to query before
            limit: Maximum messages to return

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id_str)

            # Get IDs before timestamp
            message_ids = cls._get_ids_before(redis_client, timeline_key, before_timestamp, limit)

            # Fetch full data from hash
            messages = cls._fetch_by_ids(redis_client, room_id_str, message_ids)

            # Monitor: Cache read (pagination)
            duration_ms = (time.time() - start_time) * 1000
            hit = len(messages) > 0
            monitor.log_cache_read(
                room_id_str,
                hit=hit,
                count=len(messages),
                duration_ms=duration_ms,
                source='redis'
            )

            return messages

        except Exception as e:
            print(f"Redis cache error (get_messages_before): {e}")

            # Monitor: Cache read error (miss)
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(
                room_id_str,
                hit=False,
                count=0,
                duration_ms=duration_ms,
                source='redis'
            )

            return []

    @classmethod
    def add_to_highlight_index(cls, message) -> bool:
        """Add a message to the highlight index (appears in all users' Focus view)."""
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room_id)
            message_id = str(message.id)
            score = message.created_at.timestamp()
            ttl_seconds = cls._get_ttl_hours() * 3600
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id)
            redis_client.zadd(highlight_key, {message_id: score})
            redis_client.expire(highlight_key, ttl_seconds)
            return True
        except Exception as e:
            print(f"Redis cache error (add_to_highlight_index): {e}")
            return False

    @classmethod
    def remove_from_highlight_index(cls, room_id: Union[str, UUID], message_id: str) -> bool:
        """Remove a message from the highlight index."""
        try:
            redis_client = cls._get_redis_client()
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=str(room_id))
            redis_client.zrem(highlight_key, message_id)
            return True
        except Exception as e:
            print(f"Redis cache error (remove_from_highlight_index): {e}")
            return False

    @classmethod
    def get_highlight_messages(cls, room_id: Union[str, UUID],
                                limit: int = 50, before_timestamp: float = None) -> List[Dict[str, Any]]:
        """Get highlight messages for a room."""
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id_str)

            if before_timestamp:
                max_score = f'({before_timestamp}'
            else:
                max_score = '+inf'

            results = redis_client.zrangebyscore(highlight_key, '-inf', max_score, withscores=True)

            # Sort by timestamp, take last N
            sorted_ids = sorted(
                [(mid.decode() if isinstance(mid, bytes) else mid, score) for mid, score in results],
                key=lambda x: x[1]
            )[-limit:]

            ordered_ids = [mid for mid, _ in sorted_ids]
            messages = cls._fetch_by_ids(redis_client, room_id_str, ordered_ids)

            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=len(messages) > 0,
                                   count=len(messages), duration_ms=duration_ms, source='redis')
            return messages

        except Exception as e:
            print(f"Redis cache error (get_highlight_messages): {e}")
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=False, count=0,
                                   duration_ms=duration_ms, source='redis')
            return []

    @classmethod
    def get_focus_messages(cls, room_id: Union[str, UUID], username: str,
                           limit: int = 50, before_timestamp: float = None) -> List[Dict[str, Any]]:
        """
        Get focus-mode messages: merge user's focus index + host index.

        Focus contains: user's own messages, replies to user, host messages,
        and context messages (parent messages the host replied to).

        Args:
            room_id: Chat room UUID
            username: Username to get focus for (case-insensitive)
            limit: Maximum messages to return
            before_timestamp: Optional timestamp for pagination

        Returns:
            List of message dicts (oldest first, chronological order)
        """
        start_time = time.time()
        room_id_str = str(room_id)
        username_lower = username.lower()
        try:
            redis_client = cls._get_redis_client()
            focus_key = cls.FOCUS_INDEX_KEY.format(room_id=room_id_str, username=username_lower)
            host_key = cls.HOST_INDEX_KEY.format(room_id=room_id_str)

            if before_timestamp:
                max_score = f'({before_timestamp}'
            else:
                max_score = '+inf'

            # Get IDs + scores from both indexes
            pipe = redis_client.pipeline()
            pipe.zrangebyscore(focus_key, '-inf', max_score, withscores=True)
            pipe.zrangebyscore(host_key, '-inf', max_score, withscores=True)
            focus_results, host_results = pipe.execute()

            # Merge by message ID (dedup), keeping score for ordering
            merged = {}
            for mid, score in focus_results:
                mid_str = mid.decode() if isinstance(mid, bytes) else mid
                merged[mid_str] = score
            for mid, score in host_results:
                mid_str = mid.decode() if isinstance(mid, bytes) else mid
                if mid_str not in merged:
                    merged[mid_str] = score

            # Sort by timestamp, take last N
            sorted_ids = sorted(merged.items(), key=lambda x: x[1])
            if before_timestamp:
                # Already filtered by score, take last `limit`
                sorted_ids = sorted_ids[-limit:]
            else:
                sorted_ids = sorted_ids[-limit:]

            # Fetch full data in order
            ordered_ids = [mid for mid, _ in sorted_ids]
            messages = cls._fetch_by_ids(redis_client, room_id_str, ordered_ids)

            # Monitor
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=len(messages) > 0,
                                   count=len(messages), duration_ms=duration_ms, source='redis')

            return messages

        except Exception as e:
            print(f"Redis cache error (get_focus_messages): {e}")
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=False, count=0,
                                   duration_ms=duration_ms, source='redis')
            return []

    @classmethod
    def get_gift_messages(cls, room_id: Union[str, UUID], username: str = None,
                          limit: int = 50, before_timestamp: float = None) -> List[Dict[str, Any]]:
        """
        Get gift messages from Redis cache.

        If username is provided, returns gifts for that user (sent or received).
        Otherwise returns all gifts in the room.

        Args:
            room_id: Chat room UUID
            username: Optional username to filter by (case-insensitive)
            limit: Maximum messages to return
            before_timestamp: Optional timestamp for pagination

        Returns:
            List of message dicts (oldest first, chronological order)
        """
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()

            # Pick the right index
            if username:
                index_key = cls.GIFTS_USER_INDEX_KEY.format(
                    room_id=room_id_str, username=username.lower()
                )
            else:
                index_key = cls.GIFTS_INDEX_KEY.format(room_id=room_id_str)

            if before_timestamp:
                message_ids = cls._get_ids_before(redis_client, index_key, before_timestamp, limit)
            else:
                message_ids = redis_client.zrange(index_key, -limit, -1)

            messages = cls._fetch_by_ids(redis_client, room_id_str, message_ids)

            # Monitor
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=len(messages) > 0,
                                   count=len(messages), duration_ms=duration_ms, source='redis')

            return messages

        except Exception as e:
            print(f"Redis cache error (get_gift_messages): {e}")
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=False, count=0,
                                   duration_ms=duration_ms, source='redis')
            return []

    @classmethod
    def add_pinned_message(cls, message: Message) -> bool:
        """
        Add or update a message in the pinned messages cache.

        Uses new structure:
        - room:{room_id}:pinned:{message_id} = JSON message data
        - room:{room_id}:pinned_order = sorted set (message_id: pin_amount_paid)

        This allows updating pin_amount_paid without race conditions.
        """
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room.id)
            message_id = str(message.id)

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Keys
            data_key = cls.PINNED_MESSAGE_KEY.format(room_id=room_id, message_id=message_id)
            order_key = cls.PINNED_ORDER_KEY.format(room_id=room_id)

            # Score = current_pin_amount (session value for bidding, not lifetime total)
            score = float(message.current_pin_amount) if message.current_pin_amount else 0.0

            # Use pipeline for atomic update
            pipe = redis_client.pipeline()

            # Set message data (overwrites if exists)
            pipe.set(data_key, message_json)
            pipe.expire(data_key, 7 * 24 * 3600)  # 7 days TTL

            # Update order sorted set (overwrites score if exists)
            pipe.zadd(order_key, {message_id: score})
            pipe.expire(order_key, 7 * 24 * 3600)  # 7 days TTL

            pipe.execute()

            return True

        except Exception as e:
            print(f"Redis cache error (add_pinned_message): {e}")
            return False

    @classmethod
    def remove_pinned_message(cls, room_id: Union[str, UUID], message_id: str) -> bool:
        """
        Remove a message from the pinned cache.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_id: Message UUID (as string)

        Returns:
            True if removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)

            # Keys
            data_key = cls.PINNED_MESSAGE_KEY.format(room_id=room_id_str, message_id=message_id)
            order_key = cls.PINNED_ORDER_KEY.format(room_id=room_id_str)

            # Use pipeline for atomic removal
            pipe = redis_client.pipeline()
            pipe.delete(data_key)
            pipe.zrem(order_key, message_id)
            results = pipe.execute()

            # Return True if data key was deleted
            return results[0] > 0

        except Exception as e:
            print(f"Redis cache error (remove_pinned_message): {e}")
            return False

    @classmethod
    def get_pinned_messages(cls, room_id: Union[str, UUID]) -> List[Dict[str, Any]]:
        """
        Get all active pinned messages for a chat, ordered by pin_amount_paid (highest first).

        Automatically filters out expired pins (sticky_until < now).
        Falls back to database if Redis cache is empty.
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)
            order_key = cls.PINNED_ORDER_KEY.format(room_id=room_id_str)

            # Get all message IDs ordered by score descending (highest amount first)
            message_ids = redis_client.zrevrange(order_key, 0, -1)

            if not message_ids:
                # Fallback to database and repopulate cache
                return cls._get_pinned_messages_from_db(room_id)

            # Build keys for all pinned messages
            data_keys = [
                cls.PINNED_MESSAGE_KEY.format(room_id=room_id_str, message_id=mid.decode() if isinstance(mid, bytes) else mid)
                for mid in message_ids
            ]

            # Batch fetch all message data
            message_jsons = redis_client.mget(data_keys)

            # Parse and filter expired pins
            now = time.time()
            messages = []
            expired_ids = []

            for mid, msg_json in zip(message_ids, message_jsons):
                if msg_json is None:
                    # Data key missing, clean up order set
                    expired_ids.append(mid)
                    continue

                try:
                    msg_data = json.loads(msg_json)

                    # Check if pin has expired
                    sticky_until = msg_data.get('sticky_until')
                    if sticky_until:
                        expiry_time = datetime.fromisoformat(sticky_until).timestamp()
                        if expiry_time < now:
                            expired_ids.append(mid)
                            continue

                    messages.append(msg_data)
                except (json.JSONDecodeError, ValueError):
                    expired_ids.append(mid)
                    continue

            # Clean up expired entries
            if expired_ids:
                pipe = redis_client.pipeline()
                for mid in expired_ids:
                    mid_str = mid.decode() if isinstance(mid, bytes) else mid
                    pipe.delete(cls.PINNED_MESSAGE_KEY.format(room_id=room_id_str, message_id=mid_str))
                    pipe.zrem(order_key, mid)
                pipe.execute()

            return messages

        except Exception as e:
            print(f"Redis cache error (get_pinned_messages): {e}")
            # Fallback to database on Redis error
            return cls._get_pinned_messages_from_db(room_id)

    @classmethod
    def _get_pinned_messages_from_db(cls, room_id: Union[str, UUID]) -> List[Dict[str, Any]]:
        """
        Fallback method to get pinned messages from database and repopulate Redis cache.
        """
        from django.utils import timezone

        try:
            # Query database for active pinned messages
            pinned_messages = Message.objects.filter(
                chat_room_id=room_id,
                is_pinned=True,
                sticky_until__gt=timezone.now(),
                is_deleted=False
            ).select_related('user', 'chat_room', 'reply_to').order_by('-current_pin_amount')

            messages = []
            for message in pinned_messages:
                # Serialize and add to cache
                username_is_reserved = cls._compute_username_is_reserved(message)
                msg_data = cls._serialize_message(message, username_is_reserved)
                messages.append(msg_data)

                # Repopulate Redis cache
                cls.add_pinned_message(message)

            return messages

        except Exception as e:
            print(f"Database fallback error (get_pinned_messages): {e}")
            return []

    @classmethod
    def get_top_pinned_message(cls, room_id: Union[str, UUID]) -> Optional[Dict[str, Any]]:
        """
        Get the top (highest value) active pinned message for a chat.

        Returns None if no active pins exist.
        """
        messages = cls.get_pinned_messages(room_id)
        return messages[0] if messages else None

    @classmethod
    def get_current_pin_value_cents(cls, room_id: Union[str, UUID]) -> int:
        """
        Get the current highest pin value for a chat in cents.

        Uses current_pin_amount (session value) for bidding, not lifetime total.
        Returns 0 if no active pins exist.
        """
        top_pin = cls.get_top_pinned_message(room_id)
        if top_pin:
            # current_pin_amount is the session value for bidding (dollars -> cents)
            return int(float(top_pin.get('current_pin_amount', 0)) * 100)
        return 0

    @classmethod
    def set_message_reactions(cls, room_id: Union[str, UUID], message_id: str, reactions: List[Dict[str, Any]]) -> bool:
        """
        Cache reaction summary for a message.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_id: Message UUID (as string)
            reactions: List of reaction summary dicts with keys: emoji, count, users
                      Example: [{"emoji": "👍", "count": 5, "users": ["alice", "bob"]}]

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)
            key = cls.REACTIONS_KEY.format(room_id=room_id_str, message_id=message_id)

            # Build hash mapping: emoji -> count
            # Store as strings since Redis hashes store string values
            reaction_hash = {}
            for reaction in reactions:
                emoji = reaction.get('emoji')
                count = reaction.get('count', 0)
                if emoji:
                    reaction_hash[emoji] = str(count)

            if reaction_hash:
                # Set the hash with all emoji counts
                redis_client.hset(key, mapping=reaction_hash)

                # Set TTL to match message cache TTL (from Constance)
                ttl_seconds = cls._get_ttl_hours() * 3600
                redis_client.expire(key, ttl_seconds)
            else:
                # No reactions, delete the key if it exists
                redis_client.delete(key)

            return True

        except Exception as e:
            print(f"Redis cache error (set_message_reactions): {e}")
            return False

    @classmethod
    def increment_reaction(cls, room_id: Union[str, UUID], message_id: str, emoji: str) -> int:
        """
        Atomically increment a reaction count for a specific emoji.
        Uses HINCRBY for O(1) performance instead of full recount.

        Returns:
            New count after increment, or -1 on error
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.REACTIONS_KEY.format(room_id=str(room_id), message_id=message_id)
            new_count = redis_client.hincrby(key, emoji, 1)
            # Ensure TTL is set (in case key was just created)
            ttl = redis_client.ttl(key)
            if ttl < 0:
                ttl_seconds = cls._get_ttl_hours() * 3600
                redis_client.expire(key, ttl_seconds)
            return new_count
        except Exception as e:
            print(f"Redis cache error (increment_reaction): {e}")
            return -1

    @classmethod
    def decrement_reaction(cls, room_id: Union[str, UUID], message_id: str, emoji: str) -> int:
        """
        Atomically decrement a reaction count for a specific emoji.
        Cleans up zero/negative counts with HDEL.

        Returns:
            New count after decrement (min 0), or -1 on error
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.REACTIONS_KEY.format(room_id=str(room_id), message_id=message_id)
            new_count = redis_client.hincrby(key, emoji, -1)
            if new_count <= 0:
                redis_client.hdel(key, emoji)
                return 0
            return new_count
        except Exception as e:
            print(f"Redis cache error (decrement_reaction): {e}")
            return -1

    @classmethod
    def get_message_reactions(cls, room_id: Union[str, UUID], message_id: str) -> List[Dict[str, Any]]:
        """
        Get cached reactions for a single message.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_id: Message UUID (as string)

        Returns:
            List of reaction summary dicts with keys: emoji, count
            Returns empty list if cache miss (caller should rebuild from PostgreSQL)
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)
            key = cls.REACTIONS_KEY.format(room_id=room_id_str, message_id=message_id)

            # Get all emoji -> count mappings
            reaction_hash = redis_client.hgetall(key)

            if not reaction_hash:
                return []

            # Convert back to list of dicts
            reactions = []
            for emoji_bytes, count_bytes in reaction_hash.items():
                emoji = emoji_bytes.decode('utf-8') if isinstance(emoji_bytes, bytes) else emoji_bytes
                count_str = count_bytes.decode('utf-8') if isinstance(count_bytes, bytes) else count_bytes
                try:
                    count = int(count_str)
                    reactions.append({"emoji": emoji, "count": count})
                except (ValueError, TypeError):
                    continue

            return reactions

        except Exception as e:
            print(f"Redis cache error (get_message_reactions): {e}")
            return []

    @classmethod
    def batch_get_reactions(cls, room_id: Union[str, UUID], message_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Batch fetch reactions for multiple messages using Redis pipeline.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_ids: List of message UUIDs (as strings)

        Returns:
            Dict mapping message_id -> list of reaction dicts
            Example: {"msg1": [{"emoji": "👍", "count": 5}], "msg2": []}

        Performance: Single Redis round-trip for all messages (pipelined)
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)

            if not message_ids:
                return {}

            # Use pipeline for batch fetch (single round-trip)
            pipeline = redis_client.pipeline()
            keys = []
            for message_id in message_ids:
                key = cls.REACTIONS_KEY.format(room_id=room_id_str, message_id=message_id)
                keys.append(key)
                pipeline.hgetall(key)

            # Execute pipeline and get all results
            results = pipeline.execute()

            # Build result dict
            reactions_by_message = {}
            for message_id, reaction_hash in zip(message_ids, results):
                reactions = []

                if reaction_hash:
                    for emoji_bytes, count_bytes in reaction_hash.items():
                        emoji = emoji_bytes.decode('utf-8') if isinstance(emoji_bytes, bytes) else emoji_bytes
                        count_str = count_bytes.decode('utf-8') if isinstance(count_bytes, bytes) else count_bytes
                        try:
                            count = int(count_str)
                            reactions.append({"emoji": emoji, "count": count})
                        except (ValueError, TypeError):
                            continue

                reactions_by_message[message_id] = reactions

            return reactions_by_message

        except Exception as e:
            print(f"Redis cache error (batch_get_reactions): {e}")
            return {}

    @classmethod
    def remove_message(cls, room_id: Union[str, UUID], message_id: str) -> bool:
        """
        Remove a specific message from cache (for soft deletes).

        Removes from: hash, timeline, all filter indexes, pinned cache, reactions.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_id: Message UUID (as string)

        Returns:
            True if message was found and removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)

            data_key = cls.MSG_DATA_KEY.format(room_id=room_id_str)
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id_str)

            # Check if message exists in hash
            removed = redis_client.hdel(data_key, message_id) > 0

            # Remove from timeline
            pipe = redis_client.pipeline()
            pipe.zrem(timeline_key, message_id)

            # Remove from all filter indexes (scan for idx:* keys)
            idx_pattern = f"room:{room_id_str}:idx:*"
            for idx_key in redis_client.scan_iter(match=idx_pattern, count=100):
                pipe.zrem(idx_key, message_id)

            # Remove reactions cache
            reactions_key = cls.REACTIONS_KEY.format(room_id=room_id_str, message_id=message_id)
            pipe.delete(reactions_key)

            pipe.execute()

            # Remove from pinned messages cache (if it exists there)
            cls.remove_pinned_message(room_id_str, message_id)

            if removed:
                print(f"Removed message {message_id} from Redis cache for room {room_id_str}")

            return removed

        except Exception as e:
            print(f"Redis cache error (remove_message): {e}")
            return False

    @classmethod
    def clear_room_cache(cls, room_id: Union[str, UUID]):
        """
        Clear all cached data for a chat room.

        Uses SCAN to find all room:{room_id}:* keys and deletes them.
        This covers: msg_data, timeline, all idx:*, pinned:*, reactions:*, etc.
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)

            # SCAN for all keys belonging to this room
            pattern = f"room:{room_id_str}:*"
            keys_to_delete = []
            for key in redis_client.scan_iter(match=pattern, count=200):
                keys_to_delete.append(key)

            if keys_to_delete:
                redis_client.delete(*keys_to_delete)

        except Exception as e:
            print(f"Redis cache error (clear_room_cache): {e}")

    # Backwards compatibility alias
    @classmethod
    def clear_chat_cache(cls, room_id: Union[str, UUID]):
        """Alias for clear_room_cache for backwards compatibility."""
        cls.clear_room_cache(room_id)


class UserBlockCache:
    """Redis cache manager for user blocking (site-wide)"""

    # Cache key pattern: Set of blocked usernames per user
    BLOCKED_KEY = "user:{user_id}:blocked_usernames"

    @classmethod
    def _get_redis_client(cls):
        """Get raw Redis client from django-redis"""
        return cache.client.get_client()

    @classmethod
    def get_blocked_usernames(cls, user_id: int) -> set:
        """
        Get all blocked usernames for a user.

        Strategy:
        1. Try Redis first (fast, O(1) lookup)
        2. On cache miss, load from PostgreSQL and populate Redis
        3. No TTL on Redis keys (mute lists are small and rarely change)

        Args:
            user_id: User ID (registered user)

        Returns:
            Set of blocked usernames
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.BLOCKED_KEY.format(user_id=user_id)

            # Try Redis first
            blocked_usernames = redis_client.smembers(key)

            # Cache hit - decode and return
            if blocked_usernames:
                result = set()
                for username_bytes in blocked_usernames:
                    username = username_bytes.decode('utf-8') if isinstance(username_bytes, bytes) else username_bytes
                    result.add(username)
                return result

            # Cache miss - fallback to PostgreSQL
            print(f"Redis cache miss for user {user_id} mute list, loading from PostgreSQL")
            from chats.models import UserBlock
            blocks = UserBlock.objects.filter(blocker_id=user_id).values_list('blocked_username', flat=True)
            result = set(blocks)

            # Populate Redis for next time
            if result:
                for username in result:
                    redis_client.sadd(key, username)

                # Apply TTL if configured (0 = no expiry)
                from constance import config
                ttl_hours = config.USER_BLOCK_CACHE_TTL_HOURS
                if ttl_hours > 0:
                    redis_client.expire(key, ttl_hours * 3600)

                print(f"Populated Redis cache with {len(result)} blocked usernames for user {user_id} (TTL: {'never' if ttl_hours == 0 else f'{ttl_hours}h'})")

            return result

        except Exception as e:
            print(f"Redis error, falling back to PostgreSQL: {e}")
            # Redis completely down - query PostgreSQL directly
            try:
                from chats.models import UserBlock
                blocks = UserBlock.objects.filter(blocker_id=user_id).values_list('blocked_username', flat=True)
                return set(blocks)
            except Exception as db_error:
                print(f"PostgreSQL error: {db_error}")
                return set()

    @classmethod
    def add_blocked_username(cls, user_id: int, blocked_username: str) -> bool:
        """
        Add a blocked username to Redis cache.

        Args:
            user_id: User ID (registered user)
            blocked_username: Username to block

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.BLOCKED_KEY.format(user_id=user_id)

            # SADD adds member to set (idempotent, no duplicates)
            redis_client.sadd(key, blocked_username)

            # NO TTL - persist indefinitely (mute lists are tiny, no memory concern)

            return True

        except Exception as e:
            print(f"Redis cache error (add_blocked_username): {e}")
            return False

    @classmethod
    def remove_blocked_username(cls, user_id: int, blocked_username: str) -> bool:
        """
        Remove a blocked username from Redis cache.

        Args:
            user_id: User ID (registered user)
            blocked_username: Username to unblock

        Returns:
            True if successfully removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.BLOCKED_KEY.format(user_id=user_id)

            # SREM removes member from set
            redis_client.srem(key, blocked_username)

            return True

        except Exception as e:
            print(f"Redis cache error (remove_blocked_username): {e}")
            return False

    @classmethod
    def sync_from_database(cls, user_id: int):
        """
        Sync blocked usernames from PostgreSQL to Redis.

        Useful for populating cache after Redis restart or manual cache invalidation.

        Args:
            user_id: User ID (registered user)
        """
        try:
            from chats.models import UserBlock

            # Query all blocks for this user
            blocks = UserBlock.objects.filter(blocker_id=user_id).values_list('blocked_username', flat=True)

            if not blocks:
                return

            # Write to Redis
            redis_client = cls._get_redis_client()
            key = cls.BLOCKED_KEY.format(user_id=user_id)

            # Clear existing set and add all blocks
            redis_client.delete(key)
            for blocked_username in blocks:
                redis_client.sadd(key, blocked_username)

            # NO TTL - persist indefinitely

        except Exception as e:
            print(f"Redis cache error (sync_from_database): {e}")

    @classmethod
    def clear_user_blocks(cls, user_id: int):
        """
        Clear all cached blocks for a user.

        Args:
            user_id: User ID (registered user)
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.BLOCKED_KEY.format(user_id=user_id)
            redis_client.delete(key)

        except Exception as e:
            print(f"Redis cache error (clear_user_blocks): {e}")


class GiftCatalogCache:
    """Redis cache for the gift catalog (single key, 24h TTL)"""

    CATALOG_KEY = "gift_catalog"
    TTL_SECONDS = 24 * 3600  # 24 hours

    @classmethod
    def _get_redis_client(cls):
        return cache.client.get_client()

    @classmethod
    def get_catalog(cls) -> List[Dict[str, Any]]:
        """
        Get gift catalog from Redis cache, falling back to DB.

        Returns:
            List of gift catalog item dicts
        """
        try:
            redis_client = cls._get_redis_client()
            cached = redis_client.get(cls.CATALOG_KEY)

            if cached:
                data = cached.decode('utf-8') if isinstance(cached, bytes) else cached
                return json.loads(data)

            # Cache miss - load from DB
            return cls._load_from_db()

        except Exception as e:
            print(f"Redis cache error (gift_catalog): {e}")
            return cls._load_from_db_direct()

    @classmethod
    def _load_from_db(cls) -> List[Dict[str, Any]]:
        """Load catalog from DB and populate Redis cache."""
        from chats.models import GiftCatalogItem

        items = list(GiftCatalogItem.objects.filter(is_active=True).values(
            'gift_id', 'emoji', 'name', 'price_cents', 'category', 'sort_order'
        ))

        # Populate cache
        try:
            redis_client = cls._get_redis_client()
            redis_client.set(cls.CATALOG_KEY, json.dumps(items), ex=cls.TTL_SECONDS)
        except Exception as e:
            print(f"Redis cache error (gift_catalog populate): {e}")

        return items

    @classmethod
    def _load_from_db_direct(cls) -> List[Dict[str, Any]]:
        """Direct DB load without caching (Redis down fallback)."""
        from chats.models import GiftCatalogItem
        return list(GiftCatalogItem.objects.filter(is_active=True).values(
            'gift_id', 'emoji', 'name', 'price_cents', 'category', 'sort_order'
        ))

    @classmethod
    def invalidate(cls):
        """Invalidate the catalog cache."""
        try:
            redis_client = cls._get_redis_client()
            redis_client.delete(cls.CATALOG_KEY)
        except Exception as e:
            print(f"Redis cache error (gift_catalog invalidate): {e}")


class UnacknowledgedGiftCache:
    """Redis cache for per-user unacknowledged gift queues"""

    UNACKED_KEY = "room:{room_id}:unacked_gifts:{username}"
    TTL_SECONDS = 7 * 24 * 3600  # 7 days

    @classmethod
    def _get_redis_client(cls):
        return cache.client.get_client()

    @classmethod
    def push_gift(cls, room_id: str, username: str, gift_data: Dict[str, Any]) -> bool:
        """Push a gift to the recipient's unacknowledged queue."""
        try:
            redis_client = cls._get_redis_client()
            key = cls.UNACKED_KEY.format(room_id=room_id, username=username)
            redis_client.lpush(key, json.dumps(gift_data))
            redis_client.expire(key, cls.TTL_SECONDS)
            return True
        except Exception as e:
            print(f"Redis cache error (push_gift): {e}")
            return False

    @classmethod
    def get_unacked(cls, room_id: str, username: str) -> List[Dict[str, Any]]:
        """Get all unacknowledged gifts for a user in a room."""
        try:
            redis_client = cls._get_redis_client()
            key = cls.UNACKED_KEY.format(room_id=room_id, username=username)
            items = redis_client.lrange(key, 0, -1)

            gifts = []
            for item in items:
                data = item.decode('utf-8') if isinstance(item, bytes) else item
                try:
                    gifts.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
            return gifts
        except Exception as e:
            print(f"Redis cache error (get_unacked): {e}")
            return []

    @classmethod
    def acknowledge_one(cls, room_id: str, username: str, gift_id: str) -> bool:
        """Remove a single gift from the unacknowledged queue by gift ID."""
        try:
            redis_client = cls._get_redis_client()
            key = cls.UNACKED_KEY.format(room_id=room_id, username=username)
            items = redis_client.lrange(key, 0, -1)

            for item in items:
                data = item.decode('utf-8') if isinstance(item, bytes) else item
                try:
                    gift = json.loads(data)
                    if gift.get('id') == gift_id:
                        redis_client.lrem(key, 1, item)
                        return True
                except json.JSONDecodeError:
                    continue
            return False
        except Exception as e:
            print(f"Redis cache error (acknowledge_one): {e}")
            return False

    @classmethod
    def acknowledge_all(cls, room_id: str, username: str) -> int:
        """Remove all unacknowledged gifts for a user. Returns count removed."""
        try:
            redis_client = cls._get_redis_client()
            key = cls.UNACKED_KEY.format(room_id=room_id, username=username)
            count = redis_client.llen(key)
            redis_client.delete(key)
            return count
        except Exception as e:
            print(f"Redis cache error (acknowledge_all): {e}")
            return 0


class RoomNotificationCache:
    """
    Redis SET-based room notification indicators.

    Per room type, stores a SET of participation_ids who have SEEN the latest content.
    If participation_id is in the set → no notification. If not → notification.

    Uses ChatParticipation.id (UUID) as the stable identity — unlike session_key
    (which can change across page refreshes for anonymous users) or user_id
    (which is None for anonymous identities), participation_id is stable and
    unique per identity per chat room.

    Keys: room:{room_id}:seen:{room_type}
    TTL: 7 days (content older than that doesn't need notification)
    """
    # FAB-linked notification types
    FAB_ROOMS = ('highlight', 'focus', 'gifts')
    # General-purpose notification types (not tied to FABs — for future use: push notifs, chat list badges, etc.)
    GENERAL_TYPES = ('messages', 'verified')
    # All valid types
    VALID_ROOMS = FAB_ROOMS + GENERAL_TYPES
    TTL_SECONDS = 7 * 24 * 3600  # 7 days

    @classmethod
    def _key(cls, room_id, room_type):
        return f'room:{room_id}:seen:{room_type}'

    @classmethod
    def _get_redis_client(cls):
        return cache.client.get_client()

    @classmethod
    def resolve_participation_id(cls, chat_room, username=None, user_id=None, session_key=None):
        """Look up the ChatParticipation.id for a user in a room.

        Uses username (most specific), then user_id + is_anonymous_identity=False,
        then session_key as fallback. Returns str(participation_id) or None.
        """
        from chats.models import ChatParticipation
        try:
            if username and chat_room:
                part = ChatParticipation.objects.filter(
                    chat_room=chat_room, username__iexact=username
                ).values_list('id', flat=True).first()
                if part:
                    return str(part)
            if user_id and chat_room:
                part = ChatParticipation.objects.filter(
                    chat_room=chat_room, user_id=user_id, is_anonymous_identity=False
                ).values_list('id', flat=True).first()
                if part:
                    return str(part)
            if session_key and chat_room:
                part = ChatParticipation.objects.filter(
                    chat_room=chat_room, session_key=session_key
                ).values_list('id', flat=True).first()
                if part:
                    return str(part)
        except Exception:
            pass
        return None

    @classmethod
    def mark_new_content(cls, room_id, room_type, actor_user_id=None):
        """New content arrived — clear set, add actor (they don't need notification)."""
        try:
            redis_client = cls._get_redis_client()
            key = cls._key(room_id, room_type)
            pipe = redis_client.pipeline()
            pipe.delete(key)
            if actor_user_id:
                pipe.sadd(key, str(actor_user_id))
            pipe.expire(key, cls.TTL_SECONDS)
            pipe.execute()
        except Exception as e:
            print(f"Redis cache error (mark_new_content): {e}")

    @classmethod
    def mark_seen(cls, room_id, room_type, user_id):
        """User opened this room — they've seen the content."""
        try:
            redis_client = cls._get_redis_client()
            key = cls._key(room_id, room_type)
            redis_client.sadd(key, str(user_id))
            redis_client.expire(key, cls.TTL_SECONDS)
        except Exception as e:
            print(f"Redis cache error (mark_seen): {e}")

    @classmethod
    def has_unseen(cls, room_id, user_id, room_types=None):
        """Check rooms for unseen content — returns dict of booleans.
        room_types defaults to FAB_ROOMS. Pass VALID_ROOMS to include general types."""
        if room_types is None:
            room_types = cls.FAB_ROOMS
        try:
            redis_client = cls._get_redis_client()
            pipe = redis_client.pipeline()
            for room_type in room_types:
                key = cls._key(room_id, room_type)
                pipe.exists(key)
                pipe.sismember(key, str(user_id))
            results = pipe.execute()

            notifications = {}
            for i, room_type in enumerate(room_types):
                key_exists = results[i * 2]
                is_member = results[i * 2 + 1]
                notifications[room_type] = bool(key_exists and not is_member)
            return notifications
        except Exception as e:
            print(f"Redis cache error (has_unseen): {e}")
            return {rt: False for rt in room_types}
