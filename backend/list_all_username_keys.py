#!/usr/bin/env python
"""
List ALL Redis keys related to username generation/reservation.

Usage:
    DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python list_all_username_keys.py
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatpop.settings')
django.setup()

from django.core.cache import cache
from django_redis import get_redis_connection

# Get connection to the correct database (database 1 per settings.py line 208)
redis_conn = get_redis_connection("default")

print("\n" + "="*80)
print("ALL USERNAME-RELATED REDIS KEYS")
print("="*80 + "\n")

# Define patterns to search for
patterns = [
    'username:*',
    'chat:*:recent_suggestions',
    'username_suggest_limit:*',
]

all_keys = []

for pattern in patterns:
    print(f"Searching for pattern: {pattern}")
    cursor = 0
    pattern_keys = []
    while True:
        cursor, keys = redis_conn.scan(cursor, match=pattern, count=100)
        pattern_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        if cursor == 0:
            break

    print(f"  Found {len(pattern_keys)} key(s)\n")

    if pattern_keys:
        for key in sorted(pattern_keys):
            ttl = cache.ttl(key) if hasattr(cache, 'ttl') else None
            if ttl is not None:
                print(f"    {key}")
                print(f"      TTL: {ttl} seconds ({ttl // 60} minutes remaining)")
            else:
                print(f"    {key}")
            print()

    all_keys.extend(pattern_keys)

print(f"\n{'='*80}")
print(f"TOTAL: {len(all_keys)} key(s) found")
print(f"{'='*80}\n")
