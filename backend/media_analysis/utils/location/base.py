"""
Abstract base classes for location API providers.

Defines the common interface that all location providers (Google, TomTom, etc.)
must implement for nearby place search and reverse geocoding.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePlacesClient(ABC):
    """
    Abstract base class for places/POI search providers.

    All implementations must return data in a normalized format,
    regardless of the underlying API's response structure.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the API is configured and available."""
        pass

    @abstractmethod
    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> Optional[Dict[str, Any]]:
        """
        Get city and neighborhood from coordinates.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate

        Returns:
            Normalized dict with keys:
            - city: str | None
            - neighborhood: str | None
            - county: str | None
            - state: str | None
        """
        pass

    @abstractmethod
    def nearby_search(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        max_results: int = 10,
        place_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for nearby places/POIs.

        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            radius_meters: Search radius in meters
            max_results: Maximum number of results
            place_types: Optional list of place types to filter (ChatPop categories)

        Returns:
            List of normalized place dicts with keys:
            - place_id: str (unique ID from provider)
            - name: str (display name)
            - primary_type: str (ChatPop category)
            - types: List[str] (original provider types)
            - address: str (formatted address)
            - latitude: float
            - longitude: float
            - rating: float | None (if available)
            - user_ratings_total: int | None (if available)
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'google', 'tomtom')."""
        pass
