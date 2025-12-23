"""
Hybrid caching for location suggestions.

Uses a two-tier cache strategy:
1. Redis (hot cache) - Fast lookups with TTL-based expiration
2. PostgreSQL (persistent cache) - Survives Redis restarts

Cache flow:
1. Check Redis by geohash
2. If miss, check PostgreSQL
3. If miss, call Places API (centered on geohash center)
4. Cache result in both Redis and PostgreSQL
5. Re-rank venues by distance from user's actual location
6. Return top N venues
"""

import json
import logging
import math
from typing import Dict, Any, Optional, List
from django.core.cache import cache
from django.utils.text import slugify
from constance import config

from .geohash_utils import encode_location, get_cache_key, get_geohash_bounds
from .factory import get_places_client
from .category_mapping import map_google_type
from .metro_lookup import get_metro_friendly_name
from ..rate_limit import increment_location_rate_limit

logger = logging.getLogger(__name__)


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def _rerank_suggestions_by_distance(
    suggestions: List[Dict[str, Any]],
    user_lat: float,
    user_lng: float,
    max_venues: int,
) -> List[Dict[str, Any]]:
    """
    Re-rank venue suggestions by distance from user's actual location.

    Non-venue suggestions (neighborhood, city, metro) are preserved at the end.

    Args:
        suggestions: List of suggestion dicts (venues must have lat/lng)
        user_lat: User's actual latitude
        user_lng: User's actual longitude
        max_venues: Maximum number of venues to return

    Returns:
        Re-ranked suggestions with closest venues first, then location types
    """
    venue_types = {'restaurant', 'bar', 'cafe', 'gym', 'theater', 'stadium', 'venue'}
    location_types = {'neighborhood', 'city', 'metro', 'county'}

    venues = []
    locations = []

    for suggestion in suggestions:
        stype = suggestion.get('type', '')
        if stype in location_types:
            locations.append(suggestion)
        elif stype in venue_types:
            # Calculate distance if coordinates available
            lat = suggestion.get('latitude')
            lng = suggestion.get('longitude')
            if lat is not None and lng is not None:
                distance = _haversine_distance(user_lat, user_lng, lat, lng)
                suggestion['distance_meters'] = round(distance, 1)
            else:
                suggestion['distance_meters'] = float('inf')
            venues.append(suggestion)
        else:
            # Unknown type, treat as venue
            venues.append(suggestion)

    # Sort venues by distance
    venues.sort(key=lambda v: v.get('distance_meters', float('inf')))

    # Take top max_venues
    top_venues = venues[:max_venues]

    # Combine: venues first, then locations
    return top_venues + locations


