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
    SUGGESTION_MATCHING_MAX_WORKERS,
    SUGGESTION_MATCHING_CANDIDATES_COUNT,
)

logger = logging.getLogger(__name__)


def match_suggestions_to_existing(
    seed_suggestions: List[Dict[str, Any]],
    similarity_threshold: float = SUGGESTION_MATCHING_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Match seed suggestions to existing suggestions via embedding similarity.

    Proper nouns are preserved without matching (unique entities like brands, titles).
    Generic suggestions are matched against the Suggestion table using K-NN.
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
        logger.info("\nProper nouns (PRESERVED - will NOT be matched):")
        for s in proper_noun_suggestions:
            logger.info(f"  ✓ '{s['name']}' - is_proper_noun={s.get('is_proper_noun')}")

    if generic_suggestions:
        logger.info("\nGenerics (will attempt matching):")
        for s in generic_suggestions:
            logger.info(f"  → '{s['name']}' - is_proper_noun={s.get('is_proper_noun', False)}")

    logger.info(f"{'='*80}\n")

    # Process proper nouns (create or get existing)
    proper_noun_results = []
    for proper_noun in proper_noun_suggestions:
        result = _create_or_get_suggestion(
            name=proper_noun['name'],
            key=proper_noun['key'],
            description=proper_noun.get('description', ''),
            is_proper_noun=True,
            embedding_vector=None  # Proper nouns don't need embeddings (never matched)
        )
        proper_noun_results.append(result)

    if not generic_suggestions:
        # All proper nouns - nothing to match
        return proper_noun_results

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

    return all_results


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
                'description': seed_suggestion.get('description', ''),
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
    Create a new Suggestion record or get existing by key.

    Args:
        name: Suggestion name (e.g., "Cheers!")
        key: URL-safe slug (e.g., "cheers")
        description: Description from Vision API
        is_proper_noun: Whether this is a proper noun (brand, title, etc.)
        embedding_vector: 1536-dim embedding (optional, not needed for proper nouns)

    Returns:
        Suggestion dict with metadata
    """
    try:
        # Check if suggestion already exists by key
        existing = Suggestion.objects.filter(key=key).first()

        if existing:
            # Increment usage if it already exists
            existing.increment_usage()
            logger.info(f"  ✓ Found existing suggestion '{name}' (key={key}, usage={existing.usage_count}x)")

            return {
                'name': existing.name,
                'key': existing.key,
                'description': description,
                'source': 'matched',
                'is_proper_noun': existing.is_proper_noun,
                'usage_count': existing.usage_count,
                'suggestion_id': str(existing.id)
            }

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
