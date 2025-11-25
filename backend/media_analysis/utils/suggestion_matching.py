"""
Suggestion-to-suggestion matching utility.

Replaces photo-to-photo matching with granular suggestion-level matching.
This enables collaborative discovery where:
- "Cheers!" matches "Cheers!" (relevant to both whiskey and beer)
- "Budweiser" doesn't match "Jack Daniel's" (different brands/embeddings)
- Proper nouns are preserved (never matched)
- Popular suggestions emerge naturally from usage patterns

Architecture:
1. Vision API returns 10 seed suggestions (name + description + is_proper_noun flag)
2. For each seed suggestion:
   - Proper nouns: Skip matching, return as-is (unique entities)
   - Generic suggestions: K-NN search in Suggestion table
     - Match found: Return existing suggestion, increment usage_count
     - No match: Create new Suggestion record
3. Return list of matched/created suggestions with popularity metadata
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from django.conf import settings
from django.utils import timezone
from openai import OpenAI
from pgvector.django import CosineDistance

from ..models import Suggestion
from .performance import perf_track
from ..config import (
    SUGGESTION_MATCHING_SIMILARITY_THRESHOLD,
    PROPER_NOUN_MATCHING_THRESHOLD,
    SUGGESTION_MATCHING_MAX_WORKERS,
    SUGGESTION_MATCHING_CANDIDATES_COUNT,
    DIVERSITY_FILTER_THRESHOLD,
)

logger = logging.getLogger(__name__)


def _calculate_cosine_distance(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine distance between two embeddings.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector

    Returns:
        Cosine distance (0.0 = identical, 2.0 = opposite)
    """
    import numpy as np

    # Convert to numpy arrays
    a = np.array(embedding1)
    b = np.array(embedding2)

    # Calculate cosine similarity
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0 or norm_b == 0:
        return 1.0  # Maximum distance if either vector is zero

    cosine_similarity = dot_product / (norm_a * norm_b)

    # Convert to cosine distance (1 - similarity)
    cosine_distance = 1 - cosine_similarity

    return cosine_distance


