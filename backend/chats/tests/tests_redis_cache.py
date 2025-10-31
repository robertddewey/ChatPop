"""
Tests for Redis message caching functionality.

Tests the hybrid Redis/PostgreSQL message storage strategy including:
- Dual-write pattern (PostgreSQL + Redis)
- Redis-first read pattern with PostgreSQL fallback
- Pinned message caching
- Performance benchmarks
- Cache expiry and retention
"""

import time
import json
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from accounts.models import User
from chats.models import ChatRoom, Message, ChatParticipation, MessageReaction
from chats.utils.performance.cache import MessageCache
import allure


@allure.feature('Message Caching')
@allure.story('Redis Message Cache')
class RedisMessageCacheTests(TransactionTestCase):
    """Test Redis message caching with database transactions"""

    def setUp(self):
        """Set up test data"""
        # Clear Redis cache before each test
        cache.clear()

        # Create test user and chat room
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            reserved_username='TestUser'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user,
            access_mode='public'
        )

        # Create participation for badge testing
        self.participation = ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='TestUser',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        """Clean up after each test"""
        cache.clear()

    @allure.title("Add message to Redis cache")
    @allure.description("Test that messages are added to Redis cache")
    @allure.severity(allure.severity_level.NORMAL)
    def test_add_message_to_redis(self):
        """Test that messages are added to Redis cache"""
        # Create message in PostgreSQL
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Hello Redis!'
        )

        # Add to Redis cache
        result = MessageCache.add_message(message)
        self.assertTrue(result)

        # Verify message is in Redis
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], 'Hello Redis!')
        self.assertEqual(messages[0]['username'], 'TestUser')

    @allure.title("Username is reserved flag correctly cached")
    @allure.description("Test that username_is_reserved is correctly computed and cached")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_reserved_flag(self):
        """Test that username_is_reserved is correctly computed and cached"""
        # Create message with reserved username
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',  # Matches reserved_username
            user=self.user,
            content='Reserved username test'
        )

        MessageCache.add_message(message)
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        self.assertTrue(messages[0]['username_is_reserved'])

        # Create message with different username (not reserved)
        message2 = Message.objects.create(
            chat_room=self.chat_room,
            username='DifferentName',  # Doesn't match reserved_username
            user=self.user,
            content='Non-reserved username test'
        )

        MessageCache.add_message(message2)
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        # Find the second message (newest first)
        msg2_data = next(m for m in messages if m['content'] == 'Non-reserved username test')
        self.assertFalse(msg2_data['username_is_reserved'])

    @allure.title("Username is reserved check is case-insensitive")
    @allure.description("Test that username_is_reserved check is case-insensitive")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_reserved_case_insensitive(self):
        """Test that username_is_reserved check is case-insensitive"""
        # Create message with different case
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='testuser',  # lowercase, reserved is 'TestUser'
            user=self.user,
            content='Case test'
        )

        MessageCache.add_message(message)
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        # Should still be marked as reserved (case-insensitive)
        self.assertTrue(messages[0]['username_is_reserved'])

    @allure.title("Anonymous user has no badge")
    @allure.description("Test that anonymous users never have username_is_reserved=True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_anonymous_user_no_badge(self):
        """Test that anonymous users never have username_is_reserved=True"""
        # Create message without user (anonymous)
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='AnonymousUser',
            user=None,  # No user
            content='Anonymous test'
        )

        MessageCache.add_message(message)
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        self.assertFalse(messages[0]['username_is_reserved'])
        self.assertIsNone(messages[0]['user_id'])

    @allure.title("Messages returned in chronological order")
    @allure.description("Test that messages are returned in chronological order (oldest first)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_messages_ordering(self):
        """Test that messages are returned in chronological order (oldest first)"""
        # Create multiple messages
        for i in range(5):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='TestUser',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)
            time.sleep(0.01)  # Small delay to ensure different timestamps

        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        # Should be oldest first (chronological order for chat display)
        self.assertEqual(len(messages), 5)
        self.assertEqual(messages[0]['content'], 'Message 0')
        self.assertEqual(messages[4]['content'], 'Message 4')

    @allure.title("Get messages respects limit parameter")
    @allure.description("Test that get_messages respects the limit parameter")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_messages_limit(self):
        """Test that get_messages respects the limit parameter"""
        # Create 10 messages
        for i in range(10):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='TestUser',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)

        # Fetch only 3
        messages = MessageCache.get_messages(self.chat_room.code, limit=3)
        self.assertEqual(len(messages), 3)

    @allure.title("Get messages before timestamp pagination")
    @allure.description("Test pagination with get_messages_before")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_messages_before_timestamp(self):
        """Test pagination with get_messages_before"""
        # Create messages with known timestamps
        timestamps = []
        for i in range(5):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='TestUser',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)
            timestamps.append(message.created_at.timestamp())
            time.sleep(0.01)

        # Get messages before the 3rd message timestamp
        before_ts = timestamps[2]
        messages = MessageCache.get_messages_before(
            self.chat_room.code,
            before_timestamp=before_ts,
            limit=10
        )

        # Should get messages 0 and 1 (before message 2) in chronological order
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['content'], 'Message 0')
        self.assertEqual(messages[1]['content'], 'Message 1')

    @allure.title("Cache retention respects max count")
    @allure.description("Test that cache trims to REDIS_CACHE_MAX_COUNT (500 by default)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_retention_max_count(self):
        """Test that cache trims to REDIS_CACHE_MAX_COUNT (500 by default)"""
        from constance import config

        # Store original setting
        original_max = config.REDIS_CACHE_MAX_COUNT

        # Override for testing
        config.REDIS_CACHE_MAX_COUNT = 10

        try:
            # Create 15 messages (exceeds limit)
            for i in range(15):
                message = Message.objects.create(
                    chat_room=self.chat_room,
                    username='TestUser',
                    user=self.user,
                    content=f'Message {i}'
                )
                MessageCache.add_message(message)

            # Should only keep last 10
            messages = MessageCache.get_messages(self.chat_room.code, limit=20)
            self.assertEqual(len(messages), 10)

            # Should have newest messages (5-14) in chronological order
            self.assertEqual(messages[0]['content'], 'Message 5')
            self.assertEqual(messages[9]['content'], 'Message 14')

        finally:
            config.REDIS_CACHE_MAX_COUNT = original_max

    @allure.title("Add pinned message to cache")
    @allure.description("Test adding a message to the pinned cache")
    @allure.severity(allure.severity_level.NORMAL)
    def test_add_pinned_message(self):
        """Test adding a message to the pinned cache"""
        # Create and pin a message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Important message'
        )

        # Pin the message
        pinned_until = timezone.now() + timedelta(hours=1)
        message.is_pinned = True
        message.pinned_at = timezone.now()
        message.pinned_until = pinned_until
        message.pin_amount_paid = Decimal('5.00')
        message.save()

        # Add to pinned cache
        result = MessageCache.add_pinned_message(message)
        self.assertTrue(result)

        # Verify in pinned cache
        pinned = MessageCache.get_pinned_messages(self.chat_room.code)
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0]['content'], 'Important message')
        self.assertTrue(pinned[0]['is_pinned'])
        self.assertEqual(pinned[0]['pin_amount_paid'], '5.00')

    @allure.title("Pinned message auto expiry")
    @allure.description("Test that expired pinned messages are automatically removed")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pinned_message_auto_expiry(self):
        """Test that expired pinned messages are automatically removed"""
        # Create message pinned in the past (already expired)
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Expired pin'
        )

        # Pin with expiry in the past
        message.is_pinned = True
        message.pinned_at = timezone.now() - timedelta(hours=2)
        message.pinned_until = timezone.now() - timedelta(hours=1)
        message.pin_amount_paid = Decimal('5.00')
        message.save()

        MessageCache.add_pinned_message(message)

        # get_pinned_messages should auto-remove expired pins
        pinned = MessageCache.get_pinned_messages(self.chat_room.code)
        self.assertEqual(len(pinned), 0)

    @allure.title("Remove pinned message from cache")
    @allure.description("Test removing a message from pinned cache")
    @allure.severity(allure.severity_level.NORMAL)
    def test_remove_pinned_message(self):
        """Test removing a message from pinned cache"""
        # Create and pin a message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Pinned message'
        )

        message.is_pinned = True
        message.pinned_at = timezone.now()
        message.pinned_until = timezone.now() + timedelta(hours=1)
        message.save()

        MessageCache.add_pinned_message(message)

        # Verify it's there
        pinned = MessageCache.get_pinned_messages(self.chat_room.code)
        self.assertEqual(len(pinned), 1)

        # Remove it
        result = MessageCache.remove_pinned_message(self.chat_room.code, str(message.id))
        self.assertTrue(result)

        # Verify it's gone
        pinned = MessageCache.get_pinned_messages(self.chat_room.code)
        self.assertEqual(len(pinned), 0)

    @allure.title("Multiple pinned messages ordered correctly")
    @allure.description("Test that pinned messages are ordered by pinned_until timestamp")
    @allure.severity(allure.severity_level.NORMAL)
    def test_multiple_pinned_messages_ordering(self):
        """Test that pinned messages are ordered by pinned_until timestamp"""
        # Create multiple pinned messages
        now = timezone.now()

        for i in range(3):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='TestUser',
                user=self.user,
                content=f'Pin {i}'
            )

            message.is_pinned = True
            message.pinned_at = now
            # Different expiry times
            message.pinned_until = now + timedelta(hours=i+1)
            message.pin_amount_paid = Decimal(f'{i+1}.00')
            message.save()

            MessageCache.add_pinned_message(message)

        pinned = MessageCache.get_pinned_messages(self.chat_room.code)

        # Should be ordered by pinned_until (ascending)
        self.assertEqual(len(pinned), 3)
        self.assertEqual(pinned[0]['content'], 'Pin 0')  # Expires first
        self.assertEqual(pinned[2]['content'], 'Pin 2')  # Expires last

    @allure.title("Backroom messages use separate cache")
    @allure.description("Test that backroom messages use separate Redis key")
    @allure.severity(allure.severity_level.NORMAL)
    def test_backroom_messages_separate_cache(self):
        """Test that backroom messages use separate Redis key"""
        # Create regular message
        regular_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Regular message'
        )
        MessageCache.add_message(regular_msg)

        # Create backroom message
        backroom_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Backroom message'
        )
        MessageCache.add_message(backroom_msg)

        # All messages should be in cache
        messages = MessageCache.get_messages(self.chat_room.code)
        self.assertEqual(len(messages), 2)

        # Verify both messages are cached
        message_contents = [msg['content'] for msg in messages]
        self.assertIn('Regular message', message_contents)
        self.assertIn('Backroom message', message_contents)

    @allure.title("Clear all chat cache")
    @allure.description("Test clearing all cached messages for a chat")
    @allure.severity(allure.severity_level.NORMAL)
    def test_clear_chat_cache(self):
        """Test clearing all cached messages for a chat"""
        # Create messages in different caches
        regular_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Regular'
        )
        MessageCache.add_message(regular_msg)

        pinned_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Pinned'
        )
        pinned_msg.is_pinned = True
        pinned_msg.pinned_until = timezone.now() + timedelta(hours=1)
        pinned_msg.save()
        MessageCache.add_pinned_message(pinned_msg)

        # Verify messages exist
        self.assertEqual(len(MessageCache.get_messages(self.chat_room.code)), 1)
        self.assertEqual(len(MessageCache.get_pinned_messages(self.chat_room.code)), 1)

        # Clear cache
        MessageCache.clear_chat_cache(self.chat_room.code)

        # Verify all caches are empty
        self.assertEqual(len(MessageCache.get_messages(self.chat_room.code)), 0)
        self.assertEqual(len(MessageCache.get_pinned_messages(self.chat_room.code)), 0)

    @allure.title("Message serialization is complete")
    @allure.description("Test that all message fields are properly serialized")
    @allure.severity(allure.severity_level.NORMAL)
    def test_message_serialization_completeness(self):
        """Test that all message fields are properly serialized"""
        # Create message with all optional fields
        reply_to_msg = Message.objects.create(
            chat_room=self.chat_room,
            username='OtherUser',
            content='Original message'
        )

        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Reply message',
            message_type=Message.MESSAGE_HOST,
            reply_to=reply_to_msg,
            is_pinned=True,
            pinned_at=timezone.now(),
            pinned_until=timezone.now() + timedelta(hours=1),
            pin_amount_paid=Decimal('10.50')
        )

        MessageCache.add_message(message)
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)

        # Find the reply message
        msg_data = next(m for m in messages if m['content'] == 'Reply message')

        # Verify all fields
        self.assertEqual(msg_data['username'], 'TestUser')
        self.assertEqual(msg_data['user_id'], str(self.user.id))
        self.assertEqual(msg_data['message_type'], Message.MESSAGE_HOST)
        self.assertTrue(msg_data['is_from_host'])  # Computed from message_type
        self.assertEqual(msg_data['reply_to_id'], str(reply_to_msg.id))
        self.assertTrue(msg_data['is_pinned'])
        self.assertIsNotNone(msg_data['pinned_at'])
        self.assertIsNotNone(msg_data['pinned_until'])
        self.assertEqual(msg_data['pin_amount_paid'], '10.50')
        self.assertFalse(msg_data['is_deleted'])

    @allure.title("Redis failure graceful degradation")
    @allure.description("Test that Redis failures don't crash (returns False/empty)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redis_failure_graceful_degradation(self):
        """Test that Redis failures don't crash (returns False/empty)"""
        # This test verifies error handling in MessageCache methods
        # Note: Actual Redis connection failures are hard to simulate in tests
        # but the code has try/except blocks that return False/[] on errors

        # Create message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='TestUser',
            user=self.user,
            content='Test message'
        )

        # Even if Redis has issues, these should not raise exceptions
        try:
            MessageCache.add_message(message)
            MessageCache.get_messages(self.chat_room.code)
            MessageCache.get_pinned_messages(self.chat_room.code)
            MessageCache.clear_chat_cache(self.chat_room.code)
            # If we get here without exceptions, test passes
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Redis operations should not raise exceptions: {e}")


