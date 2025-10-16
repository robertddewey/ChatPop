#!/usr/bin/env python
"""
Clear all username-related Redis keys.

This script removes all keys used for username generation tracking:
- username:generated_for_fingerprint:* (fingerprint tracking)
- username:reserved:* (global reservations)
- username:generation_attempts:* (attempt counters)
- chat:*:recent_suggestions (chat-specific suggestions)
- username_suggest_limit:* (per-chat limits)
- username:rotation_index:* (rotation tracking)
"""

import os
import sys
import django
import redis

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatpop.settings')
django.setup()

from django.core.cache import cache


def clear_username_keys():
    """Clear all username-related Redis keys"""

    # Get the Redis client from Django cache backend
    redis_client = cache._cache.get_client()

    print("=" * 80)
    print("CLEARING ALL USERNAME-RELATED REDIS KEYS")
    print("=" * 80)
    print()

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
        print(f"Searching for pattern: {pattern}")
        keys = list(redis_client.scan_iter(match=pattern, count=100))

        if keys:
            deleted = redis_client.delete(*keys)
            total_deleted += deleted
            print(f"  ✓ Deleted {deleted} key(s)")
        else:
            print(f"  - No keys found")
        print()

    print("=" * 80)
    print(f"TOTAL KEYS DELETED: {total_deleted}")
    print("=" * 80)
    print()
    print("All username generation tracking has been reset.")
    print("Users can now generate usernames with fresh rate limits.")


if __name__ == '__main__':
    clear_username_keys()
