"""
Hybrid caching for location suggestions.

Uses a two-tier cache strategy:
1. Redis (hot cache) - Fast lookups with TTL-based expiration
2. PostgreSQL (persistent cache) - Survives Redis restarts

Cache flow:
1. Check Redis by geohash
2. If miss, check PostgreSQL
3. If miss, call Google Places API
4. Cache result in both Redis and PostgreSQL
"""

import json
import logging
from typing import Dict, Any, Optional, List
from django.core.cache import cache
from django.utils.text import slugify
from constance import config

from .geohash_utils import encode_location, get_cache_key
from .google_places import GooglePlacesClient, map_google_type_to_category
from .metro_lookup import get_metro_friendly_name

logger = logging.getLogger(__name__)


def get_or_fetch_location_suggestions(
    latitude: float,
    longitude: float,
) -> Optional[Dict[str, Any]]:
    """
    Get location suggestions from cache or fetch from Google Places API.

    Cache hierarchy (hybrid approach):
    1. Redis hot cache (24h TTL) - fastest
    2. PostgreSQL persistent cache - survives restarts
    3. Google Places API - fresh fetch

    Args:
        latitude: User's latitude coordinate
        longitude: User's longitude coordinate

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

    # Get current settings for cache key
    radius = config.LOCATION_SEARCH_RADIUS_METERS
    max_venues = config.LOCATION_MAX_VENUES

    # Cache key includes settings so changing them creates new cache entries
    redis_key = get_cache_key(geohash, radius, max_venues)
    cache_key_suffix = f":r{radius}:v{max_venues}"
    pg_cache_key = f"{geohash}{cache_key_suffix}"

    # Step 1: Check Redis hot cache
    cached = cache.get(redis_key)
    if cached:
        logger.info(f"Redis cache HIT for key={redis_key}")
        try:
            result = json.loads(cached) if isinstance(cached, str) else cached
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

            # Warm Redis cache
            ttl_seconds = config.LOCATION_CACHE_TTL_HOURS * 3600
            cache.set(redis_key, json.dumps(pg_cached.suggestions_data), timeout=ttl_seconds)

            result = pg_cached.suggestions_data.copy()
            result['cached'] = True
            result['cache_source'] = 'postgresql'
            return result

    except Exception as e:
        logger.warning(f"PostgreSQL cache lookup failed: {str(e)}")

    # Step 3: Fetch from Google Places API
    logger.info(f"Cache MISS for geohash={geohash} - fetching from API")

    client = GooglePlacesClient()
    if not client.is_available():
        logger.error("Google Places API key not configured")
        return None

    # Fetch city/neighborhood/county/state via reverse geocoding
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

    # Fetch nearby venues
    venues = client.nearby_search(
        latitude=latitude,
        longitude=longitude,
        radius_meters=config.LOCATION_SEARCH_RADIUS_METERS,
        max_results=config.LOCATION_MAX_VENUES,
    )

    # Build tiered suggestions list
    suggestions = _build_tiered_suggestions(city, neighborhood, metro_area, venues)

    # Build result
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
        'suggestions': suggestions,
        'best_guess': suggestions[0] if suggestions else None,
        'cached': False,
        'cache_source': 'api',
    }

    # Step 4: Cache the result
    _cache_result(geohash, latitude, longitude, city, neighborhood, result)

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

    Cache keys include current settings (radius, max_venues) so changing
    settings automatically creates new cache entries.

    Args:
        geohash: Geohash key for cache lookup
        latitude: Original latitude
        longitude: Original longitude
        city: City name from geocoding
        neighborhood: Neighborhood name from geocoding
        result: Full result dictionary to cache
    """
    # Get current settings for cache key
    radius = config.LOCATION_SEARCH_RADIUS_METERS
    max_venues = config.LOCATION_MAX_VENUES

    # Build settings-aware cache keys
    redis_key = get_cache_key(geohash, radius, max_venues)
    cache_key_suffix = f":r{radius}:v{max_venues}"
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
    1. Closest venue (best guess - "You might be at...")
    2. Other nearby venues (alternatives)
    3. Neighborhood (if available)
    4. City/Township (if available)
    5. Metro area (if available, e.g., "Metro Detroit")

    Args:
        city: City name from geocoding
        neighborhood: Neighborhood name from geocoding
        metro_area: Metro area friendly name (e.g., "Metro Detroit")
        venues: List of nearby venues from Places API (already sorted by distance)

    Returns:
        List of suggestion dictionaries with name, key, type, description, etc.
    """
    suggestions = []

    # Add venues first (already sorted by distance from API)
    for venue in venues:
        venue_type = map_google_type_to_category(venue.get('primary_type', ''))
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
