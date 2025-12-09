"""
Google Places API client for location-based chat suggestions.

Uses the Google Places API (New) for nearby place discovery and
the Geocoding API for reverse geocoding (lat/lng to city/neighborhood).
"""

import logging
from typing import Dict, Any, List, Optional
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Place types to query for venue suggestions (broad mix for maximum appeal)
PLACE_TYPES = [
    'tourist_attraction',
    'museum',
    'art_gallery',
    'park',
    'restaurant',
    'bar',
    'cafe',
    'shopping_mall',
    'stadium',
    'movie_theater',
]


class GooglePlacesClient:
    """
    Google Places API client for fetching nearby places and reverse geocoding.

    Supports both the Places API (New) for nearby search and the
    Geocoding API for converting coordinates to city/neighborhood names.
    """

    # API endpoints
    NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self):
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        if not self.api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured")

    def is_available(self) -> bool:
        """Check if the API is configured and available."""
        return bool(self.api_key)

    def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """
        Get city and neighborhood from coordinates using Geocoding API.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Dict with 'city' and 'neighborhood' keys, or None on error
        """
        if not self.is_available():
            return None

        try:
            # Don't use result_type filter - it's too restrictive for rural/suburban areas
            # Instead, let Google return the best match and extract what we need
            params = {
                "latlng": f"{latitude},{longitude}",
                "key": self.api_key,
            }

            response = requests.get(self.GEOCODE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                logger.warning(f"Geocoding failed: {data.get('status')}")
                return None

            # Parse address components from all results
            # Priority: locality > administrative_area_level_3 > administrative_area_level_2
            city = None
            neighborhood = None

            for result in data["results"]:
                for component in result.get("address_components", []):
                    types = component.get("types", [])

                    # City: locality is preferred, but fall back to admin areas
                    if "locality" in types and not city:
                        city = component.get("long_name")
                    elif "administrative_area_level_3" in types and not city:
                        # Township/municipality level (common in MI suburbs)
                        city = component.get("long_name")

                    # Neighborhood: neighborhood or sublocality
                    if "neighborhood" in types and not neighborhood:
                        neighborhood = component.get("long_name")
                    elif "sublocality_level_1" in types and not neighborhood:
                        neighborhood = component.get("long_name")
                    elif "sublocality" in types and not neighborhood:
                        neighborhood = component.get("long_name")

            # If still no city, try administrative_area_level_2 (county)
            if not city:
                for result in data["results"]:
                    for component in result.get("address_components", []):
                        types = component.get("types", [])
                        if "administrative_area_level_2" in types:
                            city = component.get("long_name")
                            break
                    if city:
                        break

            # Also extract county for broader area suggestions
            county = None
            for result in data["results"]:
                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "administrative_area_level_2" in types:
                        county = component.get("long_name")
                        break
                if county:
                    break

            # Extract state name for metro area lookup
            state = None
            for result in data["results"]:
                for component in result.get("address_components", []):
                    types = component.get("types", [])
                    if "administrative_area_level_1" in types:
                        state = component.get("long_name")
                        break
                if state:
                    break

            logger.info(f"Geocoding result: city={city}, neighborhood={neighborhood}, county={county}, state={state}")
            return {
                "city": city,
                "neighborhood": neighborhood,
                "county": county,
                "state": state,
            }

        except requests.RequestException as e:
            logger.error(f"Geocoding API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected geocoding error: {str(e)}")
            return None

    def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        max_results: int = 10,
        place_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places using Places API (New).

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius_meters: Search radius in meters (default: 1000)
            max_results: Maximum number of results (default: 10)
            place_types: List of place types to include (default: PLACE_TYPES)

        Returns:
            List of place dictionaries with name, type, address, etc.
        """
        if not self.is_available():
            return []

        if place_types is None:
            place_types = PLACE_TYPES

        try:
            # Build request for Places API (New)
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": ",".join([
                    "places.displayName",
                    "places.id",
                    "places.types",
                    "places.primaryType",
                    "places.formattedAddress",
                    "places.location",
                    "places.rating",
                    "places.userRatingCount",
                ]),
            }

            body = {
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": latitude,
                            "longitude": longitude,
                        },
                        "radius": float(radius_meters),
                    }
                },
                "includedTypes": place_types,
                "maxResultCount": max_results,
                "rankPreference": "DISTANCE",
            }

            response = requests.post(
                self.NEARBY_SEARCH_URL,
                headers=headers,
                json=body,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            places = []
            for place in data.get("places", []):
                places.append({
                    "place_id": place.get("id", ""),
                    "name": place.get("displayName", {}).get("text", ""),
                    "primary_type": place.get("primaryType", ""),
                    "types": place.get("types", []),
                    "address": place.get("formattedAddress", ""),
                    "latitude": place.get("location", {}).get("latitude"),
                    "longitude": place.get("location", {}).get("longitude"),
                    "rating": place.get("rating"),
                    "user_ratings_total": place.get("userRatingCount"),
                })

            logger.info(f"Found {len(places)} nearby places at ({latitude}, {longitude})")
            return places

        except requests.RequestException as e:
            logger.error(f"Places API error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected places error: {str(e)}")
            return []


def map_google_type_to_category(google_type: str) -> str:
    """
    Map Google Places type to ChatPop category.

    Args:
        google_type: Google Places primaryType (e.g., "tourist_attraction")

    Returns:
        ChatPop category (e.g., "landmark", "restaurant", "venue")
    """
    TYPE_MAPPING = {
        "tourist_attraction": "landmark",
        "historical_landmark": "landmark",
        "monument": "landmark",
        "museum": "venue",
        "art_gallery": "venue",
        "park": "park",
        "national_park": "park",
        "botanical_garden": "park",
        "restaurant": "restaurant",
        "bar": "bar",
        "cafe": "cafe",
        "brewery": "bar",
        "shopping_mall": "venue",
        "stadium": "venue",
        "movie_theater": "venue",
        "amusement_park": "venue",
        "zoo": "venue",
    }
    return TYPE_MAPPING.get(google_type, "venue")
