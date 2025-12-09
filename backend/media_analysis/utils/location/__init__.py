"""
Location-based chat suggestions utilities.

This module provides geohash encoding, Google Places API integration,
and caching for location-based suggestions.
"""

from .geohash_utils import encode_location, decode_geohash, get_cache_key
from .google_places import GooglePlacesClient
from .cache import get_or_fetch_location_suggestions

__all__ = [
    'encode_location',
    'decode_geohash',
    'get_cache_key',
    'GooglePlacesClient',
    'get_or_fetch_location_suggestions',
]
