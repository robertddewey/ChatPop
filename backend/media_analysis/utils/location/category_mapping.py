"""
Unified category mapping for location providers.

Maps provider-specific place types (Google, TomTom) to ChatPop's
internal category system for consistent display across providers.

Simplified to broad categories - we don't distinguish cuisine types.
"""

from typing import Optional


# ChatPop internal categories - broad, simple categories
CHATPOP_CATEGORIES = [
    # Venues
    'restaurant',   # All restaurants regardless of cuisine
    'bar',          # Bars, pubs, breweries, nightclubs
    'cafe',         # Coffee shops, bakeries, ice cream
    'gym',          # Fitness centers, sports clubs
    'theater',      # Movie theaters, cinemas
    'stadium',      # Sports arenas, stadiums
    'venue',        # Generic catch-all for other places
    # Location types
    'neighborhood',
    'city',
    'metro',
]


# =============================================================================
# Google Places Type Mapping
# =============================================================================

GOOGLE_TYPE_MAPPING = {
    # Restaurants - ALL map to 'restaurant'
    "restaurant": "restaurant",
    "food": "restaurant",
    "meal_delivery": "restaurant",
    "meal_takeaway": "restaurant",
    "pizza_restaurant": "restaurant",
    "pizzeria": "restaurant",
    "sushi_restaurant": "restaurant",
    "japanese_restaurant": "restaurant",
    "chinese_restaurant": "restaurant",
    "mexican_restaurant": "restaurant",
    "italian_restaurant": "restaurant",
    "thai_restaurant": "restaurant",
    "indian_restaurant": "restaurant",
    "seafood_restaurant": "restaurant",
    "steak_house": "restaurant",
    "steakhouse": "restaurant",
    "hamburger_restaurant": "restaurant",
    "barbecue_restaurant": "restaurant",
    "fast_food_restaurant": "restaurant",
    "sandwich_shop": "restaurant",
    "deli": "restaurant",
    "breakfast_restaurant": "restaurant",
    "brunch_restaurant": "restaurant",
    "american_restaurant": "restaurant",
    "asian_restaurant": "restaurant",
    "french_restaurant": "restaurant",
    "greek_restaurant": "restaurant",
    "korean_restaurant": "restaurant",
    "vietnamese_restaurant": "restaurant",
    "ramen_restaurant": "restaurant",
    "food_court": "restaurant",
    "food_truck": "restaurant",

    # Bars - ALL map to 'bar'
    "bar": "bar",
    "pub": "bar",
    "night_club": "bar",
    "brewery": "bar",
    "wine_bar": "bar",
    "cocktail_bar": "bar",
    "sports_bar": "bar",

    # Cafes - ALL map to 'cafe'
    "cafe": "cafe",
    "coffee_shop": "cafe",
    "tea_house": "cafe",
    "bakery": "cafe",
    "ice_cream_shop": "cafe",
    "dessert_shop": "cafe",
    "donut_shop": "cafe",
    "juice_bar": "cafe",

    # Gyms
    "gym": "gym",
    "fitness_center": "gym",
    "health_club": "gym",

    # Theaters
    "movie_theater": "theater",
    "cinema": "theater",

    # Stadiums
    "stadium": "stadium",
    "sports_complex": "stadium",
    "arena": "stadium",

    # Generic venues
    "tourist_attraction": "venue",
    "museum": "venue",
    "art_gallery": "venue",
    "amusement_park": "venue",
    "zoo": "venue",
    "aquarium": "venue",
    "casino": "venue",
    "bowling_alley": "venue",
    "spa": "venue",
    "park": "venue",
    "shopping_mall": "venue",
}


def map_google_type(google_type: str) -> str:
    """
    Map a Google Places type to a ChatPop category.

    Args:
        google_type: Google Places primaryType (e.g., "pizza_restaurant")

    Returns:
        ChatPop category string
    """
    # Check exact match
    if google_type in GOOGLE_TYPE_MAPPING:
        return GOOGLE_TYPE_MAPPING[google_type]

    # Simple keyword fallback
    type_lower = google_type.lower()
    if "restaurant" in type_lower or "food" in type_lower:
        return "restaurant"
    if "bar" in type_lower or "pub" in type_lower or "brewery" in type_lower:
        return "bar"
    if "cafe" in type_lower or "coffee" in type_lower or "bakery" in type_lower:
        return "cafe"
    if "gym" in type_lower or "fitness" in type_lower:
        return "gym"
    if "theater" in type_lower or "cinema" in type_lower:
        return "theater"
    if "stadium" in type_lower or "arena" in type_lower:
        return "stadium"

    return "venue"


# =============================================================================
# TomTom Category Mapping
# =============================================================================

# TomTom category ID prefixes to ChatPop categories
# TomTom uses hierarchical IDs: 7315xxx = restaurants, 9379 = bars, etc.
TOMTOM_CATEGORY_MAPPING = {
    # Restaurants (7315 = Restaurant parent category)
    "7315": "restaurant",

    # Coffee/Cafe (9376 = Coffee Shop)
    "9376": "cafe",

    # Bars (9379 = Bar or Pub)
    "9379": "bar",

    # Brewery (7372)
    "7372": "bar",

    # Ice Cream (9377)
    "9377": "cafe",

    # Bakery (7317, 9382)
    "7317": "cafe",
    "9382": "cafe",

    # Gym/Sports Center (7320)
    "7320": "gym",

    # Cinema/Theater (7342)
    "7342": "theater",

    # Stadium (7374)
    "7374": "stadium",

    # Other venues
    "7376": "venue",    # Tourist Attraction
    "9902": "venue",    # Park
    "9362": "venue",    # Park
    "7373": "venue",    # Shopping Center
    "9361": "venue",    # Shopping Mall
    "7377": "venue",    # Amusement Park
    "9927": "venue",    # Zoo
    "7339": "venue",    # Casino
    "7333": "venue",    # Bowling
    "9912": "venue",    # Museum
}


def map_tomtom_category(category_id: str, category_name: str = "") -> str:
    """
    Map a TomTom category to a ChatPop category.

    Uses 4-digit prefix matching since TomTom uses hierarchical IDs.
    For example, 7315001, 7315052, 7315103 all start with "7315" (Restaurant).

    Args:
        category_id: TomTom category ID (e.g., "7315017")
        category_name: Optional category name (unused - kept for interface compatibility)

    Returns:
        ChatPop category string
    """
    # Try exact match first
    if category_id in TOMTOM_CATEGORY_MAPPING:
        return TOMTOM_CATEGORY_MAPPING[category_id]

    # Try 4-digit prefix match (covers all subcategories)
    if len(category_id) >= 4:
        prefix = category_id[:4]
        if prefix in TOMTOM_CATEGORY_MAPPING:
            return TOMTOM_CATEGORY_MAPPING[prefix]

    return "venue"


# =============================================================================
# Unified Interface
# =============================================================================

def map_type_to_category(provider_type: str, provider: str, type_name: str = "") -> str:
    """
    Map a provider-specific type to a ChatPop category.

    Args:
        provider_type: The type/category ID from the provider
        provider: Provider name ('google' or 'tomtom')
        type_name: Optional type name (unused)

    Returns:
        ChatPop category string
    """
    if provider == "google":
        return map_google_type(provider_type)
    elif provider == "tomtom":
        return map_tomtom_category(provider_type, type_name)
    return "venue"
