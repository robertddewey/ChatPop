"""
Redis message cache utilities for ChatPop.

Implements a hybrid message storage strategy:
- PostgreSQL: Permanent message log (source of truth)
- Redis: Fast cache for recent messages (last 500 or 24 hours)

Key patterns:
- Sorted sets for message ordering (score = timestamp)
- Separate cache for pinned messages (score = pinned_until)
- Dual-write on message send (PostgreSQL + Redis)
- Read from Redis first, fallback to PostgreSQL
"""

import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from django.core.cache import cache
from django.conf import settings
from chats.models import Message, ChatParticipation
from .monitoring import monitor


class MessageCache:
    """Redis cache manager for chat messages"""

    # Cache key patterns
    MESSAGES_KEY = "chat:{chat_code}:messages"
    PINNED_KEY = "chat:{chat_code}:pinned"

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
            chat_code = message.chat_room.code

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize message
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Use messages key
            key = cls.MESSAGES_KEY.format(chat_code=chat_code)

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
            monitor.log_cache_write(chat_code, count=1, duration_ms=duration_ms)

            return True

        except Exception as e:
            # Log error but don't crash (PostgreSQL has the data)
            print(f"Redis cache error (add_message): {e}")
            return False

    @classmethod
    def get_messages(cls, chat_code: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent messages from Redis cache.

        Args:
            chat_code: Chat room code
            limit: Maximum number of messages to return

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        import sys
        start_time = time.time()
        try:
            redis_client = cls._get_redis_client()
            key = cls.MESSAGES_KEY.format(chat_code=chat_code)

            print(f"DEBUG redis_cache.get_messages: chat_code={chat_code}, limit={limit}, key={key}", flush=True)
            sys.stdout.flush()

            # Check if key exists before reading
            key_exists = redis_client.exists(key)
            key_cardinality = redis_client.zcard(key)
            print(f"DEBUG redis_cache.get_messages: key_exists={key_exists}, ZCARD={key_cardinality}", flush=True)
            sys.stdout.flush()

            # Get most recent messages in chronological order (ascending)
            # ZRANGE returns lowest scores first (oldest messages first)
            # Get the last N messages by using negative indices
            message_strings = redis_client.zrange(key, -limit, -1)
            print(f"DEBUG redis_cache.get_messages: ZRANGE returned {len(message_strings)} raw strings")

            # Deserialize
            messages = []
            for msg_str in message_strings:
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    continue

            print(f"DEBUG redis_cache.get_messages: Deserialized {len(messages)} messages")

            # Monitor: Cache read
            duration_ms = (time.time() - start_time) * 1000
            hit = len(messages) > 0
            print(f"DEBUG redis_cache.get_messages: hit={hit}, count={len(messages)}, duration_ms={duration_ms}")
            monitor.log_cache_read(
                chat_code,
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
                chat_code,
                hit=False,
                count=0,
                duration_ms=duration_ms,
                source='redis'
            )

            return []

    @classmethod
    def get_messages_before(cls, chat_code: str, before_timestamp: float, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get messages before a specific timestamp (for pagination/scroll-up).

        Args:
            chat_code: Chat room code
            before_timestamp: Unix timestamp to query before
            limit: Maximum messages to return

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        start_time = time.time()
        try:
            redis_client = cls._get_redis_client()
            key = cls.MESSAGES_KEY.format(chat_code=chat_code)

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
                chat_code,
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
                chat_code,
                hit=False,
                count=0,
                duration_ms=duration_ms,
                source='redis'
            )

            return []

    @classmethod
    def add_pinned_message(cls, message: Message) -> bool:
        """
        Add a message to the pinned messages cache.

        Uses pinned_until as score for automatic expiry detection.
        """
        try:
            redis_client = cls._get_redis_client()
            chat_code = message.chat_room.code
            key = cls.PINNED_KEY.format(chat_code=chat_code)

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Score = pinned_until timestamp (for sorting and expiry)
            score = message.pinned_until.timestamp() if message.pinned_until else time.time()

            # Add to pinned sorted set
            redis_client.zadd(key, {message_json: score})

            # Set TTL (expire after longest pin duration + buffer)
            redis_client.expire(key, 7 * 24 * 3600)  # 7 days

            return True

        except Exception as e:
            print(f"Redis cache error (add_pinned_message): {e}")
            return False

    @classmethod
    def remove_pinned_message(cls, chat_code: str, message_id: str) -> bool:
        """
        Remove a message from the pinned cache.

        Args:
            chat_code: Chat room code
            message_id: Message UUID (as string)

        Returns:
            True if removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.PINNED_KEY.format(chat_code=chat_code)

            # Get all pinned messages
            message_strings = redis_client.zrange(key, 0, -1)

            # Find and remove the matching message
            for msg_str in message_strings:
                try:
                    msg_data = json.loads(msg_str)
                    if msg_data.get('id') == message_id:
                        redis_client.zrem(key, msg_str)
                        return True
                except json.JSONDecodeError:
                    continue

            return False

        except Exception as e:
            print(f"Redis cache error (remove_pinned_message): {e}")
            return False

    @classmethod
    def get_pinned_messages(cls, chat_code: str) -> List[Dict[str, Any]]:
        """
        Get all active pinned messages for a chat.

        Automatically filters out expired pins (pinned_until < now).
        """
        try:
            redis_client = cls._get_redis_client()
            key = cls.PINNED_KEY.format(chat_code=chat_code)

            # Remove expired pins (score < current time)
            now = time.time()
            redis_client.zremrangebyscore(key, '-inf', now)

            # Get remaining active pins (sorted by pinned_until, ascending)
            message_strings = redis_client.zrange(key, 0, -1)

            messages = []
            for msg_str in message_strings:
                try:
                    messages.append(json.loads(msg_str))
                except json.JSONDecodeError:
                    continue

            return messages

        except Exception as e:
            print(f"Redis cache error (get_pinned_messages): {e}")
            return []

    @classmethod
    def set_message_reactions(cls, chat_code: str, message_id: str, reactions: List[Dict[str, Any]]) -> bool:
        """
        Cache reaction summary for a message.

        Args:
            chat_code: Chat room code
            message_id: Message UUID (as string)
            reactions: List of reaction summary dicts with keys: emoji, count, users
                      Example: [{"emoji": "👍", "count": 5, "users": ["alice", "bob"]}]

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            key = f"chat:{chat_code}:reactions:{message_id}"

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
    def get_message_reactions(cls, chat_code: str, message_id: str) -> List[Dict[str, Any]]:
        """
        Get cached reactions for a single message.

        Args:
            chat_code: Chat room code
            message_id: Message UUID (as string)

        Returns:
            List of reaction summary dicts with keys: emoji, count
            Returns empty list if cache miss (caller should rebuild from PostgreSQL)
        """
        try:
            redis_client = cls._get_redis_client()
            key = f"chat:{chat_code}:reactions:{message_id}"

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
    def batch_get_reactions(cls, chat_code: str, message_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Batch fetch reactions for multiple messages using Redis pipeline.

        Args:
            chat_code: Chat room code
            message_ids: List of message UUIDs (as strings)

        Returns:
            Dict mapping message_id -> list of reaction dicts
            Example: {"msg1": [{"emoji": "👍", "count": 5}], "msg2": []}

        Performance: Single Redis round-trip for all messages (pipelined)
        """
        try:
            redis_client = cls._get_redis_client()

            if not message_ids:
                return {}

            # Use pipeline for batch fetch (single round-trip)
            pipeline = redis_client.pipeline()
            keys = []
            for message_id in message_ids:
                key = f"chat:{chat_code}:reactions:{message_id}"
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
    def remove_message(cls, chat_code: str, message_id: str) -> bool:
        """
        Remove a specific message from cache (for soft deletes).

        This removes the message from both the main messages cache and pinned cache.
        Also removes associated reactions cache.

        Args:
            chat_code: Chat room code
            message_id: Message UUID (as string)

        Returns:
            True if message was found and removed, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            removed = False

            # Remove from main messages cache
            messages_key = cls.MESSAGES_KEY.format(chat_code=chat_code)
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
            cls.remove_pinned_message(chat_code, message_id)

            # Remove reactions cache for this message
            reactions_key = f"chat:{chat_code}:reactions:{message_id}"
            redis_client.delete(reactions_key)

            if removed:
                print(f"✅ Removed message {message_id} from Redis cache for chat {chat_code}")

            return removed

        except Exception as e:
            print(f"Redis cache error (remove_message): {e}")
            return False

    @classmethod
    def clear_chat_cache(cls, chat_code: str):
        """
        Clear all cached messages for a chat room.

        Useful for testing or manual cache invalidation.
        """
        try:
            redis_client = cls._get_redis_client()

            keys_to_delete = [
                cls.MESSAGES_KEY.format(chat_code=chat_code),
                cls.PINNED_KEY.format(chat_code=chat_code),
            ]

            for key in keys_to_delete:
                redis_client.delete(key)

        except Exception as e:
            print(f"Redis cache error (clear_chat_cache): {e}")
