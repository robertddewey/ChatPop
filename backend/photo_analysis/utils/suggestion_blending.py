"""
Suggestion blending utility for hybrid room recommendations.

Combines three tiers of suggestions when a photo is uploaded:
1. Existing rooms with active users (prioritized by activity)
2. Popular suggestions from similar photos (clustering effect)
3. Fresh AI-generated suggestions (fill remaining slots)

This encourages natural room clustering while maintaining diversity.
"""

import logging
from collections import Counter
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db.models import Count, Q
from django.utils import timezone
from pgvector.django import CosineDistance

logger = logging.getLogger(__name__)

# K-Nearest Neighbors configuration for collaborative discovery
K_NEAREST_NEIGHBORS = 10  # Number of similar photos to consider (K in KNN)
MAX_COSINE_DISTANCE = 0.40  # Maximum cosine distance for similarity threshold
MIN_POPULARITY_SCORE = 1.0  # Minimum popularity score for suggestions


def get_similar_photo_popular_suggestions(
    embedding_vector: List[float],
    exclude_photo_id: Optional[str] = None,
    max_distance: float = None,
    min_popular: float = None,
    k_nearest: int = None,
) -> List[Dict[str, Any]]:
    """
    Find similar photos using K-Nearest Neighbors and extract popular suggestions.

    This function is used BEFORE refinement to provide context-relevant popular
    suggestions that should be preferred over fresh AI suggestions.

    Args:
        embedding_vector: The suggestions_embedding vector (from seed suggestions)
        exclude_photo_id: Optional photo ID to exclude (typically the current upload)
        max_distance: Maximum cosine distance threshold (default: MAX_COSINE_DISTANCE = 0.25)
        min_popular: Minimum popularity score (default: MIN_POPULARITY_SCORE = 2.0)
        k_nearest: K parameter for KNN algorithm (default: K_NEAREST_NEIGHBORS = 10)

    Returns:
        List of popular suggestions from similar photos, sorted by frequency.
        Format: [{'name': '...', 'key': '...', 'usage_count': N}, ...]

    Example:
        User uploads beer photo → K=10 similar photos have "Cheers!" appearing 5 times
        Returns: [{'name': 'Cheers!', 'key': 'cheers', 'usage_count': 5}, ...]
    """
    from photo_analysis.models import PhotoAnalysis

    # Use hardcoded defaults if not provided
    if max_distance is None:
        max_distance = MAX_COSINE_DISTANCE
    if min_popular is None:
        min_popular = MIN_POPULARITY_SCORE
    if k_nearest is None:
        k_nearest = K_NEAREST_NEIGHBORS

    # Find similar photos by suggestions_embedding
    similar_photos_query = PhotoAnalysis.objects.annotate(
        distance=CosineDistance("suggestions_embedding", embedding_vector)
    ).filter(distance__lt=max_distance, suggestions_embedding__isnull=False)

    # Exclude current photo BEFORE slicing
    if exclude_photo_id:
        similar_photos_query = similar_photos_query.exclude(id=exclude_photo_id)

    similar_photos = similar_photos_query.order_by("distance")[:k_nearest]

    logger.info(f"Found {similar_photos.count()} similar photos for extracting popular suggestions")
    logger.info(f"DEBUG: Similar photos details: {[(p.id, p.distance) for p in similar_photos]}")

    # Extract suggestion keys and count frequency
    suggestion_key_counter = Counter()
    suggestion_details = {}  # key → (name, description)

    for photo in similar_photos:
        suggestions_data = photo.suggestions
        logger.info(f"DEBUG: Processing photo {photo.id}, suggestions_data type: {type(suggestions_data)}, value: {suggestions_data}")

        if isinstance(suggestions_data, dict):
            suggestions_list = suggestions_data.get("suggestions", [])
        elif isinstance(suggestions_data, list):
            suggestions_list = suggestions_data
        else:
            logger.info(f"DEBUG: Photo {photo.id} - suggestions_data is neither dict nor list, skipping")
            continue

        logger.info(f"DEBUG: Photo {photo.id} - extracted {len(suggestions_list)} suggestions")

        for suggestion in suggestions_list:
            if isinstance(suggestion, dict) and "key" in suggestion:
                key = suggestion["key"]
                suggestion_key_counter[key] += 1
                logger.info(f"DEBUG: Counted suggestion key '{key}' (count: {suggestion_key_counter[key]})")
                # Store name and description from first occurrence
                if key not in suggestion_details:
                    suggestion_details[key] = (suggestion.get("name", key), suggestion.get("description", ""))

    # Build list of popular suggestions (frequency >= min_popular)
    popular_suggestions = []
    for key, count in suggestion_key_counter.most_common():
        if count >= min_popular:
            name, description = suggestion_details.get(key, (key, ""))
            popular_suggestions.append({"name": name, "key": key, "usage_count": count})

    logger.info(
        f"Extracted {len(popular_suggestions)} popular suggestions from similar photos "
        f"(min frequency: {min_popular})"
    )
    logger.info(f"DEBUG: Returning popular suggestions: {popular_suggestions}")

    return popular_suggestions


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
        active_users: int = 0,
        source: str = "refined",  # Always 'refined' (from refinement layer)
    ):
        self.key = key
        self.name = name
        self.description = description
        self.has_room = has_room
        self.room_id = room_id
        self.room_code = room_code
        self.room_url = room_url
        self.active_users = active_users
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "key": self.key,
            "name": self.name,
            "description": self.description,
            "has_room": self.has_room,
            "active_users": self.active_users,
            "source": self.source,
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
    from chats.models import ChatParticipation, ChatRoom

    logger.info(f"Enriching {len(refined_suggestions)} refined suggestions with room metadata")

    blended = []
    activity_threshold = timezone.now() - timedelta(hours=24)

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
        ).annotate(
            active_user_count=Count("participations", filter=Q(participations__last_seen_at__gte=activity_threshold))
        )

        # Build dict: key → room
        for room in rooms:
            rooms_dict[room.code] = room

        logger.info(f"Found {len(rooms_dict)} existing rooms out of {len(suggestion_keys)} refined suggestions")

    # =========================================================================
    # Enrich each refined suggestion with room metadata
    # =========================================================================
    for suggestion in refined_suggestions:
        key = suggestion.get("key")
        name = suggestion.get("name", key)
        description = suggestion.get("description", "")
        source = suggestion.get("source", "refined")  # Preserve source from refinement layer

        # Check if this suggestion has an existing room
        room = rooms_dict.get(key)

        if room:
            # Existing room - add full metadata
            blended.append(
                BlendedSuggestion(
                    key=key,
                    name=name,
                    description=description,
                    has_room=True,
                    room_id=str(room.id),
                    room_code=room.code,
                    room_url=room.url,
                    active_users=room.active_user_count,
                    source=source,  # Preserve source (popular/refined/seed)
                )
            )
            logger.debug(f"  ✓ {name} → has_room=True, active_users={room.active_user_count}")
        else:
            # No room yet - metadata shows has_room=False
            blended.append(
                BlendedSuggestion(
                    key=key, name=name, description=description, has_room=False, active_users=0, source=source  # Preserve source
                )
            )
            logger.debug(f"  ○ {name} → has_room=False")

    logger.info(
        f"Enrichment complete: {len(blended)} suggestions "
        f"({sum(1 for s in blended if s.has_room)} with rooms, "
        f"{sum(1 for s in blended if not s.has_room)} without rooms)"
    )

    return blended
