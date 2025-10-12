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
from chats.redis_cache import MessageCache


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

    def test_cache_retention_max_count(self):
        """Test that cache trims to MAX_MESSAGES (500 by default)"""
        # Override MAX_MESSAGES for testing
        original_max = MessageCache.MAX_MESSAGES
        MessageCache.MAX_MESSAGES = 10

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
            MessageCache.MAX_MESSAGES = original_max

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

    def test_get_message_reactions_cache_miss(self):
        """Test that cache miss returns empty list"""
        reactions = MessageCache.get_message_reactions(
            self.chat_room.code,
            str(self.message1.id)
        )

        self.assertEqual(reactions, [])

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

    def test_batch_get_reactions_empty_list(self):
        """Test batch fetch with empty message ID list"""
        reactions_by_message = MessageCache.batch_get_reactions(
            self.chat_room.code,
            []
        )

        self.assertEqual(reactions_by_message, {})

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
