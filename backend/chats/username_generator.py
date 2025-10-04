"""
Username generation utility for suggesting random usernames.
"""

import random

from accounts.models import User
from chats.models import ChatParticipation
from chats.username_words import ADJECTIVES, NOUNS
from chats.validators import validate_username
from django.conf import settings
from django.core.cache import cache


def generate_username(chat_code=None, max_attempts=100):
    """
    Generate a random username that is:
    - Valid according to validate_username
    - Not reserved by any user
    - Not taken in the specified chat (if chat_code provided)
    - Not recently suggested for this chat (if chat_code provided)

    Args:
        chat_code: The chat room code (optional - if None, skips chat-specific checks)
        max_attempts: Maximum number of generation attempts

    Returns:
        str: A valid username, or None if generation failed
    """
    # Only use cache if chat_code is provided
    use_cache = chat_code is not None
    redis_key = f"chat:{chat_code}:recent_suggestions" if use_cache else None
    cache_ttl = 1800  # 30 minutes

    for attempt in range(max_attempts):
        # Generate username: Adjective + Noun + Number
        adj = random.choice(ADJECTIVES)
        noun = random.choice(NOUNS)

        # Start with 1-999 range, expand if needed
        if attempt < 50:
            number = random.randint(1, 999)
        elif attempt < 80:
            number = random.randint(1000, 9999)
        else:
            number = random.randint(10000, 99999)

        username = f"{adj}{noun}{number}"

        # STEP 1: Validate username format (MUST pass validator), but skip badwords check
        try:
            validate_username(username, skip_badwords_check=True)
        except Exception:
            continue  # Try another combination, don't count toward user limit

        # STEP 2: Check Redis cache for recent suggestions (only if chat_code provided)
        if use_cache:
            recent_suggestions = cache.get(redis_key, set())
            if username.lower() in recent_suggestions:
                continue
        else:
            recent_suggestions = None

        # STEP 3: Check if reserved by any user (database)
        if User.objects.filter(reserved_username__iexact=username).exists():
            continue

        # STEP 4: Check if taken in this chat (only if chat_code provided)
        if chat_code and ChatParticipation.objects.filter(chat_room__code=chat_code, username__iexact=username).exists():
            continue

        # Valid username found! Add to cache if using cache
        if use_cache and recent_suggestions is not None:
            recent_suggestions.add(username.lower())
            cache.set(redis_key, recent_suggestions, cache_ttl)

            # Trim cache if it gets too large (keep last 1000)
            if len(recent_suggestions) > 1000:
                # Convert to list, keep last 800, convert back to set
                suggestions_list = list(recent_suggestions)
                recent_suggestions = set(suggestions_list[-800:])
                cache.set(redis_key, recent_suggestions, cache_ttl)

        return username

    # Fallback: If all attempts failed, try Guest with random number
    for i in range(10):
        guest_username = f"Guest{random.randint(10000, 99999)}"
        try:
            validate_username(guest_username)
            # Check if available
            if not User.objects.filter(reserved_username__iexact=guest_username).exists():
                # Only check chat participation if chat_code provided
                if chat_code:
                    if ChatParticipation.objects.filter(
                        chat_room__code=chat_code, username__iexact=guest_username
                    ).exists():
                        continue
                return guest_username
        except Exception:
            continue

    # Complete failure
    return None
