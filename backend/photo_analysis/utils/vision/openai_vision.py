"""
OpenAI Vision API client for photo analysis.
Uses GPT-4o (or other vision-capable models) to analyze images.
"""
import base64
import json
import io
from typing import BinaryIO, Optional
from PIL import Image

from django.conf import settings
from openai import OpenAI

from .base import VisionProvider, AnalysisResult, ChatSuggestion


class OpenAIVisionProvider(VisionProvider):
    """OpenAI Vision API provider implementation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize OpenAI Vision provider.

        Args:
            api_key: OpenAI API key (defaults to settings.OPENAI_API_KEY)
            model: Model to use (default: gpt-4o)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def is_available(self) -> bool:
        """Check if OpenAI API is configured."""
        return bool(self.api_key and self.client)

    def get_model_name(self) -> str:
        """Get the model identifier."""
        return self.model

    def _encode_image_to_base64(self, image_file: BinaryIO, max_size: int = 768) -> str:
        """
        Encode image to base64 string with optional resizing.

        Args:
            image_file: Image file to encode
            max_size: Maximum width/height (default: 768 for text readability)

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

            # Open and resize image
            import logging
            logger = logging.getLogger(__name__)

            img = Image.open(io.BytesIO(image_data))
            original_width, original_height = img.size
            original_megapixels = (original_width * original_height) / 1_000_000

            # Convert RGBA to RGB (JPEG doesn't support transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize if larger than max_size
            if original_width > max_size or original_height > max_size:
                # Calculate new size maintaining aspect ratio
                if original_width > original_height:
                    new_width = max_size
                    new_height = int(original_height * (max_size / original_width))
                else:
                    new_height = max_size
                    new_width = int(original_width * (max_size / original_height))

                # Resize with high-quality resampling
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save resized image to bytes
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                image_data = output.getvalue()

                logger.info(f"Resized image: {original_width}x{original_height} ({original_megapixels:.2f}MP) → {new_width}x{new_height}, base64 size: {len(image_data)} bytes")
            else:
                # Still need to convert to JPEG even if not resizing
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=85, optimize=True)
                image_data = output.getvalue()
                logger.info(f"Image within size limit: {original_width}x{original_height} ({original_megapixels:.2f}MP), base64 size: {len(image_data)} bytes")

            # Encode to base64
            return base64.b64encode(image_data).decode('utf-8')

        except Exception as e:
            raise ValueError(f"Failed to encode image: {str(e)}")

    def _parse_suggestions_from_response(self, content: str) -> list[ChatSuggestion]:
        """
        Parse chat suggestions from API response.

        Args:
            content: Response content from API

        Returns:
            List of ChatSuggestion objects

        Raises:
            ValueError: If response cannot be parsed
        """
        try:
            # Try to find JSON in the response
            # Sometimes the model wraps JSON in markdown code blocks
            content = content.strip()

            # Remove markdown code blocks if present
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json
            elif content.startswith('```'):
                content = content[3:]  # Remove ```

            if content.endswith('```'):
                content = content[:-3]  # Remove trailing ```

            content = content.strip()

            # Parse JSON
            data = json.loads(content)

            # Extract suggestions
            suggestions_data = data.get('suggestions', [])

            if not isinstance(suggestions_data, list):
                raise ValueError("Suggestions must be a list")

            suggestions = []
            for item in suggestions_data:
                if not isinstance(item, dict):
                    continue

                name = item.get('name', '').strip()
                key = item.get('key', '').strip()
                description = item.get('description', '').strip()
                is_proper_noun = item.get('is_proper_noun', False)

                if name and key:  # Require at least name and key
                    suggestions.append(ChatSuggestion(
                        name=name,
                        key=key,
                        description=description or f"Chat about {name.lower()}",
                        is_proper_noun=is_proper_noun
                    ))

            return suggestions

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {str(e)}\nContent: {content[:200]}")
        except Exception as e:
            raise ValueError(f"Failed to parse suggestions: {str(e)}")

    def analyze_image(
        self,
        image_file: BinaryIO,
        prompt: str,
        max_suggestions: int = 10,
        temperature: float = 0.7
    ) -> AnalysisResult:
        """
        Analyze an image using OpenAI Vision API.

        Args:
            image_file: Image file to analyze
            prompt: System prompt for analysis
            max_suggestions: Number of suggestions to generate
            temperature: Sampling temperature (0.0-2.0, default 0.7)

        Returns:
            AnalysisResult with suggestions and metadata

        Raises:
            ValueError: If image cannot be processed
            RuntimeError: If API call fails
        """
        if not self.is_available():
            raise RuntimeError("OpenAI API key not configured")

        try:
            # Get detail mode from Constance settings
            from constance import config
            detail_mode = config.PHOTO_ANALYSIS_DETAIL_MODE or "low"

            # Encode image to base64
            base64_image = self._encode_image_to_base64(image_file)

            # Prepare the API call
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
                                "detail": detail_mode  # Configurable via Constance: "low" or "high"
                            }
                        }
                    ]
                }
            ]

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=temperature,  # Configurable temperature from Constance
                response_format={"type": "json_object"}  # Force JSON output
            )

            # Extract response content
            content = response.choices[0].message.content

            # Parse suggestions
            suggestions = self._parse_suggestions_from_response(content)

            # Limit to max_suggestions
            suggestions = suggestions[:max_suggestions]

            # Extract token usage
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

            # Prepare raw response (convert to dict for JSON serialization)
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

            return AnalysisResult(
                suggestions=suggestions,
                raw_response=raw_response,
                token_usage=token_usage,
                model=self.model
            )

        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")


# Factory function to get the default vision provider
def get_vision_provider(model: Optional[str] = None) -> VisionProvider:
    """
    Get the default vision provider.

    Args:
        model: Optional model name to use (defaults to settings or "gpt-4o")

    Returns:
        Configured VisionProvider instance

    Example:
        >>> provider = get_vision_provider()
        >>> result = provider.analyze_image(image_file, prompt)
    """
    # For now, we only support OpenAI
    # In the future, we could add support for Claude, Gemini, etc.
    model = model or getattr(settings, 'PHOTO_ANALYSIS_OPENAI_MODEL', 'gpt-4o-mini')
    return OpenAIVisionProvider(model=model)