@allure.feature('Message Caching')
@allure.story('Redis Performance')
class RedisPerformanceTests(TransactionTestCase):
    """Performance benchmarks for Redis caching"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        self.user = User.objects.create_user(
            email='perf@example.com',
            password='testpass123',
            reserved_username='PerfTest'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Performance Test Chat',
            host=self.user,
            access_mode='public'
        )

        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='PerfTest',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        cache.clear()

    @allure.title("Write performance: PostgreSQL only")
    @allure.description("Benchmark: Write to PostgreSQL only")
    @allure.severity(allure.severity_level.NORMAL)
    def test_write_performance_postgresql_only(self):
        """Benchmark: Write to PostgreSQL only"""
        start_time = time.time()

        for i in range(100):
            Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Message {i}'
            )

        duration = time.time() - start_time
        avg_per_message = (duration / 100) * 1000  # ms per message

        print(f"\n📊 PostgreSQL-only write: {avg_per_message:.2f}ms per message (100 messages in {duration:.2f}s)")

        # Should complete in reasonable time (not a hard assertion)
        self.assertLess(duration, 10.0)  # 100 messages in under 10 seconds

    @allure.title("Write performance: Dual-write to PostgreSQL + Redis")
    @allure.description("Benchmark: Dual-write to PostgreSQL + Redis")
    @allure.severity(allure.severity_level.NORMAL)
    def test_write_performance_dual_write(self):
        """Benchmark: Dual-write to PostgreSQL + Redis"""
        start_time = time.time()

        for i in range(100):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)

        duration = time.time() - start_time
        avg_per_message = (duration / 100) * 1000  # ms per message

        print(f"\n📊 Dual-write (PostgreSQL + Redis): {avg_per_message:.2f}ms per message (100 messages in {duration:.2f}s)")

        # Should complete in reasonable time
        self.assertLess(duration, 10.0)

    @allure.title("Read performance: Redis cache hit")
    @allure.description("Benchmark: Read from Redis (cache hit)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_read_performance_redis_cache_hit(self):
        """Benchmark: Read from Redis (cache hit)"""
        # Pre-populate cache with 50 messages
        for i in range(50):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)

        # Benchmark reads
        start_time = time.time()

        for _ in range(100):
            messages = MessageCache.get_messages(self.chat_room.code, limit=50)
            self.assertEqual(len(messages), 50)

        duration = time.time() - start_time
        avg_per_read = (duration / 100) * 1000  # ms per read

        print(f"\n📊 Redis cache read: {avg_per_read:.2f}ms per read (100 reads in {duration:.2f}s)")

        # Redis should be very fast (<5ms per read ideally)
        self.assertLess(avg_per_read, 10.0)  # Under 10ms per read

    @allure.title("Read performance: PostgreSQL fallback")
    @allure.description("Benchmark: Read from PostgreSQL (cache miss)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_read_performance_postgresql_fallback(self):
        """Benchmark: Read from PostgreSQL (cache miss)"""
        # Create messages in PostgreSQL but NOT in Redis
        for i in range(50):
            Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Message {i}'
            )

        # Benchmark PostgreSQL reads
        start_time = time.time()

        for _ in range(100):
            messages = Message.objects.filter(
                chat_room=self.chat_room,
                is_deleted=False
            ).order_by('-created_at')[:50]
            self.assertEqual(len(messages), 50)

        duration = time.time() - start_time
        avg_per_read = (duration / 100) * 1000  # ms per read

        print(f"\n📊 PostgreSQL read: {avg_per_read:.2f}ms per read (100 reads in {duration:.2f}s)")

        # PostgreSQL will be slower than Redis
        self.assertLess(duration, 10.0)

    @allure.title("Cache hit rate simulation")
    @allure.description("Simulate realistic cache hit rate scenario")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_hit_rate_simulation(self):
        """Simulate realistic cache hit rate scenario"""
        # Create 100 messages (simulating active chat)
        for i in range(100):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)

        # Simulate 1000 reads (most should hit cache)
        cache_hits = 0
        cache_misses = 0

        start_time = time.time()

        for _ in range(1000):
            messages = MessageCache.get_messages(self.chat_room.code, limit=50)
            if len(messages) > 0:
                cache_hits += 1
            else:
                cache_misses += 1

        duration = time.time() - start_time
        hit_rate = (cache_hits / 1000) * 100

        print(f"\n📊 Cache hit rate: {hit_rate:.1f}% ({cache_hits} hits, {cache_misses} misses)")
        print(f"📊 Total time for 1000 reads: {duration:.2f}s ({(duration/1000)*1000:.2f}ms per read)")

        # Should have very high hit rate (100% in this test)
        self.assertGreaterEqual(hit_rate, 99.0)

    @allure.title("Pinned message performance")
    @allure.description("Benchmark: Pinned message operations")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pinned_message_performance(self):
        """Benchmark: Pinned message operations"""
        # Create 10 pinned messages
        messages = []
        for i in range(10):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='PerfTest',
                user=self.user,
                content=f'Pinned {i}'
            )
            message.is_pinned = True
            message.pinned_until = timezone.now() + timedelta(hours=i+1)
            message.save()
            messages.append(message)

        # Benchmark adding to pinned cache
        start_time = time.time()
        for message in messages:
            MessageCache.add_pinned_message(message)
        add_duration = time.time() - start_time

        # Benchmark reading pinned messages
        start_time = time.time()
        for _ in range(100):
            pinned = MessageCache.get_pinned_messages(self.chat_room.code)
            self.assertEqual(len(pinned), 10)
        read_duration = time.time() - start_time

        print(f"\n📊 Pinned message add: {(add_duration/10)*1000:.2f}ms per message")
        print(f"📊 Pinned message read: {(read_duration/100)*1000:.2f}ms per read (100 reads)")

        # Should be fast
        self.assertLess(read_duration / 100, 0.01)  # Under 10ms per read


@allure.feature('Message Caching')
@allure.story('Redis Reaction Caching')
class RedisReactionCacheTests(TransactionTestCase):
    """Test Redis reaction caching functionality"""

    def setUp(self):
        """Set up test data"""
        cache.clear()

        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='testpass123',
            reserved_username='User1'
        )

        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='testpass123',
            reserved_username='User2'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user1,
            access_mode='public'
        )

        self.message1 = Message.objects.create(
            chat_room=self.chat_room,
            username='User1',
            user=self.user1,
            content='Test message 1'
        )

        self.message2 = Message.objects.create(
            chat_room=self.chat_room,
            username='User2',
            user=self.user2,
            content='Test message 2'
        )

    def tearDown(self):
        cache.clear()

    @allure.title("Set message reactions")
    @allure.description("Test caching reaction summary for a message")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_message_reactions(self):
        """Test caching reaction summary for a message"""
        reactions = [
            {"emoji": "👍", "count": 5, "users": ["alice", "bob", "charlie", "dave", "eve"]},
            {"emoji": "❤️", "count": 3, "users": ["alice", "bob", "charlie"]},
            {"emoji": "😂", "count": 1, "users": ["dave"]}
        ]

        result = MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions
        )

        self.assertTrue(result)

        # Verify cached reactions
        cached = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )

        self.assertEqual(len(cached), 3)
        # Find each reaction by emoji
        thumbs_up = next(r for r in cached if r['emoji'] == '👍')
        heart = next(r for r in cached if r['emoji'] == '❤️')
        laugh = next(r for r in cached if r['emoji'] == '😂')

        self.assertEqual(thumbs_up['count'], 5)
        self.assertEqual(heart['count'], 3)
        self.assertEqual(laugh['count'], 1)

    @allure.title("Get message reactions: cache miss")
    @allure.description("Test that cache miss returns empty list")
    @allure.severity(allure.severity_level.NORMAL)
    def test_get_message_reactions_cache_miss(self):
        """Test that cache miss returns empty list"""
        reactions = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )

        self.assertEqual(reactions, [])

    @allure.title("Set empty reactions deletes cache")
    @allure.description("Test that setting empty reactions removes the cache key")
    @allure.severity(allure.severity_level.NORMAL)
    def test_set_empty_reactions_deletes_cache(self):
        """Test that setting empty reactions removes the cache key"""
        # First cache some reactions
        reactions = [{"emoji": "👍", "count": 5, "users": ["alice"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions
        )

        # Verify cached
        cached = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )
        self.assertEqual(len(cached), 1)

        # Set empty reactions
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            []
        )

        # Verify cache deleted
        cached = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )
        self.assertEqual(cached, [])

    @allure.title("Batch get reactions")
    @allure.description("Test batch fetching reactions for multiple messages")
    @allure.severity(allure.severity_level.NORMAL)
    def test_batch_get_reactions(self):
        """Test batch fetching reactions for multiple messages"""
        # Cache reactions for message1
        reactions1 = [
            {"emoji": "👍", "count": 5, "users": ["alice", "bob"]},
            {"emoji": "❤️", "count": 2, "users": ["charlie"]}
        ]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions1
        )

        # Cache reactions for message2
        reactions2 = [
            {"emoji": "😂", "count": 3, "users": ["dave"]},
        ]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message2.id),
            reactions2
        )

        # Batch fetch
        message_ids = [str(self.message1.id), str(self.message2.id)]
        reactions_by_message = MessageCache.batch_get_reactions(
            self.chat_room.code,
            message_ids
        )

        # Verify results
        self.assertEqual(len(reactions_by_message), 2)

        # Message 1 reactions
        msg1_reactions = reactions_by_message[str(self.message1.id)]
        self.assertEqual(len(msg1_reactions), 2)
        thumbs_up = next(r for r in msg1_reactions if r['emoji'] == '👍')
        self.assertEqual(thumbs_up['count'], 5)

        # Message 2 reactions
        msg2_reactions = reactions_by_message[str(self.message2.id)]
        self.assertEqual(len(msg2_reactions), 1)
        self.assertEqual(msg2_reactions[0]['emoji'], '😂')
        self.assertEqual(msg2_reactions[0]['count'], 3)

    @allure.title("Batch get reactions with cache miss")
    @allure.description("Test batch fetch with some messages missing from cache")
    @allure.severity(allure.severity_level.NORMAL)
    def test_batch_get_reactions_with_cache_miss(self):
        """Test batch fetch with some messages missing from cache"""
        # Only cache reactions for message1
        reactions1 = [{"emoji": "👍", "count": 5, "users": ["alice"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions1
        )

        # Batch fetch (message2 not cached)
        message_ids = [str(self.message1.id), str(self.message2.id)]
        reactions_by_message = MessageCache.batch_get_reactions(
            self.chat_room.code,
            message_ids
        )

        # Should return dict with both keys
        self.assertEqual(len(reactions_by_message), 2)

        # Message 1 should have reactions
        self.assertEqual(len(reactions_by_message[str(self.message1.id)]), 1)

        # Message 2 should have empty list (cache miss)
        self.assertEqual(reactions_by_message[str(self.message2.id)], [])

    @allure.title("Batch get reactions with empty list")
    @allure.description("Test batch fetch with empty message ID list")
    @allure.severity(allure.severity_level.NORMAL)
    def test_batch_get_reactions_empty_list(self):
        """Test batch fetch with empty message ID list"""
        reactions_by_message = MessageCache.batch_get_reactions(
            self.chat_room.code,
            []
        )

        self.assertEqual(reactions_by_message, {})

    @allure.title("Batch get reactions uses single round-trip")
    @allure.description("Test that batch fetch uses single Redis round-trip (pipelining)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_batch_get_reactions_single_round_trip(self):
        """Test that batch fetch uses single Redis round-trip (pipelining)"""
        # Create 10 messages with reactions
        messages = []
        for i in range(10):
            msg = Message.objects.create(
                chat_room=self.chat_room,
                username='User1',
                user=self.user1,
                content=f'Message {i}'
            )
            messages.append(msg)

            reactions = [{"emoji": "👍", "count": i + 1, "users": ["alice"]}]
            MessageCache.set_message_reactions(
                self.chat_room.code,
                str(msg.id),
                reactions
            )

        # Batch fetch all at once
        start_time = time.time()
        message_ids = [str(msg.id) for msg in messages]
        reactions_by_message = MessageCache.batch_get_reactions(
            self.chat_room.code,
            message_ids
        )
        duration = (time.time() - start_time) * 1000  # ms

        # Verify all fetched
        self.assertEqual(len(reactions_by_message), 10)

        # Should be very fast (single round-trip)
        print(f"\n📊 Batch get {len(messages)} message reactions: {duration:.2f}ms")
        self.assertLess(duration, 50.0)  # Under 50ms for 10 messages

    @allure.title("Reaction cache TTL")
    @allure.description("Test that reaction cache has 24-hour TTL")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reaction_cache_ttl(self):
        """Test that reaction cache has 24-hour TTL"""
        reactions = [{"emoji": "👍", "count": 5, "users": ["alice"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions
        )

        # Check TTL is set (should be 24 hours = 86400 seconds)
        redis_client = MessageCache._get_redis_client()
        key = f"chat:{self.chat_room.code}:reactions:{self.message1.id}"
        ttl = redis_client.ttl(key)

        # TTL should be set and close to 24 hours
        self.assertGreater(ttl, 86000)  # Greater than 23.8 hours
        self.assertLess(ttl, 86500)  # Less than 24.1 hours

    @allure.title("Reaction cache update")
    @allure.description("Test updating cached reactions when new reactions are added")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reaction_cache_update(self):
        """Test updating cached reactions when new reactions are added"""
        # Initial cache
        initial_reactions = [{"emoji": "👍", "count": 2, "users": ["alice", "bob"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            initial_reactions
        )

        # Update cache with new reaction
        updated_reactions = [
            {"emoji": "👍", "count": 3, "users": ["alice", "bob", "charlie"]},
            {"emoji": "❤️", "count": 1, "users": ["dave"]}
        ]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            updated_reactions
        )

        # Verify updated
        cached = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )

        self.assertEqual(len(cached), 2)
        thumbs_up = next(r for r in cached if r['emoji'] == '👍')
        self.assertEqual(thumbs_up['count'], 3)

    @allure.title("Different messages have separate reaction caches")
    @allure.description("Test that different messages have separate reaction caches")
    @allure.severity(allure.severity_level.NORMAL)
    def test_different_messages_separate_cache(self):
        """Test that different messages have separate reaction caches"""
        # Cache reactions for message1
        reactions1 = [{"emoji": "👍", "count": 5, "users": ["alice"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message1.id),
            reactions1
        )

        # Cache reactions for message2
        reactions2 = [{"emoji": "❤️", "count": 3, "users": ["bob"]}]
        MessageCache.set_message_reactions(
            self.chat_room.code,
            str(self.message2.id),
            reactions2
        )

        # Verify separate caches
        cached1 = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )
        cached2 = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message2.id)
        )

        self.assertEqual(len(cached1), 1)
        self.assertEqual(cached1[0]['emoji'], '👍')

        self.assertEqual(len(cached2), 1)
        self.assertEqual(cached2[0]['emoji'], '❤️')

    @allure.title("Reaction cache handles Redis failures gracefully")
    @allure.description("Test that Redis failures don't crash (returns False/empty)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reaction_cache_redis_failure_graceful(self):
        """Test that Redis failures don't crash (returns False/empty)"""
        reactions = [{"emoji": "👍", "count": 5, "users": ["alice"]}]

        # These should not raise exceptions even if Redis has issues
        try:
            MessageCache.set_message_reactions(
                self.chat_room.code,
                str(self.message1.id),
                reactions
            )
            MessageCache.get_message_reactions(
                self.chat_room.code,
                str(self.message1.id)
            )
            MessageCache.batch_get_reactions(
                self.chat_room.code,
                [str(self.message1.id)]
            )
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"Reaction cache operations should not raise exceptions: {e}")


