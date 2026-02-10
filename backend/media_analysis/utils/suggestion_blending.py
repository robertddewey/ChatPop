"""
Suggestion blending utility for hybrid room recommendations.

Combines three tiers of suggestions when a photo is uploaded:
1. Existing rooms with active users (prioritized by activity)
2. Popular suggestions from similar photos (clustering effect)
3. Fresh AI-generated suggestions (fill remaining slots)

This encourages natural room clustering while maintaining diversity.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BlendedSuggestion:
    """A suggestion with room metadata added by the blending layer.

    This is a pure metadata wrapper - all intelligent suggestion selection
    is handled by the refinement layer (LLM-based deduplication).
    Blending only adds routing info for existing rooms.
    """

    def __init__(
        self,
        key: str,
        name: str,
        description: str,
        has_room: bool = False,
        room_id: Optional[str] = None,
        room_code: Optional[str] = None,
        room_url: Optional[str] = None,
        messages_24h: int = 0,  # Total messages in last 24 hours
        messages_10min: int = 0,  # Messages in last 10 minutes (for "active" indicator)
        source: str = "refined",  # Always 'refined' (from refinement layer)
        usage_count: int = 0,  # Number of times this suggestion has been used
        is_proper_noun: bool = False,  # Whether this is a proper noun (brand, title, etc.)
    ):
        self.key = key
        self.name = name
        self.description = description
        self.has_room = has_room
        self.room_id = room_id
        self.room_code = room_code
        self.room_url = room_url
        self.messages_24h = messages_24h
        self.messages_10min = messages_10min
        self.source = source
        self.usage_count = usage_count
        self.is_proper_noun = is_proper_noun

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "has_room": self.has_room,
            "messages_24h": self.messages_24h,
            "messages_10min": self.messages_10min,
            "source": self.source,
            "usage_count": self.usage_count,
            "is_proper_noun": self.is_proper_noun,
        }
        if self.has_room:
            result.update(
                {
                    "room_id": self.room_id,
                    "room_code": self.room_code,
                    "room_url": self.room_url,
                }
            )
        return result


def blend_suggestions(
    refined_suggestions: List[Dict[str, str]], exclude_photo_id: Optional[str] = None
) -> List[BlendedSuggestion]:
    """
    Enrich refined suggestions with room metadata (pure metadata layer).

    This function is now a simple metadata enrichment layer. Refinement handles
    ALL intelligent suggestion selection (including incorporating popular suggestions).
    Blending ONLY adds routing metadata for existing rooms.

    Algorithm:
    1. For each refined suggestion, query ChatRoom for matching key
    2. If room exists: add room_id, room_code, room_url, active_users, has_room=True
    3. If not exists: has_room=False, active_users=0
    4. Return enriched suggestions (preserves refinement's decisions)

    Args:
        refined_suggestions: List of refined suggestions from refinement (key, name, description)
        exclude_photo_id: Optional photo ID (not used, kept for backward compatibility)

    Returns:
        List of BlendedSuggestion objects with room metadata added

    Example:
        Refined suggestions: [
            {"key": "twisters", "name": "Twisters", "description": "..."},
            {"key": "twister", "name": "Twister", "description": "..."}
        ]

        After blending (if "twister" has an existing room):
        [
            BlendedSuggestion(
                key="twisters",
                name="Twisters",
                has_room=False,
                active_users=0,
                source="refined"
            ),
            BlendedSuggestion(
                key="twister",
                name="Twister",
                has_room=True,
                room_id="abc123",
                room_code="twister",
                room_url="/chat/twister",
                active_users=5,
                source="refined"
            )
        ]
    """
    from chats.models import ChatRoom
    from .message_activity import get_message_activity_for_rooms

    logger.info(f"Enriching {len(refined_suggestions)} refined suggestions with room metadata")

    blended = []

    # =========================================================================
    # Extract suggestion keys for room lookup
    # =========================================================================
    suggestion_keys = [s.get("key") for s in refined_suggestions if s.get("key")]

    if not suggestion_keys:
        logger.warning("No suggestion keys found in refined suggestions")
        return []

    # =========================================================================
    # Query existing rooms for these keys (batch lookup)
    # =========================================================================
    rooms_dict = {}
    if suggestion_keys:
        rooms = ChatRoom.objects.filter(
            code__in=suggestion_keys,
            source=ChatRoom.SOURCE_AI,  # Only AI-generated collaborative discovery rooms
            is_active=True,
        )

        # Build dict: key → room
        for room in rooms:
            rooms_dict[room.code] = room

        logger.info(f"Found {len(rooms_dict)} existing rooms out of {len(suggestion_keys)} refined suggestions")

    # =========================================================================
    # Get message activity for existing rooms (batch lookup with caching)
    # =========================================================================
    room_ids = [str(room.id) for room in rooms_dict.values()]
    message_activity = get_message_activity_for_rooms(room_ids) if room_ids else {}

    # Map room_id -> room_code for easy lookup
    room_id_to_code = {str(room.id): room.code for room in rooms_dict.values()}

    # =========================================================================
    # Enrich each refined suggestion with room metadata
    # =========================================================================
    for suggestion in refined_suggestions:
        key = suggestion.get("key")
        name = suggestion.get("name", key)
        description = suggestion.get("description", "")
        source = suggestion.get("source", "refined")  # Preserve source from refinement layer
        usage_count = suggestion.get("usage_count", 0)  # Preserve usage count
        is_proper_noun = suggestion.get("is_proper_noun", False)  # Preserve proper noun flag

        # Check if this suggestion has an existing room
        room = rooms_dict.get(key)

        if room:
            # Get message activity for this room
            room_id = str(room.id)
            activity = message_activity.get(room_id)
            msgs_24h = activity.messages_24h if activity else 0
            msgs_10min = activity.messages_10min if activity else 0

            # Existing room - add full metadata
            blended.append(
                BlendedSuggestion(
                    key=key,
                    name=name,
                    description=description,
                    has_room=True,
                    room_id=room_id,
                    room_code=room.code,
                    room_url=room.url,
                    messages_24h=msgs_24h,
                    messages_10min=msgs_10min,
                    source=source,  # Preserve source (popular/refined/seed)
                    usage_count=usage_count,  # Preserve usage count
                    is_proper_noun=is_proper_noun,  # Preserve proper noun flag
                )
            )
            logger.debug(f"  ✓ {name} → has_room=True, messages_24h={msgs_24h}, messages_10min={msgs_10min}")
        else:
            # No room yet - metadata shows has_room=False
            blended.append(
                BlendedSuggestion(
                    key=key,
                    name=name,
                    description=description,
                    has_room=False,
                    messages_24h=0,
                    messages_10min=0,
                    source=source,  # Preserve source
                    usage_count=usage_count,  # Preserve usage count
                    is_proper_noun=is_proper_noun,  # Preserve proper noun flag
                )
            )
            logger.debug(f"  ○ {name} → has_room=False")

    logger.info(
        f"Enrichment complete: {len(blended)} suggestions "
        f"({sum(1 for s in blended if s.has_room)} with rooms, "
        f"{sum(1 for s in blended if not s.has_room)} without rooms)"
    )

    return blended
