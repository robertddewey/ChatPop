"""
ACRCloud audio recognition utility for music identification.
"""
import base64
import hashlib
import hmac
import time
import logging
from typing import Dict, Any, Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ACRCloudRecognizer:
    """
    ACRCloud audio recognition client for identifying songs from audio recordings.
    """

    def __init__(self):
        self.access_key = settings.ACRCLOUD_ACCESS_KEY
        self.secret_key = settings.ACRCLOUD_SECRET_KEY
        self.host = settings.ACRCLOUD_HOST
        self.endpoint = f"https://{self.host}/v1/identify"

        if not self.access_key or not self.secret_key:
            logger.warning("ACRCloud credentials not configured")

    def _build_signature(self, method: str, uri: str, access_key: str, data_type: str, signature_version: str, timestamp: str) -> str:
        """
        Build the signature for ACRCloud API request.
        """
        string_to_sign = f"{method}\n{uri}\n{access_key}\n{data_type}\n{signature_version}\n{timestamp}"
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha1
            ).digest()
        ).decode('utf-8')
        return signature

    def recognize(self, audio_data: bytes, audio_format: str = "webm") -> Dict[str, Any]:
        """
        Recognize a song from audio data.

        Args:
            audio_data: The audio file bytes
            audio_format: The audio format (webm, mp3, wav, etc.)

        Returns:
            Dictionary with recognition results:
            {
                "success": bool,
                "song": str,  # Song title
                "artist": str,  # Artist name
                "album": str,  # Album name (optional)
                "release_date": str,  # Release date (optional)
                "duration_ms": int,  # Song duration in milliseconds
                "score": int,  # Confidence score (0-100)
                "external_ids": {
                    "spotify": str,
                    "youtube": str,
                    ...
                },
                "raw_response": dict  # Full ACRCloud response
            }
        """
        if not self.access_key or not self.secret_key:
            return {
                "success": False,
                "error": "ACRCloud credentials not configured"
            }

        try:
            # Build request parameters
            timestamp = str(int(time.time()))
            data_type = "audio"
            signature_version = "1"
            signature = self._build_signature(
                "POST",
                "/v1/identify",
                self.access_key,
                data_type,
                signature_version,
                timestamp
            )

            # Prepare multipart form data
            files = {
                'sample': (f'audio.{audio_format}', audio_data, f'audio/{audio_format}')
            }

            data = {
                'access_key': self.access_key,
                'data_type': data_type,
                'signature_version': signature_version,
                'signature': signature,
                'sample_bytes': str(len(audio_data)),
                'timestamp': timestamp,
            }

            # Make request to ACRCloud
            logger.info(f"Sending audio recognition request to ACRCloud (size: {len(audio_data)} bytes)")
            response = requests.post(self.endpoint, files=files, data=data, timeout=10)
            response.raise_for_status()

            result = response.json()
            logger.info(f"ACRCloud response status: {result.get('status', {}).get('msg', 'unknown')}")

            # Parse the response
            return self._parse_response(result)

        except requests.RequestException as e:
            logger.error(f"ACRCloud API request failed: {str(e)}")
            return {
                "success": False,
                "error": f"API request failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Audio recognition failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _parse_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse ACRCloud API response into a standardized format.
        """
        status = response.get("status", {})

        # Check if recognition was successful
        if status.get("code") != 0:
            return {
                "success": False,
                "error": status.get("msg", "Recognition failed"),
                "raw_response": response
            }

        metadata = response.get("metadata", {})
        music_list = metadata.get("music", [])

        if not music_list:
            return {
                "success": False,
                "error": "No music found in audio",
                "raw_response": response
            }

        # Get the first (best) match
        best_match = music_list[0]

        # Extract song metadata
        external_metadata = best_match.get("external_metadata", {})
        spotify = external_metadata.get("spotify", {})
        youtube = external_metadata.get("youtube", {})

        result = {
            "success": True,
            "song": best_match.get("title", "Unknown"),
            "artist": ", ".join([artist.get("name", "") for artist in best_match.get("artists", [])]),
            "album": best_match.get("album", {}).get("name", ""),
            "release_date": best_match.get("release_date", ""),
            "duration_ms": best_match.get("duration_ms", 0),
            "score": best_match.get("score", 0),
            "external_ids": {
                "spotify": spotify.get("track", {}).get("id", "") if spotify else "",
                "youtube": youtube.get("vid", "") if youtube else "",
            },
            "raw_response": response
        }

        logger.info(f"Successfully recognized: {result['song']} by {result['artist']} (score: {result['score']})")
        return result


def recognize_audio(audio_data: bytes, audio_format: str = "webm") -> Dict[str, Any]:
    """
    Convenience function to recognize audio using ACRCloud.

    Args:
        audio_data: The audio file bytes
        audio_format: The audio format (webm, mp3, wav, etc.)

    Returns:
        Recognition results dictionary
    """
    recognizer = ACRCloudRecognizer()
    return recognizer.recognize(audio_data, audio_format)
