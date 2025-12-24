"""
Redis message cache utilities for ChatPop.

Implements a hybrid message storage strategy:
- PostgreSQL: Permanent message log (source of truth)
- Redis: Fast cache for recent messages (last 500 or 24 hours)

Key patterns:
- room:{room_id}:messages - Sorted set for message ordering (score = timestamp)
- room:{room_id}:pinned:{message_id} - Individual pinned message data
- room:{room_id}:pinned_order - Sorted set for pin ordering (score = pin_amount_paid)
- room:{room_id}:reactions:{message_id} - Hash for reaction counts
- Dual-write on message send (PostgreSQL + Redis)
- Read from Redis first, fallback to PostgreSQL

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

    # Cache key patterns (using room UUID for uniqueness)
    MESSAGES_KEY = "room:{room_id}:messages"
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
    def _serialize_message(cls, message: Message, username_is_reserved: bool = False) -> Dict[str, Any]:
        """
        Serialize a Message instance to JSON-compatible dict.

        Includes username_is_reserved flag for frontend badge display.
        """
        # Build reply_to_message object if there's a reply
        reply_to_message = None
        if message.reply_to:
            reply_to_message = {
                "id": str(message.reply_to.id),
                "username": message.reply_to.username,
                "content": message.reply_to.content[:100] if message.reply_to.content else "",
                "is_from_host": message.reply_to.message_type == "host",
            }

        return {
            "id": str(message.id),
            "chat_code": message.chat_room.code,
            "username": message.username,
            "username_is_reserved": username_is_reserved,
            "user_id": str(message.user.id) if message.user else None,
            "message_type": message.message_type,
            "is_from_host": message.message_type == "host",
            "content": message.content,
            "voice_url": message.voice_url,
            "voice_duration": message.voice_duration,
            "voice_waveform": message.voice_waveform,
            "reply_to_id": str(message.reply_to.id) if message.reply_to else None,
            "reply_to_message": reply_to_message,
            "is_pinned": message.is_pinned,
            "pinned_at": message.pinned_at.isoformat() if message.pinned_at else None,
            "pinned_until": message.pinned_until.isoformat() if message.pinned_until else None,
            "pin_amount_paid": str(message.pin_amount_paid) if message.pin_amount_paid else "0.00",
            "created_at": message.created_at.isoformat(),
            "is_deleted": message.is_deleted,
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
        Add a message to Redis cache.

        Args:
            message: Message instance (already saved to PostgreSQL)

        Returns:
            True if successfully cached, False otherwise
        """
        start_time = time.time()
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room.id)

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize message
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Use messages key
            key = cls.MESSAGES_KEY.format(room_id=room_id)

            # Use microsecond timestamp for ordering
            score = message.created_at.timestamp()

            # Add to sorted set
            redis_client.zadd(key, {message_json: score})

            # Trim to max message count (keep most recent)
            max_messages = cls._get_max_messages()
            total_messages = redis_client.zcard(key)
            if total_messages > max_messages:
                # Remove oldest messages
                redis_client.zremrangebyrank(key, 0, total_messages - max_messages - 1)

            # Set TTL on the key (refreshed on each add)
            ttl_seconds = cls._get_ttl_hours() * 3600
            redis_client.expire(key, ttl_seconds)

            # Monitor: Cache write
            duration_ms = (time.time() - start_time) * 1000
            monitor.log_cache_write(room_id, count=1, duration_ms=duration_ms)

            return True

        except Exception as e:
            # Log error but don't crash (PostgreSQL has the data)
            print(f"Redis cache error (add_message): {e}")
            return False

    @classmethod
    def update_message(cls, message: Message) -> bool:
        """
        Update an existing message in the Redis cache.

        Finds the message by ID, removes the old version, and adds the updated version
        with the same timestamp/score.

        Args:
            message: Message instance with updated data

        Returns:
            True if successfully updated, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id = str(message.chat_room.id)
            message_id = str(message.id)
            key = cls.MESSAGES_KEY.format(room_id=room_id)

            # Get all messages with scores
            message_strings_with_scores = redis_client.zrange(key, 0, -1, withscores=True)

            # Find the message with matching ID
            old_message_json = None
            old_score = None
            for msg_str, score in message_strings_with_scores:
                try:
                    msg_data = json.loads(msg_str)
                    if msg_data.get('id') == message_id:
                        old_message_json = msg_str
                        old_score = score
                        break
                except json.JSONDecodeError:
                    continue

            if old_message_json is None:
                # Message not in cache - just add it
                return cls.add_message(message)

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize the updated message
            message_data = cls._serialize_message(message, username_is_reserved)
            new_message_json = json.dumps(message_data)

            # Use pipeline for atomic remove + add
            pipe = redis_client.pipeline()
            pipe.zrem(key, old_message_json)
            pipe.zadd(key, {new_message_json: old_score})
            pipe.execute()

            return True

        except Exception as e:
            print(f"Redis cache error (update_message): {e}")
            return False

    @classmethod
    def get_messages(cls, room_id: Union[str, UUID], limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent messages from Redis cache.

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
            key = cls.MESSAGES_KEY.format(room_id=room_id_str)

            # Get most recent messages in chronological order (ascending)
            # ZRANGE returns lowest scores first (oldest messages first)
            # Get the last N messages by using negative indices
            message_strings = redis_client.zrange(key, -limit, -1)

            # Deserialize
            messages = []
            for msg_str in message_strings:
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    continue

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
    def get_messages_before(cls, room_id: Union[str, UUID], before_timestamp: float, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get messages before a specific timestamp (for pagination/scroll-up).

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
            key = cls.MESSAGES_KEY.format(room_id=room_id_str)

            # Get messages with score < before_timestamp (exclusive)
            # ZRANGEBYSCORE: ascending order, exclusive max boundary using '(' prefix
            # We need to get the last N messages before the timestamp, so use ZREVRANGEBYSCORE
            # to get them newest-first, then reverse to chronological order
            message_strings = redis_client.zrevrangebyscore(
                key,
                max=f'({before_timestamp}',  # Exclusive boundary
                min='-inf',
                start=0,
                num=limit
            )

            messages = []
            for msg_str in message_strings:
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    continue

            # Reverse to chronological order (oldest first)
            messages.reverse()

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

            # Score = pin_amount_paid (for ordering by highest bidder)
            score = float(message.pin_amount_paid) if message.pin_amount_paid else 0.0

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

        Automatically filters out expired pins (pinned_until < now).
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)
            order_key = cls.PINNED_ORDER_KEY.format(room_id=room_id_str)

            # Get all message IDs ordered by score descending (highest amount first)
            message_ids = redis_client.zrevrange(order_key, 0, -1)

            if not message_ids:
                return []

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
                    pinned_until = msg_data.get('pinned_until')
                    if pinned_until:
                        expiry_time = datetime.fromisoformat(pinned_until).timestamp()
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

        Returns 0 if no active pins exist.
        """
        top_pin = cls.get_top_pinned_message(room_id)
        if top_pin:
            # pin_amount_paid is stored as dollars (e.g., 0.25), convert to cents
            return int(float(top_pin.get('pin_amount_paid', 0)) * 100)
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

        This removes the message from both the main messages cache and pinned cache.
        Also removes associated reactions cache.

        Args:
            room_id: Chat room UUID (as string or UUID object)
            message_id: Message UUID (as string)

        Returns:
            True if message was found and removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)
            removed = False

            # Remove from main messages cache
            messages_key = cls.MESSAGES_KEY.format(room_id=room_id_str)
            message_strings = redis_client.zrange(messages_key, 0, -1)

            for msg_str in message_strings:
                try:
                    msg_data = json.loads(msg_str)
                    if msg_data.get('id') == message_id:
                        redis_client.zrem(messages_key, msg_str)
                        removed = True
                        break
                except json.JSONDecodeError:
                    continue

            # Remove from pinned messages cache (if it exists there)
            cls.remove_pinned_message(room_id_str, message_id)

            # Remove reactions cache for this message
            reactions_key = cls.REACTIONS_KEY.format(room_id=room_id_str, message_id=message_id)
            redis_client.delete(reactions_key)

            if removed:
                print(f"✅ Removed message {message_id} from Redis cache for room {room_id_str}")

            return removed

        except Exception as e:
            print(f"Redis cache error (remove_message): {e}")
            return False

    @classmethod
    def clear_room_cache(cls, room_id: Union[str, UUID]):
        """
        Clear all cached messages for a chat room.

        Useful for testing or manual cache invalidation.

        Note: This clears the main messages cache and pinned order,
        but individual pinned message keys may need separate cleanup.
        """
        try:
            redis_client = cls._get_redis_client()
            room_id_str = str(room_id)

            # Clear main keys
            keys_to_delete = [
                cls.MESSAGES_KEY.format(room_id=room_id_str),
                cls.PINNED_ORDER_KEY.format(room_id=room_id_str),
            ]

            for key in keys_to_delete:
                redis_client.delete(key)

            # Also clear any pinned message data keys (pattern match)
            pinned_pattern = f"room:{room_id_str}:pinned:*"
            pinned_keys = redis_client.keys(pinned_pattern)
            if pinned_keys:
                redis_client.delete(*pinned_keys)

            # Clear reaction keys (pattern match)
            reactions_pattern = f"room:{room_id_str}:reactions:*"
            reaction_keys = redis_client.keys(reactions_pattern)
            if reaction_keys:
                redis_client.delete(*reaction_keys)

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
