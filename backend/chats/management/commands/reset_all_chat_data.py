"""Management command to reset all chat messages, gifts, transactions, and Redis cache."""

from django.core.management.base import BaseCommand
from django_redis import get_redis_connection


class Command(BaseCommand):
    help = 'Reset all chat messages, gifts, transactions, reactions, and Redis cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(self.style.WARNING(
                'This will DELETE all messages, gifts, transactions, reactions, and flush Redis.'
            ))
            confirm = input('Type "yes" to confirm: ')
            if confirm != 'yes':
                self.stdout.write('Aborted.')
                return

        # Flush Redis
        try:
            redis_client = get_redis_connection("default")
            redis_client.flushdb()
            self.stdout.write(self.style.SUCCESS('Redis cache flushed'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Redis flush failed: {e}'))

        # Delete in dependency order
        from chats.models import MessageReaction, Gift, Transaction, Message

        counts = {}
        counts['reactions'] = MessageReaction.objects.all().delete()[0]
        counts['gifts'] = Gift.objects.all().delete()[0]
        counts['transactions'] = Transaction.objects.all().delete()[0]
        counts['messages'] = Message.objects.all().delete()[0]

        for name, count in counts.items():
            self.stdout.write(f'  Deleted {count} {name}')

        self.stdout.write(self.style.SUCCESS('All chat data reset successfully'))
