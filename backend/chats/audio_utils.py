"""
Audio transcoding utilities for iOS compatibility.

iOS Safari MediaRecorder produces WebM/Opus files that iOS itself cannot play.
This module provides transcoding to M4A/AAC format which works on all platforms.
"""

import ffmpeg
import tempfile
import os
from django.core.files.base import ContentFile


def transcode_webm_to_m4a(input_file):
    """
    Transcode WebM audio to M4A (AAC) format for iOS compatibility.

    Args:
        input_file: Django UploadedFile object containing WebM audio

    Returns:
        ContentFile: Transcoded M4A audio file

    Raises:
        Exception: If transcoding fails
    """
    # Create temporary files for input and output
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as input_temp:
        # Write uploaded file to temp file
        for chunk in input_file.chunks():
            input_temp.write(chunk)
        input_temp_path = input_temp.name

    output_temp_path = input_temp_path.replace('.webm', '.m4a')

    try:
        # Transcode using FFmpeg
        # -i: input file
        # -c:a aac: use AAC audio codec (iOS compatible)
        # -b:a 128k: audio bitrate 128kbps (good quality for voice)
        # -ar 44100: sample rate 44.1kHz (standard)
        # -y: overwrite output file
        (
            ffmpeg
            .input(input_temp_path)
            .output(output_temp_path, **{
                'c:a': 'aac',
                'b:a': '128k',
                'ar': '44100',
            })
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True, quiet=True)
        )

        # Read transcoded file
        with open(output_temp_path, 'rb') as f:
            transcoded_data = f.read()

        # Return as ContentFile
        return ContentFile(transcoded_data, name='voice.m4a')

    finally:
        # Clean up temporary files
        if os.path.exists(input_temp_path):
            os.unlink(input_temp_path)
        if os.path.exists(output_temp_path):
            os.unlink(output_temp_path)
