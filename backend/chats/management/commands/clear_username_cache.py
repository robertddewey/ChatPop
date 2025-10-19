"""
Django management command to clear all username-related Redis keys.

Usage:
    python manage.py clear_username_cache
"""
from django.core.management.base import BaseCommand
from django_redis import get_redis_connection


class Command(BaseCommand):
    help = """Clear all username-related Redis keys.

    This removes all keys used for username generation tracking:
    - username:generated_for_fingerprint:* (fingerprint tracking)
    - username:reserved:* (global reservations)
    - username:generation_attempts:* (attempt counters)
    - chat:*:recent_suggestions (chat-specific suggestions)
    - username_suggest_limit:* (per-chat limits)
    - username:rotation_index:* (rotation tracking)
    """

    def handle(self, *args, **options):
        """Clear all username-related Redis keys"""

        # Get Redis connection
        redis_client = get_redis_connection("default")

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.WARNING("CLEARING ALL USERNAME-RELATED REDIS KEYS"))
        self.stdout.write("=" * 80)
        self.stdout.write("")

        # Define key patterns to clear
        patterns = [
            'username:generated_for_fingerprint:*',
            'username:reserved:*',
            'username:generation_attempts:*',
            'chat:*:recent_suggestions',
            'username_suggest_limit:*',
            'username:rotation_index:*',
        ]

        total_deleted = 0

        for pattern in patterns:
            self.stdout.write(f"Searching for pattern: {pattern}")
            keys = list(redis_client.scan_iter(match=pattern, count=100))

            if keys:
                deleted = redis_client.delete(*keys)
                total_deleted += deleted
                self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {deleted} key(s)"))
            else:
                self.stdout.write("  - No keys found")
            self.stdout.write("")

        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS(f"TOTAL KEYS DELETED: {total_deleted}"))
        self.stdout.write("=" * 80)
        self.stdout.write("")
        self.stdout.write("All username generation tracking has been reset.")
        self.stdout.write("Users can now generate usernames with fresh rate limits.")
