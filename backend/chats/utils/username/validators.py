"""
Shared validators for chat application
"""
import re
from django.core.exceptions import ValidationError
from django.db.models import Q


def validate_username(value, skip_badwords_check=False):
    """
    Validate username format for both reserved usernames and chat usernames.

    Rules:
    - Minimum length: 5 characters
    - Maximum length: 15 characters
    - Allowed characters: letters (a-z, A-Z), numbers (0-9), and underscores (_)
    - No spaces allowed
    - Case is preserved but doesn't count toward uniqueness
    - Optional profanity check (skipped for auto-generated usernames)
    """
    if not value:
        raise ValidationError("Username cannot be empty")

    # Strip whitespace
    value = value.strip()

    # Check minimum length
    if len(value) < 5:
        raise ValidationError("Username must be at least 5 characters long")

    # Check maximum length
    if len(value) > 15:
        raise ValidationError("Username must be at most 15 characters long")

    # Check allowed characters (letters, numbers, underscores only)
    if not re.match(r'^[a-zA-Z0-9_]+$', value):
        raise ValidationError("Username can only contain letters, numbers, and underscores (no spaces)")

    # Profanity check (only for user-chosen usernames)
    if not skip_badwords_check:
        try:
            from .profanity import is_username_allowed
            result = is_username_allowed(value)
            if not result.allowed:
                raise ValidationError(f"Username not allowed: {result.reason}")
        except ImportError:
            # If profanity checker is not available, skip the check
            pass

    return value


def is_username_globally_available(username):
    """
    Check if a username is available globally (across entire platform).

    A username is considered TAKEN if:
    - Reserved by any registered user (User.reserved_username)
    - Used in any chat room (ChatParticipation.username)
    - Temporarily reserved in Redis (pending registration/chat join)

    Args:
        username: The username to check (case-insensitive)

    Returns:
        bool: True if available, False if taken
    """
    # Avoid circular imports
    from accounts.models import User
    from chats.models import ChatParticipation
    from django.core.cache import cache

    username_lower = username.lower()

    # Check if reserved by any user
    if User.objects.filter(reserved_username__iexact=username_lower).exists():
        return False

    # Check if used in any chat (uses indexed query for performance)
    if ChatParticipation.objects.filter(username__iexact=username_lower).exists():
        return False

    # Check if temporarily reserved in Redis (prevents race conditions)
    reservation_key = f"username:reserved:{username_lower}"
    if cache.get(reservation_key):
        return False

    return True
