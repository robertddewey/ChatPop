"""
Similarity search utility for photo-based collaborative discovery.

Finds existing chat rooms similar to a newly uploaded photo by comparing
semantic embeddings of AI-generated suggestions.
"""
import logging
from typing import List, Dict, Any
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q
from pgvector.django import CosineDistance
from constance import config

logger = logging.getLogger(__name__)


class SimilarRoom:
    """Similar room recommendation."""

    def __init__(
        self,
        room_id: str,
        room_code: str,
        room_name: str,
        room_url: str,
        active_users: int,
        similarity_distance: float,
        source_photo_id: str
    ):
        self.room_id = room_id
        self.room_code = room_code
        self.room_name = room_name
        self.room_url = room_url
        self.active_users = active_users
        self.similarity_distance = similarity_distance
        self.source_photo_id = source_photo_id


def find_similar_rooms(
    embedding_vector: List[float],
    exclude_photo_id: str = None
) -> List[SimilarRoom]:
    """
    Find existing chat rooms similar to the given embedding vector.

    This is the core collaborative discovery function. When a user uploads a photo,
    we search for existing rooms created from similar photos by comparing
    suggestions_embedding vectors using cosine distance.

    Algorithm:
    1. Query PhotoAnalysis for similar embeddings (cosine distance < threshold)
    2. Extract all suggestion keys from similar photos
    3. Find ChatRooms with matching codes (key → code)
    4. Count active users in each room (last_seen_at within 24h)
    5. Filter by minimum active users
    6. Return sorted by similarity (closest first)

    Args:
        embedding_vector: The suggestions_embedding vector to compare against
        exclude_photo_id: Optional photo ID to exclude from results (e.g., current upload)

    Returns:
        List of SimilarRoom objects sorted by similarity (closest first)

    Example:
        Person A uploads beer photo → creates "bar-room"
        Person B uploads similar beer photo → we return:
        [
            SimilarRoom(
                room_code="bar-room",
                room_name="Bar Room",
                room_url="/chat/discover/bar-room",
                active_users=3,
                similarity_distance=0.15,
                ...
            )
        ]
    """
    from photo_analysis.models import PhotoAnalysis
    from chats.models import ChatRoom, ChatParticipation

    # Get configuration
    max_distance = config.PHOTO_SIMILARITY_MAX_DISTANCE
    max_results = config.PHOTO_SIMILARITY_MAX_RESULTS
    min_users = config.PHOTO_SIMILARITY_MIN_USERS

    logger.info(
        f"Finding similar rooms: max_distance={max_distance}, "
        f"max_results={max_results}, min_users={min_users}"
    )

    # Step 1: Find similar photos by embedding
    similar_photos = PhotoAnalysis.objects.annotate(
        distance=CosineDistance('suggestions_embedding', embedding_vector)
    ).filter(
        distance__lt=max_distance,
        suggestions_embedding__isnull=False
    ).order_by('distance')[:max_results * 5]  # Get extra to account for filtering

    if exclude_photo_id:
        similar_photos = similar_photos.exclude(id=exclude_photo_id)

    logger.info(f"Found {similar_photos.count()} similar photos")

    # Step 2: Extract suggestion keys and build room lookup
    room_codes_to_check = set()
    photo_distance_map = {}  # code → (photo_id, distance)

    for photo in similar_photos:
        photo_distance_map[str(photo.id)] = photo.distance

        # Extract suggestion keys from the suggestions JSON
        suggestions_data = photo.suggestions
        if isinstance(suggestions_data, dict):
            suggestions_list = suggestions_data.get('suggestions', [])
        elif isinstance(suggestions_data, list):
            suggestions_list = suggestions_data
        else:
            continue

        # Add all suggestion keys as potential room codes
        for suggestion in suggestions_list:
            if isinstance(suggestion, dict) and 'key' in suggestion:
                room_codes_to_check.add(suggestion['key'])

    if not room_codes_to_check:
        logger.info("No suggestion keys found in similar photos")
        return []

    logger.info(f"Checking {len(room_codes_to_check)} potential room codes")

    # Step 3: Find existing rooms with matching codes
    # Define "recently active" as last_seen_at within past 24 hours
    activity_threshold = timezone.now() - timedelta(hours=24)

    rooms = ChatRoom.objects.filter(
        code__in=room_codes_to_check,
        is_active=True
    ).annotate(
        active_user_count=Count(
            'participations',
            filter=Q(participations__last_seen_at__gte=activity_threshold)
        )
    ).filter(
        active_user_count__gte=min_users
    )

    logger.info(f"Found {rooms.count()} rooms with at least {min_users} active users")

    # Step 4: Build SimilarRoom results
    similar_rooms = []
    room_code_to_photo = {}  # Track which photo each room came from

    # Map room codes back to photos to get distances
    for photo in similar_photos:
        suggestions_data = photo.suggestions
        if isinstance(suggestions_data, dict):
            suggestions_list = suggestions_data.get('suggestions', [])
        elif isinstance(suggestions_data, list):
            suggestions_list = suggestions_data
        else:
            continue

        for suggestion in suggestions_list:
            if isinstance(suggestion, dict) and 'key' in suggestion:
                key = suggestion['key']
                # Use first (closest) photo for each room code
                if key not in room_code_to_photo:
                    room_code_to_photo[key] = (str(photo.id), photo.distance)

    # Create SimilarRoom objects
    for room in rooms:
        if room.code in room_code_to_photo:
            source_photo_id, distance = room_code_to_photo[room.code]

            similar_room = SimilarRoom(
                room_id=str(room.id),
                room_code=room.code,
                room_name=room.name,
                room_url=room.url,
                active_users=room.active_user_count,
                similarity_distance=float(distance),
                source_photo_id=source_photo_id
            )
            similar_rooms.append(similar_room)

    # Sort by similarity (closest distance first)
    similar_rooms.sort(key=lambda r: r.similarity_distance)

    # Limit to max_results
    similar_rooms = similar_rooms[:max_results]

    logger.info(f"Returning {len(similar_rooms)} similar rooms")

    return similar_rooms