def apply_diversity_filter(
    suggestions: List[Dict[str, Any]],
    diversity_threshold: float = DIVERSITY_FILTER_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Filter out suggestions that are too similar to each other.

    This prevents returning multiple variations of the same concept
    (e.g., "Brew Culture", "Brew Masters", "Craft Beer" all in the same result set).

    Algorithm:
    1. Sort suggestions by priority (proper nouns first, then by usage_count)
    2. Iterate through suggestions in order
    3. For each suggestion, check if it's too similar to any already accepted suggestion
    4. If too similar (distance < threshold), skip it
    5. If sufficiently different, add it to the result set

    Args:
        suggestions: List of matched suggestions with embeddings
        diversity_threshold: Maximum cosine distance allowed between suggestions
                           (lower = require more diversity)

    Returns:
        Filtered list of diverse suggestions

    Example:
        Input: ["Craft Beer" (usage=3), "Brew Culture" (usage=2), "Summer Sips" (usage=1)]
        With threshold 0.25:
        - "Craft Beer" accepted (first)
        - "Brew Culture" rejected (too similar to "Craft Beer", distance=0.12)
        - "Summer Sips" accepted (different enough from "Craft Beer", distance=0.65)
        Output: ["Craft Beer", "Summer Sips"]
    """
    if not suggestions:
        return []

    # We need embeddings to calculate diversity
    # Get embeddings for all suggestions from the database
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Prepare embeddings map: suggestion_id -> embedding
    embeddings_map = {}

    for suggestion in suggestions:
        suggestion_id = suggestion.get('suggestion_id')
        if not suggestion_id:
            continue

        # Check if we already have the embedding from matching
        # For matched suggestions, we may have generated embeddings in the previous step
        # For proper nouns, we need to generate embeddings now
        is_proper_noun = suggestion.get('is_proper_noun', False)

        if is_proper_noun:
            # Generate embedding for proper noun
            text = f"{suggestion['name']}\n{suggestion.get('description', '')}"
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=[text]
            )
            embeddings_map[suggestion_id] = response.data[0].embedding
        else:
            # Try to get embedding from database
            try:
                suggestion_obj = Suggestion.objects.get(id=suggestion_id)
                if suggestion_obj.embedding is not None:
                    embeddings_map[suggestion_id] = suggestion_obj.embedding
                else:
                    # Generate if missing
                    text = f"{suggestion['name']}\n{suggestion.get('description', '')}"
                    response = client.embeddings.create(
                        model="text-embedding-3-small",
                        input=[text]
                    )
                    embeddings_map[suggestion_id] = response.data[0].embedding
            except Suggestion.DoesNotExist:
                # Skip if suggestion not found
                continue

    logger.info(f"\n{'='*80}")
    logger.info("DIVERSITY FILTER")
    logger.info(f"{'='*80}")
    logger.info(f"Input: {len(suggestions)} suggestions")
    logger.info(f"Diversity threshold: {diversity_threshold} (must be >{diversity_threshold*100:.0f}% different)")

    # Sort by proper noun first, then usage_count (descending)
    sorted_suggestions = sorted(
        suggestions,
        key=lambda s: (not s.get('is_proper_noun', False), -s.get('usage_count', 0))
    )

    filtered_suggestions = []

    for suggestion in sorted_suggestions:
        suggestion_id = suggestion.get('suggestion_id')
        suggestion_name = suggestion['name']

        # If no embedding available, accept by default
        if suggestion_id not in embeddings_map:
            logger.info(f"  ✓ '{suggestion_name}' - accepted (no embedding for comparison)")
            filtered_suggestions.append(suggestion)
            continue

        # Check similarity against all already-accepted suggestions
        too_similar = False
        most_similar_name = None
        min_distance = float('inf')

        for accepted in filtered_suggestions:
            accepted_id = accepted.get('suggestion_id')

            # Skip if no embedding for accepted suggestion
            if accepted_id not in embeddings_map:
                continue

            # Calculate distance
            distance = _calculate_cosine_distance(
                embeddings_map[suggestion_id],
                embeddings_map[accepted_id]
            )

            if distance < min_distance:
                min_distance = distance
                most_similar_name = accepted['name']

            # Check if too similar
            if distance < diversity_threshold:
                too_similar = True
                logger.info(
                    f"  ✗ '{suggestion_name}' - rejected (too similar to '{accepted['name']}', "
                    f"distance: {distance:.4f}, threshold: {diversity_threshold})"
                )
                break

        if not too_similar:
            if filtered_suggestions:
                logger.info(
                    f"  ✓ '{suggestion_name}' - accepted (most similar: '{most_similar_name}', "
                    f"distance: {min_distance:.4f})"
                )
            else:
                logger.info(f"  ✓ '{suggestion_name}' - accepted (first suggestion)")
            filtered_suggestions.append(suggestion)

    logger.info(f"\nOutput: {len(filtered_suggestions)} diverse suggestions")
    logger.info(f"{'='*80}\n")

    return filtered_suggestions


def _find_or_create_proper_noun(
    embedding_vector: List[float],
    seed_suggestion: Dict[str, Any],
    threshold: float
) -> Dict[str, Any]:
    """
    K-NN search for similar existing proper noun suggestions.

    Uses strict threshold to prevent false matches between items with same name
    but different content (e.g., "Open Season" book vs movie).

    If match found: Return existing suggestion
    If no match: Create new suggestion with unique key (append -2, -3, etc. if needed)

    Args:
        embedding_vector: Embedding of name + description
        seed_suggestion: Original seed suggestion dict
        threshold: Cosine distance threshold (strict, e.g., 0.15)

    Returns:
        Matched or created proper noun suggestion
    """
    suggestion_name = seed_suggestion['name']
    base_key = seed_suggestion['key']
    prefix = f"[{suggestion_name}]"

    try:
        # K-NN search in existing proper nouns ONLY
        candidates = Suggestion.objects.filter(
            is_proper_noun=True
        ).annotate(
            distance=CosineDistance('embedding', embedding_vector)
        ).order_by('distance')[:SUGGESTION_MATCHING_CANDIDATES_COUNT]

        # Log matching details
        logger.info(f"{prefix} {'='*70}")
        logger.info(f"{prefix} Proper Noun Matching (threshold: {threshold})")
        logger.info(f"{prefix} {'='*70}")

        if not candidates:
            logger.info(f"{prefix}   No existing proper nouns - creating new")
            logger.info(f"{prefix} {'='*70}")
            return _create_or_get_suggestion(
                name=seed_suggestion['name'],
                key=base_key,
                description=seed_suggestion.get('description', ''),
                is_proper_noun=True,
                embedding_vector=embedding_vector
            )

        for i, candidate in enumerate(candidates, 1):
            match_symbol = "✓ MATCHED" if candidate.distance < threshold else "○"
            logger.info(
                f"{prefix}   {i}. {match_symbol} '{candidate.name}' (key: {candidate.key}) - "
                f"distance: {candidate.distance:.4f} "
                f"(similarity: {(1 - candidate.distance):.1%}, usage: {candidate.usage_count}x)"
            )

        logger.info(f"{prefix} {'='*70}")

        # Check best match against strict threshold
        best_candidate = candidates[0]
        if best_candidate.distance < threshold:
            # Match found - increment usage
            best_candidate.increment_usage()

            logger.info(
                f"{prefix} ✓ FINAL: Matched → '{best_candidate.name}' (key: {best_candidate.key}) "
                f"(distance: {best_candidate.distance:.4f}, new usage: {best_candidate.usage_count}x)"
            )

            return {
                'name': best_candidate.name,
                'key': best_candidate.key,
                'description': seed_suggestion.get('description', best_candidate.description),  # Use NEW description
                'source': 'matched',
                'is_proper_noun': True,
                'usage_count': best_candidate.usage_count,
                'similarity_score': 1 - best_candidate.distance,
                'suggestion_id': str(best_candidate.id)
            }
        else:
            # No match - create new with unique key
            logger.info(
                f"{prefix} ○ FINAL: No match - best distance {best_candidate.distance:.4f} "
                f"exceeds threshold {threshold} - creating new with unique key"
            )

            return _create_or_get_suggestion(
                name=seed_suggestion['name'],
                key=base_key,
                description=seed_suggestion.get('description', ''),
                is_proper_noun=True,
                embedding_vector=embedding_vector
            )

    except Exception as e:
        logger.warning(
            f"Failed to match proper noun '{seed_suggestion['name']}': {str(e)}"
        )
        # On error, create new
        return _create_or_get_suggestion(
            name=seed_suggestion['name'],
            key=base_key,
            description=seed_suggestion.get('description', ''),
            is_proper_noun=True,
            embedding_vector=embedding_vector
        )


def match_suggestions_to_existing(
    seed_suggestions: List[Dict[str, Any]],
    similarity_threshold: float = SUGGESTION_MATCHING_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Match seed suggestions to existing suggestions via embedding similarity.

    Proper nouns are matched using strict embedding similarity to prevent false matches
    (e.g., "Open Season" book vs movie should create separate suggestions).
    Generic suggestions are matched with looser threshold to encourage consolidation.
    If a match is found, the existing suggestion is used and its usage_count is incremented.
    If no match is found, a new Suggestion record is created.

    Args:
        seed_suggestions: List of seed suggestions from Vision API
                         [{"name": "Beer Tasting", "key": "beer-tasting",
                           "description": "...", "is_proper_noun": false}, ...]
        similarity_threshold: Cosine distance threshold (default: 0.15)

    Returns:
        List of matched suggestions with popularity metadata
        [{"name": "Cheers!", "key": "cheers", "source": "matched",
          "usage_count": 5, "is_proper_noun": false}, ...]

    Example:
        Input seed suggestions:
        [
            {"name": "Cheers!", "key": "cheers", "description": "...", "is_proper_noun": false},
            {"name": "Jack Daniel's", "key": "jack-daniels", "description": "...", "is_proper_noun": true},
            {"name": "Bar Chat", "key": "bar-chat", "description": "...", "is_proper_noun": false}
        ]

        Output (assuming "Cheers!" exists with 5 uses, "Jack Daniel's" is new, "Bar Chat" matches existing):
        [
            {"name": "Cheers!", "key": "cheers", "source": "matched", "usage_count": 6, ...},
            {"name": "Jack Daniel's", "key": "jack-daniels", "source": "proper_noun", "usage_count": 1, ...},
            {"name": "Bar Chat", "key": "bar-chat", "source": "matched", "usage_count": 3, ...}
        ]
    """
    if not seed_suggestions:
        return []

    # Split by proper noun flag
    generic_suggestions = [s for s in seed_suggestions if not s.get('is_proper_noun', False)]
    proper_noun_suggestions = [s for s in seed_suggestions if s.get('is_proper_noun', False)]

    logger.info(f"\n{'='*80}")
    logger.info("SUGGESTION MATCHING - Proper Noun Split")
    logger.info(f"{'='*80}")
    logger.info(
        f"Total suggestions: {len(seed_suggestions)} "
        f"({len(proper_noun_suggestions)} proper nouns, {len(generic_suggestions)} generics)"
    )

    if proper_noun_suggestions:
        logger.info("\nProper nouns (will match with STRICT threshold to prevent collisions):")
        for s in proper_noun_suggestions:
            logger.info(f"  ✓ '{s['name']}' - is_proper_noun={s.get('is_proper_noun')}")

    if generic_suggestions:
        logger.info("\nGenerics (will match with standard threshold):")
        for s in generic_suggestions:
            logger.info(f"  → '{s['name']}' - is_proper_noun={s.get('is_proper_noun', False)}")

    logger.info(f"{'='*80}\n")

    # Process proper nouns with embedding-based matching (strict threshold)
    proper_noun_results = []
    if proper_noun_suggestions:
        with perf_track("Batch embed proper nouns", metadata=f"{len(proper_noun_suggestions)} proper nouns"):
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Generate embeddings for proper nouns (name + description)
            input_texts = [
                f"{s['name']}\n{s['description']}" if s.get('description') else s['name']
                for s in proper_noun_suggestions
            ]

            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=input_texts
            )

        # Match each proper noun using strict threshold
        with perf_track("K-NN proper noun matching", metadata=f"{len(proper_noun_suggestions)} parallel searches"):
            with ThreadPoolExecutor(max_workers=SUGGESTION_MATCHING_MAX_WORKERS) as executor:
                futures = {
                    executor.submit(
                        _find_or_create_proper_noun,
                        response.data[i].embedding,
                        proper_noun_suggestions[i],
                        PROPER_NOUN_MATCHING_THRESHOLD  # Use strict threshold (e.g., 0.15)
                    ): i
                    for i in range(len(proper_noun_suggestions))
                }

                for future in as_completed(futures):
                    proper_noun_results.append(future.result())

    if not generic_suggestions:
        # All proper nouns - apply diversity filter and return
        diverse_results = apply_diversity_filter(proper_noun_results)
        return diverse_results

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

    # Parallel K-NN searches for suggestion matches
    with perf_track("K-NN suggestion matching", metadata=f"{len(generic_suggestions)} parallel searches"):
        matched_suggestions = []
        with ThreadPoolExecutor(max_workers=SUGGESTION_MATCHING_MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _find_or_create_similar_suggestion,
                    response.data[i].embedding,
                    generic_suggestions[i],
                    similarity_threshold
                ): i
                for i in range(len(generic_suggestions))
            }

            for future in as_completed(futures):
                matched_suggestions.append(future.result())

    # Count how many were matched vs created
    matched_count = sum(1 for s in matched_suggestions if s.get('source') == 'matched')
    created_count = sum(1 for s in matched_suggestions if s.get('source') == 'created')

    logger.info(
        f"\nSuggestion matching complete: "
        f"{matched_count} matched to existing, "
        f"{created_count} created new, "
        f"{len(proper_noun_results)} proper nouns preserved"
    )

    # Recombine: proper nouns + matched/created generics
    # Maintain original order from seed_suggestions
    all_results = proper_noun_results + matched_suggestions

    # Apply diversity filter to remove similar suggestions
    diverse_results = apply_diversity_filter(all_results)

    return diverse_results


