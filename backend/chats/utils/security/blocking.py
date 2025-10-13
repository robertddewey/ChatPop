"""
Utility functions for user blocking in chats.
"""
from django.utils import timezone
from django.db.models import Q
from chats.models import ChatBlock, ChatRoom, ChatParticipation
from django.contrib.auth import get_user_model

User = get_user_model()


def block_participation(chat_room, participation, blocked_by):
    """
    Block a user across all their identifiers.
    Creates multiple ChatBlock records to cover username, fingerprint, and user account.

    Args:
        chat_room: ChatRoom instance
        participation: ChatParticipation to block
        blocked_by: ChatParticipation of blocker (usually host)

    Returns:
        List of created ChatBlock instances

    Raises:
        ValueError: If trying to block oneself or if blocked_by is not host
    """
    # Prevent self-blocking (check if it's the exact same participation)
    if blocked_by.id == participation.id:
        raise ValueError("Cannot block yourself")

    # Also prevent blocking if it's the same user account
    if blocked_by.user and participation.user and blocked_by.user == participation.user:
        raise ValueError("Cannot block yourself")

    # Verify that blocker is the host
    if chat_room.host != blocked_by.user:
        raise ValueError("Only the host can block users")

    blocks_created = []

    # Block username (case-insensitive)
    if participation.username:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_username=participation.username.lower(),
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    # Block fingerprint ONLY for anonymous users (prevents them from rejoining with new username)
    # Don't block fingerprint for logged-in users (they're already blocked by user account)
    if participation.fingerprint and not participation.user:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_fingerprint=participation.fingerprint,
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    # Block user account (logged-in users)
    if participation.user:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_user=participation.user,
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    return blocks_created


def check_if_blocked(chat_room, username=None, fingerprint=None, user=None, email=None, phone=None):
    """
    Check if user is blocked from this chat.

    Args:
        chat_room: ChatRoom instance
        username: Username to check (optional)
        fingerprint: Browser fingerprint to check (optional)
        user: User instance to check (optional)
        email: Email to check (optional, future)
        phone: Phone to check (optional, future)

    Returns:
        (is_blocked: bool, error_message: str|None)
    """
    blocks = ChatBlock.objects.filter(chat_room=chat_room)

    # Check for expired blocks
    now = timezone.now()
    blocks = blocks.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    # Check username (case-insensitive)
    if username and blocks.filter(blocked_username__iexact=username).exists():
        return True, "You have been blocked from this chat."

    # Check fingerprint ONLY for anonymous users (logged-in users bypass fingerprint blocks)
    # Fingerprint blocks are only created for anonymous users, so only check for anonymous access
    if fingerprint and not user and blocks.filter(blocked_fingerprint=fingerprint).exists():
        return True, "You have been blocked from this chat."

    # Check user account
    if user and blocks.filter(blocked_user=user).exists():
        return True, "You have been blocked from this chat."

    # Check email (future)
    if email and blocks.filter(blocked_email__iexact=email).exists():
        return True, "You have been blocked from this chat."

    # Check phone (future)
    if phone and blocks.filter(blocked_phone=phone).exists():
        return True, "You have been blocked from this chat."

    return False, None


def unblock_participation(chat_room, participation):
    """
    Unblock a user by removing all their ChatBlock records.

    Args:
        chat_room: ChatRoom instance
        participation: ChatParticipation to unblock

    Returns:
        int: Count of deleted blocks
    """
    blocks_to_delete = ChatBlock.objects.filter(chat_room=chat_room)

    # Build a query to match all blocks for this participation
    query = Q()

    if participation.username:
        query |= Q(blocked_username__iexact=participation.username)

    if participation.fingerprint:
        query |= Q(blocked_fingerprint=participation.fingerprint)

    if participation.user:
        query |= Q(blocked_user=participation.user)

    blocks_to_delete = blocks_to_delete.filter(query)
    count = blocks_to_delete.count()
    blocks_to_delete.delete()

    return count


def get_blocked_users(chat_room):
    """
    Get all active blocks for a chat room.

    Args:
        chat_room: ChatRoom instance

    Returns:
        List of dict with blocked user information
    """
    blocks = ChatBlock.objects.filter(chat_room=chat_room)

    # Filter out expired blocks
    now = timezone.now()
    blocks = blocks.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    # Group blocks by the actual values being blocked
    # We group blocks that share at least one identifier (username, fingerprint, or user)
    blocked_users_map = {}

    for block in blocks.select_related('blocked_user'):
        # Create a unique grouping key based on the blocked values
        # Priority: username > user_id > fingerprint
        key = None
        if block.blocked_username:
            key = f"u:{block.blocked_username.lower()}"
        elif block.blocked_user_id:
            key = f"uid:{block.blocked_user_id}"
        elif block.blocked_fingerprint:
            key = f"fp:{block.blocked_fingerprint}"

        if not key:
            continue  # Skip blocks with no identifiers

        # If this key doesn't exist yet, create a new entry
        if key not in blocked_users_map:
            blocked_users_map[key] = {
                'username': block.blocked_username or (block.blocked_user.reserved_username if block.blocked_user else None),
                'blocked_at': block.blocked_at,
                'reason': block.reason,
                'blocked_identifiers': [],
                'expires_at': block.expires_at,
                '_seen_fingerprints': set(),  # Track fingerprints we've seen for this user
            }

        # Update username if we find a more complete one
        if block.blocked_username and not blocked_users_map[key]['username']:
            blocked_users_map[key]['username'] = block.blocked_username

        # Add identifier types (avoid duplicates)
        if block.blocked_username and 'username' not in blocked_users_map[key]['blocked_identifiers']:
            blocked_users_map[key]['blocked_identifiers'].append('username')
        if block.blocked_fingerprint:
            # Only add fingerprint identifier once, even if we see it multiple times
            if block.blocked_fingerprint not in blocked_users_map[key]['_seen_fingerprints']:
                blocked_users_map[key]['_seen_fingerprints'].add(block.blocked_fingerprint)
                if 'fingerprint' not in blocked_users_map[key]['blocked_identifiers']:
                    blocked_users_map[key]['blocked_identifiers'].append('fingerprint')
        if block.blocked_user and 'user_account' not in blocked_users_map[key]['blocked_identifiers']:
            blocked_users_map[key]['blocked_identifiers'].append('user_account')

    # Remove temporary tracking fields
    result = []
    for user_data in blocked_users_map.values():
        user_data.pop('_seen_fingerprints', None)
        result.append(user_data)

    return result
