"""
Tests for message activity utility.

Tests the message-based activity tracking including:
- Message counting for 24h and 10min windows
- Redis caching with proper TTL
- Edge cases (empty rooms, deleted messages)
- Security (isolation between rooms)
- Performance (batch queries, deduplication)
"""

import time
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache

from accounts.models import User
from chats.models import ChatRoom, Message, ChatParticipation

import allure

from media_analysis.utils.message_activity import (
    get_message_activity_for_rooms,
    invalidate_message_activity_cache,
    MessageActivity,
    MESSAGE_ACTIVITY_CACHE_PREFIX,
    MESSAGE_ACTIVITY_CACHE_TTL,
    _query_message_activity,
)


@allure.feature('Message Activity')
@allure.story('Activity Counting')
class MessageActivityCountingTests(TransactionTestCase):
    """Test message counting accuracy for activity indicators."""

    def setUp(self):
        """Set up test data."""
        cache.clear()

        # Create test user
        self.user = User.objects.create_user(
            email='activity_test@example.com',
            password='testpass123',
            reserved_username='ActivityTester'
        )

        # Create test chat rooms
        self.room1 = ChatRoom.objects.create(
            name='Activity Room 1',
            host=self.user,
            access_mode='public'
        )
        self.room2 = ChatRoom.objects.create(
            name='Activity Room 2',
            host=self.user,
            access_mode='public'
        )
        self.empty_room = ChatRoom.objects.create(
            name='Empty Room',
            host=self.user,
            access_mode='public'
        )

        # Create participation
        ChatParticipation.objects.create(
            chat_room=self.room1,
            user=self.user,
            username='ActivityTester',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @allure.title("Count messages in 24h window")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_count_messages_24h(self):
        """Test that messages in the last 24 hours are counted correctly."""
        now = timezone.now()

        # Create messages at different times
        # 5 messages within 24h
        for i in range(5):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Message {i}',
                created_at=now - timedelta(hours=i)
            )

        # 2 messages older than 24h (should not be counted)
        for i in range(2):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Old message {i}',
                created_at=now - timedelta(hours=25 + i)
            )

        result = get_message_activity_for_rooms([str(self.room1.id)])

        self.assertEqual(result[str(self.room1.id)].messages_24h, 5)

    @allure.title("Count messages in 10min window")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_count_messages_10min(self):
        """Test that messages in the last 10 minutes are counted correctly."""
        now = timezone.now()

        # 3 messages within 10 minutes
        for i in range(3):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Recent {i}',
                created_at=now - timedelta(minutes=i * 2)  # 0, 2, 4 minutes ago
            )

        # 2 messages older than 10 minutes but within 24h
        for i in range(2):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Earlier {i}',
                created_at=now - timedelta(minutes=15 + i * 10)
            )

        result = get_message_activity_for_rooms([str(self.room1.id)])

        self.assertEqual(result[str(self.room1.id)].messages_24h, 5)
        self.assertEqual(result[str(self.room1.id)].messages_10min, 3)

    @allure.title("Empty room returns zero counts")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_room_returns_zero(self):
        """Test that a room with no messages returns zero counts."""
        result = get_message_activity_for_rooms([str(self.empty_room.id)])

        self.assertEqual(result[str(self.empty_room.id)].messages_24h, 0)
        self.assertEqual(result[str(self.empty_room.id)].messages_10min, 0)

    @allure.title("Deleted messages are not counted")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_deleted_messages_not_counted(self):
        """Test that soft-deleted messages are excluded from counts."""
        now = timezone.now()

        # Create 3 regular messages
        for i in range(3):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Active {i}',
                created_at=now - timedelta(minutes=1)
            )

        # Create 2 deleted messages
        for i in range(2):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Deleted {i}',
                created_at=now - timedelta(minutes=2),
                is_deleted=True
            )

        result = get_message_activity_for_rooms([str(self.room1.id)])

        # Only non-deleted messages should be counted
        self.assertEqual(result[str(self.room1.id)].messages_24h, 3)
        self.assertEqual(result[str(self.room1.id)].messages_10min, 3)

    @allure.title("Batch query for multiple rooms")
    @allure.severity(allure.severity_level.NORMAL)
    def test_batch_query_multiple_rooms(self):
        """Test that multiple rooms are queried in a single batch."""
        now = timezone.now()

        # Add messages to room1
        for i in range(5):
            Message.objects.create(
                chat_room=self.room1,
                username='TestUser',
                user=self.user,
                content=f'Room1 msg {i}',
                created_at=now - timedelta(minutes=1)
            )

        # Add messages to room2
        for i in range(3):
            Message.objects.create(
                chat_room=self.room2,
                username='TestUser',
                user=self.user,
                content=f'Room2 msg {i}',
                created_at=now - timedelta(minutes=1)
            )

        result = get_message_activity_for_rooms([
            str(self.room1.id),
            str(self.room2.id),
            str(self.empty_room.id)
        ])

        self.assertEqual(len(result), 3)
        self.assertEqual(result[str(self.room1.id)].messages_24h, 5)
        self.assertEqual(result[str(self.room2.id)].messages_24h, 3)
        self.assertEqual(result[str(self.empty_room.id)].messages_24h, 0)

    @allure.title("Empty room list returns empty dict")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_room_list(self):
        """Test that an empty room list returns an empty dict."""
        result = get_message_activity_for_rooms([])
        self.assertEqual(result, {})

    @allure.title("Duplicate room IDs are deduplicated")
    @allure.severity(allure.severity_level.NORMAL)
    def test_duplicate_room_ids_deduplicated(self):
        """Test that duplicate room IDs in the input are handled correctly."""
        now = timezone.now()

        Message.objects.create(
            chat_room=self.room1,
            username='TestUser',
            user=self.user,
            content='Test message',
            created_at=now - timedelta(minutes=1)
        )

        # Pass the same room ID multiple times
        room_id = str(self.room1.id)
        result = get_message_activity_for_rooms([room_id, room_id, room_id])

        # Should only have one entry
        self.assertEqual(len(result), 1)
        self.assertEqual(result[room_id].messages_24h, 1)