def _find_or_create_similar_suggestion(
    embedding_vector: List[float],
    seed_suggestion: Dict[str, Any],
    threshold: float
) -> Dict[str, Any]:
    """
    K-NN search for most similar existing suggestion.

    If a match is found within threshold, return existing suggestion and increment usage_count.
    If no match is found, create a new Suggestion record.

    Args:
        embedding_vector: Embedding of the seed suggestion (name + description)
        seed_suggestion: Original seed suggestion dict
        threshold: Cosine distance threshold

    Returns:
        Matched or created suggestion dict with metadata
    """
    suggestion_name = seed_suggestion['name']
    prefix = f"[{suggestion_name}]"

    try:
        # K-NN search in Suggestion table (exclude proper nouns from matching)
        # Get top N candidates to show matching details
        candidates = Suggestion.objects.filter(
            is_proper_noun=False  # Never match against proper nouns
        ).annotate(
            distance=CosineDistance('embedding', embedding_vector)
        ).order_by('distance')[:SUGGESTION_MATCHING_CANDIDATES_COUNT]

        # Log all candidates with their distances
        logger.info(f"{prefix} {'='*70}")
        logger.info(f"{prefix} Matching (threshold: {threshold})")
        logger.info(f"{prefix} {'='*70}")

        if not candidates:
            logger.info(f"{prefix}   No existing suggestions found - creating new")
            logger.info(f"{prefix} {'='*70}")
            return _create_or_get_suggestion(
                name=seed_suggestion['name'],
                key=seed_suggestion['key'],
                description=seed_suggestion.get('description', ''),
                is_proper_noun=False,
                embedding_vector=embedding_vector
            )

        for i, candidate in enumerate(candidates, 1):
            match_symbol = "✓ MATCHED" if candidate.distance < threshold else "○"
            logger.info(
                f"{prefix}   {i}. {match_symbol} '{candidate.name}' - distance: {candidate.distance:.4f} "
                f"(similarity: {(1 - candidate.distance):.1%}, usage: {candidate.usage_count}x)"
            )

        logger.info(f"{prefix} {'='*70}")

        # Use the best match if it's below threshold
        best_candidate = candidates[0]
        if best_candidate.distance < threshold:
            # Match found - increment usage and return existing suggestion
            best_candidate.increment_usage()

            logger.info(
                f"{prefix} ✓ FINAL: Matched → '{best_candidate.name}' "
                f"(distance: {best_candidate.distance:.4f}, new usage: {best_candidate.usage_count}x)"
            )

            return {
                'name': best_candidate.name,
                'key': best_candidate.key,
                'description': seed_suggestion.get('description', best_candidate.description),  # Use NEW description
                'source': 'matched',
                'is_proper_noun': False,
                'usage_count': best_candidate.usage_count,
                'similarity_score': 1 - best_candidate.distance,
                'suggestion_id': str(best_candidate.id)
            }
        else:
            # No match - create new suggestion
            logger.info(
                f"{prefix} ○ FINAL: No match - best distance {best_candidate.distance:.4f} "
                f"exceeds threshold {threshold} - creating new"
            )

            return _create_or_get_suggestion(
                name=seed_suggestion['name'],
                key=seed_suggestion['key'],
                description=seed_suggestion.get('description', ''),
                is_proper_noun=False,
                embedding_vector=embedding_vector
            )

    except Exception as e:
        logger.warning(
            f"Failed to match '{seed_suggestion['name']}': {str(e)}"
        )
        # On error, create new suggestion
        return _create_or_get_suggestion(
            name=seed_suggestion['name'],
            key=seed_suggestion['key'],
            description=seed_suggestion.get('description', ''),
            is_proper_noun=False,
            embedding_vector=embedding_vector
        )


