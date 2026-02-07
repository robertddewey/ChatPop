"""
Avatar generation and storage utility.
Fetches avatars from DiceBear API and stores them in S3/local storage.
"""
import io
import requests
from typing import Optional
from django.conf import settings
from constance import config

from .storage import save_avatar, get_avatar_url


def get_dicebear_style() -> str:
    """Get the DiceBear avatar style from Constance config."""
    try:
        return config.DICEBEAR_STYLE
    except Exception:
        return 'pixel-art'


def get_dicebear_size() -> int:
    """Get the DiceBear avatar size from Constance config."""
    try:
        return config.DICEBEAR_SIZE
    except Exception:
        return 80


def fetch_dicebear_avatar(seed: str, style: Optional[str] = None, size: Optional[int] = None) -> Optional[bytes]:
    """
    Fetch an avatar from DiceBear API.

    Args:
        seed: The seed string (typically username) for generating the avatar
        style: DiceBear style (e.g., 'pixel-art', 'avataaars', 'bottts')
        size: Size in pixels

    Returns:
        SVG content as bytes, or None if fetch failed
    """
    if style is None:
        style = get_dicebear_style()
    if size is None:
        size = get_dicebear_size()

    url = f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}&size={size}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"[Avatar] Error fetching DiceBear avatar for seed '{seed}': {e}")
        return None


def generate_and_store_avatar(seed: str, style: Optional[str] = None, size: Optional[int] = None) -> Optional[str]:
    """
    Fetch avatar from DiceBear and store it in S3/local storage.

    Args:
        seed: The seed string (typically username) for generating the avatar
        style: DiceBear style (optional, uses Constance config if not provided)
        size: Size in pixels (optional, uses Constance config if not provided)

    Returns:
        Storage URL path (e.g., '/api/chats/media/avatars/uuid.svg'), or None if failed
    """
    avatar_content = fetch_dicebear_avatar(seed, style, size)
    if avatar_content is None:
        return None

    try:
        # Wrap content in a file-like object
        file_obj = io.BytesIO(avatar_content)

        # Save to storage
        storage_path, storage_type = save_avatar(file_obj)

        # Get the proxy URL
        url = get_avatar_url(storage_path)

        print(f"[Avatar] Generated and stored avatar for seed '{seed}': {url} (storage: {storage_type})")
        return url
    except Exception as e:
        print(f"[Avatar] Error storing avatar for seed '{seed}': {e}")
        return None


def get_fallback_dicebear_url(seed: str, style: Optional[str] = None, size: Optional[int] = None) -> str:
    """
    Get the direct DiceBear API URL for fallback (when we can't store locally).

    Args:
        seed: The seed string (typically username) for generating the avatar
        style: DiceBear style (optional)
        size: Size in pixels (optional)

    Returns:
        Direct DiceBear API URL
    """
    if style is None:
        style = get_dicebear_style()
    if size is None:
        size = get_dicebear_size()

    return f"https://api.dicebear.com/7.x/{style}/svg?seed={seed}&size={size}"
