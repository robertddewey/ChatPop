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
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from uuid import UUID
from django.core.cache import cache
from django.conf import settings
from chats.models import Message, ChatParticipation
from .monitoring import monitor

logger = logging.getLogger(__name__)


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
    # Media indexes — membership based on media field presence, gifts excluded
    PHOTO_INDEX_KEY = "room:{room_id}:idx:photo"
    VIDEO_INDEX_KEY = "room:{room_id}:idx:video"
    AUDIO_INDEX_KEY = "room:{room_id}:idx:audio"
    # Hydration flag — set once per room/type after scan of MSG_DATA_KEY
    MEDIA_HYDRATED_KEY = "room:{room_id}:idx:{media_type}:hydrated"
    # Protected message set — membership = "protected from normal eviction".
    # Updated at write time (and on highlight toggle) so eviction does not need
    # to HGET + JSON-parse every candidate. SMEMBERS is one O(N) op vs. N HGETs.
    PROTECTED_SET_KEY = "room:{room_id}:protected"
    # Index registry — Redis SET listing every idx:* key add_message has touched
    # for this room. Eviction reads this instead of `scan_iter` on the keyspace,
    # which is non-deterministic and walks unrelated keys.
    IDX_KEYS_REGISTRY = "room:{room_id}:idx_keys"

    # Legacy key (kept for migration/cleanup reference)
    MESSAGES_KEY = "room:{room_id}:messages"

    # Pinned and reactions (unchanged)
    PINNED_MESSAGE_KEY = "room:{room_id}:pinned:{message_id}"
    PINNED_ORDER_KEY = "room:{room_id}:pinned_order"
    REACTIONS_KEY = "room:{room_id}:reactions:{message_id}"

    # Eviction: how many oldest candidates to inspect for "protected" status
    # before giving up and force-evicting. Higher = more tolerance for
    # protected-dense chats; lower = faster eviction but less density benefit.
    EVICTION_SCAN_LIMIT = 100

    # Eviction batching: don't trim until we're this many messages OVER the cap,
    # then evict this many at once. Amortizes eviction cost ~Nx — at 5 msg/sec
    # post-cap with batch=100, trim fires every ~20s instead of every 200ms.
    # Effective ceiling is `cap + EVICTION_BATCH_SIZE`. Approved 2026-04-15.
    EVICTION_BATCH_SIZE = 100

    @classmethod
    def _get_max_messages(cls) -> int:
        """Get max messages from Constance (dynamic) or fallback to settings (static)"""
        try:
            from constance import config
            return config.REDIS_CACHE_MAX_COUNT
        except:
            return getattr(settings, 'MESSAGE_CACHE_MAX_COUNT', 5000)

    @classmethod
    def _is_protected(cls, msg_data: Dict[str, Any]) -> bool:
        """Check if a message should be retained longer than plain messages.

        Protected messages are those featured in dedicated filter rooms:
        - Highlighted (starred)
        - Has a photo (Photo Room)
        - Has a video (Video Room)
        - Has a voice/audio message (Audio Room)
        - Is a gift (Gift Room — monetary value, important for history)

        Protected messages are skipped during normal eviction until the
        EVICTION_SCAN_LIMIT is exhausted, at which point force-eviction kicks in.
        """
        if msg_data.get('is_highlight'):
            return True
        if msg_data.get('message_type') == 'gift':
            return True
        if msg_data.get('photo_url'):
            return True
        if msg_data.get('video_url'):
            return True
        if msg_data.get('voice_url'):
            return True
        return False

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
    def _enrich_with_cdn_urls(cls, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace proxy URLs in a cached message dict with directly-fetchable
        CloudFront-signed URLs. Mutates AND returns the dict.

        Why at read time, not write time:
        Cached entries can sit in Redis for hours; a CDN-signed URL stored in
        cache would expire (1-hour TTL on signatures) and the next reader
        would get 403s. Signing at read time guarantees fresh URLs.

        Cost: one HMAC sign per non-empty media field per message read
        (microseconds). Avatars in the /api/chats/media/avatars/user/<id>
        form additionally require a single User lookup the first time we
        sign for that user; otherwise zero DB hits.
        """
        from chatpop.utils.media.storage import MediaStorage

        for field in ("avatar_url", "voice_url", "photo_url", "video_url", "video_thumbnail_url"):
            cdn_url = MediaStorage.proxy_url_to_cdn_url(msg.get(field))
            if cdn_url:
                msg[field] = cdn_url

        return msg

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
        # Build reply_to_message object if there's a reply.
        # has_photo / has_video / has_voice flags let the reply preview render
        # the right icon + label (Photo / Video / Voice) instead of falling
        # back to a generic '[Voice message]' string for any media-only parent.
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
                "has_photo": bool(message.reply_to.photo_url),
                "has_video": bool(message.reply_to.video_url),
                "has_voice": bool(message.reply_to.voice_url),
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
            "voice_duration": float(message.voice_duration) if message.voice_duration else None,
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
            "highlighted_at": message.highlighted_at.isoformat() if message.highlighted_at else None,
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
    def _queue_message_to_pipeline(cls, pipe, message: Message, ttl_seconds: int):
        """Queue all Redis writes for a single message onto an existing pipeline.

        Adds: msg_data HSET, timeline ZADD, all relevant filter index ZADDs.
        Does NOT add: protected-SET SADD or registry SADD — those are deferred
        so callers (single-message vs bulk hydration) can batch them efficiently.

        Returns:
            (touched_indexes: List[str], message_data: Dict, message_id: str)
            — `touched_indexes` is the list of every idx:* key written to;
            `message_data` is the serialized dict (caller checks _is_protected);
            `message_id` is the str-uuid of the message.
        """
        room_id = str(message.chat_room.id)
        message_id = str(message.id)
        score = message.created_at.timestamp()

        # Serialize
        username_is_reserved = cls._compute_username_is_reserved(message)
        message_data = cls._serialize_message(message, username_is_reserved)
        message_json = json.dumps(message_data)

        # 1. msg_data HSET
        data_key = cls.MSG_DATA_KEY.format(room_id=room_id)
        pipe.hset(data_key, message_id, message_json)
        pipe.expire(data_key, ttl_seconds)

        # 2. Timeline ZADD
        timeline_key = cls.TIMELINE_KEY.format(room_id=room_id)
        pipe.zadd(timeline_key, {message_id: score})
        pipe.expire(timeline_key, ttl_seconds)

        # 3. Filter indexes
        sender_username = message.username.lower()
        touched_indexes: List[str] = []

        if message.is_from_host:
            host_key = cls.HOST_INDEX_KEY.format(room_id=room_id)
            pipe.zadd(host_key, {message_id: score})
            pipe.expire(host_key, ttl_seconds)
            touched_indexes.append(host_key)

        focus_key = cls.FOCUS_INDEX_KEY.format(room_id=room_id, username=sender_username)
        pipe.zadd(focus_key, {message_id: score})
        pipe.expire(focus_key, ttl_seconds)
        touched_indexes.append(focus_key)

        if message.reply_to:
            parent_username = message.reply_to.username.lower()
            if parent_username != sender_username:
                parent_focus_key = cls.FOCUS_INDEX_KEY.format(room_id=room_id, username=parent_username)
                pipe.zadd(parent_focus_key, {message_id: score})
                pipe.expire(parent_focus_key, ttl_seconds)
                touched_indexes.append(parent_focus_key)

                if message.is_from_host:
                    parent_msg_id = str(message.reply_to.id)
                    parent_score = message.reply_to.created_at.timestamp()
                    pipe.zadd(parent_focus_key, {parent_msg_id: parent_score})

        if message.is_highlight:
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id)
            # Score by highlighted_at so the Highlight Room is ordered by when
            # the host starred the message, not when the message was sent.
            # Fall back to created_at for legacy rows without highlighted_at.
            highlight_score = (message.highlighted_at or message.created_at).timestamp()
            pipe.zadd(highlight_key, {message_id: highlight_score})
            pipe.expire(highlight_key, ttl_seconds)
            touched_indexes.append(highlight_key)

        if message.message_type == 'gift':
            gifts_key = cls.GIFTS_INDEX_KEY.format(room_id=room_id)
            pipe.zadd(gifts_key, {message_id: score})
            pipe.expire(gifts_key, ttl_seconds)
            touched_indexes.append(gifts_key)

            gifts_sender_key = cls.GIFTS_USER_INDEX_KEY.format(room_id=room_id, username=sender_username)
            pipe.zadd(gifts_sender_key, {message_id: score})
            pipe.expire(gifts_sender_key, ttl_seconds)
            touched_indexes.append(gifts_sender_key)

            if message.gift_recipient:
                recipient_username = message.gift_recipient.lower()
                if recipient_username != sender_username:
                    gifts_recipient_key = cls.GIFTS_USER_INDEX_KEY.format(room_id=room_id, username=recipient_username)
                    pipe.zadd(gifts_recipient_key, {message_id: score})
                    pipe.expire(gifts_recipient_key, ttl_seconds)
                    touched_indexes.append(gifts_recipient_key)

        if message.message_type != 'gift':
            if message.photo_url:
                photo_key = cls.PHOTO_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(photo_key, {message_id: score})
                pipe.expire(photo_key, ttl_seconds)
                touched_indexes.append(photo_key)
            if message.video_url:
                video_key = cls.VIDEO_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(video_key, {message_id: score})
                pipe.expire(video_key, ttl_seconds)
                touched_indexes.append(video_key)
            if message.voice_url:
                audio_key = cls.AUDIO_INDEX_KEY.format(room_id=room_id)
                pipe.zadd(audio_key, {message_id: score})
                pipe.expire(audio_key, ttl_seconds)
                touched_indexes.append(audio_key)

        return touched_indexes, message_data, message_id

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
            ttl_seconds = cls._get_ttl_hours() * 3600
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id)

            # Build the pipeline using the shared helper.
            pipe = redis_client.pipeline()
            touched_indexes, message_data, message_id = cls._queue_message_to_pipeline(
                pipe, message, ttl_seconds
            )

            # Register touched indexes so eviction can SREM members from them
            # without scanning the whole Redis keyspace.
            registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id)
            if touched_indexes:
                pipe.sadd(registry_key, *touched_indexes)
                pipe.expire(registry_key, ttl_seconds)

            # Protected SET — eviction reads this once per trim (SMEMBERS) instead
            # of HGET+JSON-parse per candidate. Stay in sync with _is_protected.
            if cls._is_protected(message_data):
                protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id)
                pipe.sadd(protected_key, message_id)
                pipe.expire(protected_key, ttl_seconds)

            pipe.execute()

            # Trim timeline to max, with "protected message" awareness.
            # Protected messages (highlights, gifts, media) are skipped during
            # normal eviction so the filter-room indexes stay dense in Redis.
            #
            # Batching: we don't trim until we're EVICTION_BATCH_SIZE over the
            # cap, then we evict the whole batch at once. This amortizes the
            # eviction cost ~Nx — at sustained 5 msg/sec post-cap with batch=100,
            # one trim per 20s instead of one per write. Effective ceiling is
            # `max_messages + EVICTION_BATCH_SIZE`.
            #
            # Performance: protection status is read from the PROTECTED_SET in
            # one O(N) SMEMBERS call instead of N HGETs + JSON parses.
            max_messages = cls._get_max_messages()
            trim_threshold = max_messages + cls.EVICTION_BATCH_SIZE
            total_messages = redis_client.zcard(timeline_key)
            if total_messages > trim_threshold:
                evict_start = time.time()
                # Aim to bring the cache back down to max_messages exactly.
                overflow = total_messages - max_messages
                # Scan more candidates than needed so we can skip protected ones.
                scan_count = min(total_messages, overflow + cls.EVICTION_SCAN_LIMIT)
                candidate_ids = redis_client.zrange(timeline_key, 0, scan_count - 1)

                # One SMEMBERS instead of N HGETs.
                protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id)
                protected_raw = redis_client.smembers(protected_key)
                protected_ids = {
                    (m.decode() if isinstance(m, bytes) else m)
                    for m in protected_raw
                }

                # Walk from oldest, evicting unprotected until overflow resolved
                to_evict = []
                skipped = []  # Oldest-first, used for force-evict fallback
                for cid in candidate_ids:
                    if len(to_evict) >= overflow:
                        break
                    cid_str = cid.decode() if isinstance(cid, bytes) else cid
                    if cid_str in protected_ids:
                        skipped.append(cid_str)
                    else:
                        to_evict.append(cid_str)

                # If we couldn't find enough unprotected candidates within the
                # scan window, force-evict the oldest (even if protected) to
                # prevent unbounded growth. This only kicks in for chats where
                # the oldest EVICTION_SCAN_LIMIT messages are ALL protected.
                normal_evicted = len(to_evict)
                force_evicted = 0
                if len(to_evict) < overflow:
                    for cid_str in skipped:
                        if len(to_evict) >= overflow:
                            break
                        to_evict.append(cid_str)
                        force_evicted += 1

                if to_evict:
                    cls._evict_messages(redis_client, room_id, to_evict)

                evict_ms = (time.time() - evict_start) * 1000
                monitor.log_eviction(
                    chat_code=room_id,
                    evicted=normal_evicted,
                    protected_skipped=len(skipped) - force_evicted,
                    force_evicted=force_evicted,
                    duration_ms=evict_ms,
                )

            # Monitor: Cache write
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_write(room_id, count=1, duration_ms=duration_ms)

            return True

        except Exception as e:
            # Surface at ERROR with stack trace so silent serialization regressions
            # (e.g. the voice_duration Decimal bug) cannot hide. PostgreSQL still
            # has the data, so we don't re-raise.
            logger.exception(
                "MessageCache.add_message failed for room=%s message=%s: %s",
                getattr(message.chat_room, 'id', '?'),
                getattr(message, 'id', '?'),
                e.__class__.__name__,
            )
            return False

    @classmethod
    def _evict_messages(cls, redis_client, room_id: str, message_ids: list):
        """Remove evicted messages from hash, timeline, all filter indexes,
        and the protected SET."""
        if not message_ids:
            return
        pipe = redis_client.pipeline()
        data_key = cls.MSG_DATA_KEY.format(room_id=room_id)
        timeline_key = cls.TIMELINE_KEY.format(room_id=room_id)
        protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id)

        for mid_bytes in message_ids:
            mid = mid_bytes.decode() if isinstance(mid_bytes, bytes) else mid_bytes
            pipe.hdel(data_key, mid)
            pipe.zrem(timeline_key, mid)
            pipe.srem(protected_key, mid)

        # Clean all index keys for this room. Read the registry once instead of
        # walking the entire keyspace with scan_iter — deterministic and skips
        # unrelated keys.
        registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id)
        registered = redis_client.smembers(registry_key)
        for idx_key_raw in registered:
            idx_key = idx_key_raw.decode() if isinstance(idx_key_raw, bytes) else idx_key_raw
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

            # O(1) overwrite in hash + re-sync protected SET. update_message is
            # the path highlight-toggle goes through, so we re-evaluate
            # _is_protected here and SADD/SREM accordingly. Untouched if the
            # message's protection status hasn't changed.
            protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id)
            ttl_seconds = cls._get_ttl_hours() * 3600
            pipe = redis_client.pipeline()
            pipe.hset(data_key, message_id, message_json)
            if cls._is_protected(message_data):
                pipe.sadd(protected_key, message_id)
                pipe.expire(protected_key, ttl_seconds)
            else:
                pipe.srem(protected_key, message_id)
            pipe.execute()

            return True

        except Exception as e:
            logger.exception(
                "MessageCache.update_message failed for room=%s message=%s: %s",
                getattr(message.chat_room, 'id', '?'),
                getattr(message, 'id', '?'),
                e.__class__.__name__,
            )
            return False

    @classmethod
    def get_message_by_id(cls, room_id: Union[str, UUID], message_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single message by ID. Cache-first; returns None on miss.

        Used by the message-detail endpoint that powers the reply-preview popup.
        Caller is responsible for falling back to PostgreSQL on miss.
        """
        try:
            redis_client = cls._get_redis_client()
            data_key = cls.MSG_DATA_KEY.format(room_id=str(room_id))
            raw = redis_client.hget(data_key, str(message_id))
            if raw is None:
                return None
            msg = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            cls._enrich_with_cdn_urls(msg)
            return msg
        except Exception:
            logger.exception(
                "MessageCache.get_message_by_id failed for room=%s message=%s",
                room_id, message_id,
            )
            return None

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
                msg = json.loads(raw)
                # Enrich with direct CDN URLs for media fields. Read-time
                # signing keeps URLs fresh even when cache is older than the
                # signature TTL.
                cls._enrich_with_cdn_urls(msg)
                messages.append(msg)
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

    # Sentinel returned alongside an empty list when last_seen_id can't be
    # found in the timeline cache (Redis evicted it, or it's unknown). The
    # WS hello-handshake handler uses this to signal the client that the
    # delta can't be computed and a full reload is needed.
    BACKFILL_OVERFLOW = object()

    @classmethod
    def get_messages_after_id(
        cls,
        room_id: Union[str, UUID],
        last_seen_id: str,
        limit: int = 100,
    ):
        """
        Get messages strictly newer than `last_seen_id`. Used by the WebSocket
        reconnect handshake to send only the delta the client missed while
        disconnected, rather than a full window refetch.

        Returns one of:
          - (messages, False)              normal: list of dicts (oldest first,
                                            chronological), capped at `limit`
          - (messages, True)               OVERFLOW: more than `limit` newer
                                            messages exist; client should
                                            full-reload instead of merging
                                            (we still return the first `limit`
                                            so the client can use them, but
                                            the flag signals the overflow)
          - (BACKFILL_OVERFLOW, True)      last_seen_id not in timeline (e.g.,
                                            evicted from Redis); client must
                                            full-reload — there's no anchor
                                            to compute the delta from
        """
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            timeline_key = cls.TIMELINE_KEY.format(room_id=room_id_str)

            # Find the timestamp of last_seen_id. ZSCORE returns None if the
            # message isn't in the timeline cache.
            last_seen_score = redis_client.zscore(timeline_key, last_seen_id)
            if last_seen_score is None:
                # Anchor not in cache → can't compute delta. Signal overflow.
                return cls.BACKFILL_OVERFLOW, True

            # Fetch one extra to detect overflow (more new messages than limit).
            ids = redis_client.zrangebyscore(
                timeline_key,
                min=f'({last_seen_score}',  # exclusive — strictly newer
                max='+inf',
                start=0,
                num=limit + 1,
            )

            overflow = len(ids) > limit
            if overflow:
                ids = ids[:limit]

            messages = cls._fetch_by_ids(redis_client, room_id_str, ids)

            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(
                room_id_str,
                hit=len(messages) > 0,
                count=len(messages),
                duration_ms=duration_ms,
                source='redis',
            )

            return messages, overflow

        except Exception as e:
            logger.exception("MessageCache.get_messages_after_id failed: %s", e)
            return cls.BACKFILL_OVERFLOW, True

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
        """Add a message to the highlight index (appears in all users' Focus view).

        Uses highlighted_at as the score so the Highlight Room is ordered by
        when the host starred the message, not when the message was sent.
        Re-highlighting a previously-evicted message updates the score in place.
        """
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room_id)
            message_id = str(message.id)
            # Score by highlighted_at; fall back to created_at for legacy rows.
            score = (message.highlighted_at or message.created_at).timestamp()
            ttl_seconds = cls._get_ttl_hours() * 3600
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id)
            registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id)
            pipe = redis_client.pipeline()
            pipe.zadd(highlight_key, {message_id: score})
            pipe.expire(highlight_key, ttl_seconds)
            # Register so eviction sees this index without scan_iter.
            pipe.sadd(registry_key, highlight_key)
            pipe.expire(registry_key, ttl_seconds)
            pipe.execute()
            return True
        except Exception:
            logger.exception(
                "MessageCache.add_to_highlight_index failed for message=%s",
                getattr(message, 'id', '?'),
            )
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
    def _hydrate_highlight_index(cls, redis_client, room_id_str: str) -> None:
        """Seed the highlight index (and msg_data) from PostgreSQL, once per room.

        Mirrors `_hydrate_media_index` but for `is_highlight=True` messages.
        Messages are queued onto a single bulk pipeline (one Redis round-trip
        regardless of count). Capped at REDIS_CACHE_MAX_COUNT — same shared
        cache budget as the main timeline. Guarded by a hydration flag.

        Without this, an empty highlight index recovers via the general
        cache-miss + backfill path which is limited to one query of `limit`
        per request — fine for chats with ≤50 highlights, but slow for chats
        with many curated highlights when scrolling back from a cold cache.
        """
        hydrated_key = cls.MEDIA_HYDRATED_KEY.format(
            room_id=room_id_str, media_type='highlight'
        )
        if redis_client.exists(hydrated_key):
            return

        start_time = time.time()
        from chats.models import Message
        ttl_seconds = cls._get_ttl_hours() * 3600
        cap = cls._get_max_messages()

        qs = (Message.objects
              .filter(chat_room_id=room_id_str, is_deleted=False, is_highlight=True)
              .select_related('user', 'reply_to', 'chat_room')
              .order_by('-highlighted_at', '-created_at')[:cap])

        # Bulk-pipelined hydration: queue every message's writes onto a single
        # pipeline and execute once.
        pipe = redis_client.pipeline()
        all_touched: set = set()
        protected_ids: List[str] = []
        hydrated_count = 0

        for msg in qs:
            try:
                touched, message_data, message_id = cls._queue_message_to_pipeline(
                    pipe, msg, ttl_seconds
                )
                all_touched.update(touched)
                if cls._is_protected(message_data):
                    protected_ids.append(message_id)
                hydrated_count += 1
            except Exception:
                logger.exception(
                    "Highlight hydration queue failed for room=%s message=%s",
                    room_id_str, msg.id,
                )

        registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id_str)
        if all_touched:
            pipe.sadd(registry_key, *all_touched)
            pipe.expire(registry_key, ttl_seconds)

        protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id_str)
        if protected_ids:
            pipe.sadd(protected_key, *protected_ids)
            pipe.expire(protected_key, ttl_seconds)

        pipe.set(hydrated_key, '1', ex=ttl_seconds)

        try:
            pipe.execute()
        except Exception:
            logger.exception(
                "Highlight hydration pipeline.execute failed for room=%s (queued=%d)",
                room_id_str, hydrated_count,
            )
            hydrated_count = 0

        duration_ms = (time.time() - start_time) * 1000
        monitor.log_hydration(
            chat_code=room_id_str,
            media_type='highlight',
            count=hydrated_count,
            duration_ms=duration_ms,
        )

    @classmethod
    def get_highlight_messages(cls, room_id: Union[str, UUID],
                                limit: int = 50, before_timestamp: float = None) -> List[Dict[str, Any]]:
        """Get highlight messages for a room."""
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            highlight_key = cls.HIGHLIGHT_INDEX_KEY.format(room_id=room_id_str)

            cls._hydrate_highlight_index(redis_client, room_id_str)

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
    def _hydrate_media_index(cls, redis_client, room_id_str: str, media_field: str,
                              media_type: str) -> None:
        """Seed the media index (and msg_data) from PostgreSQL, once per room/type.

        Media indexes are populated by add_message() going forward, but messages
        that existed before the feature shipped — or that have aged out of the
        recent-message window — are missing from both the index and the bounded
        MSG_DATA_KEY hash. This loads every matching message from PostgreSQL and
        runs it through add_message(), which atomically writes msg_data, the
        timeline, and all relevant indexes. Guarded by a hydration flag.
        Capped at REDIS_CACHE_MAX_COUNT to bound memory in large chats.
        """
        hydrated_key = cls.MEDIA_HYDRATED_KEY.format(room_id=room_id_str, media_type=media_type)
        if redis_client.exists(hydrated_key):
            return

        start_time = time.time()
        from chats.models import Message
        ttl_seconds = cls._get_ttl_hours() * 3600
        cap = cls._get_max_messages()

        field_filter = {f"{media_field}__isnull": False}
        qs = (Message.objects
              .filter(chat_room_id=room_id_str, is_deleted=False, **field_filter)
              .exclude(**{media_field: ''})
              .exclude(message_type='gift')
              .select_related('user', 'reply_to', 'chat_room')
              .order_by('-created_at')[:cap])

        # Bulk-pipelined hydration: queue every message's writes onto a single
        # pipeline and execute once. For 5000 messages this is one round-trip
        # instead of 5000 — turns a multi-second cliff into a sub-200ms warmup.
        pipe = redis_client.pipeline()
        all_touched: set = set()
        protected_ids: List[str] = []
        hydrated_count = 0

        for msg in qs:
            try:
                touched, message_data, message_id = cls._queue_message_to_pipeline(
                    pipe, msg, ttl_seconds
                )
                all_touched.update(touched)
                if cls._is_protected(message_data):
                    protected_ids.append(message_id)
                hydrated_count += 1
            except Exception:
                logger.exception(
                    "Hydration queue failed for room=%s message=%s type=%s",
                    room_id_str, msg.id, media_type,
                )

        # Bulk-register every index touched + every protected ID, in the same
        # pipeline as the message writes.
        registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id_str)
        if all_touched:
            pipe.sadd(registry_key, *all_touched)
            pipe.expire(registry_key, ttl_seconds)

        protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id_str)
        if protected_ids:
            pipe.sadd(protected_key, *protected_ids)
            pipe.expire(protected_key, ttl_seconds)

        # Mark the hydration flag in the same execute() so the whole operation
        # is one atomic round-trip.
        pipe.set(hydrated_key, '1', ex=ttl_seconds)

        try:
            pipe.execute()
        except Exception:
            logger.exception(
                "Hydration pipeline.execute failed for room=%s type=%s (queued=%d)",
                room_id_str, media_type, hydrated_count,
            )
            hydrated_count = 0

        duration_ms = (time.time() - start_time) * 1000
        monitor.log_hydration(
            chat_code=room_id_str,
            media_type=media_type,
            count=hydrated_count,
            duration_ms=duration_ms,
        )

    @classmethod
    def _get_media_messages(cls, room_id: Union[str, UUID], index_key_template: str,
                             media_field: str, media_type: str,
                             limit: int = 50, before_timestamp: Optional[float] = None) -> List[Dict[str, Any]]:
        """Shared helper for photo/video/audio message retrieval."""
        start_time = time.time()
        room_id_str = str(room_id)
        try:
            redis_client = cls._get_redis_client()
            index_key = index_key_template.format(room_id=room_id_str)

            cls._hydrate_media_index(redis_client, room_id_str, media_field, media_type)

            if before_timestamp:
                max_score = f'({before_timestamp}'
            else:
                max_score = '+inf'

            results = redis_client.zrangebyscore(index_key, '-inf', max_score, withscores=True)

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
            print(f"Redis cache error (_get_media_messages): {e}")
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_read(room_id_str, hit=False, count=0,
                                   duration_ms=duration_ms, source='redis')
            return []

    @classmethod
    def get_photo_messages(cls, room_id, limit=50, before_timestamp=None):
        """Get photo messages for a room (messages with photo_url, excluding gifts)."""
        return cls._get_media_messages(room_id, cls.PHOTO_INDEX_KEY, 'photo_url', 'photo', limit, before_timestamp)

    @classmethod
    def get_video_messages(cls, room_id, limit=50, before_timestamp=None):
        """Get video messages for a room (messages with video_url, excluding gifts)."""
        return cls._get_media_messages(room_id, cls.VIDEO_INDEX_KEY, 'video_url', 'video', limit, before_timestamp)

    @classmethod
    def get_audio_messages(cls, room_id, limit=50, before_timestamp=None):
        """Get audio (voice) messages for a room (messages with voice_url, excluding gifts)."""
        return cls._get_media_messages(room_id, cls.AUDIO_INDEX_KEY, 'voice_url', 'audio', limit, before_timestamp)

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

                    cls._enrich_with_cdn_urls(msg_data)
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
            protected_key = cls.PROTECTED_SET_KEY.format(room_id=room_id_str)

            # Check if message exists in hash
            removed = redis_client.hdel(data_key, message_id) > 0

            # Remove from timeline + protected set
            pipe = redis_client.pipeline()
            pipe.zrem(timeline_key, message_id)
            pipe.srem(protected_key, message_id)

            # Remove from all filter indexes via the registry (no scan_iter).
            registry_key = cls.IDX_KEYS_REGISTRY.format(room_id=room_id_str)
            registered = redis_client.smembers(registry_key)
            for idx_key_raw in registered:
                idx_key = idx_key_raw.decode() if isinstance(idx_key_raw, bytes) else idx_key_raw
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

    Per room type, maintains two SETs of participation_ids:
      - seen:    users who have seen the latest content (cleared on new content)
      - visited: users who have ever opened this room (never cleared by new content)

    Notification shown iff: user is in `visited` AND NOT in `seen`.
    This suppresses markers for rooms a user has never opened — new joiners
    only get notifications after they've actually visited a room and new
    activity arrives.

    Uses ChatParticipation.id (UUID) as the stable identity — unlike session_key
    (which can change across page refreshes for anonymous users) or user_id
    (which is None for anonymous identities), participation_id is stable and
    unique per identity per chat room.

    Keys:
      room:{room_id}:seen:{room_type}
      room:{room_id}:visited:{room_type}
    TTL: 7 days (content older than that doesn't need notification)
    """
    # FAB-linked notification types
    FAB_ROOMS = ('highlight', 'focus', 'gifts', 'photo', 'video', 'audio')
    # General-purpose notification types (not tied to FABs — for future use: push notifs, chat list badges, etc.)
    GENERAL_TYPES = ('messages', 'verified')
    # All valid types
    VALID_ROOMS = FAB_ROOMS + GENERAL_TYPES
    TTL_SECONDS = 7 * 24 * 3600  # 7 days

    @classmethod
    def _key(cls, room_id, room_type):
        return f'room:{room_id}:seen:{room_type}'

    @classmethod
    def _visited_key(cls, room_id, room_type):
        return f'room:{room_id}:visited:{room_type}'

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
        """User opened this room — they've seen the content and have visited it."""
        try:
            redis_client = cls._get_redis_client()
            seen_key = cls._key(room_id, room_type)
            visited_key = cls._visited_key(room_id, room_type)
            pipe = redis_client.pipeline()
            pipe.sadd(seen_key, str(user_id))
            pipe.expire(seen_key, cls.TTL_SECONDS)
            pipe.sadd(visited_key, str(user_id))
            pipe.expire(visited_key, cls.TTL_SECONDS)
            pipe.execute()
        except Exception as e:
            print(f"Redis cache error (mark_seen): {e}")

    @classmethod
    def has_unseen(cls, room_id, user_id, room_types=None):
        """Check rooms for unseen content — returns dict of booleans.

        Returns True for a room iff the user has visited it AND is not in the
        seen set. New joiners (no visit history) never get notifications until
        they actually open a room.

        room_types defaults to FAB_ROOMS. Pass VALID_ROOMS to include general types.
        """
        if room_types is None:
            room_types = cls.FAB_ROOMS
        try:
            redis_client = cls._get_redis_client()
            pipe = redis_client.pipeline()
            for room_type in room_types:
                pipe.sismember(cls._visited_key(room_id, room_type), str(user_id))
                pipe.sismember(cls._key(room_id, room_type), str(user_id))
            results = pipe.execute()

            notifications = {}
            for i, room_type in enumerate(room_types):
                is_visited = results[i * 2]
                is_seen = results[i * 2 + 1]
                notifications[room_type] = bool(is_visited and not is_seen)
            return notifications
        except Exception as e:
            print(f"Redis cache error (has_unseen): {e}")
            return {rt: False for rt in room_types}
