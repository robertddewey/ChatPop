"""
LLM-based suggestion refinement for deduplication.

Removes semantic duplicates while preserving distinct entities using GPT-4o-mini.
Solves the "Twister vs Twisters" problem by providing full context to the LLM.
"""

import json
import logging
from typing import Any, Dict, List

from django.conf import settings
from django.db.models import Count
from openai import OpenAI

from .performance import perf_track

logger = logging.getLogger(__name__)

# Refinement configuration (hardcoded sensible defaults)
REFINEMENT_MODEL = "gpt-4o-mini"
REFINEMENT_TEMPERATURE = 0.3
REFINEMENT_MIN_SUGGESTIONS = 5
REFINEMENT_MAX_SUGGESTIONS = 7
REFINEMENT_K_NEAREST_NEIGHBORS = 10  # Number of similar photos to fetch for popular suggestions

# Refinement prompt template
REFINEMENT_PROMPT_TEMPLATE = """Refine {seed_count} AI-generated chat room suggestions to {min_suggestions}-{max_suggestions} distinct, high-quality names.

PHOTO CONTEXT:
Title: {caption_title} | Category: {caption_category} | Caption: {caption_full} | Visible Text: {caption_visible_text}

INPUT: {seed_suggestions}

RULES:
1. DUPLICATES: Remove semantically identical suggestions. Ask: "Would these attract the same people having the same conversation?" If yes, keep only one. Prefer 'popular' source over 'seed'.

2. DISTINCT ENTITIES: Keep different proper nouns (Star Wars ≠ Star Trek, Budweiser ≠ Miller). They're distinct even if related.

3. DIVERSITY: Ensure different aspects of photo, not just synonyms. "Brewery Tour" + "Beer Tasting" = diverse (location + activity). "Excitement" + "Thrills" = redundant.

4. PROPER NOUNS: Restore canonical names from context. "Matrix Fans" + caption "The Matrix movie poster" → "The Matrix". Use official titles, include "The" if part of name, add year for disambiguation (e.g., "The Matrix (1999)").

5. PROPER NOUN DETECTION: Mark "is_proper_noun": true for specific named entities:
   - Movies/Shows: "The Matrix (1999)", "Twister (1996)", "Twisters (2024)"
   - Brands: "Budweiser", "Apple", "Nike"
   - Products: "iPhone 15 Pro", "Tesla Model 3"
   - Named Places: "Eiffel Tower", "Grand Canyon"
   Mark "is_proper_noun": false for generic topics: "Coffee Chat", "Beer Tasting", "Cat Lovers"

6. SOURCE TRACKING:
   - Keep unchanged → preserve original source
   - Merge same source → preserve that source
   - Merge different sources → mark 'refined'

OUTPUT (JSON):
{{
  "refined_suggestions": [
    {{"name": "Chat Name", "key": "chat-name", "description": "Brief topic description", "source": "popular|seed|refined", "is_proper_noun": true|false}}
  ]
}}"""


