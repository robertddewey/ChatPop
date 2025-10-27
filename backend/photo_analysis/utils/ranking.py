"""
Intelligent ranking utility for canonical suggestion prioritization.

Ensures that the suggestion matching the current photo's canonical name
(from title/visible_text) always ranks #1, even if other suggestions
are more popular globally.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def rank_by_canonical_match(
    suggestions: List[Dict[str, Any]],
    caption_title: Optional[str] = None,
    caption_visible_text: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Rank suggestions so the best canonical match appears at #1.

    This ensures that when you upload a photo of "Jim Beam", the suggestion
    "Jim Beam" ranks #1, even if "Jack Daniels" is more popular globally.

    Algorithm:
    1. Find the suggestion that best matches caption_title or caption_visible_text
    2. Move that suggestion to position #1
    3. Keep all other suggestions in their current order

    Args:
        suggestions: List of suggestion dicts (popular + refined combined)
        caption_title: Photo title (e.g., "The Twisters Movie Poster")
        caption_visible_text: Visible text in photo (e.g., "THE TWISTERS")

    Returns:
        Re-ranked suggestions list with canonical match at #1

    Example:
        >>> suggestions = [
        ...     {'name': 'Twister', 'key': 'twister', 'source': 'popular', 'usage_count': 10},
        ...     {'name': 'Movie Poster', 'key': 'movie-poster', 'source': 'refined'},
        ...     {'name': 'The Twisters', 'key': 'the-twisters', 'source': 'refined'}
        ... ]
        >>> ranked = rank_by_canonical_match(
        ...     suggestions,
        ...     caption_title="The Twisters Movie Poster",
        ...     caption_visible_text="THE TWISTERS"
        ... )
        >>> ranked[0]['name']
        'The Twisters'  # Canonical match moved to #1
    """
    if not suggestions:
        return suggestions

    if not caption_title and not caption_visible_text:
        logger.debug("No caption data for ranking, returning suggestions as-is")
        return suggestions

    # Normalize canonical text for matching (lowercase, remove extra whitespace)
    def normalize(text: Optional[str]) -> str:
        if not text:
            return ""
        return " ".join(text.lower().strip().split())

    canonical_texts = []
    if caption_title:
        canonical_texts.append(normalize(caption_title))
    if caption_visible_text:
        canonical_texts.append(normalize(caption_visible_text))

    logger.debug(f"Canonical texts for matching: {canonical_texts}")

    # Find best matching suggestion
    best_match_idx = None
    best_match_score = 0

    for idx, suggestion in enumerate(suggestions):
        name = normalize(suggestion.get('name', ''))
        key = normalize(suggestion.get('key', '').replace('-', ' '))
        source = suggestion.get('source', '')

        # Calculate match score (simple substring matching)
        score = 0
        for canonical in canonical_texts:
            # Exact match (highest priority)
            if name == canonical or key == canonical:
                score += 100
            # Name is substring of canonical (e.g., "Jim Beam" in "Jim Beam Bourbon Bottle")
            elif name and canonical and name in canonical:
                score += 50
            # Canonical is substring of name (e.g., "Twisters" in "The Twisters")
            elif canonical and name and canonical in name:
                score += 40
            # Key matches canonical
            elif key and canonical and key == canonical:
                score += 30

        # Update best match
        if score > best_match_score:
            # New high score - always update
            best_match_score = score
            best_match_idx = idx
        elif score == best_match_score:
            # Tie-breaker: prefer 'refined' over 'popular', but only break tie once
            # This ensures AI-generated suggestions for THIS photo rank higher
            # than popular suggestions, while keeping first-wins for same-type ties
            current_best_source = suggestions[best_match_idx].get('source', '') if best_match_idx is not None else ''
            if current_best_source != 'refined' and source == 'refined':
                best_match_idx = idx

    # If we found a match, move it to #1
    if best_match_idx is not None and best_match_score > 0:
        matched_suggestion = suggestions[best_match_idx]
        source = matched_suggestion.get('source', 'unknown')
        logger.info(
            f"Canonical match found: '{matched_suggestion['name']}' (score={best_match_score}, source={source}) "
            f"→ moving from position #{best_match_idx + 1} to #1"
        )

        # Move matched suggestion to position #1
        ranked_suggestions = [matched_suggestion] + suggestions[:best_match_idx] + suggestions[best_match_idx + 1:]
        return ranked_suggestions
    else:
        logger.debug("No strong canonical match found, keeping original order")
        return suggestions
