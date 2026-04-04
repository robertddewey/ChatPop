"""
Utility functions for user blocking in chats.
"""
from django.utils import timezone
from django.db.models import Q
from chats.models import ChatBlock, ChatRoom, ChatParticipation
from django.contrib.auth import get_user_model

User = get_user_model()


def block_participation(chat_room, participation, blocked_by, ip_address=None, ban_tier='session'):
    """
    Block a user with the specified ban tier.
    Creates a SINGLE consolidated ChatBlock record with identifiers appropriate to the tier.

    Args:
        chat_room: ChatRoom instance
        participation: ChatParticipation to block
        blocked_by: ChatParticipation of blocker (usually host)
        ip_address: Optional IP address
        ban_tier: 'session' (default), 'fingerprint_ip', or 'ip'

    Returns:
        ChatBlock instance

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

    # Check if this user is already blocked (by any identifier)
    # If they are, update the existing block to include all identifiers
    existing_block = None

    # Check for existing block by username
    if participation.username:
        existing_block = ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_username__iexact=participation.username
        ).first()

    # Check for existing block by fingerprint (if not found by username)
    if not existing_block and participation.fingerprint:
        existing_block = ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_fingerprint=participation.fingerprint
        ).first()

    # Check for existing block by user account (if not found yet)
    if not existing_block and participation.user:
        existing_block = ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_user=participation.user
        ).first()

    if existing_block:
        # Update existing block with all identifiers and new tier
        if participation.username:
            existing_block.blocked_username = participation.username.lower()
        if participation.fingerprint:
            existing_block.blocked_fingerprint = participation.fingerprint
        if participation.session_key:
            existing_block.blocked_session_key = participation.session_key
        if participation.user:
            existing_block.blocked_user = participation.user
        if ip_address:
            existing_block.blocked_ip_address = ip_address
        existing_block.ban_tier = ban_tier
        existing_block.save()
        return existing_block
    else:
        # Create new consolidated block with identifiers and tier
        block = ChatBlock.objects.create(
            chat_room=chat_room,
            blocked_username=participation.username.lower() if participation.username else None,
            blocked_fingerprint=participation.fingerprint,
            blocked_session_key=participation.session_key,
            blocked_user=participation.user,
            blocked_ip_address=ip_address,
            blocked_by=blocked_by,
            ban_tier=ban_tier
        )
        return block


def check_if_blocked(chat_room, username=None, fingerprint=None, session_key=None, user=None, ip_address=None):
    """
    Check if user is blocked from this chat using tiered ban enforcement.
    Host of the chat is always exempt from all bans.

    Ban tiers:
    - session: matches blocked_session_key only (clearable by clearing cookies)
    - fingerprint_ip: matches blocked_fingerprint AND blocked_ip_address
    - ip: matches blocked_ip_address only (blocks everyone on that IP)

    Username and user account blocks always apply regardless of tier.

    Returns:
        (is_blocked: bool, error_message: str|None)
    """
    # Host exemption: host is never blocked from their own chat
    if user and hasattr(chat_room, 'host') and chat_room.host == user:
        return False, None

    blocks = ChatBlock.objects.filter(chat_room=chat_room)

    # Filter out expired blocks
    now = timezone.now()
    blocks = blocks.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    # Username blocks always apply (regardless of tier)
    if username and blocks.filter(blocked_username__iexact=username).exists():
        return True, "You have been blocked from this chat."

    # User account blocks always apply
    if user and blocks.filter(blocked_user=user).exists():
        return True, "You have been blocked from this chat."

    # Session tier: check session_key
    if session_key and blocks.filter(
        ban_tier=ChatBlock.BAN_TIER_SESSION,
        blocked_session_key=session_key
    ).exists():
        return True, "You have been blocked from this chat."

    # Fingerprint+IP tier: both must match
    if fingerprint and ip_address and blocks.filter(
        ban_tier=ChatBlock.BAN_TIER_FINGERPRINT_IP,
        blocked_fingerprint=fingerprint,
        blocked_ip_address=ip_address
    ).exists():
        return True, "You have been blocked from this chat."

    # IP tier: just IP
    if ip_address and blocks.filter(
        ban_tier=ChatBlock.BAN_TIER_IP,
        blocked_ip_address=ip_address
    ).exists():
        return True, "You have been blocked from this chat."

    return False, None


def unblock_participation(chat_room, participation):
    """
    Unblock a user by removing their consolidated ChatBlock record.

    With consolidated blocking, we look for the single block row that contains
    any of the user's identifiers and delete it.

    Args:
        chat_room: ChatRoom instance
        participation: ChatParticipation to unblock

    Returns:
        int: Count of deleted blocks (should be 0 or 1 with consolidated approach)
    """
    blocks_to_delete = ChatBlock.objects.filter(chat_room=chat_room)

    # Build a query to match blocks by any identifier (OR logic)
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

    With consolidated blocking, each block is a single row with all identifiers,
    so we simply return each block as a separate entry.

    Args:
        chat_room: ChatRoom instance

    Returns:
        List of dict with blocked user information
    """
    blocks = ChatBlock.objects.filter(chat_room=chat_room)

    # Filter out expired blocks
    now = timezone.now()
    blocks = blocks.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    # Convert each block to a dict
    result = []
    for block in blocks.select_related('blocked_user'):
        # Determine username to display
        username = block.blocked_username or (
            block.blocked_user.reserved_username if block.blocked_user else None
        )

        # List which identifiers are blocked
        blocked_identifiers = []
        if block.blocked_username:
            blocked_identifiers.append('username')
        if block.blocked_fingerprint:
            blocked_identifiers.append('fingerprint')
        if block.blocked_user:
            blocked_identifiers.append('user_account')
        if block.blocked_ip_address:
            blocked_identifiers.append('ip_address')

        result.append({
            'username': username,
            'blocked_at': block.blocked_at,
            'reason': block.reason,
            'blocked_identifiers': blocked_identifiers,
            'expires_at': block.expires_at,
        })

    return result
