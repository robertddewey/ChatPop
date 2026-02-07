"""
Media utilities for ChatPop.

Provides audio transcoding and storage functionality for voice, photo, video messages, and avatars.
"""

from .audio import transcode_webm_to_m4a
from .avatar import (
    generate_and_store_avatar,
    get_fallback_dicebear_url,
    fetch_dicebear_avatar,
)
from .storage import (
    MediaStorage,
    save_voice_message,
    get_voice_message_url,
    save_photo_message,
    get_photo_message_url,
    save_video_message,
    save_video_thumbnail,
    get_video_message_url,
    save_avatar,
    get_avatar_url,
    delete_avatar,
    PHOTO_CONTENT_TYPE_TO_EXT,
    VIDEO_CONTENT_TYPE_TO_EXT,
)

__all__ = [
    'transcode_webm_to_m4a',
    'MediaStorage',
    'save_voice_message',
    'get_voice_message_url',
    'save_photo_message',
    'get_photo_message_url',
    'save_video_message',
    'save_video_thumbnail',
    'get_video_message_url',
    'save_avatar',
    'get_avatar_url',
    'delete_avatar',
    'generate_and_store_avatar',
    'get_fallback_dicebear_url',
    'fetch_dicebear_avatar',
    'PHOTO_CONTENT_TYPE_TO_EXT',
    'VIDEO_CONTENT_TYPE_TO_EXT',
]
