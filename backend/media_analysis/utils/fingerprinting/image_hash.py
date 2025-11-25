"""
Perceptual image hashing (pHash) for detecting similar images.
Uses imagehash library to generate perceptual hashes.
"""
import imagehash
from PIL import Image
from typing import BinaryIO, Union
import io


def calculate_phash(image_file: Union[BinaryIO, bytes], hash_size: int = 8) -> str:
    """
    Calculate perceptual hash (pHash) of an image.

    Args:
        image_file: File object or bytes containing image data
        hash_size: Size of the hash (default 8 = 64-bit hash)

    Returns:
        Hex string representation of the perceptual hash

    Raises:
        ValueError: If image cannot be processed

    Example:
        >>> with open('photo.jpg', 'rb') as f:
        >>>     phash = calculate_phash(f)
        >>> print(phash)  # "d879f4f8e3b0c1a2"
    """
    try:
        # Handle bytes input
        if isinstance(image_file, bytes):
            image_file = io.BytesIO(image_file)

        # Ensure we're at the beginning of the file
        if hasattr(image_file, 'seek'):
            image_file.seek(0)

        # Open image with PIL
        image = Image.open(image_file)

        # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        # Calculate perceptual hash
        phash = imagehash.phash(image, hash_size=hash_size)

        # Return as hex string
        return str(phash)

    except Exception as e:
        raise ValueError(f"Failed to calculate perceptual hash: {str(e)}")


def calculate_phash_from_path(image_path: str, hash_size: int = 8) -> str:
    """
    Calculate perceptual hash from an image file path.

    Args:
        image_path: Path to the image file
        hash_size: Size of the hash (default 8 = 64-bit hash)

    Returns:
        Hex string representation of the perceptual hash

    Example:
        >>> phash = calculate_phash_from_path('/path/to/photo.jpg')
        >>> print(phash)  # "d879f4f8e3b0c1a2"
    """
    try:
        image = Image.open(image_path)
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')
        phash = imagehash.phash(image, hash_size=hash_size)
        return str(phash)
    except Exception as e:
        raise ValueError(f"Failed to calculate perceptual hash from path: {str(e)}")


def compare_phash(hash1: str, hash2: str) -> int:
    """
    Compare two perceptual hashes and return the Hamming distance.

    Args:
        hash1: First perceptual hash (hex string)
        hash2: Second perceptual hash (hex string)

    Returns:
        Hamming distance (0 = identical, higher = more different)

    Note:
        - Distance 0-5: Very similar images (likely the same with minor edits)
        - Distance 6-10: Similar images (resized, compressed, cropped)
        - Distance >10: Likely different images

    Example:
        >>> distance = compare_phash("d879f4f8e3b0c1a2", "d879f4f8e3b0c1a3")
        >>> print(distance)  # 1 (very similar)
    """
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2  # Returns Hamming distance
    except Exception as e:
        raise ValueError(f"Failed to compare perceptual hashes: {str(e)}")


def are_images_similar(hash1: str, hash2: str, threshold: int = 5) -> bool:
    """
    Check if two images are similar based on their perceptual hashes.

    Args:
        hash1: First perceptual hash (hex string)
        hash2: Second perceptual hash (hex string)
        threshold: Maximum Hamming distance to consider similar (default 5)

    Returns:
        True if images are similar, False otherwise

    Example:
        >>> similar = are_images_similar("d879f4f8e3b0c1a2", "d879f4f8e3b0c1a3")
        >>> print(similar)  # True
    """
    distance = compare_phash(hash1, hash2)
    return distance <= threshold