def get_or_fetch_location_suggestions(
    latitude: float,
    longitude: float,
    user_id: Optional[int] = None,
    fingerprint: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get location suggestions from cache or fetch from Places API.

    Cache hierarchy (hybrid approach):
    1. Redis hot cache (24h TTL) - fastest
    2. PostgreSQL persistent cache - survives restarts
    3. Places API - fresh fetch (centered on geohash center)

    All results are re-ranked by distance from user's actual location.

    Rate limiting:
    - Only counts API calls (cache hits don't increment rate limit)
    - Pass user_id/fingerprint/ip_address to enable rate limit tracking

    Args:
        latitude: User's latitude coordinate
        longitude: User's longitude coordinate
        user_id: Authenticated user ID (for rate limiting)
        fingerprint: Browser fingerprint (for rate limiting)
        ip_address: Client IP address (for rate limiting)

    Returns:
        Dictionary with location info and suggestions, or None on error

    Example:
        >>> result = get_or_fetch_location_suggestions(37.7749, -122.4194)
        >>> result['location']['city']
        'San Francisco'
    """
    # Check if feature is enabled
    if not config.LOCATION_SUGGESTIONS_ENABLED:
        logger.info("Location suggestions disabled via LOCATION_SUGGESTIONS_ENABLED")
        return None

    # Generate geohash for cache lookup
    geohash = encode_location(latitude, longitude)

    # Get current settings
    radius = config.LOCATION_SEARCH_RADIUS_METERS
    max_venues_return = config.LOCATION_MAX_VENUES  # How many to return to user
    max_venues_cache = config.LOCATION_CACHE_MAX_VENUES  # How many to store in cache

    # Cache key uses cache max (what we store), not return max
    redis_key = get_cache_key(geohash, radius, max_venues_cache)
    cache_key_suffix = f":r{radius}:v{max_venues_cache}"
    pg_cache_key = f"{geohash}{cache_key_suffix}"

    # Step 1: Check Redis hot cache
    cached = cache.get(redis_key)
    if cached:
        logger.info(f"Redis cache HIT for key={redis_key}")
        try:
            result = json.loads(cached) if isinstance(cached, str) else cached
            result = result.copy()  # Don't mutate cached data

            # Re-rank suggestions by distance from user's actual location
            if result.get('suggestions'):
                result['suggestions'] = _rerank_suggestions_by_distance(
                    result['suggestions'],
                    latitude,
                    longitude,
                    max_venues_return,
                )
                result['best_guess'] = result['suggestions'][0] if result['suggestions'] else None

            result['cached'] = True
            result['cache_source'] = 'redis'
            return result
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse Redis cache: {e}")

    # Step 2: Check PostgreSQL persistent cache
    try:
        from media_analysis.models import LocationSuggestionsCache

        pg_cached = LocationSuggestionsCache.objects.filter(
            geohash=pg_cache_key
        ).first()

        if pg_cached:
            logger.info(f"PostgreSQL cache HIT for key={pg_cache_key}")
            pg_cached.increment_lookup()

            # Warm Redis cache (with full data, not re-ranked)
            ttl_seconds = config.LOCATION_CACHE_TTL_HOURS * 3600
            cache.set(redis_key, json.dumps(pg_cached.suggestions_data), timeout=ttl_seconds)

            result = pg_cached.suggestions_data.copy()

            # Re-rank suggestions by distance from user's actual location
            if result.get('suggestions'):
                result['suggestions'] = _rerank_suggestions_by_distance(
                    result['suggestions'],
                    latitude,
                    longitude,
                    max_venues_return,
                )
                result['best_guess'] = result['suggestions'][0] if result['suggestions'] else None

            result['cached'] = True
            result['cache_source'] = 'postgresql'
            return result

    except Exception as e:
        logger.warning(f"PostgreSQL cache lookup failed: {str(e)}")

    # Step 3: Fetch from Places API (uses factory for provider selection)
    logger.info(f"Cache MISS for geohash={geohash} - fetching from API")

    # Increment rate limit counter only on API calls (not cache hits)
    if ip_address:
        new_count = increment_location_rate_limit(user_id, fingerprint, ip_address)
        logger.info(f"Location API call - rate limit incremented to {new_count}")

    client = get_places_client()
    if not client:
        logger.error("No places API provider available")
        return None

    # Get geohash center coordinates for API search
    # This ensures consistent coverage for all users in the same geohash cell
    bounds = get_geohash_bounds(geohash)
    center_lat = bounds['center_lat']
    center_lng = bounds['center_lng']

    logger.info(f"Using geohash center ({center_lat}, {center_lng}) for API search "
                f"(user at {latitude}, {longitude})")

    # Fetch city/neighborhood/county/state via reverse geocoding (use user's location for accuracy)
    geocode_result = client.reverse_geocode(latitude, longitude)
    city = geocode_result.get('city') if geocode_result else None
    neighborhood = geocode_result.get('neighborhood') if geocode_result else None
    county = geocode_result.get('county') if geocode_result else None
    state = geocode_result.get('state') if geocode_result else None

    # Look up metro area from county + state
    metro_area = None
    if county and state:
        metro_area = get_metro_friendly_name(county, state)
        if metro_area:
            logger.info(f"Metro area lookup: {county}, {state} -> {metro_area}")

    # Fetch nearby venues from geohash CENTER (not user's location)
    # This provides consistent coverage for the entire geohash cell
    venues = client.nearby_search(
        latitude=center_lat,
        longitude=center_lng,
        radius_meters=radius,
        max_results=max_venues_cache,  # Fetch more for caching
    )

    # Build tiered suggestions list (includes lat/lng for each venue)
    all_suggestions = _build_tiered_suggestions(city, neighborhood, metro_area, venues)

    # Build cache result (stores all venues)
    cache_result = {
        'location': {
            'city': city,
            'neighborhood': neighborhood,
            'county': county,
            'metro_area': metro_area,
            'state': state,
            'geohash': geohash,
            'center_latitude': center_lat,
            'center_longitude': center_lng,
        },
        'suggestions': all_suggestions,
    }

    # Step 4: Cache the full result
    _cache_result(geohash, center_lat, center_lng, city, neighborhood, cache_result)

    # Re-rank for this specific user before returning
    reranked_suggestions = _rerank_suggestions_by_distance(
        all_suggestions,
        latitude,
        longitude,
        max_venues_return,
    )

    # Build user-specific result
    result = {
        'location': {
            'city': city,
            'neighborhood': neighborhood,
            'county': county,
            'metro_area': metro_area,
            'state': state,
            'geohash': geohash,
            'latitude': latitude,
            'longitude': longitude,
        },
        'suggestions': reranked_suggestions,
        'best_guess': reranked_suggestions[0] if reranked_suggestions else None,
        'cached': False,
        'cache_source': 'api',
    }

    return result


def _cache_result(
    geohash: str,
    latitude: float,
    longitude: float,
    city: Optional[str],
    neighborhood: Optional[str],
    result: Dict[str, Any],
) -> None:
    """
    Cache location suggestions in both Redis and PostgreSQL.

    Cache keys include current settings (radius, cache_max_venues) so changing
    settings automatically creates new cache entries.

    Args:
        geohash: Geohash key for cache lookup
        latitude: Geohash center latitude
        longitude: Geohash center longitude
        city: City name from geocoding
        neighborhood: Neighborhood name from geocoding
        result: Full result dictionary to cache (with all venues)
    """
    # Get current settings for cache key
    radius = config.LOCATION_SEARCH_RADIUS_METERS
    max_venues_cache = config.LOCATION_CACHE_MAX_VENUES  # Use cache max, not return max

    # Build settings-aware cache keys
    redis_key = get_cache_key(geohash, radius, max_venues_cache)
    cache_key_suffix = f":r{radius}:v{max_venues_cache}"
    pg_cache_key = f"{geohash}{cache_key_suffix}"

    # Cache in Redis (hot cache)
    try:
        ttl_seconds = config.LOCATION_CACHE_TTL_HOURS * 3600
        cache.set(redis_key, json.dumps(result), timeout=ttl_seconds)
        logger.info(f"Cached in Redis: {redis_key} (TTL: {ttl_seconds}s)")
    except Exception as e:
        logger.warning(f"Failed to cache in Redis: {str(e)}")

    # Cache in PostgreSQL (persistent cache)
    try:
        from media_analysis.models import LocationSuggestionsCache

        LocationSuggestionsCache.objects.update_or_create(
            geohash=pg_cache_key,
            defaults={
                'latitude': latitude,
                'longitude': longitude,
                'city_name': city or '',
                'neighborhood_name': neighborhood or '',
                'suggestions_data': result,
            }
        )
        logger.info(f"Cached in PostgreSQL: geohash={pg_cache_key}")
    except Exception as e:
        logger.warning(f"Failed to cache in PostgreSQL: {str(e)}")


def invalidate_location_cache(geohash: str) -> bool:
    """
    Invalidate cache for a specific geohash.

    Removes from both Redis and PostgreSQL caches.

    Args:
        geohash: Geohash to invalidate

    Returns:
        True if successfully invalidated, False otherwise
    """
    redis_key = get_cache_key(geohash)

    try:
        # Remove from Redis
        cache.delete(redis_key)

        # Remove from PostgreSQL
        from media_analysis.models import LocationSuggestionsCache
        LocationSuggestionsCache.objects.filter(geohash=geohash).delete()

        logger.info(f"Invalidated cache for geohash={geohash}")
        return True

    except Exception as e:
        logger.error(f"Failed to invalidate cache: {str(e)}")
        return False


def _sanitize_venue_name(name: str) -> str:
    """
    Clean up venue names from Google Places API.

    Fixes common issues like:
    - Unbalanced parentheses: "Foo (Bar )BAZ)" -> "Foo (Bar BAZ)"
    - Extra whitespace: "Foo  Bar" -> "Foo Bar"
    - Trailing/leading whitespace

    Args:
        name: Raw venue name from Google Places API

    Returns:
        Cleaned venue name
    """
    import re

    if not name:
        return name

    # Normalize whitespace (collapse multiple spaces, trim)
    name = ' '.join(name.split())

    # Fix unbalanced parentheses by removing content in parens if malformed
    open_count = name.count('(')
    close_count = name.count(')')

    if open_count != close_count:
        # Remove all parenthetical content if unbalanced
        name = re.sub(r'\s*\([^)]*\)?\s*', ' ', name)
        name = re.sub(r'\s*\)[^(]*\(?\s*', ' ', name)
        name = ' '.join(name.split())

    return name.strip()


def _build_tiered_suggestions(
    city: Optional[str],
    neighborhood: Optional[str],
    metro_area: Optional[str],
    venues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Build a tiered list of location suggestions.

    Order:
    1. Venues (will be re-ranked by distance from user's location)
    2. Neighborhood (if available)
    3. City/Township (if available)
    4. Metro area (if available, e.g., "Metro Detroit")

    Args:
        city: City name from geocoding
        neighborhood: Neighborhood name from geocoding
        metro_area: Metro area friendly name (e.g., "Metro Detroit")
        venues: List of nearby venues from Places API

    Returns:
        List of suggestion dictionaries with name, key, type, lat/lng, etc.
    """
    suggestions = []

    # Add venues with their coordinates for later re-ranking
    for venue in venues:
        # primary_type is already mapped to ChatPop category by the provider client
        venue_type = venue.get('primary_type', 'venue')
        name = _sanitize_venue_name(venue.get('name', ''))

        if not name:
            continue

        # Create a unique key from venue name and place_id
        place_id = venue.get('place_id', '')
        key = slugify(name)[:80]
        if place_id:
            # Add last 6 chars of place_id for uniqueness
            key = f"{key}-{place_id[-6:]}"

        suggestions.append({
            'name': name,
            'key': key,
            'type': venue_type,
            'place_id': place_id,
            'latitude': venue.get('latitude'),
            'longitude': venue.get('longitude'),
        })

    # Add neighborhood after venues
    if neighborhood:
        suggestions.append({
            'name': neighborhood,
            'key': slugify(neighborhood),
            'type': 'neighborhood',
        })

    # Add city
    if city:
        suggestions.append({
            'name': city,
            'key': slugify(city),
            'type': 'city',
        })

    # Add metro area last (if available)
    if metro_area:
        suggestions.append({
            'name': metro_area,
            'key': slugify(metro_area),
            'type': 'metro',
        })

    return suggestions
