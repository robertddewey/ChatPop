"""
Image processing utilities for photo analysis.
"""
import io
import math
import logging
from typing import BinaryIO, Tuple
from PIL import Image

logger = logging.getLogger(__name__)


def resize_image_if_needed(
    image_file: BinaryIO,
    max_megapixels: float
) -> Tuple[io.BytesIO, bool]:
    """
    Resize image if it exceeds the maximum megapixel limit.

    This reduces token usage when sending images to OpenAI Vision API
    by ensuring the base64 payload isn't unnecessarily large.

    Args:
        image_file: Image file to potentially resize
        max_megapixels: Maximum megapixels (e.g., 2.0 = 2 million pixels)

    Returns:
        Tuple of (image_bytes_io, was_resized)
        - image_bytes_io: BytesIO containing the image (original or resized)
        - was_resized: Boolean indicating if resize was performed

    Raises:
        ValueError: If image cannot be processed

    Example:
        >>> with open('large_image.jpg', 'rb') as f:
        >>>     resized, was_resized = resize_image_if_needed(f, 2.0)
        >>>     if was_resized:
        >>>         print("Image was resized to reduce token usage")
    """
    try:
        # Ensure we're at the beginning of the file
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        # Read and open image
        image_data = image_file.read()
        img = Image.open(io.BytesIO(image_data))

        # Calculate current megapixels
        width, height = img.size
        current_megapixels = (width * height) / 1_000_000

        logger.info(f"Image dimensions: {width}x{height} ({current_megapixels:.2f}MP), max allowed: {max_megapixels}MP")

        # Check if resize is needed
        if current_megapixels <= max_megapixels:
            # No resize needed - return original
            logger.info(f"No resize needed - image is within limit")
            return io.BytesIO(image_data), False

        # Calculate scale factor to reach target megapixels
        scale = math.sqrt(max_megapixels / current_megapixels)
        new_width = int(width * scale)
        new_height = int(height * scale)

        logger.info(f"Resizing from {width}x{height} to {new_width}x{new_height} (scale: {scale:.3f})")

        # Resize image using high-quality LANCZOS resampling
        resized_img = img.resize((new_width, new_height), Image.LANCZOS)

        # Determine output format (preserve original format if possible)
        output_format = img.format or 'JPEG'
        if output_format not in ['JPEG', 'PNG', 'WEBP']:
            output_format = 'JPEG'  # Default to JPEG for unsupported formats

        # Save resized image to BytesIO
        output = io.BytesIO()

        # Handle different formats appropriately
        if output_format == 'JPEG':
            # Convert RGBA to RGB for JPEG (no transparency support)
            if resized_img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
                background = Image.new('RGB', resized_img.size, (255, 255, 255))
                if resized_img.mode == 'P':
                    resized_img = resized_img.convert('RGBA')
                background.paste(resized_img, mask=resized_img.split()[-1] if resized_img.mode == 'RGBA' else None)
                resized_img = background

            resized_img.save(output, format='JPEG', quality=85, optimize=True)
        else:
            resized_img.save(output, format=output_format, optimize=True)

        output.seek(0)

        return output, True

    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}")


def get_image_dimensions(image_file: BinaryIO) -> Tuple[int, int]:
    """
    Get image dimensions without loading full image into memory.

    Args:
        image_file: Image file to measure

    Returns:
        Tuple of (width, height)

    Raises:
        ValueError: If image cannot be opened
    """
    try:
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        img = Image.open(image_file)
        width, height = img.size

        # Reset file pointer
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        return width, height

    except Exception as e:
        raise ValueError(f"Failed to read image dimensions: {str(e)}")
