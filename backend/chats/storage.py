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


# Convenience functions for voice messages specifically
def save_voice_message(file_obj: BinaryIO, filename: Optional[str] = None) -> tuple[str, str]:
    """
    Save a voice message file.

    Args:
        file_obj: Voice message file object
        filename: Optional custom filename

    Returns:
        tuple: (storage_path, storage_type)
    """
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
