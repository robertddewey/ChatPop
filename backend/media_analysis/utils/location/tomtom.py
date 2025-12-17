"""
TomTom Search API client for location-based chat suggestions.

Uses the TomTom Nearby Search API for POI discovery and
the Reverse Geocoding API for coordinate-to-address conversion.

API Documentation:
- Nearby Search: https://developer.tomtom.com/search-api/documentation/search-service/nearby-search
- Reverse Geocode: https://developer.tomtom.com/search-api/documentation/reverse-geocoding-service/reverse-geocode
"""

import logging
from typing import Dict, Any, List, Optional
import requests
from django.conf import settings

from .base import BasePlacesClient
from .category_mapping import map_tomtom_category, CHATPOP_CATEGORIES

logger = logging.getLogger(__name__)

# Categories we want to show in location suggestions (exclude location types and generic venue)
DESIRED_CATEGORIES = {'restaurant', 'bar', 'cafe', 'gym', 'theater', 'stadium'}


# TomTom category IDs to request for venue suggestions
# IMPORTANT: TomTom limits categorySet to 10 categories max
# See: https://developer.tomtom.com/search-api/documentation/search-service/poi-categories
#
# Focus: Conversation-friendly places where people gather and socialize
TOMTOM_CATEGORY_IDS = [
    # Food & Drink
    7315,   # Restaurant
    9376,   # Coffee Shop
    9379,   # Bar or Pub
    7372,   # Brewery
    # Sports & Entertainment
    7320,   # Gym / Sports Center
    7374,   # Stadium
    7342,   # Cinema / Theater
]


class TomTomClient(BasePlacesClient):
    """
    TomTom Search API client for fetching nearby places and reverse geocoding.

    Implements the BasePlacesClient interface with TomTom-specific API calls,
    normalizing responses to match the expected output format.
    """

    # API endpoints
    NEARBY_SEARCH_URL = "https://api.tomtom.com/search/2/nearbySearch/.json"
    REVERSE_GEOCODE_URL = "https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json"

    def __init__(self):
        self.api_key = getattr(settings, 'TOMTOM_API_KEY', None)
        if not self.api_key:
            logger.warning("TOMTOM_API_KEY not configured")

    def is_available(self) -> bool:
        """Check if the API is configured and available."""
        return bool(self.api_key)

    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "tomtom"

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Get city and neighborhood from coordinates using TomTom Reverse Geocoding.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Normalized dict with city, neighborhood, county, state keys
        """
        if not self.is_available():
            return None

        try:
            url = self.REVERSE_GEOCODE_URL.format(lat=latitude, lon=longitude)
            params = {
                "key": self.api_key,
                "radius": 100,  # meters
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            addresses = data.get("addresses", [])
            if not addresses:
                logger.warning(f"TomTom reverse geocode returned no addresses for ({latitude}, {longitude})")
                return None

            # TomTom returns addresses array, take the first (closest)
            address = addresses[0].get("address", {})

            # Extract location components
            # TomTom uses different field names than Google
            city = (
                address.get("municipality") or
                address.get("localName") or
                address.get("municipalitySubdivision")
            )
            neighborhood = address.get("municipalitySubdivision")
            county = address.get("countrySecondarySubdivision")
            state = address.get("countrySubdivision")

            # If neighborhood equals city, clear neighborhood to avoid duplication
            if neighborhood and city and neighborhood.lower() == city.lower():
                neighborhood = None

            logger.info(
                f"TomTom geocoding result: city={city}, neighborhood={neighborhood}, "
                f"county={county}, state={state}"
            )

            return {
                "city": city,
                "neighborhood": neighborhood,
                "county": county,
                "state": state,
            }

        except requests.RequestException as e:
            logger.error(f"TomTom Geocoding API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected TomTom geocoding error: {str(e)}")
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
        Search for nearby places using TomTom Nearby Search API.

        Uses categorySet parameter to filter results at the API level,
        ensuring we get relevant venue types (restaurants, cafes, bars, etc.)
        instead of mixed POIs sorted by distance.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius_meters: Search radius in meters (default: 1000)
            max_results: Maximum number of results to return (default: 10)
            place_types: List of ChatPop categories to filter (not used - we use TOMTOM_CATEGORY_IDS)

        Returns:
            List of normalized place dictionaries
        """
        if not self.is_available():
            return []

        try:
            # Use categorySet to filter at API level for relevant venue types
            # This ensures all returned results are restaurants, cafes, bars, etc.
            category_set = ",".join(str(cat_id) for cat_id in TOMTOM_CATEGORY_IDS)

            params = {
                "key": self.api_key,
                "lat": latitude,
                "lon": longitude,
                "radius": radius_meters,
                "limit": 100,  # Request max, we'll take up to max_results
                "categorySet": category_set,
            }

            response = requests.get(self.NEARBY_SEARCH_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            places = []
            for result in data.get("results", []):
                poi = result.get("poi", {})
                address = result.get("address", {})
                position = result.get("position", {})

                # Get category info for mapping
                categories = poi.get("categories", [])
                category_ids = poi.get("categorySet", [])

                # Use first category ID if available, otherwise empty
                primary_category_id = ""
                primary_category_name = ""
                if category_ids:
                    primary_category_id = str(category_ids[0].get("id", ""))
                if categories:
                    primary_category_name = categories[0]

                # Map to ChatPop category
                chatpop_category = map_tomtom_category(primary_category_id, primary_category_name)

                # Filter to desired categories (skip generic 'venue' and location types)
                if chatpop_category not in DESIRED_CATEGORIES:
                    continue

                # Skip places where TomTom's category name indicates a school/education
                # even if they have incorrect category IDs (TomTom data quality issue)
                # Also check all categories in case "school" appears in secondary types
                all_category_names = [c.lower() for c in categories]
                school_keywords = ('school', 'elementary', 'middle school', 'high school',
                                   'primary school', 'secondary school', 'college', 'university')
                if any(kw in name for name in all_category_names for kw in school_keywords):
                    continue

                # Build normalized place dict
                places.append({
                    "place_id": result.get("id", ""),
                    "name": poi.get("name", ""),
                    "primary_type": chatpop_category,
                    "types": categories,
                    "address": address.get("freeformAddress", ""),
                    "latitude": position.get("lat"),
                    "longitude": position.get("lon"),
                    "rating": None,  # TomTom doesn't provide ratings
                    "user_ratings_total": None,
                })

                # Stop once we have enough results
                if len(places) >= max_results:
                    break

            logger.info(
                f"TomTom found {len(places)} nearby places at ({latitude}, {longitude}) "
                f"using categorySet API filtering"
            )
            return places

        except requests.RequestException as e:
            logger.error(f"TomTom Places API error: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected TomTom places error: {str(e)}")
            return []
