"""
Media storage utility for voice messages and other media files.
Automatically switches between local filesystem and S3 based on AWS credentials.
"""
import os
from typing import BinaryIO, Optional
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import uuid


class MediaStorage:
    """Hybrid storage system that uses S3 when configured, local filesystem otherwise"""

    @staticmethod
    def is_s3_configured() -> bool:
        """Check if AWS S3 credentials are configured"""
        return bool(
            settings.AWS_ACCESS_KEY_ID and
            settings.AWS_SECRET_ACCESS_KEY and
            settings.AWS_STORAGE_BUCKET_NAME
        )

    @staticmethod
    def get_storage_type() -> str:
        """Return current storage type: 's3' or 'local'"""
        return 's3' if MediaStorage.is_s3_configured() else 'local'

    @staticmethod
    def save_file(file_obj: BinaryIO, directory: str, filename: Optional[str] = None) -> tuple[str, str]:
        """
        Save a file to storage (S3 or local based on configuration).

        Args:
            file_obj: File object to save
            directory: Directory/prefix to save under (e.g., 'voice_messages')
            filename: Optional filename (auto-generated if not provided)

        Returns:
            tuple: (storage_path, storage_type) where storage_type is 's3' or 'local'
        """
        if filename is None:
            # Generate unique filename preserving extension if present
            ext = getattr(file_obj, 'name', '').split('.')[-1] if hasattr(file_obj, 'name') else 'webm'
            filename = f"{uuid.uuid4()}.{ext}"

        # Build storage path
        storage_path = os.path.join(directory, filename)

        # Read file content
        content = file_obj.read()

        # Save to storage (Django will use S3 backend if configured, otherwise local)
        default_storage.save(storage_path, ContentFile(content))

        return storage_path, MediaStorage.get_storage_type()

    @staticmethod
    def delete_file(storage_path: str) -> bool:
        """
        Delete a file from storage.

        Args:
            storage_path: Path to the file in storage

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            if default_storage.exists(storage_path):
                default_storage.delete(storage_path)
                return True
            return False
        except Exception as e:
            print(f"Error deleting file {storage_path}: {e}")
            return False

    @staticmethod
    def get_file_url(storage_path: str) -> str:
        """
        Get the URL for accessing a file through Django proxy.

        Args:
            storage_path: Path to the file in storage

        Returns:
            str: Relative URL path for Django proxy endpoint
        """
        # Return proxy URL path (actual URL generation happens in views)
        # Format: /api/chats/media/voice_messages/<filename>
        return f"/api/chats/media/{storage_path}"

    @staticmethod
    def proxy_url_to_cdn_url(proxy_url):
        """
        Convert a /api/chats/media/<...> proxy URL into a directly-fetchable
        CloudFront-signed URL. Used by serializers/views that want to skip
        the Daphne 302 hop.

        URLs are stable within a 5-minute time bucket — every call inside
        the bucket produces the *same* signed URL string. This matters for
        the frontend: if the URL string changed on every API response, React
        would diff <img src=...> as different and remount the element,
        re-triggering the image fetch and a loading flash on every WebSocket
        message. With time-bucketed URLs, src stays identical across
        re-renders within the bucket, so React reuses the loaded image.

        Returns None when:
          - proxy_url is empty
          - it's not a /api/chats/media/ proxy URL (e.g., external DiceBear URL)
          - S3 storage isn't configured (local-storage dev mode)
          - signing fails
          - the URL is the user-id pattern but the user doesn't exist or has
            no avatar

        Caller falls back to the original proxy URL when this returns None.
        """
        import time
        from django.conf import settings
        from django.core.files.storage import default_storage

        if not proxy_url:
            return None
        if not getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
            return None
        prefix = "/api/chats/media/"
        if not proxy_url.startswith(prefix):
            return None  # external URL — leave as-is

        path = proxy_url[len(prefix):]

        # avatars/user/<user_id>: resolve user → storage path via single DB hit.
        if path.startswith("avatars/user/"):
            user_id = path[len("avatars/user/"):].rstrip("/")
            try:
                from accounts.models import User
                user = User.objects.only("avatar_url").get(id=user_id)
            except (User.DoesNotExist, ValueError):
                return None
            if not user.avatar_url or not user.avatar_url.startswith(prefix):
                return None
            path = user.avatar_url[len(prefix):]

        # Time-bucket the Expires param so URLs are stable across reads in
        # the same 5-minute window. The URL still has ~1 hour of validity
        # past the bucket boundary, so a viewer mid-load doesn't get a 403
        # if their request crosses a bucket edge.
        BUCKET_SECONDS = 300       # URL string changes every 5 minutes
        VALIDITY_SECONDS = 3600    # URL works for 1 hour from now
        now = int(time.time())
        absolute_expires = ((now + VALIDITY_SECONDS) // BUCKET_SECONDS) * BUCKET_SECONDS
        expire_in = absolute_expires - now

        try:
            return default_storage.url(path, expire=expire_in)
        except Exception:
            return None

    @staticmethod
    def get_file(storage_path: str) -> Optional[BinaryIO]:
        """
        Retrieve a file from storage.

        Args:
            storage_path: Path to the file in storage

        Returns:
            File object if found, None otherwise
        """
        try:
            if default_storage.exists(storage_path):
                return default_storage.open(storage_path, 'rb')
            return None
        except Exception as e:
            print(f"Error retrieving file {storage_path}: {e}")
            return None

    @staticmethod
    def file_exists(storage_path: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            storage_path: Path to the file in storage

        Returns:
            bool: True if file exists, False otherwise
        """
        return default_storage.exists(storage_path)


