"""
Location-based chat suggestions utilities.

This module provides geohash encoding, location API integration,
and caching for location-based suggestions.

Supports multiple providers (Google, TomTom) with configurable
fallback via PLACES_PROVIDER and PLACES_PROVIDER_FALLBACK settings.
"""

from .geohash_utils import (
    encode_location,
    decode_geohash,
    get_cache_key,
    get_geohash_bounds,
    get_precision,
)
from .base import BasePlacesClient
from .google_places import GooglePlacesClient
from .tomtom import TomTomClient
from .factory import get_places_client, get_available_providers
from .category_mapping import map_google_type, map_tomtom_category
from .cache import get_or_fetch_location_suggestions

__all__ = [
    # Geohash utilities
    'encode_location',
    'decode_geohash',
    'get_cache_key',
    'get_geohash_bounds',
    'get_precision',
    # Provider clients
    'BasePlacesClient',
    'GooglePlacesClient',
    'TomTomClient',
    # Factory
    'get_places_client',
    'get_available_providers',
    # Category mapping
    'map_google_type',
    'map_tomtom_category',
    # Caching
    'get_or_fetch_location_suggestions',
]
