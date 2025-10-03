"""
Shared validators for chat application
"""
import re
from django.core.exceptions import ValidationError


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
            from chats.username_profanity_check import is_username_allowed
            result = is_username_allowed(value)
            if not result.allowed:
                raise ValidationError(f"Username not allowed: {result.reason}")
        except ImportError:
            # If profanity checker is not available, skip the check
            pass

    return value
