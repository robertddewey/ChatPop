"""
Geohash utilities for location-based caching.

Geohash encodes geographic coordinates into a short string of letters and digits.
The precision of the encoding determines the size of the area represented.

Precision levels:
- 4: ~39km x 20km (city level)
- 5: ~4.9km x 4.9km (neighborhood level)
- 6: ~1.2km x 0.6km (venue level)
- 7: ~150m x 150m (default - optimal for dense urban areas like NYC)

Note: Precision is now configurable via Constance LOCATION_GEOHASH_PRECISION setting.
Changing precision will invalidate all existing cache entries (they expire at TTL).
"""

import pygeohash as pgh
from typing import Tuple, Dict

# Default precision as fallback (used if Constance not available)
# Precision 7 = ~150m x 150m cells, optimal for dense urban areas
DEFAULT_GEOHASH_PRECISION = 7


def get_precision() -> int:
    """
    Get the current geohash precision from Constance settings.
    Falls back to default if Constance is not available.
    """
    try:
        from constance import config
        return config.LOCATION_GEOHASH_PRECISION
    except Exception:
        return DEFAULT_GEOHASH_PRECISION


def encode_location(latitude: float, longitude: float, precision: int = None) -> str:
    """
    Encode latitude/longitude to a geohash string.

    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        precision: Number of characters in geohash (default: from Constance settings)

    Returns:
        Geohash string (e.g., "9q8yym" for San Francisco)

    Example:
        >>> encode_location(37.7749, -122.4194)
        '9q8yym'
    """
    if precision is None:
        precision = get_precision()
    return pgh.encode(latitude, longitude, precision=precision)


def decode_geohash(geohash: str) -> Tuple[float, float]:
    """
    Decode geohash back to latitude/longitude center point.

    Args:
        geohash: Geohash string (e.g., "9q8yym")

    Returns:
        Tuple of (latitude, longitude) at center of geohash cell

    Example:
        >>> decode_geohash("9q8yym")
        (37.7749, -122.4194)
    """
    return pgh.decode(geohash)


def get_cache_key(geohash: str, radius_meters: int = None, max_venues: int = None) -> str:
    """
    Generate Redis cache key for location suggestions.

    Includes search settings in the key to ensure cache invalidation
    when settings change.

    Args:
        geohash: Geohash string (e.g., "9q8yym")
        radius_meters: Search radius setting (from Constance)
        max_venues: Max venues setting (from Constance)

    Returns:
        Redis cache key (e.g., "location:suggestions:9q8yym:r500:v10")
    """
    from constance import config

    # Use provided values or fetch from Constance
    radius = radius_meters if radius_meters is not None else config.LOCATION_SEARCH_RADIUS_METERS
    venues = max_venues if max_venues is not None else config.LOCATION_MAX_VENUES

    return f"location:suggestions:{geohash}:r{radius}:v{venues}"


def get_neighboring_geohashes(geohash: str) -> list:
    """
    Get all neighboring geohashes (8 surrounding cells + center).

    Useful for expanding search radius when cache misses occur.

    Args:
        geohash: Center geohash string

    Returns:
        List of 9 geohashes (center + 8 neighbors)
    """
    neighbors = pgh.neighbors(geohash)
    return [geohash] + list(neighbors.values())


def get_geohash_bounds(geohash: str) -> Dict[str, float]:
    """
    Get the bounding box coordinates for a geohash cell.

    Uses pygeohash's decode_exactly to get the center point and error margins,
    then calculates the bounding box corners.

    Args:
        geohash: Geohash string (e.g., "9q8yym")

    Returns:
        Dictionary with bounding box coordinates:
        {
            'min_lat': south boundary latitude,
            'max_lat': north boundary latitude,
            'min_lng': west boundary longitude,
            'max_lng': east boundary longitude,
            'center_lat': center latitude,
            'center_lng': center longitude,
        }

    Example:
        >>> get_geohash_bounds("9q8yym")
        {'min_lat': 37.77, 'max_lat': 37.78, 'min_lng': -122.42, 'max_lng': -122.41, ...}
    """
    # decode_exactly returns (lat, lng, lat_err, lng_err)
    lat, lng, lat_err, lng_err = pgh.decode_exactly(geohash)

    return {
        'min_lat': lat - lat_err,
        'max_lat': lat + lat_err,
        'min_lng': lng - lng_err,
        'max_lng': lng + lng_err,
        'center_lat': lat,
        'center_lng': lng,
    }
