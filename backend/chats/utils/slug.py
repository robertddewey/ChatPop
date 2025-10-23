"""
Utility functions for generating URL-safe slugs from chat names.
"""
import re
from django.utils.text import slugify


def generate_chat_code(name: str, max_length: int = 100) -> str:
    """
    Generate a URL-safe code from a chat room name.

    Converts the name to lowercase, replaces spaces with hyphens,
    removes non-alphanumeric characters, and strips consecutive hyphens.

    Args:
        name: The chat room name (e.g., "My Awesome Bar Room!")
        max_length: Maximum length for the generated code (default: 100)

    Returns:
        URL-safe slug (e.g., "my-awesome-bar-room")

    Examples:
        >>> generate_chat_code("Bar Room")
        'bar-room'
        >>> generate_chat_code("Robert's Bar!!!")
        'roberts-bar'
        >>> generate_chat_code("My   Awesome  Room")
        'my-awesome-room'
        >>> generate_chat_code("  Coffee Shop  ")
        'coffee-shop'
    """
    if not name:
        return ""

    # Use Django's slugify for basic conversion
    # This handles: lowercase, spaces→hyphens, removes special chars
    slug = slugify(name)

    # Strip consecutive hyphens (slugify already does most of this, but be thorough)
    slug = re.sub(r'-+', '-', slug)

    # Strip leading/trailing hyphens
    slug = slug.strip('-')

    # Truncate to max_length
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip('-')

    return slug


def generate_unique_chat_code(name: str, host, source: str = 'manual', max_attempts: int = 100) -> str:
    """
    Generate a unique chat code, handling collisions by appending numbers.

    For manual rooms: checks uniqueness within the host's namespace
    For AI rooms: checks global uniqueness

    Args:
        name: The chat room name
        host: The User instance who is creating the room
        source: 'manual' or 'ai' (determines uniqueness scope)
        max_attempts: Maximum number of collision attempts (default: 100)

    Returns:
        Unique URL-safe slug

    Raises:
        ValueError: If unable to generate unique code after max_attempts

    Examples:
        - First "Bar Room" → "bar-room"
        - Second "Bar Room" by same user → "bar-room-2"
        - Third "Bar Room" by same user → "bar-room-3"
    """
    from chats.models import ChatRoom

    base_slug = generate_chat_code(name)

    if not base_slug:
        # Fallback if name generates empty slug
        base_slug = "chat-room"

    # Try base slug first
    slug = base_slug

    for attempt in range(max_attempts):
        # Check if slug is available
        if source == 'manual':
            # Manual rooms: check uniqueness within host's namespace
            exists = ChatRoom.objects.filter(
                host=host,
                code=slug,
                source='manual'
            ).exists()
        else:
            # AI rooms: check global uniqueness
            exists = ChatRoom.objects.filter(
                code=slug,
                source='ai'
            ).exists()

        if not exists:
            return slug

        # Collision detected, append number
        slug = f"{base_slug}-{attempt + 2}"

    # Failed to find unique slug after max_attempts
    raise ValueError(
        f"Unable to generate unique code for '{name}' after {max_attempts} attempts"
    )
