"""
Pre-refinement room matching utility.

Normalizes generic seed suggestions to existing rooms via K-NN similarity search.
Preserves proper nouns (unique entities) without comparison.

This module replaces LLM-based refinement with deterministic embedding-based matching:
- Faster (no LLM API call needed)
- Cheaper (no GPT-4o-mini cost)
- Deterministic (same input = same output)
- Direct room links (normalized suggestions ARE existing rooms)
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from django.conf import settings
from openai import OpenAI
from pgvector.django import CosineDistance

from .performance import perf_track

logger = logging.getLogger(__name__)

# Configuration
ROOM_MATCHING_SIMILARITY_THRESHOLD = 0.15  # Cosine distance threshold for room matching
ROOM_MATCHING_MAX_WORKERS = 10  # Parallel K-NN searches


def normalize_suggestions_to_rooms(
    suggestions: List[Dict[str, Any]],
    similarity_threshold: float = ROOM_MATCHING_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Normalize suggestions to existing rooms via embedding similarity.

    Splits suggestions into proper nouns (preserved) and generics (normalized).
    Generic suggestions are matched against existing room embeddings using K-NN.
    If a close match is found, the suggestion is swapped with the existing room.

    Args:
        suggestions: List of seed suggestions from Vision API (with is_proper_noun flags)
        similarity_threshold: Cosine distance threshold (default: 0.15)

    Returns:
        List of normalized suggestions (proper nouns preserved, generics matched to rooms)

    Example:
        Input:
        [
            {"name": "Beer Tasting", "key": "beer-tasting", "is_proper_noun": false},
            {"name": "Budweiser Fans", "key": "budweiser-fans", "is_proper_noun": true},
            {"name": "Bar Chat", "key": "bar-chat", "is_proper_noun": false}
        ]

        Output (assuming "Craft Beer Discussion" room exists with close embedding):
        [
            {"name": "Craft Beer Discussion", "key": "craft-beer-discussion", "source": "normalized", ...},
            {"name": "Budweiser Fans", "key": "budweiser-fans", "source": "seed", ...},
            {"name": "Bar Chat", "key": "bar-chat", "source": "seed", ...}  # No match found
        ]
    """
    if not suggestions:
        return []

    # Split by proper noun flag
    generic_suggestions = [s for s in suggestions if not s.get('is_proper_noun', False)]
    proper_noun_suggestions = [s for s in suggestions if s.get('is_proper_noun', False)]

    logger.info(
        f"Split suggestions: {len(proper_noun_suggestions)} proper nouns (preserved), "
        f"{len(generic_suggestions)} generics (will normalize)"
    )

    if not generic_suggestions:
        # All proper nouns - nothing to normalize
        return proper_noun_suggestions

    # Batch generate embeddings for generic suggestions
    with perf_track("Batch embed generic suggestions", metadata=f"{len(generic_suggestions)} suggestions"):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        input_texts = [s['name'] for s in generic_suggestions]

        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=input_texts
        )

    # Parallel K-NN searches for room matches
    with perf_track("K-NN room matching", metadata=f"{len(generic_suggestions)} parallel searches"):
        matched_suggestions = []
        with ThreadPoolExecutor(max_workers=ROOM_MATCHING_MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _find_similar_room,
                    response.data[i].embedding,
                    generic_suggestions[i],
                    similarity_threshold
                ): i
                for i in range(len(generic_suggestions))
            }

            for future in as_completed(futures):
                matched_suggestions.append(future.result())

    # Count how many were normalized
    normalized_count = sum(1 for s in matched_suggestions if s.get('source') == 'normalized')
    logger.info(
        f"Room matching complete: {normalized_count}/{len(generic_suggestions)} suggestions "
        f"normalized to existing rooms"
    )

    # Recombine: proper nouns + normalized/unmatched generics
    return proper_noun_suggestions + matched_suggestions


def _find_similar_room(
    embedding_vector: List[float],
    original_suggestion: Dict[str, Any],
    threshold: float
) -> Dict[str, Any]:
    """
    K-NN search for most similar existing room.

    Searches only active AI-generated rooms with embeddings.
    Returns the closest match if within threshold, otherwise returns original suggestion.

    Args:
        embedding_vector: Embedding of the suggestion name
        original_suggestion: Original suggestion dict
        threshold: Cosine distance threshold

    Returns:
        Matched room dict (if found) or original suggestion dict
    """
    from chats.models import ChatRoom

    try:
        # CRITICAL: Only match against AI-generated rooms (source='ai')
        # - AI rooms are globally unique collaborative discovery rooms (/chat/discover/beer-tasting)
        # - Manual rooms are user-specific (/chat/robert/my-room, /chat/alice/my-room)
        # - We never normalize suggestions to manual rooms (privacy + not globally accessible)
        match = ChatRoom.objects.filter(
            name_embedding__isnull=False,
            is_active=True,
            source=ChatRoom.SOURCE_AI  # Only AI-generated collaborative discovery rooms
        ).annotate(
            distance=CosineDistance('name_embedding', embedding_vector)
        ).filter(
            distance__lt=threshold
        ).order_by('distance').first()

        if match:
            logger.info(
                f"✓ Matched '{original_suggestion['name']}' → '{match.name}' "
                f"(distance: {match.distance:.3f})"
            )
            return {
                'name': match.name,
                'key': match.code,
                'description': original_suggestion.get('description', ''),
                'source': 'normalized',
                'is_proper_noun': False,
                'matched_room_id': str(match.id),
                'similarity_score': 1 - match.distance
            }
        else:
            logger.debug(
                f"○ No match for '{original_suggestion['name']}' "
                f"(threshold: {threshold})"
            )
            # Keep source as 'seed' if not normalized
            result = original_suggestion.copy()
            if 'source' not in result:
                result['source'] = 'seed'
            return result

    except Exception as e:
        logger.warning(
            f"Failed to match '{original_suggestion['name']}': {str(e)}"
        )
        # On error, return original suggestion
        result = original_suggestion.copy()
        if 'source' not in result:
            result['source'] = 'seed'
        return result


def generate_room_embedding(room_name: str) -> List[float]:
    """
    Generate embedding for a room name.

    Used when creating new rooms to enable future normalization matching.

    Args:
        room_name: Name of the chat room (e.g., "Beer Tasting")

    Returns:
        1536-dimensional embedding vector

    Example:
        >>> embedding = generate_room_embedding("Coffee Chat")
        >>> len(embedding)
        1536
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[room_name]
    )

    return response.data[0].embedding
