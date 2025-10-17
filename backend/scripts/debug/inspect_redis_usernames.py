#!/usr/bin/env python
"""
Inspect Redis username data for a specific chat.

Usage:
    DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python inspect_redis_usernames.py REWO30UI
"""

import sys
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatpop.settings')
django.setup()

from django.core.cache import cache
from constance import config as constance_config


def inspect_chat_username_data(chat_code):
    """Inspect all username-related Redis data for a chat."""

    print(f"\n{'='*80}")
    print(f"Redis Username Data for Chat: {chat_code}")
    print(f"{'='*80}\n")

    # Get Constance config values
    print("Configuration:")
    print(f"  USERNAME_RESERVATION_TTL_MINUTES: {constance_config.USERNAME_RESERVATION_TTL_MINUTES}")
    print(f"  MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL: {constance_config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL}")
    print(f"  MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT: {constance_config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT}")
    print()

    # 1. Chat-specific recent suggestions cache
    print(f"\n{'─'*80}")
    print("1. CHAT-SPECIFIC RECENT SUGGESTIONS")
    print(f"{'─'*80}")
    chat_cache_key = f"chat:{chat_code}:recent_suggestions"
    recent_suggestions = cache.get(chat_cache_key, set())
    print(f"  Key: {chat_cache_key}")
    print(f"  TTL: 30 minutes (1800 seconds)")
    ttl = cache.ttl(chat_cache_key) if hasattr(cache, 'ttl') else None
    if ttl is not None:
        print(f"  Remaining TTL: {ttl} seconds ({ttl // 60} minutes)")
    print(f"  Count: {len(recent_suggestions)}")
    if recent_suggestions:
        print(f"  Usernames: {sorted(list(recent_suggestions))}")
    else:
        print(f"  Usernames: (none)")

    # 2. Find all fingerprints that have generated usernames
    # We need to scan for keys matching username:generated_for_fingerprint:*
    print(f"\n{'─'*80}")
    print("2. FINGERPRINTS WITH GENERATED USERNAMES")
    print(f"{'─'*80}")

    # Get all keys that match the pattern (this requires Redis client access)
    # Since Django cache doesn't expose SCAN, we'll use the underlying Redis client
    from django_redis import get_redis_connection
    redis_conn = get_redis_connection("default")

    fingerprint_keys = []
    cursor = 0
    while True:
        cursor, keys = redis_conn.scan(cursor, match='username:generated_for_fingerprint:*', count=100)
        fingerprint_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        if cursor == 0:
            break

    print(f"  Found {len(fingerprint_keys)} fingerprint(s) with generated usernames\n")

    for fp_key in sorted(fingerprint_keys):
        fingerprint = fp_key.split(':')[-1]
        print(f"  Fingerprint: {fingerprint}")
        print(f"  ─────────────────────────────────────────────────")

        # Get generated usernames for this fingerprint
        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
        generated_usernames = cache.get(generated_key, set())
        ttl = cache.ttl(generated_key) if hasattr(cache, 'ttl') else None

        print(f"    Key: {generated_key}")
        if ttl is not None:
            print(f"    TTL: {ttl} seconds ({ttl // 60} minutes remaining)")
        print(f"    Usernames generated: {len(generated_usernames)}")
        if generated_usernames:
            print(f"    Usernames: {sorted(list(generated_usernames))}")

        # Get generation attempts count
        attempts_key = f"username:generation_attempts:{fingerprint}"
        attempts = cache.get(attempts_key, 0)
        attempts_ttl = cache.ttl(attempts_key) if hasattr(cache, 'ttl') else None
        print(f"\n    Generation attempts: {attempts}/{constance_config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL}")
        if attempts_ttl is not None:
            print(f"    Attempts TTL: {attempts_ttl} seconds ({attempts_ttl // 60} minutes remaining)")

        # Get per-chat rate limit for this fingerprint
        rate_limit_key = f"username_suggest_limit:{chat_code}:{fingerprint}"
        chat_attempts = cache.get(rate_limit_key, 0)
        chat_ttl = cache.ttl(rate_limit_key) if hasattr(cache, 'ttl') else None
        print(f"\n    Per-chat suggestions: {chat_attempts}/{constance_config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT}")
        if chat_ttl is not None:
            print(f"    Per-chat TTL: {chat_ttl} seconds ({chat_ttl // 60} minutes remaining)")

        # Get rotation index
        rotation_key = f"username:rotation_index:{fingerprint}"
        rotation_index = cache.get(rotation_key, 0)
        rotation_ttl = cache.ttl(rotation_key) if hasattr(cache, 'ttl') else None
        if rotation_index > 0 or rotation_ttl:
            print(f"\n    Rotation index: {rotation_index}")
            if rotation_ttl is not None:
                print(f"    Rotation TTL: {rotation_ttl} seconds ({rotation_ttl // 60} minutes remaining)")

        print()

    # 3. Reserved usernames
    print(f"\n{'─'*80}")
    print("3. RESERVED USERNAMES (Global)")
    print(f"{'─'*80}")

    # Scan for reserved username keys
    reserved_keys = []
    cursor = 0
    while True:
        cursor, keys = redis_conn.scan(cursor, match='username:reserved:*', count=100)
        reserved_keys.extend([key.decode() if isinstance(key, bytes) else key for key in keys])
        if cursor == 0:
            break

    print(f"  Found {len(reserved_keys)} reserved username(s)\n")

    for res_key in sorted(reserved_keys)[:20]:  # Show first 20
        username = res_key.split(':')[-1]
        ttl = cache.ttl(res_key) if hasattr(cache, 'ttl') else None
        print(f"    Username: {username}")
        if ttl is not None:
            print(f"      TTL: {ttl} seconds ({ttl // 60} minutes remaining)")

    if len(reserved_keys) > 20:
        print(f"\n    ... and {len(reserved_keys) - 20} more")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python inspect_redis_usernames.py <chat_code>")
        sys.exit(1)

    chat_code = sys.argv[1]
    inspect_chat_username_data(chat_code)
