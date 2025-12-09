"""
Metro area lookup utilities.

Looks up metropolitan/combined statistical areas from county + state
using Census Bureau CBSA data.
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# State name to abbreviation mapping
STATE_ABBREVIATIONS = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


@lru_cache(maxsize=1)
def _load_county_to_metro() -> Dict[str, Dict[str, str]]:
    """Load the county to metro JSON mapping (cached)."""
    json_path = Path(__file__).parent / "county_to_metro.json"

    if not json_path.exists():
        logger.warning(f"Metro lookup data not found at {json_path}")
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load metro lookup data: {e}")
        return {}


def normalize_county(county_name: str) -> str:
    """
    Normalize county name for consistent lookups.

    Args:
        county_name: County name from Google Geocoding (e.g., "Oakland County")

    Returns:
        Normalized county name (e.g., "oakland")
    """
    # Remove common suffixes
    name = re.sub(
        r'\s+(County|Parish|Borough|Municipality|Census Area|City and Borough)$',
        '',
        county_name,
        flags=re.IGNORECASE
    )
    return name.strip().lower()


def normalize_state(state_name: str) -> str:
    """
    Normalize state name for consistent lookups.

    Args:
        state_name: State name (e.g., "Michigan" or "MI")

    Returns:
        Lowercase state name (e.g., "michigan")
    """
    return state_name.strip().lower()


def lookup_metro_area(county: str, state: str) -> Optional[Tuple[str, str]]:
    """
    Look up the metro area for a given county and state.

    Args:
        county: County name (e.g., "Oakland County", "Oakland")
        state: State name (e.g., "Michigan", "MI")

    Returns:
        Tuple of (official_name, friendly_name) or None if not found.
        Example: ("Detroit-Warren-Ann Arbor, MI", "Metro Detroit")
    """
    county_to_metro = _load_county_to_metro()

    if not county_to_metro:
        return None

    normalized_county = normalize_county(county)
    normalized_state = normalize_state(state)

    # Build lookup key
    key = f"{normalized_county}|{normalized_state}"

    result = county_to_metro.get(key)
    if result:
        return (result["csa"], result["friendly"])

    # Try with "county" suffix if not found
    key_with_suffix = f"{normalized_county} county|{normalized_state}"
    result = county_to_metro.get(key_with_suffix)
    if result:
        return (result["csa"], result["friendly"])

    logger.debug(f"No metro area found for county={county}, state={state}")
    return None


def get_metro_friendly_name(county: str, state: str) -> Optional[str]:
    """
    Get just the friendly metro area name.

    Args:
        county: County name (e.g., "Oakland County")
        state: State name (e.g., "Michigan")

    Returns:
        Friendly metro name (e.g., "Metro Detroit") or None
    """
    result = lookup_metro_area(county, state)
    return result[1] if result else None