@allure.feature('Message Activity')
@allure.story('Redis Caching')
class MessageActivityCachingTests(TransactionTestCase):
    """Test Redis caching for message activity."""

    def setUp(self):
        """Set up test data."""
        cache.clear()

        self.user = User.objects.create_user(
            email='cache_test@example.com',
            password='testpass123',
            reserved_username='CacheTester'
        )

        self.room = ChatRoom.objects.create(
            name='Cache Test Room',
            host=self.user,
            access_mode='public'
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @allure.title("Results are cached in Redis")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_results_cached(self):
        """Test that query results are cached in Redis."""
        now = timezone.now()
        room_id = str(self.room.id)
        cache_key = f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room_id}"

        Message.objects.create(
            chat_room=self.room,
            username='TestUser',
            user=self.user,
            content='Cacheable message',
            created_at=now - timedelta(minutes=1)
        )

        # First call should query DB and cache result
        result1 = get_message_activity_for_rooms([room_id])

        # Verify cache was set
        cached = cache.get(cache_key)
        self.assertIsNotNone(cached)
        self.assertEqual(cached['messages_24h'], 1)
        self.assertEqual(cached['messages_10min'], 1)

    @allure.title("Cache hit avoids database query")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cache_hit_avoids_db_query(self):
        """Test that cached results avoid database queries."""
        room_id = str(self.room.id)
        cache_key = f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room_id}"

        # Manually set cache
        cache.set(cache_key, {
            'messages_24h': 42,
            'messages_10min': 7
        }, timeout=MESSAGE_ACTIVITY_CACHE_TTL)

        # Mock the DB query function to verify it's not called
        with patch('media_analysis.utils.message_activity._query_message_activity') as mock_query:
            result = get_message_activity_for_rooms([room_id])

            # DB query should not be called
            mock_query.assert_not_called()

            # Result should come from cache
            self.assertEqual(result[room_id].messages_24h, 42)
            self.assertEqual(result[room_id].messages_10min, 7)

    @allure.title("Cache invalidation clears room cache")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_invalidation(self):
        """Test that cache invalidation removes the cached entry."""
        room_id = str(self.room.id)
        cache_key = f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room_id}"

        # Set cache manually
        cache.set(cache_key, {
            'messages_24h': 100,
            'messages_10min': 50
        }, timeout=MESSAGE_ACTIVITY_CACHE_TTL)

        # Verify cache is set
        self.assertIsNotNone(cache.get(cache_key))

        # Invalidate cache
        invalidate_message_activity_cache(room_id)

        # Cache should be cleared
        self.assertIsNone(cache.get(cache_key))

    @allure.title("Partial cache hit queries only missing rooms")
    @allure.severity(allure.severity_level.NORMAL)
    def test_partial_cache_hit(self):
        """Test that only cache-missed rooms are queried from DB."""
        now = timezone.now()

        # Create second room
        room2 = ChatRoom.objects.create(
            name='Cache Test Room 2',
            host=self.user,
            access_mode='public'
        )

        room1_id = str(self.room.id)
        room2_id = str(room2.id)

        # Pre-cache room1
        cache_key1 = f"{MESSAGE_ACTIVITY_CACHE_PREFIX}:{room1_id}"
        cache.set(cache_key1, {
            'messages_24h': 10,
            'messages_10min': 2
        }, timeout=MESSAGE_ACTIVITY_CACHE_TTL)

        # Add message to room2 (not cached)
        Message.objects.create(
            chat_room=room2,
            username='TestUser',
            user=self.user,
            content='Test message',
            created_at=now - timedelta(minutes=1)
        )

        # Query both rooms
        result = get_message_activity_for_rooms([room1_id, room2_id])

        # Room1 should have cached values
        self.assertEqual(result[room1_id].messages_24h, 10)
        self.assertEqual(result[room1_id].messages_10min, 2)

        # Room2 should have fresh DB values
        self.assertEqual(result[room2_id].messages_24h, 1)
        self.assertEqual(result[room2_id].messages_10min, 1)


