"""
Embedding generation utility for photo analysis.
Generates semantic embeddings from image captions using OpenAI's text-embedding models.
"""

import logging
from typing import Any, Dict, List, Optional

from django.conf import settings
from openai import OpenAI

from .performance import perf_track

logger = logging.getLogger(__name__)


class EmbeddingData:
    """Embedding generation result."""

    def __init__(self, embedding: List[float], model: str, token_usage: Dict[str, int], input_text: str):
        self.embedding = embedding
        self.model = model
        self.token_usage = token_usage
        self.input_text = input_text


def _combine_caption_fields(
    caption_full: str, caption_visible_text: str, caption_title: str, caption_category: str
) -> str:
    """
    Combine caption fields into a single text string for embedding.

    Combines in order: title, category, visible_text, full caption.
    Filters out empty fields automatically.

    Args:
        caption_full: Full semantic caption
        caption_visible_text: Visible text extracted from image
        caption_title: Short title
        caption_category: Category classification

    Returns:
        Combined text string optimized for embedding generation

    Example:
        >>> _combine_caption_fields(
        ...     caption_full="Budweiser beer bottle...",
        ...     caption_visible_text="Budweiser, King of Beers",
        ...     caption_title="Budweiser Beer Bottle",
        ...     caption_category="beer bottle"
        ... )
        'Budweiser Beer Bottle. beer bottle. Budweiser, King of Beers. Budweiser beer bottle...'
    """
    # Combine fields in priority order: title → category → visible_text → full caption
    # This ensures the most important information appears first for embedding models
    parts = []

    if caption_title:
        parts.append(caption_title.strip())

    if caption_category:
        parts.append(caption_category.strip())

    if caption_visible_text:
        parts.append(caption_visible_text.strip())

    if caption_full:
        parts.append(caption_full.strip())

    # Join with periods for natural sentence flow
    combined = ". ".join(parts)

    logger.debug(f"Combined caption fields: {len(parts)} parts, " f"{len(combined)} characters")

    return combined


