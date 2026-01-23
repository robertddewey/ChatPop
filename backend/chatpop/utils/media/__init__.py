"""
Media utilities for ChatPop.

Provides audio transcoding and storage functionality for voice, photo, and video messages.
"""

from .audio import transcode_webm_to_m4a
from .storage import (
    MediaStorage,
    save_voice_message,
    get_voice_message_url,
    save_photo_message,
    get_photo_message_url,
    save_video_message,
    save_video_thumbnail,
    get_video_message_url,
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
    'PHOTO_CONTENT_TYPE_TO_EXT',
    'VIDEO_CONTENT_TYPE_TO_EXT',
]
