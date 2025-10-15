"""
Username generation utility for suggesting random usernames.
"""

import random

from accounts.models import User
from chats.models import ChatParticipation
from .words import ADJECTIVES, NOUNS
from .validators import validate_username, is_username_globally_available
from django.conf import settings
from django.core.cache import cache
from constance import config


def generate_username(fingerprint, chat_code=None, max_attempts=None):
    """
    Generate a random globally-unique username with fingerprint-based rate limiting.

    IMPORTANT: This function implements the Global Username System with:
    - Globally unique usernames (checked across all chats and reserved usernames)
    - Fingerprint-based rate limiting (10 attempts per hour by default)
    - Redis tracking of generated usernames per fingerprint
    - API bypass prevention (tracks which usernames were generated for this fingerprint)

    Args:
        fingerprint: Browser fingerprint for rate limiting and tracking (required)
        chat_code: The chat room code (optional - used for chat-specific suggestion caching)
        max_attempts: Maximum generation attempts (defaults to Constance config value)

    Returns:
        tuple: (username, remaining_attempts) where:
            - username: str or None (valid username if successful, None if rate limit hit or generation failed)
            - remaining_attempts: int (number of attempts left for this fingerprint in current hour)

    Examples:
        >>> generate_username("abc123", "CHATCODE")
        ("HappyTiger42", 9)  # Success, 9 attempts remaining

        >>> generate_username("abc123")  # Rate limit exceeded
        (None, 0)  # Failed, no attempts remaining
    """
    # Get max attempts from Constance config (default: 10)
    if max_attempts is None:
        max_attempts = config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL

    # Redis key patterns
    attempts_key = f"username:generation_attempts:{fingerprint}"
    generated_key = f"username:generated_for_fingerprint:{fingerprint}"  # Global tracking (for API bypass prevention)
    generated_per_chat_key = f"username:generated_for_chat:{chat_code}:{fingerprint}" if chat_code else None  # Per-chat tracking (for rotation)
    cache_ttl = int(config.USERNAME_RESERVATION_TTL_MINUTES * 60)  # Convert minutes to seconds

    # Check current attempt count
    current_attempts = cache.get(attempts_key, 0)
    remaining_attempts = max(0, max_attempts - current_attempts)

    # Rate limit check
    if current_attempts >= max_attempts:
        return (None, 0)

    # Increment attempt counter
    cache.set(attempts_key, current_attempts + 1, cache_ttl)
    remaining_attempts = max(0, max_attempts - (current_attempts + 1))

    # Get set of usernames already generated for this fingerprint (for API bypass prevention)
    generated_usernames = cache.get(generated_key, set())

    # Chat-specific suggestion cache (prevents immediate re-suggestions within same chat)
    use_chat_cache = chat_code is not None
    chat_cache_key = f"chat:{chat_code}:recent_suggestions" if use_chat_cache else None
    chat_cache_ttl = 1800  # 30 minutes

    # Try to generate a username
    internal_max_attempts = 100  # Internal retry limit (doesn't count toward user limit)
    for attempt in range(internal_max_attempts):
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

        # STEP 2: Check chat-specific cache for recent suggestions (only if chat_code provided)
        if use_chat_cache:
            recent_suggestions = cache.get(chat_cache_key, set())
            if username.lower() in recent_suggestions:
                continue
        else:
            recent_suggestions = None

        # STEP 3: Check global availability (uses indexed queries for performance)
        if not is_username_globally_available(username):
            continue

        # Valid username found! Track it and update caches
        # STEP 4: Reserve username globally to prevent race conditions
        # This prevents two users from getting the same username simultaneously
        reservation_key = f"username:reserved:{username.lower()}"
        cache.set(reservation_key, True, cache_ttl)  # 1 hour TTL (same as fingerprint tracking)

        # Add to fingerprint's generated usernames set (for API bypass prevention)
        # Store original capitalization (e.g., "HappyTiger42" not "happytiger42")
        generated_usernames.add(username)
        cache.set(generated_key, generated_usernames, cache_ttl)

        # ALSO add to per-chat tracking (if chat_code provided) for rotation
        if generated_per_chat_key:
            generated_per_chat = cache.get(generated_per_chat_key, set())
            generated_per_chat.add(username)
            cache.set(generated_per_chat_key, generated_per_chat, cache_ttl)

        # Add to chat-specific cache if using chat cache
        if use_chat_cache and recent_suggestions is not None:
            recent_suggestions.add(username.lower())
            cache.set(chat_cache_key, recent_suggestions, chat_cache_ttl)

            # Trim cache if it gets too large (keep last 1000)
            if len(recent_suggestions) > 1000:
                # Convert to list, keep last 800, convert back to set
                suggestions_list = list(recent_suggestions)
                recent_suggestions = set(suggestions_list[-800:])
                cache.set(chat_cache_key, recent_suggestions, chat_cache_ttl)

        return (username, remaining_attempts)

    # Fallback: If all attempts failed, try Guest with random number
    for i in range(10):
        guest_username = f"Guest{random.randint(10000, 99999)}"
        try:
            validate_username(guest_username)
            # Check global availability
            if is_username_globally_available(guest_username):
                # Reserve username globally
                reservation_key = f"username:reserved:{guest_username.lower()}"
                cache.set(reservation_key, True, cache_ttl)

                # Track it (preserve original capitalization)
                generated_usernames.add(guest_username)
                cache.set(generated_key, generated_usernames, cache_ttl)

                # ALSO add to per-chat tracking (if chat_code provided)
                if generated_per_chat_key:
                    generated_per_chat = cache.get(generated_per_chat_key, set())
                    generated_per_chat.add(guest_username)
                    cache.set(generated_per_chat_key, generated_per_chat, cache_ttl)

                return (guest_username, remaining_attempts)
        except Exception:
            continue

    # Complete failure
    return (None, remaining_attempts)
