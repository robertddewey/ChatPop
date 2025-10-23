"""
File hashing utilities for exact file match detection.
Uses MD5 for fast, byte-perfect duplicate detection.
"""
import hashlib
from typing import BinaryIO, Union
import io


def calculate_md5(file_obj: Union[BinaryIO, bytes], chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash of a file.

    Args:
        file_obj: File object or bytes to hash
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        MD5 hash as hex string

    Example:
        >>> with open('photo.jpg', 'rb') as f:
        >>>     md5 = calculate_md5(f)
        >>> print(md5)  # "098f6bcd4621d373cade4e832627b4f6"
    """
    md5_hash = hashlib.md5()

    # Handle bytes input
    if isinstance(file_obj, bytes):
        md5_hash.update(file_obj)
        return md5_hash.hexdigest()

    # Ensure we're at the beginning of the file
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    # Read and hash file in chunks
    while chunk := file_obj.read(chunk_size):
        md5_hash.update(chunk)

    # Reset file pointer to beginning
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    return md5_hash.hexdigest()


def calculate_md5_from_path(file_path: str, chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash from a file path.

    Args:
        file_path: Path to the file
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        MD5 hash as hex string

    Example:
        >>> md5 = calculate_md5_from_path('/path/to/photo.jpg')
        >>> print(md5)  # "098f6bcd4621d373cade4e832627b4f6"
    """
    with open(file_path, 'rb') as f:
        return calculate_md5(f, chunk_size)


def calculate_sha256(file_obj: Union[BinaryIO, bytes], chunk_size: int = 8192) -> str:
    """
    Calculate SHA256 hash of a file (more secure alternative to MD5).

    Args:
        file_obj: File object or bytes to hash
        chunk_size: Size of chunks to read (default 8KB)

    Returns:
        SHA256 hash as hex string

    Note:
        SHA256 is more cryptographically secure than MD5, but MD5 is faster
        and sufficient for deduplication purposes.

    Example:
        >>> with open('photo.jpg', 'rb') as f:
        >>>     sha256 = calculate_sha256(f)
        >>> print(sha256)  # "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    """
    sha256_hash = hashlib.sha256()

    # Handle bytes input
    if isinstance(file_obj, bytes):
        sha256_hash.update(file_obj)
        return sha256_hash.hexdigest()

    # Ensure we're at the beginning of the file
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    # Read and hash file in chunks
    while chunk := file_obj.read(chunk_size):
        sha256_hash.update(chunk)

    # Reset file pointer to beginning
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0)

    return sha256_hash.hexdigest()


def get_file_size(file_obj: Union[BinaryIO, bytes]) -> int:
    """
    Get the size of a file in bytes.

    Args:
        file_obj: File object or bytes

    Returns:
        File size in bytes

    Example:
        >>> with open('photo.jpg', 'rb') as f:
        >>>     size = get_file_size(f)
        >>> print(f"File is {size} bytes")  # "File is 1024000 bytes"
    """
    if isinstance(file_obj, bytes):
        return len(file_obj)

    # Save current position
    current_pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0

    # Seek to end to get size
    if hasattr(file_obj, 'seek'):
        file_obj.seek(0, 2)  # Seek to end
        size = file_obj.tell()
        file_obj.seek(current_pos)  # Restore position
        return size

    # Fallback: read entire file
    data = file_obj.read()
    if hasattr(file_obj, 'seek'):
        file_obj.seek(current_pos)
    return len(data)


def verify_file_integrity(file_obj: BinaryIO, expected_md5: str) -> bool:
    """
    Verify file integrity by comparing with expected MD5 hash.

    Args:
        file_obj: File object to verify
        expected_md5: Expected MD5 hash

    Returns:
        True if file matches expected hash, False otherwise

    Example:
        >>> with open('photo.jpg', 'rb') as f:
        >>>     valid = verify_file_integrity(f, "098f6bcd4621d373cade4e832627b4f6")
        >>> print(valid)  # True or False
    """
    actual_md5 = calculate_md5(file_obj)
    return actual_md5.lower() == expected_md5.lower()
