"""
Management command to sync all message reactions from PostgreSQL to Redis cache.

Usage:
    ./venv/bin/python manage.py sync_reaction_cache [--chat CHAT_CODE]

Examples:
    # Sync all chats
    ./venv/bin/python manage.py sync_reaction_cache

    # Sync specific chat
    ./venv/bin/python manage.py sync_reaction_cache --chat ABC123
"""

from django.core.management.base import BaseCommand
from chats.models import ChatRoom, Message, MessageReaction
from chats.utils.performance.cache import MessageCache
from collections import defaultdict


class Command(BaseCommand):
    help = 'Sync message reactions from PostgreSQL to Redis cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chat',
            type=str,
            help='Specific chat code to sync (optional, syncs all chats if omitted)',
        )

    def handle(self, *args, **options):
        chat_code = options.get('chat')

        if chat_code:
            # Sync specific chat
            try:
                chat_room = ChatRoom.objects.get(code=chat_code)
                self.sync_chat(chat_room)
            except ChatRoom.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Chat not found: {chat_code}'))
                return
        else:
            # Sync all chats
            chats = ChatRoom.objects.filter(is_active=True)
            total = chats.count()
            self.stdout.write(f'Syncing reactions for {total} active chats...\n')

            for i, chat_room in enumerate(chats, 1):
                self.stdout.write(f'[{i}/{total}] {chat_room.code} ({chat_room.name})')
                self.sync_chat(chat_room)

            self.stdout.write(self.style.SUCCESS(f'\n✓ Synced reactions for {total} chats'))

    def sync_chat(self, chat_room):
        """Sync reactions for a single chat"""
        # Get all messages with reactions in this chat
        messages = Message.objects.filter(
            chat_room=chat_room,
            reactions__isnull=False
        ).distinct()

        message_count = messages.count()
        if message_count == 0:
            self.stdout.write('  No reactions to sync')
            return

        synced = 0
        failed = 0

        for msg in messages:
            reactions_list = MessageReaction.objects.filter(message=msg)
            emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0, 'users': []})

            for reaction in reactions_list:
                emoji = reaction.emoji
                emoji_counts[emoji]['emoji'] = emoji
                emoji_counts[emoji]['count'] += 1
                emoji_counts[emoji]['users'].append(reaction.username)

            # Get top 3 reactions by count
            top_reactions = sorted(emoji_counts.values(), key=lambda x: x['count'], reverse=True)[:3]

            # Cache them
            success = MessageCache.set_message_reactions(chat_room.code, str(msg.id), top_reactions)

            if success:
                synced += 1
            else:
                failed += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Failed to cache reactions for message {msg.id}'))

        if failed == 0:
            self.stdout.write(self.style.SUCCESS(f'  ✓ Synced {synced} messages with reactions'))
        else:
            self.stdout.write(self.style.WARNING(f'  ⚠ Synced {synced} messages, failed {failed}'))