def refine_suggestions(
    seed_suggestions: List[Dict[str, str]],
    caption_title: str = "",
    caption_category: str = "",
    caption_full: str = "",
    caption_visible_text: str = "",
    similar_photo_popular: List[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Refine seed suggestions using GPT-4o-mini to remove duplicates
    while preserving distinct entities.

    This function passes full photo context to the LLM, enabling it to:
    - Remove true semantic duplicates ("Bar Room" vs "Drinking Lounge")
    - Preserve distinct entities ("Twister" (1996) vs "Twisters" (2024))
    - Restore proper nouns ("Matrix Fans" → "The Matrix" for movie posters)
    - Prefer existing popular suggestions for consistency

    Args:
        seed_suggestions: 10 initial AI suggestions from GPT-4 Vision
        caption_title: Photo title
        caption_category: Photo category
        caption_full: Full semantic caption
        caption_visible_text: Visible text in image

    Returns:
        5-7 refined distinct suggestions

    Raises:
        RuntimeError: If OpenAI API key not configured or API call fails

    Example:
        >>> seed = [
        ...     {"name": "Bar Room", "key": "bar-room", "description": "..."},
        ...     {"name": "Drinking Lounge", "key": "drinking-lounge", "description": "..."},
        ...     {"name": "Happy Hour", "key": "happy-hour", "description": "..."}
        ... ]
        >>> refined = refine_suggestions(seed, caption_title="Budweiser Beer Bottle")
        >>> len(refined)  # Returns 5-7 suggestions
        6
        >>> refined[0]['name']  # "Bar Room" or similar (duplicates merged)
        'Bar Room'
    """
    # Validate required field
    if not seed_suggestions or len(seed_suggestions) == 0:
        raise ValueError("seed_suggestions cannot be empty")

    # Check API key
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Format seed suggestions for prompt
        seed_formatted = json.dumps(seed_suggestions, indent=2)
        seed_count = len(seed_suggestions)

        # Build prompt with template variables (no popular suggestions - three-tier approach)
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            caption_title=caption_title or "N/A",
            caption_category=caption_category or "N/A",
            caption_full=caption_full or "N/A",
            caption_visible_text=caption_visible_text or "N/A",
            seed_count=seed_count,
            seed_suggestions=seed_formatted,
            min_suggestions=REFINEMENT_MIN_SUGGESTIONS,
            max_suggestions=REFINEMENT_MAX_SUGGESTIONS,
        )

        logger.info(
            f"Refining {seed_count} seed suggestions with {REFINEMENT_MODEL} "
            f"(temp={REFINEMENT_TEMPERATURE}, target={REFINEMENT_MIN_SUGGESTIONS}-{REFINEMENT_MAX_SUGGESTIONS})"
        )

        # Call OpenAI Chat Completions API
        with perf_track(f"Refinement LLM API ({REFINEMENT_MODEL})", metadata=f"{seed_count} input"):
            response = client.chat.completions.create(
                model=REFINEMENT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=REFINEMENT_TEMPERATURE,
            )

        # Extract refined suggestions from JSON response
        result = json.loads(response.choices[0].message.content)
        refined = result.get("refined_suggestions", [])

        logger.info(
            f"Refinement complete: {seed_count} → {len(refined)} suggestions "
            f"(removed {seed_count - len(refined)} duplicates)"
        )

        # Validate output
        if not refined or len(refined) < REFINEMENT_MIN_SUGGESTIONS:
            logger.warning(
                f"Refinement returned {len(refined)} suggestions, "
                f"expected {REFINEMENT_MIN_SUGGESTIONS}-{REFINEMENT_MAX_SUGGESTIONS}. Using seed suggestions as fallback."
            )
            return seed_suggestions[:REFINEMENT_MAX_SUGGESTIONS]

        return refined

    except Exception as e:
        logger.error(f"Suggestion refinement failed: {str(e)}", exc_info=True)
        # Fallback to seed suggestions if refinement fails
        logger.warning(f"Using seed suggestions as fallback due to error: {str(e)}")
        return seed_suggestions


def get_popular_suggestions(limit: int = 20) -> List[Dict[str, str]]:
    """
    Get most popular suggestions across all users.

    Used to inform refinement - if a seed suggestion matches a popular existing one,
    the LLM is instructed to prefer the popular variant for clustering consistency.

    Args:
        limit: Maximum number of popular suggestions to return (default: 20)

    Returns:
        List of popular suggestions with usage counts

    Example:
        >>> popular = get_popular_suggestions(limit=5)
        >>> popular[0]
        {'name': 'Coffee Chat', 'key': 'coffee-chat', 'usage_count': 42}
    """
    try:
        from chats.models import ChatRoom

        # Count code usage across all rooms
        # Groups by code and name, orders by frequency
        popular = (
            ChatRoom.objects.exclude(code__isnull=True)
            .exclude(code="")
            .values("code", "name")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )

        result = [{"name": item["name"], "key": item["code"], "usage_count": item["count"]} for item in popular]

        logger.debug(f"Retrieved {len(result)} popular suggestions for refinement context")
        return result

    except Exception as e:
        logger.warning(f"Failed to get popular suggestions: {str(e)}")
        # Return empty list if query fails (non-fatal)
        return []
