"""
Factory for creating location API provider clients.

Provides a unified interface for selecting between Google and TomTom
providers with optional fallback support.
"""

import logging
from typing import Optional

from constance import config

from .base import BasePlacesClient
from .google_places import GooglePlacesClient
from .tomtom import TomTomClient

logger = logging.getLogger(__name__)

# Provider name constants
PROVIDER_GOOGLE = "google"
PROVIDER_TOMTOM = "tomtom"

# Map provider names to client classes
PROVIDER_CLIENTS = {
    PROVIDER_GOOGLE: GooglePlacesClient,
    PROVIDER_TOMTOM: TomTomClient,
}


def get_places_client(
    provider: Optional[str] = None,
    fallback: Optional[str] = None,
) -> Optional[BasePlacesClient]:
    """
    Get a places API client based on configuration.

    Uses Constance settings for provider selection if not specified.
    Supports automatic fallback to secondary provider if primary fails.

    Args:
        provider: Override primary provider ('google' or 'tomtom').
                  Defaults to PLACES_PROVIDER setting.
        fallback: Override fallback provider ('google' or 'tomtom').
                  Defaults to PLACES_PROVIDER_FALLBACK setting.
                  Set to None or empty string to disable fallback.

    Returns:
        BasePlacesClient instance, or None if no provider available.

    Example:
        >>> client = get_places_client()
        >>> if client:
        ...     venues = client.nearby_search(37.7749, -122.4194)
    """
    # Get settings with defaults
    primary = (provider or getattr(config, 'PLACES_PROVIDER', PROVIDER_GOOGLE)).lower()
    fallback_provider = fallback if fallback is not None else getattr(
        config, 'PLACES_PROVIDER_FALLBACK', ''
    )
    if fallback_provider:
        fallback_provider = fallback_provider.lower()

    # Try primary provider
    client = _create_client(primary)
    if client and client.is_available():
        logger.info(f"Using primary places provider: {primary}")
        return client

    logger.warning(f"Primary places provider '{primary}' is not available")

    # Try fallback if configured
    if fallback_provider and fallback_provider != primary:
        client = _create_client(fallback_provider)
        if client and client.is_available():
            logger.info(f"Falling back to secondary provider: {fallback_provider}")
            return client
        logger.warning(f"Fallback provider '{fallback_provider}' is also not available")

    logger.error("No places provider available")
    return None


def _create_client(provider: str) -> Optional[BasePlacesClient]:
    """
    Create a client instance for the given provider.

    Args:
        provider: Provider name ('google' or 'tomtom')

    Returns:
        Client instance or None if provider unknown
    """
    client_class = PROVIDER_CLIENTS.get(provider)
    if client_class:
        return client_class()

    logger.error(f"Unknown places provider: {provider}")
    return None


def get_available_providers() -> list:
    """
    Get list of currently available (configured) providers.

    Returns:
        List of provider names that have API keys configured.
    """
    available = []
    for provider, client_class in PROVIDER_CLIENTS.items():
        client = client_class()
        if client.is_available():
            available.append(provider)
    return available
