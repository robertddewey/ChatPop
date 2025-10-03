"""
Username generation utility for suggesting random usernames.
"""
import random
from django.core.cache import cache
from django.conf import settings
from accounts.models import User
from chats.models import ChatParticipation
from chats.validators import validate_username
from chats.username_words import ADJECTIVES, NOUNS


def generate_username(chat_code, max_attempts=100):
    """
    Generate a random username that is:
    - Valid according to validate_username
    - Not reserved by any user
    - Not taken in the specified chat
    - Not recently suggested for this chat

    Args:
        chat_code: The chat room code
        max_attempts: Maximum number of generation attempts

    Returns:
        str: A valid username, or None if generation failed
    """
    redis_key = f"chat:{chat_code}:recent_suggestions"

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

        # STEP 2: Check Redis cache for recent suggestions (O(1) lookup)
        recent_suggestions = cache.get(redis_key, set())
        if username.lower() in recent_suggestions:
            continue

        # STEP 3: Check if reserved by any user (database)
        if User.objects.filter(reserved_username__iexact=username).exists():
            continue

        # STEP 4: Check if taken in this chat (database)
        if ChatParticipation.objects.filter(
            chat_room__code=chat_code,
            username__iexact=username
        ).exists():
            continue

        # Valid username found! Add to cache and return
        recent_suggestions.add(username.lower())
        cache.set(redis_key, recent_suggestions, 3600)  # 1 hour TTL

        # Trim cache if it gets too large (keep last 1000)
        if len(recent_suggestions) > 1000:
            # Convert to list, keep last 800, convert back to set
            suggestions_list = list(recent_suggestions)
            recent_suggestions = set(suggestions_list[-800:])
            cache.set(redis_key, recent_suggestions, 3600)

        return username

    # Fallback: If all attempts failed, try Guest with random number
    for i in range(10):
        guest_username = f"Guest{random.randint(10000, 99999)}"
        try:
            validate_username(guest_username)
            # Check if available
            if not User.objects.filter(reserved_username__iexact=guest_username).exists():
                if not ChatParticipation.objects.filter(
                    chat_room__code=chat_code,
                    username__iexact=guest_username
                ).exists():
                    return guest_username
        except Exception:
            continue

    # Complete failure
    return None