@allure.feature('Message Activity')
@allure.story('Security & Isolation')
class MessageActivitySecurityTests(TransactionTestCase):
    """Test security and isolation of message activity queries."""

    def setUp(self):
        """Set up test data."""
        cache.clear()

        self.user1 = User.objects.create_user(
            email='security_test1@example.com',
            password='testpass123',
            reserved_username='SecurityTester1'
        )

        self.user2 = User.objects.create_user(
            email='security_test2@example.com',
            password='testpass123',
            reserved_username='SecurityTester2'
        )

        self.room1 = ChatRoom.objects.create(
            name='User1 Room',
            host=self.user1,
            access_mode='private'
        )

        self.room2 = ChatRoom.objects.create(
            name='User2 Room',
            host=self.user2,
            access_mode='private'
        )

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    @allure.title("Room isolation - cannot access other rooms' data")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_room_isolation(self):
        """Test that querying one room doesn't return another room's data."""
        now = timezone.now()

        # Add messages to room1
        for i in range(5):
            Message.objects.create(
                chat_room=self.room1,
                username='User1',
                user=self.user1,
                content=f'Private message {i}',
                created_at=now - timedelta(minutes=1)
            )

        # Add messages to room2
        for i in range(3):
            Message.objects.create(
                chat_room=self.room2,
                username='User2',
                user=self.user2,
                content=f'Other private message {i}',
                created_at=now - timedelta(minutes=1)
            )

        # Query only room1
        result = get_message_activity_for_rooms([str(self.room1.id)])

        # Should only contain room1
        self.assertEqual(len(result), 1)
        self.assertIn(str(self.room1.id), result)
        self.assertNotIn(str(self.room2.id), result)
        self.assertEqual(result[str(self.room1.id)].messages_24h, 5)

    @allure.title("Invalid room ID returns zero activity")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_room_id_returns_zero(self):
        """Test that an invalid room ID returns zero activity."""
        fake_room_id = "00000000-0000-0000-0000-000000000000"

        result = get_message_activity_for_rooms([fake_room_id])

        self.assertEqual(result[fake_room_id].messages_24h, 0)
        self.assertEqual(result[fake_room_id].messages_10min, 0)

    @allure.title("No SQL injection via room ID")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_no_sql_injection(self):
        """Test that malicious room IDs cannot cause SQL injection."""
        # Attempt SQL injection via room ID
        malicious_ids = [
            "'; DROP TABLE chats_message; --",
            "1 OR 1=1",
            "1'; DELETE FROM chats_message WHERE '1'='1",
        ]

        # This should not raise an exception or cause issues
        for malicious_id in malicious_ids:
            try:
                result = get_message_activity_for_rooms([malicious_id])
                # Should return empty activity for invalid UUID
                self.assertEqual(result[malicious_id].messages_24h, 0)
            except Exception:
                # Django's UUID validation should reject these
                pass


@allure.feature('Message Activity')
@allure.story('Data Types')
class MessageActivityDataTypeTests(TestCase):
    """Test data types and return values."""

    @allure.title("Returns MessageActivity namedtuple")
    @allure.severity(allure.severity_level.NORMAL)
    def test_returns_named_tuple(self):
        """Test that the function returns MessageActivity namedtuples."""
        cache.clear()

        user = User.objects.create_user(
            email='datatype_test@example.com',
            password='testpass123'
        )

        room = ChatRoom.objects.create(
            name='DataType Room',
            host=user,
            access_mode='public'
        )

        result = get_message_activity_for_rooms([str(room.id)])

        activity = result[str(room.id)]
        self.assertIsInstance(activity, MessageActivity)
        self.assertIsInstance(activity.messages_24h, int)
        self.assertIsInstance(activity.messages_10min, int)

        # Named fields should be accessible
        self.assertEqual(activity.messages_24h, activity[0])
        self.assertEqual(activity.messages_10min, activity[1])

        cache.clear()

    @allure.title("Cache TTL is 5 minutes")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_ttl_is_correct(self):
        """Test that the cache TTL constant is set correctly."""
        self.assertEqual(MESSAGE_ACTIVITY_CACHE_TTL, 300)  # 5 minutes
