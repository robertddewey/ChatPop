"""
Django management command to inspect and debug Redis message cache.

Usage:
    ./venv/bin/python manage.py inspect_redis --list
    ./venv/bin/python manage.py inspect_redis --chat robert/my-chat
    ./venv/bin/python manage.py inspect_redis --chat robert/my-chat --show-messages
    ./venv/bin/python manage.py inspect_redis --chat robert/my-chat --compare
    ./venv/bin/python manage.py inspect_redis --message <uuid>
    ./venv/bin/python manage.py inspect_redis --chat robert/my-chat --clear
    ./venv/bin/python manage.py inspect_redis --chat robert/my-chat --monitor
"""

import json
import time
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User
from chats.models import ChatRoom, Message
from chats.utils.performance.cache import MessageCache


class Command(BaseCommand):
    help = 'Inspect and debug Redis message cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all chat caches in Redis'
        )
        parser.add_argument(
            '--chat',
            type=str,
            help='Chat path in format username/code (e.g., robert/my-chat)'
        )
        parser.add_argument(
            '--show-messages',
            action='store_true',
            help='Show cached messages for the chat'
        )
        parser.add_argument(
            '--show-reactions',
            action='store_true',
            help='Show cached reactions for the chat'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Number of messages to show (default: 10)'
        )
        parser.add_argument(
            '--compare',
            action='store_true',
            help='Compare Redis cache with PostgreSQL'
        )
        parser.add_argument(
            '--message',
            type=str,
            help='Show specific message by ID'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear Redis cache for the chat'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt when clearing'
        )
        parser.add_argument(
            '--monitor',
            action='store_true',
            help='Monitor cache in real-time (Ctrl+C to stop)'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show overall Redis statistics'
        )

    def get_chat_room(self, chat_path):
        """Parse username/code format and return ChatRoom"""
        if '/' not in chat_path:
            raise CommandError(
                f"Invalid format: '{chat_path}'\n"
                f"Expected format: username/code (e.g., robert/my-chat)"
            )

        username, chat_code = chat_path.split('/', 1)

        try:
            host_user = User.objects.get(reserved_username=username)
        except User.DoesNotExist:
            raise CommandError(f"User with username '{username}' not found")

        try:
            chat_room = ChatRoom.objects.get(
                host=host_user,
                code=chat_code,
                is_active=True
            )
        except ChatRoom.DoesNotExist:
            raise CommandError(
                f"Chat room '{chat_code}' not found for user '{username}'\n"
                f"Full path: {username}/{chat_code}"
            )

        return chat_room

    def handle(self, *args, **options):
        if options['list']:
            self.list_caches()
        elif options['stats']:
            self.show_stats()
        elif options['message']:
            self.inspect_message(options['message'])
        elif options['chat']:
            chat_path = options['chat']
            chat_room = self.get_chat_room(chat_path)
            if options['clear']:
                self.clear_cache(chat_room, options['force'])
            elif options['monitor']:
                self.monitor_cache(chat_room)
            elif options['compare']:
                self.compare_cache(chat_room)
            else:
                self.inspect_chat(chat_room, options['show_messages'], options['show_reactions'], options['limit'])
        else:
            self.stdout.write(self.style.ERROR('Please specify an action. Use --help for usage.'))

    def list_caches(self):
        """List all chat caches in Redis"""
        redis_client = MessageCache._get_redis_client()

        # Get all chat room codes
        chats = ChatRoom.objects.filter(is_active=True).order_by('-created_at')

        self.stdout.write(self.style.SUCCESS('\n📦 Redis Chat Caches:\n'))

        found_any = False
        for chat in chats:
            room_id = str(chat.id)
            # Check each key type
            keys = [
                (MessageCache.MESSAGES_KEY.format(room_id=room_id), 'messages'),
                (MessageCache.PINNED_ORDER_KEY.format(room_id=room_id), 'pinned'),
            ]

            for key, key_type in keys:
                count = redis_client.zcard(key)
                if count > 0:
                    found_any = True
                    ttl = redis_client.ttl(key)
                    ttl_str = self._format_ttl(ttl)

                    self.stdout.write(
                        f'  {key} ({count} {key_type}, TTL: {ttl_str})'
                    )

        if not found_any:
            self.stdout.write(self.style.WARNING('  No caches found in Redis'))

        self.stdout.write('')

    def inspect_chat(self, chat_room, show_messages=False, show_reactions=False, limit=10):
        """Inspect a specific chat's Redis cache"""
        redis_client = MessageCache._get_redis_client()
        room_id = str(chat_room.id)

        self.stdout.write(self.style.SUCCESS(f'\n🔍 Chat: {chat_room.host.reserved_username}/{chat_room.code} ({chat_room.name})'))
        self.stdout.write('━' * 60)

        # Main messages
        main_key = MessageCache.MESSAGES_KEY.format(room_id=room_id)
        main_count = redis_client.zcard(main_key)
        self.stdout.write(f'\n📨 Main Messages ({main_count} cached)')
        self.stdout.write(f'  Key: {main_key}')

        if main_count > 0:
            ttl = redis_client.ttl(main_key)
            self.stdout.write(f'  TTL: {self._format_ttl(ttl)}')

            # Get oldest and newest
            oldest = redis_client.zrange(main_key, 0, 0)
            newest = redis_client.zrange(main_key, -1, -1)

            if oldest:
                oldest_data = json.loads(oldest[0])
                self.stdout.write(f'  Oldest: {oldest_data["created_at"]}')

            if newest:
                newest_data = json.loads(newest[0])
                self.stdout.write(f'  Newest: {newest_data["created_at"]}')

        # Pinned messages
        pinned_key = MessageCache.PINNED_ORDER_KEY.format(room_id=room_id)
        pinned_count = redis_client.zcard(pinned_key)
        self.stdout.write(f'\n📌 Pinned Messages ({pinned_count} cached)')
        self.stdout.write(f'  Key: {pinned_key}')

        if pinned_count > 0:
            ttl = redis_client.ttl(pinned_key)
            self.stdout.write(f'  TTL: {self._format_ttl(ttl)}')

        # Reaction caches
        self.stdout.write(f'\n😀 Reaction Caches')
        reaction_pattern = f"room:{room_id}:reactions:*"
        reaction_keys = redis_client.keys(reaction_pattern)
        self.stdout.write(f'  Pattern: {reaction_pattern}')
        self.stdout.write(f'  Count: {len(reaction_keys)} messages with cached reactions')

        if len(reaction_keys) > 0:
            # Sample TTL from first key
            sample_ttl = redis_client.ttl(reaction_keys[0])
            self.stdout.write(f'  TTL: {self._format_ttl(sample_ttl)}')

        # Show messages if requested
        if show_messages and main_count > 0:
            self.stdout.write(f'\n📨 Last {limit} Messages in Redis:\n')
            messages = MessageCache.get_messages(room_id, limit=limit)

            for msg in messages[-limit:]:  # Show most recent
                timestamp = datetime.fromisoformat(msg['created_at']).strftime('%Y-%m-%d %H:%M:%S')
                username = msg['username']

                # Add badges
                badges = []
                if msg['message_type'] == 'host':
                    badges.append('HOST 👑')
                if msg.get('username_is_reserved'):
                    badges.append('VERIFIED ✓')

                badge_str = f" ({', '.join(badges)})" if badges else ''

                self.stdout.write(f'[{timestamp}] {username}{badge_str}')
                self.stdout.write(f'  "{msg["content"]}"')
                if msg.get('is_pinned'):
                    self.stdout.write(f'  📌 Pinned (${msg["pin_amount_paid"]})')
                self.stdout.write('')

        # Show reactions if requested
        if show_reactions and len(reaction_keys) > 0:
            self.stdout.write(f'\n😀 Reaction Cache Details (showing up to {limit}):\n')

            for reaction_key in reaction_keys[:limit]:
                # Extract message_id from key: room:{room_id}:reactions:{msg_id}
                message_id = reaction_key.decode('utf-8').split(':')[-1] if isinstance(reaction_key, bytes) else reaction_key.split(':')[-1]

                # Get reactions for this message
                reactions = MessageCache.get_message_reactions(room_id, message_id)

                if reactions:
                    # Get message details for context
                    try:
                        message = Message.objects.get(id=message_id)
                        username = message.username
                        content_preview = message.content[:50] + '...' if len(message.content) > 50 else message.content
                    except Message.DoesNotExist:
                        username = '[deleted]'
                        content_preview = '[message not found]'

                    self.stdout.write(f'Message ID: {message_id}')
                    self.stdout.write(f'  From: {username}')
                    self.stdout.write(f'  Content: "{content_preview}"')
                    reactions_str = ", ".join([f"{r['emoji']} ({r['count']})" for r in reactions])
                    self.stdout.write(f'  Reactions: {reactions_str}')
                    self.stdout.write('')

        self.stdout.write('')

    def compare_cache(self, chat_room):
        """Compare Redis cache with PostgreSQL"""
        room_id = str(chat_room.id)

        # Get PostgreSQL count
        pg_count = Message.objects.filter(chat_room=chat_room, is_deleted=False).count()

        # Get Redis count
        redis_messages = MessageCache.get_messages(room_id, limit=1000)  # Get all
        redis_count = len(redis_messages)

        self.stdout.write(self.style.SUCCESS(f'\n🔄 PostgreSQL vs Redis Comparison:\n'))
        self.stdout.write(f'PostgreSQL: {pg_count} messages')
        self.stdout.write(f'Redis:      {redis_count} messages')

        if redis_count == pg_count:
            self.stdout.write(self.style.SUCCESS('Match:      ✓\n'))
        else:
            self.stdout.write(self.style.WARNING(f'Difference: {pg_count - redis_count} messages\n'))

        # Latest message comparison
        latest_pg = Message.objects.filter(chat_room=chat_room, is_deleted=False).order_by('-created_at').first()

        if latest_pg and redis_messages:
            latest_redis = redis_messages[-1]

            self.stdout.write(f'Latest in PostgreSQL: {latest_pg.created_at.isoformat()} (id: {latest_pg.id})')
            self.stdout.write(f'Latest in Redis:      {latest_redis["created_at"]} (id: {latest_redis["id"]})')

            if str(latest_pg.id) == latest_redis['id']:
                self.stdout.write(self.style.SUCCESS('Sync Status:          ✓ Up to date\n'))
            else:
                self.stdout.write(self.style.WARNING('Sync Status:          ⚠ Out of sync\n'))

        # Find missing/extra messages
        if redis_count > 0 and pg_count > 0:
            redis_ids = {msg['id'] for msg in redis_messages}
            pg_messages = Message.objects.filter(chat_room=chat_room, is_deleted=False).order_by('-created_at')[:redis_count]
            pg_ids = {str(msg.id) for msg in pg_messages}

            missing_in_redis = pg_ids - redis_ids
            extra_in_redis = redis_ids - pg_ids

            self.stdout.write(f'Missing in Redis:     {len(missing_in_redis)} messages')
            self.stdout.write(f'Extra in Redis:       {len(extra_in_redis)} messages')

        self.stdout.write('')

    def inspect_message(self, message_id):
        """Inspect a specific message"""
        try:
            message = Message.objects.get(id=message_id)
        except Message.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Message {message_id} not found in PostgreSQL'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n🔍 Message: {message_id}\n'))

        # PostgreSQL data
        self.stdout.write('PostgreSQL:')
        self.stdout.write('  ✓ Found')
        self.stdout.write(f'  Type: {message.message_type}')
        self.stdout.write(f'  Username: {message.username}')
        self.stdout.write(f'  Content: "{message.content}"')
        self.stdout.write(f'  Created: {message.created_at}')

        # Check Redis
        room_id = str(message.chat_room.id)
        redis_messages = MessageCache.get_messages(room_id, limit=500)
        redis_msg = next((msg for msg in redis_messages if msg['id'] == str(message_id)), None)

        self.stdout.write('\nRedis:')
        if redis_msg:
            self.stdout.write(f'  ✓ Found in room:{room_id}:messages')
            self.stdout.write('  Serialized data:')
            self.stdout.write('    ' + json.dumps(redis_msg, indent=4).replace('\n', '\n    '))
        else:
            self.stdout.write(self.style.WARNING('  ✗ Not found in Redis cache'))

        self.stdout.write('')

    def clear_cache(self, chat_room, force=False):
        """Clear Redis cache for a chat"""
        room_id = str(chat_room.id)
        redis_client = MessageCache._get_redis_client()

        # Count messages
        keys = [
            MessageCache.MESSAGES_KEY.format(room_id=room_id),
            MessageCache.PINNED_ORDER_KEY.format(room_id=room_id),
        ]

        counts = {key: redis_client.zcard(key) for key in keys}

        if not force:
            self.stdout.write(self.style.WARNING(f'\n⚠️  About to clear Redis cache for chat {chat_room.host.reserved_username}/{chat_room.code}:'))
            for key, count in counts.items():
                if count > 0:
                    self.stdout.write(f'  - {key} ({count} messages)')

            confirm = input('\nAre you sure? [y/N]: ')
            if confirm.lower() != 'y':
                self.stdout.write('Cancelled.')
                return

        # Clear cache
        MessageCache.clear_room_cache(room_id)

        self.stdout.write(self.style.SUCCESS(f'\n✓ Cleared {len([c for c in counts.values() if c > 0])} keys:'))
        for key, count in counts.items():
            if count > 0:
                self.stdout.write(f'  - {key} ({count} messages)')

        self.stdout.write('')

    def monitor_cache(self, chat_room):
        """Monitor cache in real-time"""
        room_id = str(chat_room.id)
        redis_client = MessageCache._get_redis_client()
        key = MessageCache.MESSAGES_KEY.format(room_id=room_id)

        self.stdout.write(self.style.SUCCESS(f'\n🔴 Monitoring {key} (Press Ctrl+C to stop)\n'))

        prev_count = 0

        try:
            while True:
                count = redis_client.zcard(key)
                ttl = redis_client.ttl(key)
                ttl_str = self._format_ttl(ttl)

                timestamp = datetime.now().strftime('%H:%M:%S')

                status = ''
                if count > prev_count:
                    status = self.style.SUCCESS(f'  ← NEW MESSAGE (+{count - prev_count})')
                elif count < prev_count:
                    status = self.style.WARNING(f'  ← DELETED (-{prev_count - count})')

                self.stdout.write(f'{timestamp} | {count} messages | TTL: {ttl_str}{status}')

                prev_count = count
                time.sleep(2)

        except KeyboardInterrupt:
            self.stdout.write('\n\nMonitoring stopped.')

    def show_stats(self):
        """Show overall Redis statistics"""
        redis_client = MessageCache._get_redis_client()

        self.stdout.write(self.style.SUCCESS('\n📊 Redis Statistics:\n'))

        # Count all keys
        total_message_keys = 0
        total_pinned_keys = 0
        total_messages = 0
        total_reaction_keys = 0

        chats = ChatRoom.objects.filter(is_active=True)

        for chat in chats:
            room_id = str(chat.id)
            msg_count = redis_client.zcard(MessageCache.MESSAGES_KEY.format(room_id=room_id))
            pin_count = redis_client.zcard(MessageCache.PINNED_ORDER_KEY.format(room_id=room_id))
            reaction_pattern = f"room:{room_id}:reactions:*"
            reaction_keys = redis_client.keys(reaction_pattern)

            if msg_count > 0:
                total_message_keys += 1
                total_messages += msg_count
            if pin_count > 0:
                total_pinned_keys += 1
            total_reaction_keys += len(reaction_keys)

        self.stdout.write(f'Total chats cached:     {total_message_keys}')
        self.stdout.write(f'Total messages cached:  {total_messages}')
        self.stdout.write(f'Pinned message caches:  {total_pinned_keys}')
        self.stdout.write(f'Reaction caches:        {total_reaction_keys}')
        self.stdout.write('')

    def _format_ttl(self, ttl_seconds):
        """Format TTL in human-readable form"""
        if ttl_seconds < 0:
            return 'No expiry'

        hours = ttl_seconds // 3600
        minutes = (ttl_seconds % 3600) // 60

        if hours > 0:
            return f'{hours}h {minutes}m'
        else:
            return f'{minutes}m'