def _create_or_get_suggestion(
    name: str,
    key: str,
    description: str,
    is_proper_noun: bool,
    embedding_vector: List[float] = None
) -> Dict[str, Any]:
    """
    Create a new Suggestion record with unique key.

    For proper nouns: Handles key collisions by appending numeric suffixes
    (e.g., "open-season", "open-season-2", "open-season-3")

    For generics: Creates new suggestion (generics already matched by embedding
    before calling this function, so we only create if truly new)

    Args:
        name: Suggestion name (e.g., "Open Season")
        key: URL-safe slug base (e.g., "open-season")
        description: Description from Vision API
        is_proper_noun: Whether this is a proper noun (brand, title, etc.)
        embedding_vector: 1536-dim embedding

    Returns:
        Suggestion dict with metadata
    """
    try:
        # Handle key collision for proper nouns by appending numeric suffix
        if is_proper_noun:
            # Check if base key exists
            base_key = key
            unique_key = base_key
            suffix = 2

            while Suggestion.objects.filter(key=unique_key).exists():
                unique_key = f"{base_key}-{suffix}"
                suffix += 1

            if unique_key != base_key:
                logger.info(
                    f"  ! Key collision: '{base_key}' exists, using '{unique_key}' instead"
                )

            key = unique_key

        # Create new suggestion
        suggestion = Suggestion.objects.create(
            name=name,
            key=key,
            description=description,
            is_proper_noun=is_proper_noun,
            embedding=embedding_vector,
            usage_count=1,
            last_used_at=timezone.now()
        )

        logger.info(
            f"  + Created new suggestion '{name}' "
            f"(key={key}, is_proper_noun={is_proper_noun})"
        )

        return {
            'name': suggestion.name,
            'key': suggestion.key,
            'description': description,
            'source': 'created',
            'is_proper_noun': is_proper_noun,
            'usage_count': 1,
            'suggestion_id': str(suggestion.id)
        }

    except Exception as e:
        logger.error(f"Failed to create/get suggestion '{name}': {str(e)}")
        # Return fallback dict without database record
        return {
            'name': name,
            'key': key,
            'description': description,
            'source': 'seed',
            'is_proper_noun': is_proper_noun,
            'usage_count': 0
        }
