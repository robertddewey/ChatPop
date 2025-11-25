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

    logger.info(f"\n{'='*80}")
    logger.info("PROPER NOUN SPLIT")
    logger.info(f"{'='*80}")
    logger.info(
        f"Total suggestions: {len(suggestions)} "
        f"({len(proper_noun_suggestions)} proper nouns, {len(generic_suggestions)} generics)"
    )

    if proper_noun_suggestions:
        logger.info("\nProper nouns (PRESERVED - will NOT be normalized):")
        for s in proper_noun_suggestions:
            logger.info(f"  ✓ '{s['name']}' - is_proper_noun={s.get('is_proper_noun')}")

    if generic_suggestions:
        logger.info("\nGenerics (will attempt normalization):")
        for s in generic_suggestions:
            logger.info(f"  → '{s['name']}' - is_proper_noun={s.get('is_proper_noun', False)}")

    logger.info(f"{'='*80}\n")

    if not generic_suggestions:
        # All proper nouns - nothing to normalize
        return proper_noun_suggestions

    # Batch generate embeddings for generic suggestions (name + description)
    with perf_track("Batch embed generic suggestions", metadata=f"{len(generic_suggestions)} suggestions"):
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Format: "Name\nDescription" (or just "Name" if no description)
        input_texts = [
            f"{s['name']}\n{s['description']}" if s.get('description') else s['name']
            for s in generic_suggestions
        ]

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

        # Get top 5 candidates to show matching details
        candidates = ChatRoom.objects.filter(
            name_embedding__isnull=False,
            is_active=True,
            source=ChatRoom.SOURCE_AI  # Only AI-generated collaborative discovery rooms
        ).annotate(
            distance=CosineDistance('name_embedding', embedding_vector)
        ).order_by('distance')[:5]

        # Log all candidates with their distances
        suggestion_name = original_suggestion['name']
        logger.info(f"\n{'='*80}")
        logger.info(f"Matching '{suggestion_name}' (threshold: {threshold})")
        logger.info(f"{'='*80}")

        if not candidates:
            logger.info("  No existing rooms with embeddings found")
            logger.info(f"{'='*80}\n")
            result = original_suggestion.copy()
            if 'source' not in result:
                result['source'] = 'seed'
            return result

        for i, candidate in enumerate(candidates, 1):
            match_symbol = "✓ MATCHED" if candidate.distance < threshold else "○"
            logger.info(
                f"  {i}. {match_symbol} '{candidate.name}' - distance: {candidate.distance:.4f} "
                f"(similarity: {(1 - candidate.distance):.1%})"
            )

        logger.info(f"{'='*80}\n")

        # Use the best match if it's below threshold
        best_candidate = candidates[0]
        if best_candidate.distance < threshold:
            logger.info(
                f"✓ FINAL: Matched '{suggestion_name}' → '{best_candidate.name}' "
                f"(distance: {best_candidate.distance:.4f})"
            )
            return {
                'name': best_candidate.name,
                'key': best_candidate.code,
                'description': original_suggestion.get('description', ''),
                'source': 'normalized',
                'is_proper_noun': False,
                'matched_room_id': str(best_candidate.id),
                'similarity_score': 1 - best_candidate.distance
            }
        else:
            logger.info(
                f"○ FINAL: No match for '{suggestion_name}' - best distance {best_candidate.distance:.4f} "
                f"exceeds threshold {threshold}"
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


def generate_room_embedding(room_name: str, room_description: str = "") -> List[float]:
    """
    Generate embedding for a room name and description.

    Used when creating new rooms to enable future normalization matching.
    Embeddings include both name and description for better semantic matching
    (e.g., "Suds" + "beer" vs "Suds" + "soap" have different embeddings).

    Args:
        room_name: Name of the chat room (e.g., "Beer Tasting")
        room_description: Description of the room (e.g., "Discuss craft beer flavors")
                          Optional - if empty, only name is embedded

    Returns:
        1536-dimensional embedding vector

    Example:
        >>> embedding = generate_room_embedding("Coffee Chat", "Share coffee experiences")
        >>> len(embedding)
        1536
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Format: "Name\nDescription" (or just "Name" if no description)
    input_text = f"{room_name}\n{room_description}" if room_description else room_name

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=[input_text]
    )

    return response.data[0].embedding
