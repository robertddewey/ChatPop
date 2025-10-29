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
REFINEMENT_PROMPT_TEMPLATE = """You are refining AI-generated chat room suggestions for a photo-based social app.

PHOTO CONTEXT:
- Title: {caption_title}
- Category: {caption_category}
- Full Caption: {caption_full}
- Visible Text: {caption_visible_text}

INPUT SUGGESTIONS ({seed_count} suggestions - mix of popular and seed):
{seed_suggestions}

NOTE: Input suggestions are marked with 'source':
- 'popular' = From similar photos uploaded by other users (collaborative discovery)
- 'seed' = Fresh AI-generated suggestions for this specific photo

YOUR TASK:
Refine the input suggestions to {min_suggestions}-{max_suggestions} distinct, high-quality chat room names.

RULES:
1. Remove TRUE DUPLICATES - merge semantically identical suggestions

   A. EXACT DUPLICATES - identical name with identical key from different sources:
      - If same suggestion appears in BOTH popular and seed → Always keep the popular version
      - Example: "Cheers!" (popular, key: cheers) + "Cheers!" (seed, key: cheers) → Keep "Cheers!" with source: "popular"
      - Punctuation variations: "Cheers" vs "Cheers!" with same key → Keep one consistent form (prefer with punctuation)
      - Wrong: Marking exact duplicates as "preserved_distinct_entity" (they're identical, not distinct!)

   B. SEMANTIC DUPLICATES - generic phrases describing same topic with different words:
      Critical question: "Would these attract the SAME people having the SAME conversation?"
      - If YES → They're duplicates, keep only 1
      - If NO → They're distinct topics, keep both

2. Preserve DISTINCT ENTITIES - specific named entities are NOT duplicates

   Different proper nouns refer to different real-world things, even if related.
   Example: "Star Wars" vs "Star Trek" → Keep both (different franchises)
   Example: "Budweiser" vs "Miller" → Keep both (different brands)

3. Maintain DIVERSE TOPICS - ensure refined suggestions cover different conversation angles

   Diversity means different ASPECTS of the photo, not just different ADJECTIVES.
   Example: "Brewery Tour" (location) vs "Beer Tasting" (activity) → Keep both (different aspects)

   Not diverse: Multiple generic reactions to the same thing (excitement, thrills, chaos, action)

4. RESTORE PROPER NOUNS - use full canonical names for specific entities
   Example: Seed "Matrix Fans" + Caption "The Matrix movie poster" → "The Matrix" or "The Matrix (1999)"
   Example: Seed "Godfather Talk" + Visible Text "THE GODFATHER" → "The Godfather"
   Example: Seed "Beatles Music" + Caption "The Beatles album cover" → "The Beatles"

   When to restore proper nouns:
   - Movie/TV titles: Use official title from caption/visible text (include "The" if part of title)
   - Book titles: Use full canonical title
   - Band/artist names: Use official name (include "The" if part of name)
   - Brand/product names: Preserve exact spelling from visible text
   - Add year/edition for disambiguation when helpful: "The Matrix (1999)", "The Office (US)"

   Clues that suggest proper nouns:
   - category contains: "movie poster", "album cover", "book cover", "product", "logo"
   - visible_text contains: ALL CAPS TEXT (often brand/title)
   - caption mentions: "titled", "called", "featuring", "by [artist]", "[year]"

5. General suggestions can omit articles and stay concise
   Example: "Bar Room", "Happy Hour", "Craft Beer" (generic topics, no articles needed)
   Example: "Coffee Lovers", "Recipe Exchange", "Travel Stories" (generic, stay concise)

6. PRESERVE SOURCE TRACKING - include 'source' field in your output
   - If you keep a suggestion unchanged, preserve its original source ('popular' or 'seed')
   - If you merge/modify suggestions from DIFFERENT sources, mark as 'refined'
   - If you merge/modify suggestions from SAME source, preserve that source

   Examples:
   - Keep "Cheers!" from popular suggestions → source: "popular"
   - Merge "Bar Room" (seed) + "Drinking Lounge" (seed) → "Bar Room" with source: "seed"
   - Merge "Jim Beam" (popular) + "Bourbon Bottles" (seed) → "Jim Beam" with source: "refined"
   - Restore proper noun "Matrix Fans" (seed) → "The Matrix" with source: "seed"

OUTPUT FORMAT (JSON):
{{
  "refined_suggestions": [
    {{
      "name": "Chat Name",
      "key": "chat-name",
      "description": "Brief description of chat topic",
      "source": "popular|seed|refined",
      "reasoning": "Why this suggestion was kept (removed_duplicates: [...] or preserved_distinct_entity or matched_popular_suggestion or restored_proper_noun: 'original → canonical')"
    }}
  ],
  "removed_duplicates": [
    {{
      "removed": "Similar Suggestion",
      "kept_instead": "Final Suggestion",
      "reason": "Explanation"
    }}
  ]
}}

Return {min_suggestions}-{max_suggestions} refined suggestions that maximize diversity while removing true duplicates and restoring proper nouns where appropriate."""


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
