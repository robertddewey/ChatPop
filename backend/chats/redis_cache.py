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


class MessageCache:
    """Redis cache manager for chat messages"""

    # Cache key patterns
    MESSAGES_KEY = "chat:{chat_code}:messages"
    PINNED_KEY = "chat:{chat_code}:pinned"
    BACKROOM_KEY = "chat:{chat_code}:backroom:messages"

    # Configuration from settings
    MAX_MESSAGES = getattr(settings, 'MESSAGE_CACHE_MAX_COUNT', 500)
    TTL_HOURS = getattr(settings, 'MESSAGE_CACHE_TTL_HOURS', 24)

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
            "reply_to_id": str(message.reply_to.id) if message.reply_to else None,
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
    def add_message(cls, message: Message, is_backroom: bool = False) -> bool:
        """
        Add a message to Redis cache.

        Args:
            message: Message instance (already saved to PostgreSQL)
            is_backroom: Whether this is a back room message

        Returns:
            True if successfully cached, False otherwise
        """
        try:
            redis_client = cls._get_redis_client()
            chat_code = message.chat_room.code

            # Compute badge status
            username_is_reserved = cls._compute_username_is_reserved(message)

            # Serialize message
            message_data = cls._serialize_message(message, username_is_reserved)
            message_json = json.dumps(message_data)

            # Choose key based on room type
            key = (cls.BACKROOM_KEY if is_backroom else cls.MESSAGES_KEY).format(chat_code=chat_code)

            # Use microsecond timestamp for ordering
            score = message.created_at.timestamp()

            # Add to sorted set
            redis_client.zadd(key, {message_json: score})

            # Trim to max message count (keep most recent)
            total_messages = redis_client.zcard(key)
            if total_messages > cls.MAX_MESSAGES:
                # Remove oldest messages
                redis_client.zremrangebyrank(key, 0, total_messages - cls.MAX_MESSAGES - 1)

            # Set TTL on the key (refreshed on each add)
            ttl_seconds = cls.TTL_HOURS * 3600
            redis_client.expire(key, ttl_seconds)

            return True

        except Exception as e:
            # Log error but don't crash (PostgreSQL has the data)
            print(f"Redis cache error (add_message): {e}")
            return False

    @classmethod
    def get_messages(cls, chat_code: str, limit: int = 50, is_backroom: bool = False) -> List[Dict[str, Any]]:
        """
        Get recent messages from Redis cache.

        Args:
            chat_code: Chat room code
            limit: Maximum number of messages to return
            is_backroom: Whether to fetch back room messages

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        try:
            redis_client = cls._get_redis_client()
            key = (cls.BACKROOM_KEY if is_backroom else cls.MESSAGES_KEY).format(chat_code=chat_code)

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

            return messages

        except Exception as e:
            print(f"Redis cache error (get_messages): {e}")
            return []

    @classmethod
    def get_messages_before(cls, chat_code: str, before_timestamp: float, limit: int = 50, is_backroom: bool = False) -> List[Dict[str, Any]]:
        """
        Get messages before a specific timestamp (for pagination/scroll-up).

        Args:
            chat_code: Chat room code
            before_timestamp: Unix timestamp to query before
            limit: Maximum messages to return
            is_backroom: Whether to fetch back room messages

        Returns:
            List of message dicts (oldest first, chronological order for chat display)
        """
        try:
            redis_client = cls._get_redis_client()
            key = (cls.BACKROOM_KEY if is_backroom else cls.MESSAGES_KEY).format(chat_code=chat_code)

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

            return messages

        except Exception as e:
            print(f"Redis cache error (get_messages_before): {e}")
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
    def clear_chat_cache(cls, chat_code: str):
        """
        Clear all cached messages for a chat room.

        Useful for testing or manual cache invalidation.
        """
        try:
            redis_client = cls._get_redis_client()

            keys_to_delete = [
                cls.MESSAGES_KEY.format(chat_code=chat_code),
                cls.BACKROOM_KEY.format(chat_code=chat_code),
                cls.PINNED_KEY.format(chat_code=chat_code),
            ]

            for key in keys_to_delete:
                redis_client.delete(key)

        except Exception as e:
            print(f"Redis cache error (clear_chat_cache): {e}")
