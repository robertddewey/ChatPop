"""
ACRCloud Metadata API utility for fetching extended track metadata.

This fetches additional metadata (genres, album art, streaming links)
that isn't available in the identification response.

API Docs: https://docs.acrcloud.com/reference/metadata-api
"""
import logging
from typing import Dict, Any, Optional, List
import requests
from django.conf import settings

from ..models import MusicMetadataCache

logger = logging.getLogger(__name__)


class ACRCloudMetadataClient:
    """
    Client for ACRCloud Metadata API.
    Fetches extended track information using acr_id from identification response.
    """

    BASE_URL = "https://eu-api-v2.acrcloud.com/api"

    def __init__(self):
        self.bearer_token = settings.ACRCLOUD_BEARER_TOKEN
        if not self.bearer_token:
            logger.warning("ACRCLOUD_BEARER_TOKEN not configured - metadata fetching disabled")

    def is_available(self) -> bool:
        """Check if the Metadata API is configured."""
        return bool(self.bearer_token)

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Accept": "application/json",
        }

    def fetch_track_metadata(self, acr_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch extended metadata for a track by acr_id.

        Args:
            acr_id: ACRCloud's internal track ID (from identification response)

        Returns:
            Dictionary with metadata or None if not found/error:
            {
                "genres": ["Pop", "Dance"],
                "album_art": "https://...",
                "streaming_links": {...},
                "raw_metadata": {...}  # Full API response
            }
        """
        if not self.is_available():
            logger.warning("Metadata API not available - missing bearer token")
            return None

        try:
            url = f"{self.BASE_URL}/external-metadata/tracks"
            params = {
                "acr_id": acr_id,
            }

            logger.info(f"Fetching metadata for acr_id={acr_id[:8]}...")
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=10
            )

            if response.status_code == 404:
                logger.info(f"No metadata found for acr_id={acr_id[:8]}...")
                return None

            response.raise_for_status()
            data = response.json()

            logger.info(f"Metadata fetch successful for acr_id={acr_id[:8]}...")
            return self._parse_metadata_response(data)

        except requests.RequestException as e:
            logger.error(f"Metadata API request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Metadata fetch failed: {str(e)}", exc_info=True)
            return None

    def _parse_metadata_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse the Metadata API response into a standardized format.

        Response structure (from API docs):
        {
            "data": [
                {
                    "name": "song title",
                    "artists": [{"name": "Artist"}],
                    "genres": [{"name": "Pop"}, {"name": "Dance"}],
                    "album": {"name": "Album", "cover": "url"},
                    "external_ids": {...},
                    "external_metadata": {...}
                }
            ]
        }
        """
        data_list = response.get("data", [])
        if not data_list:
            return {
                "genres": [],
                "album_art": None,
                "streaming_links": {},
                "raw_metadata": response
            }

        # Get the first (best) match
        track = data_list[0]

        # Extract genres
        genres = []
        genre_list = track.get("genres", [])
        for genre in genre_list:
            if isinstance(genre, dict):
                genre_name = genre.get("name")
                if genre_name:
                    genres.append(genre_name)
            elif isinstance(genre, str):
                genres.append(genre)

        # Extract album art
        album_art = None
        album = track.get("album", {})
        if album:
            album_art = album.get("cover") or album.get("covers", {}).get("large")

        # Extract streaming links from external_metadata
        # Note: The API returns arrays for each platform, not single objects
        streaming_links = {}
        external_metadata = track.get("external_metadata", {})

        # Spotify - API returns array of spotify entries
        spotify_list = external_metadata.get("spotify", [])
        if spotify_list and isinstance(spotify_list, list) and len(spotify_list) > 0:
            spotify = spotify_list[0]
            spotify_id = spotify.get("id")
            if spotify_id:
                streaming_links["spotify"] = {
                    "id": spotify_id,
                    "url": spotify.get("link") or f"https://open.spotify.com/track/{spotify_id}"
                }
                # Check for album art in spotify entry
                if not album_art:
                    spotify_album = spotify.get("album", {})
                    if spotify_album:
                        album_art = spotify_album.get("cover")

        # YouTube - API returns array
        youtube_list = external_metadata.get("youtube", [])
        if youtube_list and isinstance(youtube_list, list) and len(youtube_list) > 0:
            youtube = youtube_list[0]
            vid = youtube.get("vid")
            if vid:
                streaming_links["youtube"] = {
                    "id": vid,
                    "url": f"https://www.youtube.com/watch?v={vid}"
                }

        # Apple Music - API returns array
        apple_list = external_metadata.get("apple_music", [])
        if apple_list and isinstance(apple_list, list) and len(apple_list) > 0:
            apple = apple_list[0]
            apple_id = apple.get("id")
            if apple_id:
                streaming_links["apple_music"] = {
                    "id": apple_id,
                    "url": apple.get("link") or apple.get("url")
                }

        # Deezer - API returns array
        deezer_list = external_metadata.get("deezer", [])
        if deezer_list and isinstance(deezer_list, list) and len(deezer_list) > 0:
            deezer = deezer_list[0]
            deezer_id = deezer.get("id")
            if deezer_id:
                streaming_links["deezer"] = {
                    "id": str(deezer_id),
                    "url": deezer.get("link") or f"https://www.deezer.com/track/{deezer_id}"
                }

        return {
            "genres": genres,
            "album_art": album_art,
            "streaming_links": streaming_links,
            "raw_metadata": response
        }


def get_or_fetch_metadata(
    acr_id: str,
    song_title: str,
    artist: str
) -> Optional[Dict[str, Any]]:
    """
    Get metadata from cache or fetch from ACRCloud Metadata API.

    This is the main entry point for metadata retrieval:
    1. Check if metadata fetching is enabled (Constance setting)
    2. Check MusicMetadataCache for existing entry
    3. If not cached, fetch from Metadata API
    4. Cache the result for future lookups

    Args:
        acr_id: ACRCloud's internal track ID
        song_title: Song title (for cache record)
        artist: Artist name (for cache record)

    Returns:
        Dictionary with metadata or None:
        {
            "genres": ["Pop", "Dance"],
            "album_art": "https://...",
            "streaming_links": {...},
            "raw_metadata": {...},
            "cached": bool  # True if from cache
        }
    """
    if not acr_id:
        logger.warning("No acr_id provided - cannot fetch metadata")
        return None

    # Check if metadata fetching is enabled via Constance
    from constance import config
    if not config.MUSIC_RECOGNITION_FETCH_METADATA:
        logger.info("Metadata fetching disabled via MUSIC_RECOGNITION_FETCH_METADATA setting")
        return None

    # Step 1: Check cache
    try:
        cached = MusicMetadataCache.objects.filter(acr_id=acr_id).first()
        if cached:
            logger.info(f"Metadata cache HIT for acr_id={acr_id[:8]}... (lookup #{cached.lookup_count})")
            cached.increment_lookup()
            return {
                "genres": cached.genres or [],
                "album_art": cached.raw_metadata.get("album_art") if cached.raw_metadata else None,
                "streaming_links": cached.raw_metadata.get("streaming_links", {}) if cached.raw_metadata else {},
                "raw_metadata": cached.raw_metadata,
                "cached": True
            }
    except Exception as e:
        logger.warning(f"Cache lookup failed (non-fatal): {str(e)}")

    # Step 2: Fetch from API
    logger.info(f"Metadata cache MISS for acr_id={acr_id[:8]}... - fetching from API")
    client = ACRCloudMetadataClient()

    if not client.is_available():
        return None

    metadata = client.fetch_track_metadata(acr_id)
    if not metadata:
        return None

    # Step 3: Cache the result
    try:
        MusicMetadataCache.objects.create(
            acr_id=acr_id,
            song_title=song_title[:500] if song_title else "",
            artist=artist[:500] if artist else "",
            genres=metadata.get("genres", []),
            raw_metadata=metadata
        )
        logger.info(f"Cached metadata for acr_id={acr_id[:8]}...")
    except Exception as e:
        # Cache write failure is non-fatal
        logger.warning(f"Failed to cache metadata (non-fatal): {str(e)}")

    metadata["cached"] = False
    return metadata


def get_genres_for_acr_id(acr_id: str, song_title: str = "", artist: str = "") -> List[str]:
    """
    Convenience function to get just the genres for a track.

    Args:
        acr_id: ACRCloud's internal track ID
        song_title: Song title (optional, for caching)
        artist: Artist name (optional, for caching)

    Returns:
        List of genre strings, or empty list if not available
    """
    metadata = get_or_fetch_metadata(acr_id, song_title, artist)
    if metadata:
        return metadata.get("genres", [])
    return []