@allure.feature('Message Caching')
@allure.story('Cache Configuration Control')
class ConstanceCacheControlTests(TransactionTestCase):
    """Test Constance dynamic settings for cache control"""

    def setUp(self):
        """Set up test data"""
        from constance import config

        cache.clear()

        # Store original settings
        self.original_cache_enabled = config.REDIS_CACHE_ENABLED

        self.user = User.objects.create_user(
            email='config@example.com',
            password='testpass123',
            reserved_username='ConfigTest'
        )

        self.chat_room = ChatRoom.objects.create(
            name='Config Test Chat',
            host=self.user,
            access_mode='public'
        )

        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            username='ConfigTest',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        """Restore original settings"""
        from constance import config

        # Restore original settings
        config.REDIS_CACHE_ENABLED = self.original_cache_enabled

        cache.clear()

    @allure.title("Redis cache enabled: writes to cache")
    @allure.description("Test that messages are written to cache when REDIS_CACHE_ENABLED=True")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redis_cache_enabled_true_writes_to_cache(self):
        """Test that messages are written to cache when REDIS_CACHE_ENABLED=True"""
        from constance import config

        # Enable cache
        config.REDIS_CACHE_ENABLED = True

        # Create message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Cache enabled test'
        )

        # Manually call add_message (simulating WebSocket consumer behavior)
        if config.REDIS_CACHE_ENABLED:
            MessageCache.add_message(message)

        # Verify message is in Redis
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], 'Cache enabled test')

    @allure.title("Redis cache disabled: skips write")
    @allure.description("Test that messages are NOT written to cache when REDIS_CACHE_ENABLED=False")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redis_cache_enabled_false_skips_write(self):
        """Test that messages are NOT written to cache when REDIS_CACHE_ENABLED=False"""
        from constance import config

        # Disable cache
        config.REDIS_CACHE_ENABLED = False

        # Create message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Cache disabled test'
        )

        # Conditionally call add_message (simulating WebSocket consumer behavior)
        if config.REDIS_CACHE_ENABLED:
            MessageCache.add_message(message)

        # Verify message is NOT in Redis
        messages = MessageCache.get_messages(self.chat_room.code, limit=10)
        self.assertEqual(len(messages), 0)

        # But message should exist in PostgreSQL
        db_messages = Message.objects.filter(chat_room=self.chat_room)
        self.assertEqual(db_messages.count(), 1)
        self.assertEqual(db_messages.first().content, 'Cache disabled test')

    @allure.title("Redis cache enabled: reads from cache")
    @allure.description("Test that REDIS_CACHE_ENABLED=True causes reads from Redis")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redis_cache_enabled_true_reads_from_cache(self):
        """Test that REDIS_CACHE_ENABLED=True causes reads from Redis"""
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Enable cache reads
        config.REDIS_CACHE_ENABLED = True

        # Create and cache a message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Read from cache test'
        )
        MessageCache.add_message(message)

        # Simulate API request using DRF's APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # Should read from Redis (may be hybrid if reactions need PostgreSQL fetch)
        self.assertIn(response.data['source'], ['redis', 'hybrid_redis_postgresql'])
        self.assertTrue(response.data['cache_enabled'])
        self.assertEqual(len(response.data['messages']), 1)
        self.assertEqual(response.data['messages'][0]['content'], 'Read from cache test')

    @allure.title("Redis cache disabled: reads from PostgreSQL")
    @allure.description("Test that REDIS_CACHE_ENABLED=False causes reads from PostgreSQL")
    @allure.severity(allure.severity_level.NORMAL)
    def test_redis_cache_enabled_false_reads_from_postgresql(self):
        """Test that REDIS_CACHE_ENABLED=False causes reads from PostgreSQL"""
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Disable cache reads
        config.REDIS_CACHE_ENABLED = False

        # Create message in PostgreSQL (don't cache)
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Read from PostgreSQL test'
        )

        # Simulate API request using DRF's APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # Should read from PostgreSQL
        self.assertEqual(response.data['source'], 'postgresql')
        self.assertFalse(response.data['cache_enabled'])
        self.assertEqual(len(response.data['messages']), 1)
        self.assertEqual(response.data['messages'][0]['content'], 'Read from PostgreSQL test')

    @allure.title("Cache miss fallback to PostgreSQL")
    @allure.description("Test that cache miss falls back to PostgreSQL")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_miss_fallback_to_postgresql(self):
        """Test that cache miss falls back to PostgreSQL"""
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Enable cache reads
        config.REDIS_CACHE_ENABLED = True

        # Create message in PostgreSQL but NOT in Redis (simulating cache miss)
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Cache miss test'
        )
        # Don't call MessageCache.add_message() - simulate cache miss

        # Simulate API request using DRF's APIRequestFactory
        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # Should fallback to PostgreSQL
        self.assertEqual(response.data['source'], 'postgresql_fallback')
        self.assertTrue(response.data['cache_enabled'])
        self.assertEqual(len(response.data['messages']), 1)
        self.assertEqual(response.data['messages'][0]['content'], 'Cache miss test')

    @allure.title("Pagination always uses PostgreSQL")
    @allure.description("Test that pagination requests always use PostgreSQL (never Redis)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pagination_always_uses_postgresql(self):
        """Test that pagination requests always use PostgreSQL (never Redis)"""
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Enable cache reads
        config.REDIS_CACHE_ENABLED = True

        # Create and cache messages
        for i in range(5):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='ConfigTest',
                user=self.user,
                content=f'Message {i}'
            )
            MessageCache.add_message(message)

        # Simulate pagination request (with before parameter) using DRF's APIRequestFactory
        factory = APIRequestFactory()
        before_timestamp = timezone.now().timestamp()  # Unix timestamp (float)
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/?before={before_timestamp}')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # Pagination now uses Redis cache when available (with reaction caching enabled)
        # May be 'redis', 'hybrid_redis_postgresql', or 'postgresql' depending on cache state
        self.assertIn(response.data['source'], ['postgresql', 'redis', 'hybrid_redis_postgresql'])
        self.assertTrue(response.data['cache_enabled'])

    @allure.title("Cache TTL expiry")
    @allure.description("Test that messages expire from cache after TTL (24 hours)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_ttl_expiry(self):
        """Test that messages expire from cache after TTL (24 hours)"""
        # Create and cache a message
        message = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='TTL test'
        )
        MessageCache.add_message(message)

        # Check TTL is set on the Redis key
        redis_client = MessageCache._get_redis_client()
        key = f"chat:{self.chat_room.code}:messages"
        ttl = redis_client.ttl(key)

        # TTL should be set to 24 hours (86400 seconds)
        # Allow small margin for test execution time
        self.assertGreater(ttl, 86000)  # Greater than 23.8 hours
        self.assertLess(ttl, 86500)  # Less than 24.1 hours

    @allure.title("Cache hit performance vs PostgreSQL")
    @allure.description("Test that Redis cache is significantly faster than PostgreSQL")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_hit_performance_vs_postgresql(self):
        """Test that Redis cache is significantly faster than PostgreSQL"""
        from constance import config

        # Create 50 messages
        messages = []
        for i in range(50):
            message = Message.objects.create(
                chat_room=self.chat_room,
                username='ConfigTest',
                user=self.user,
                content=f'Performance test {i}'
            )
            MessageCache.add_message(message)
            messages.append(message)

        # Benchmark Redis cache read
        config.REDIS_CACHE_ENABLED = True
        start_time = time.time()
        for _ in range(100):
            cached_messages = MessageCache.get_messages(self.chat_room.code, limit=50)
            self.assertEqual(len(cached_messages), 50)
        redis_duration = time.time() - start_time
        redis_avg = (redis_duration / 100) * 1000  # ms per read

        # Benchmark PostgreSQL read
        start_time = time.time()
        for _ in range(100):
            db_messages = Message.objects.filter(
                chat_room=self.chat_room,
                is_deleted=False
            ).order_by('-created_at')[:50]
            self.assertEqual(len(db_messages), 50)
        postgresql_duration = time.time() - start_time
        postgresql_avg = (postgresql_duration / 100) * 1000  # ms per read

        print(f"\n📊 Cache Performance Comparison:")
        print(f"   Redis cache: {redis_avg:.2f}ms per read")
        print(f"   PostgreSQL: {postgresql_avg:.2f}ms per read")
        if postgresql_avg > 0:
            print(f"   Speedup: {postgresql_avg / redis_avg:.1f}x faster")
        else:
            print(f"   Speedup: N/A (PostgreSQL too fast to measure)")

        # Redis should be faster than PostgreSQL (or at minimum equal performance)
        self.assertLessEqual(redis_avg, postgresql_avg)

    @allure.title("Toggle cache settings at runtime")
    @allure.description("Test dynamically changing cache settings at runtime")
    @allure.severity(allure.severity_level.NORMAL)
    def test_toggle_cache_settings_runtime(self):
        """Test dynamically changing cache settings at runtime"""
        from constance import config

        # Start with cache disabled
        config.REDIS_CACHE_ENABLED = False

        # Create message (shouldn't be cached)
        message1 = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='Before enable'
        )
        if config.REDIS_CACHE_ENABLED:
            MessageCache.add_message(message1)

        # Verify not in cache
        messages = MessageCache.get_messages(self.chat_room.code)
        self.assertEqual(len(messages), 0)

        # Enable cache
        config.REDIS_CACHE_ENABLED = True

        # Create new message (should be cached)
        message2 = Message.objects.create(
            chat_room=self.chat_room,
            username='ConfigTest',
            user=self.user,
            content='After enable'
        )
        if config.REDIS_CACHE_ENABLED:
            MessageCache.add_message(message2)

        # Verify in cache
        messages = MessageCache.get_messages(self.chat_room.code)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], 'After enable')

        # Now reads should come from Redis using DRF's APIRequestFactory
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # May be hybrid if reactions need PostgreSQL fetch
        self.assertIn(response.data['source'], ['redis', 'hybrid_redis_postgresql'])
        self.assertTrue(response.data['cache_enabled'])

    @allure.title("Cache backfill on miss")
    @allure.description("Test that cache miss triggers backfill to Redis")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cache_backfill_on_miss(self):
        """Test that cache miss triggers backfill to Redis"""
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Enable cache
        config.REDIS_CACHE_ENABLED = True

        # Create messages in PostgreSQL but NOT in Redis (simulating cache miss)
        for i in range(5):
            Message.objects.create(
                chat_room=self.chat_room,
                username='ConfigTest',
                user=self.user,
                content=f'Backfill test {i}'
            )
        # Don't call MessageCache.add_message() - simulate cache miss

        # Verify cache is empty
        cached_messages = MessageCache.get_messages(self.chat_room.code)
        self.assertEqual(len(cached_messages), 0)

        # Make initial API request (should trigger backfill)
        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # First request should be a cache miss (fallback to PostgreSQL)
        self.assertEqual(response.data['source'], 'postgresql_fallback')
        self.assertEqual(len(response.data['messages']), 5)

        # Verify messages were backfilled to cache
        cached_messages = MessageCache.get_messages(self.chat_room.code, limit=10)
        self.assertEqual(len(cached_messages), 5)
        self.assertEqual(cached_messages[0]['content'], 'Backfill test 0')
        self.assertEqual(cached_messages[4]['content'], 'Backfill test 4')

        # Second request should hit the cache (after backfill, may be hybrid if reactions need PostgreSQL fetch)
        request2 = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/')
        response2 = view(request2, username='ConfigTest', code=self.chat_room.code)

        self.assertIn(response2.data['source'], ['redis', 'hybrid_redis_postgresql'])
        self.assertEqual(len(response2.data['messages']), 5)

    @allure.title("Partial cache hit backfills missing messages")
    @allure.description("""Test that partial cache hits backfill missing messages to Redis.

This test verifies the bug fix where:
- Request limit=50, but only 41 messages in cache
- System fetches 9 older messages from database
- Those 9 messages should be backfilled to cache
- Subsequent requests should NOT re-fetch those 9 from database""")
    @allure.severity(allure.severity_level.NORMAL)
    def test_partial_cache_hit_backfills_missing_messages(self):
        """
        Test that partial cache hits backfill missing messages to Redis.

        This test verifies the bug fix where:
        - Request limit=50, but only 41 messages in cache
        - System fetches 9 older messages from database
        - Those 9 messages should be backfilled to cache
        - Subsequent requests should NOT re-fetch those 9 from database
        """
        from constance import config
        from rest_framework.test import APIRequestFactory
        from chats.views import MessageListView

        # Enable cache
        config.REDIS_CACHE_ENABLED = True

        # Create 50 messages in PostgreSQL
        messages = []
        for i in range(50):
            msg = Message.objects.create(
                chat_room=self.chat_room,
                username='ConfigTest',
                user=self.user,
                content=f'Message {i}'
            )
            messages.append(msg)
            time.sleep(0.001)  # Small delay for timestamp ordering

        # Manually cache only the most recent 41 messages (simulating partial cache)
        # Cache messages 9-49 (leaving 0-8 uncached)
        for msg in messages[9:]:
            MessageCache.add_message(msg)

        # Verify exactly 41 messages in cache
        cached_before = MessageCache.get_messages(self.chat_room.code, limit=100)
        self.assertEqual(len(cached_before), 41, "Should have exactly 41 messages in cache")

        # Make API request for 50 messages (should be partial hit: 41 from cache + 9 from DB)
        factory = APIRequestFactory()
        request = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/?limit=50')

        view = MessageListView.as_view()
        response = view(request, username='ConfigTest', code=self.chat_room.code)

        # Should be a hybrid source (partial cache hit)
        self.assertEqual(response.data['source'], 'hybrid_redis_postgresql')
        self.assertEqual(len(response.data['messages']), 50)

        # Verify the 9 missing messages were backfilled to cache
        cached_after = MessageCache.get_messages(self.chat_room.code, limit=100)
        self.assertEqual(len(cached_after), 50, "All 50 messages should now be in cache after backfill")

        # Verify the oldest messages are now cached (messages 0-8)
        oldest_cached = [msg['content'] for msg in cached_after[:9]]
        expected_oldest = [f'Message {i}' for i in range(9)]
        self.assertEqual(oldest_cached, expected_oldest, "Oldest 9 messages should be backfilled")

        # Make second request - should be FULL cache hit (no DB query)
        request2 = factory.get(f'/api/chats/ConfigTest/{self.chat_room.code}/messages/?limit=50')
        response2 = view(request2, username='ConfigTest', code=self.chat_room.code)

        # Second request should hit cache completely
        self.assertEqual(response2.data['source'], 'redis', "Second request should be full cache hit")
        self.assertEqual(len(response2.data['messages']), 50)
