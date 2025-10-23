"""
Caption generation utility for photo analysis.
Generates semantic captions optimized for text embedding models.
"""
import base64
import json
import io
import logging
from typing import BinaryIO, Optional, Dict, Any
from PIL import Image

from django.conf import settings
from openai import OpenAI
from constance import config

logger = logging.getLogger(__name__)


class CaptionData:
    """Caption generation result."""

    def __init__(
        self,
        title: str,
        category: str,
        visible_text: str,
        caption: str,
        raw_response: Optional[Dict[str, Any]] = None,
        token_usage: Optional[Dict[str, int]] = None,
        model: str = "gpt-4o-mini"
    ):
        self.title = title
        self.category = category
        self.visible_text = visible_text
        self.caption = caption
        self.raw_response = raw_response or {}
        self.token_usage = token_usage or {}
        self.model = model

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for storage."""
        return {
            'title': self.title,
            'category': self.category,
            'visible_text': self.visible_text,
            'caption': self.caption
        }


def _encode_image_to_base64(image_file: BinaryIO) -> str:
    """
    Encode image to base64 string.

    Args:
        image_file: Image file to encode

    Returns:
        Base64-encoded image string

    Raises:
        ValueError: If image cannot be encoded
    """
    try:
        # Ensure we're at the beginning of the file
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        # Read and validate image
        image_data = image_file.read()

        # Verify it's a valid image
        try:
            img = Image.open(io.BytesIO(image_data))
            width, height = img.size
            megapixels = (width * height) / 1_000_000
            logger.info(
                f"Encoding image for caption generation: {width}x{height} "
                f"({megapixels:.2f}MP), size: {len(image_data)} bytes"
            )
            img.verify()
        except Exception as e:
            raise ValueError(f"Invalid image file: {str(e)}")

        # Encode to base64
        return base64.b64encode(image_data).decode('utf-8')

    except Exception as e:
        raise ValueError(f"Failed to encode image: {str(e)}")


def _parse_caption_response(content: str) -> Dict[str, str]:
    """
    Parse caption data from API response.

    Args:
        content: Response content from API

    Returns:
        Dictionary with title, category, visible_text, and caption

    Raises:
        ValueError: If response cannot be parsed
    """
    try:
        # Remove markdown code blocks if present
        content = content.strip()

        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]

        if content.endswith('```'):
            content = content[:-3]

        content = content.strip()

        # Parse JSON
        data = json.loads(content)

        # Extract required fields
        title = data.get('title', '').strip()
        category = data.get('category', '').strip()
        visible_text = data.get('visible_text', '').strip()
        caption = data.get('caption', '').strip()

        if not caption:
            raise ValueError("Caption field is required but was empty")

        return {
            'title': title,
            'category': category,
            'visible_text': visible_text,
            'caption': caption
        }

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Failed to parse JSON response: {str(e)}\n"
            f"Content: {content[:200]}"
        )
    except Exception as e:
        raise ValueError(f"Failed to parse caption response: {str(e)}")


def generate_caption(
    image_file: BinaryIO,
    model: Optional[str] = None,
    prompt: Optional[str] = None,
    temperature: Optional[float] = None
) -> CaptionData:
    """
    Generate a semantic caption for an image using OpenAI Vision API.

    This function generates structured caption data optimized for text
    embedding models. The caption includes:
    - A short title (2-4 words)
    - Category classification
    - Visible text/labels in the image
    - Full semantic description (1-2 sentences)

    Args:
        image_file: Image file (BinaryIO) to analyze
        model: Optional model override (defaults to PHOTO_ANALYSIS_CAPTION_MODEL)
        prompt: Optional prompt override (defaults to PHOTO_ANALYSIS_CAPTION_PROMPT)
        temperature: Optional temperature override (defaults to PHOTO_ANALYSIS_CAPTION_TEMPERATURE)

    Returns:
        CaptionData object with title, category, visible_text, caption, and metadata

    Raises:
        RuntimeError: If OpenAI API key not configured or API call fails
        ValueError: If image cannot be processed or response cannot be parsed

    Example:
        >>> with open('beer.jpg', 'rb') as f:
        ...     caption_data = generate_caption(f)
        ...     print(caption_data.title)
        'Budweiser Beer Bottle'
        ...     print(caption_data.caption)
        'Budweiser beer bottle labeled King of Beers...'
    """
    # Check if captions are enabled
    if not config.PHOTO_ANALYSIS_ENABLE_CAPTIONS:
        raise RuntimeError("Caption generation is disabled in settings")

    # Check API key
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OpenAI API key not configured")

    # Get configuration from Constance
    model = model or config.PHOTO_ANALYSIS_CAPTION_MODEL
    prompt = prompt or config.PHOTO_ANALYSIS_CAPTION_PROMPT
    temperature = temperature if temperature is not None else config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE
    detail_mode = config.PHOTO_ANALYSIS_DETAIL_MODE or "low"

    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)

        # Encode image to base64
        base64_image = _encode_image_to_base64(image_file)

        # Prepare API call
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                            "detail": detail_mode
                        }
                    }
                ]
            }
        ]

        # Call OpenAI API
        logger.info(
            f"Generating caption with model={model}, "
            f"temperature={temperature}, detail={detail_mode}"
        )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,  # Captions are shorter than suggestions
            temperature=temperature,
            response_format={"type": "json_object"}  # Force JSON output
        )

        # Extract response content
        content = response.choices[0].message.content

        # Parse caption data
        caption_dict = _parse_caption_response(content)

        # Extract token usage
        token_usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        # Prepare raw response
        raw_response = {
            "model": response.model,
            "created": response.created,
            "choices": [
                {
                    "index": choice.index,
                    "message": {
                        "role": choice.message.role,
                        "content": choice.message.content
                    },
                    "finish_reason": choice.finish_reason
                }
                for choice in response.choices
            ],
            "usage": token_usage
        }

        logger.info(
            f"Caption generated successfully: title='{caption_dict['title']}', "
            f"tokens={token_usage['total_tokens']}"
        )

        return CaptionData(
            title=caption_dict['title'],
            category=caption_dict['category'],
            visible_text=caption_dict['visible_text'],
            caption=caption_dict['caption'],
            raw_response=raw_response,
            token_usage=token_usage,
            model=model
        )

    except Exception as e:
        logger.error(f"Caption generation failed: {str(e)}")
        raise RuntimeError(f"Caption generation failed: {str(e)}")