# Content-Type to file extension mapping for voice messages
VOICE_CONTENT_TYPE_TO_EXT = {
    'audio/mp4': 'm4a',      # iOS Safari recording format (M4A/AAC)
    'audio/webm': 'webm',     # Desktop Chrome recording format (WebM/Opus)
    'audio/mpeg': 'mp3',      # MP3 format
    'audio/ogg': 'ogg',       # Ogg Vorbis
    'audio/wav': 'wav',       # WAV format
    'audio/x-m4a': 'm4a',     # Alternative M4A MIME type
}


# Convenience functions for voice messages specifically
def save_voice_message(file_obj: BinaryIO, filename: Optional[str] = None, content_type: Optional[str] = None) -> tuple[str, str]:
    """
    Save a voice message file with correct extension based on content type.

    Args:
        file_obj: Voice message file object
        filename: Optional custom filename (if not provided, auto-generated)
        content_type: MIME type of the audio file (e.g., 'audio/mp4', 'audio/webm')

    Returns:
        tuple: (storage_path, storage_type)
    """
    # Auto-generate filename with correct extension if not provided
    if filename is None and content_type:
        # Map content type to file extension
        ext = VOICE_CONTENT_TYPE_TO_EXT.get(content_type, 'webm')  # Default to webm if unknown
        filename = f"{uuid.uuid4()}.{ext}"

    return MediaStorage.save_file(file_obj, 'voice_messages', filename)


def get_voice_message_url(storage_path: str) -> str:
    """
    Get the proxy URL for a voice message.

    Args:
        storage_path: Storage path from save_voice_message()

    Returns:
        str: URL path for accessing the voice message through Django proxy
    """
    return MediaStorage.get_file_url(storage_path)


def delete_voice_message(storage_path: str) -> bool:
    """
    Delete a voice message file.

    Args:
        storage_path: Storage path from save_voice_message()

    Returns:
        bool: True if deleted successfully
    """
    return MediaStorage.delete_file(storage_path)


# Content-Type to file extension mapping for photo messages
PHOTO_CONTENT_TYPE_TO_EXT = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
    'image/heic': 'heic',
    'image/heif': 'heif',
}

# Content-Type to file extension mapping for video messages
VIDEO_CONTENT_TYPE_TO_EXT = {
    'video/mp4': 'mp4',
    'video/webm': 'webm',
    'video/quicktime': 'mov',
    'video/x-m4v': 'm4v',
}


# Convenience functions for photo messages
def save_photo_message(file_obj: BinaryIO, filename: Optional[str] = None, content_type: Optional[str] = None) -> tuple[str, str]:
    """
    Save a photo message file with correct extension based on content type.

    Args:
        file_obj: Photo file object
        filename: Optional custom filename (if not provided, auto-generated)
        content_type: MIME type of the image file (e.g., 'image/jpeg', 'image/png')

    Returns:
        tuple: (storage_path, storage_type)
    """
    if filename is None and content_type:
        ext = PHOTO_CONTENT_TYPE_TO_EXT.get(content_type, 'jpg')
        filename = f"{uuid.uuid4()}.{ext}"

    return MediaStorage.save_file(file_obj, 'photos', filename)


def get_photo_message_url(storage_path: str) -> str:
    """Get the proxy URL for a photo message."""
    return MediaStorage.get_file_url(storage_path)


def delete_photo_message(storage_path: str) -> bool:
    """Delete a photo message file."""
    return MediaStorage.delete_file(storage_path)


# Convenience functions for video messages
def save_video_message(file_obj: BinaryIO, filename: Optional[str] = None, content_type: Optional[str] = None) -> tuple[str, str]:
    """
    Save a video message file with correct extension based on content type.

    Args:
        file_obj: Video file object
        filename: Optional custom filename (if not provided, auto-generated)
        content_type: MIME type of the video file (e.g., 'video/mp4', 'video/webm')

    Returns:
        tuple: (storage_path, storage_type)
    """
    if filename is None and content_type:
        ext = VIDEO_CONTENT_TYPE_TO_EXT.get(content_type, 'mp4')
        filename = f"{uuid.uuid4()}.{ext}"

    return MediaStorage.save_file(file_obj, 'videos', filename)


def save_video_thumbnail(file_obj: BinaryIO, video_filename: str) -> tuple[str, str]:
    """
    Save a video thumbnail image.

    Args:
        file_obj: Thumbnail image file object (JPEG)
        video_filename: Base filename of the video (used to create matching thumbnail name)

    Returns:
        tuple: (storage_path, storage_type)
    """
    # Use same base name as video but with _thumb.jpg suffix
    base_name = video_filename.rsplit('.', 1)[0]
    thumb_filename = f"{base_name}_thumb.jpg"

    return MediaStorage.save_file(file_obj, 'video_thumbnails', thumb_filename)


def get_video_message_url(storage_path: str) -> str:
    """Get the proxy URL for a video message."""
    return MediaStorage.get_file_url(storage_path)


def delete_video_message(storage_path: str) -> bool:
    """Delete a video message file."""
    return MediaStorage.delete_file(storage_path)


# Convenience functions for avatars
def save_avatar(file_obj: BinaryIO, filename: Optional[str] = None) -> tuple[str, str]:
    """
    Save an avatar image file.

    Args:
        file_obj: Avatar image file object (typically SVG from DiceBear)
        filename: Optional custom filename (if not provided, auto-generated)

    Returns:
        tuple: (storage_path, storage_type)
    """
    if filename is None:
        filename = f"{uuid.uuid4()}.svg"

    return MediaStorage.save_file(file_obj, 'avatars', filename)


def get_avatar_url(storage_path: str) -> str:
    """Get the proxy URL for an avatar."""
    return MediaStorage.get_file_url(storage_path)


def delete_avatar(storage_path: str) -> bool:
    """Delete an avatar file."""
    return MediaStorage.delete_file(storage_path)