def generate_embedding(
    caption_full: str,
    caption_visible_text: str = "",
    caption_title: str = "",
    caption_category: str = "",
    model: str = "text-embedding-3-small",
) -> EmbeddingData:
    """
    Generate semantic embedding from caption fields using OpenAI Embeddings API.

    This function combines the caption fields and generates a 1536-dimensional
    vector embedding using text-embedding-3-small model. The embedding is used
    for similarity search to find related photos and reduce chat room fragmentation.

    Args:
        caption_full: Full semantic caption (required)
        caption_visible_text: Visible text/labels from image (optional)
        caption_title: Short title (optional)
        caption_category: Category classification (optional)
        model: OpenAI embedding model (default: text-embedding-3-small)

    Returns:
        EmbeddingData object with embedding vector, model info, and token usage

    Raises:
        RuntimeError: If OpenAI API key not configured or API call fails
        ValueError: If caption_full is empty

    Example:
        >>> embedding_data = generate_embedding(
        ...     caption_full="Budweiser beer bottle labeled King of Beers...",
        ...     caption_visible_text="Budweiser, King of Beers",
        ...     caption_title="Budweiser Beer Bottle",
        ...     caption_category="beer bottle"
        ... )
        >>> len(embedding_data.embedding)
        1536
        >>> embedding_data.model
        'text-embedding-3-small'
    """
    # Validate required field
    if not caption_full or not caption_full.strip():
        raise ValueError("caption_full is required for embedding generation")

    # Check API key
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Combine caption fields into single text string
        input_text = _combine_caption_fields(
            caption_full=caption_full,
            caption_visible_text=caption_visible_text,
            caption_title=caption_title,
            caption_category=caption_category,
        )

        logger.info(f"Generating embedding with model={model}, " f"input_length={len(input_text)} chars")

        # Call OpenAI Embeddings API
        with perf_track(f"Caption embedding API ({model})"):
            response = client.embeddings.create(input=input_text, model=model)

        # Extract embedding vector
        embedding = response.data[0].embedding

        # Extract token usage
        token_usage = {"prompt_tokens": response.usage.prompt_tokens, "total_tokens": response.usage.total_tokens}

        logger.info(
            f"Embedding generated successfully: "
            f"dimensions={len(embedding)}, "
            f"tokens={token_usage['total_tokens']}, "
            f"model={response.model}"
        )

        return EmbeddingData(embedding=embedding, model=response.model, token_usage=token_usage, input_text=input_text)

    except Exception as e:
        logger.error(f"Embedding generation failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"Embedding generation failed: {str(e)}")


def _combine_suggestions_only(suggestions: List[Dict[str, str]]) -> str:
    """
    Combine suggestion names and descriptions for conversational/topic embedding.

    This creates the input text for Embedding 2 (Conversational/Topic embedding),
    which groups photos by conversation potential and social context, NOT by visual content.

    Args:
        suggestions: List of suggestion dicts with 'name' and 'description' keys

    Returns:
        Combined text string of all suggestion names and descriptions

    Example:
        >>> suggestions = [
        ...     {"name": "Bar Room", "description": "Discuss favorite beers and breweries"},
        ...     {"name": "Happy Hour", "description": "Share cocktail recipes and bar stories"}
        ... ]
        >>> _combine_suggestions_only(suggestions)
        'Bar Room. Discuss favorite beers and breweries. Happy Hour. Share cocktail recipes and bar stories.'
    """
    parts = []

    # Add ALL suggestion names and descriptions
    # This enables clustering by conversation topics (e.g., "Bar Room", "Happy Hour")
    # rather than visual content (e.g., "beer bottle", "bar photo")
    for suggestion in suggestions:
        name = suggestion.get("name", "").strip()
        description = suggestion.get("description", "").strip()

        if name:
            parts.append(name)
        if description:
            parts.append(description)

    # Join with periods for natural sentence flow
    combined = ". ".join(parts)

    logger.debug(
        f"Combined suggestions only: {len(parts)} parts, "
        f"{len(suggestions)} suggestions, {len(combined)} characters"
    )

    return combined


def generate_suggestions_embedding(
    caption_full: str,
    caption_visible_text: str,
    caption_title: str,
    caption_category: str,
    suggestions: List[Dict[str, str]],
    model: str = "text-embedding-3-small",
) -> EmbeddingData:
    """
    Generate conversational/topic embedding from caption fields + ALL suggestion names/descriptions.

    This is Embedding 2 (PRIMARY for collaborative discovery). It groups photos by
    conversation potential and social context rather than just visual content.

    Why: "bar-room", "happy-hour", "brew-talk" all cluster in the same semantic space,
    enabling collaborative discovery where Person B uploading a similar photo sees
    existing rooms like "bar-room (1 user)" as recommendations.

    Args:
        caption_full: Full semantic caption (required)
        caption_visible_text: Visible text/labels from image (optional)
        caption_title: Short title (optional)
        caption_category: Category classification (optional)
        suggestions: List of suggestion dicts with 'name' and 'description' keys (required)
        model: OpenAI embedding model (default: text-embedding-3-small)

    Returns:
        EmbeddingData object with embedding vector, model info, and token usage

    Raises:
        RuntimeError: If OpenAI API key not configured or API call fails
        ValueError: If caption_full is empty or suggestions list is empty

    Example:
        >>> suggestions = [
        ...     {"name": "Bar Room", "key": "bar-room", "description": "Discuss favorite beers"},
        ...     {"name": "Happy Hour", "key": "happy-hour", "description": "Share bar stories"}
        ... ]
        >>> embedding_data = generate_suggestions_embedding(
        ...     caption_full="Budweiser beer bottle labeled King of Beers...",
        ...     caption_visible_text="Budweiser, King of Beers",
        ...     caption_title="Budweiser Beer Bottle",
        ...     caption_category="beer bottle",
        ...     suggestions=suggestions
        ... )
        >>> len(embedding_data.embedding)
        1536
        >>> embedding_data.model
        'text-embedding-3-small'
    """
    # Validate required fields
    if not caption_full or not caption_full.strip():
        raise ValueError("caption_full is required for embedding generation")

    if not suggestions or len(suggestions) == 0:
        raise ValueError("suggestions list cannot be empty for suggestions embedding")

    # Check API key
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Combine ALL suggestions (names + descriptions) for topic/conversation embedding
        # Caption fields are NOT used here - this is intentional for collaborative discovery
        input_text = _combine_suggestions_only(suggestions=suggestions)

        logger.info(
            f"Generating suggestions embedding with model={model}, "
            f"input_length={len(input_text)} chars, "
            f"suggestions_count={len(suggestions)}"
        )

        # Call OpenAI Embeddings API
        with perf_track(f"Suggestions embedding API ({model})"):
            response = client.embeddings.create(input=input_text, model=model)

        # Extract embedding vector
        embedding = response.data[0].embedding

        # Extract token usage
        token_usage = {"prompt_tokens": response.usage.prompt_tokens, "total_tokens": response.usage.total_tokens}

        logger.info(
            f"Suggestions embedding generated successfully: "
            f"dimensions={len(embedding)}, "
            f"tokens={token_usage['total_tokens']}, "
            f"model={response.model}"
        )

        return EmbeddingData(embedding=embedding, model=response.model, token_usage=token_usage, input_text=input_text)

    except Exception as e:
        logger.error(f"Suggestions embedding generation failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"Suggestions embedding generation failed: {str(e)}")
