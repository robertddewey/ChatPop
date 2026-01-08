"""
Pin Tier Utilities

Handles tier validation and computation for the message pinning system.
Tiers are configured via constance settings.
"""
import json
from typing import List, Optional, Dict
from constance import config


def get_time_tiers() -> Dict[int, int]:
    """
    Get the explicit time tiers mapping (amount_cents -> duration_minutes).
    Parses the JSON from constance config.

    Returns:
        Dict mapping amount in cents to duration in minutes
    """
    try:
        tiers = json.loads(config.PIN_TIME_TIERS_JSON)
        # Convert string keys to integers (JSON keys are always strings)
        return {int(k): int(v) for k, v in tiers.items()}
    except (json.JSONDecodeError, ValueError):
        # Fallback to default tiers if config is invalid
        return {100: 10, 200: 15, 500: 20, 1000: 30, 1500: 45, 2000: 60}


def get_valid_pin_tiers() -> List[int]:
    """
    Get all valid tier amounts in cents, sorted ascending.

    Includes:
    - Explicit tiers from PIN_TIME_TIERS_JSON
    - Generated tiers from last explicit tier up to PIN_TIER_MAX_CENTS
      using PIN_TIER_INCREMENT_CENTS increments

    Returns:
        Sorted list of valid tier amounts in cents
    """
    time_tiers = get_time_tiers()
    tiers = list(time_tiers.keys())

    # Get increment and max from constance
    increment = config.PIN_TIER_INCREMENT_CENTS
    max_cents = config.PIN_TIER_MAX_CENTS

    # Find the last explicit tier
    if tiers:
        last_explicit = max(tiers)

        # Generate additional tiers by increment
        current = last_explicit + increment
        while current <= max_cents:
            tiers.append(current)
            current += increment

    return sorted(tiers)


def is_valid_tier(amount_cents: int) -> bool:
    """
    Check if an amount is a valid tier.

    Args:
        amount_cents: Amount to check in cents

    Returns:
        True if amount is a valid tier, False otherwise
    """
    return amount_cents in get_valid_pin_tiers()


def get_next_tier_above(amount_cents: int) -> Optional[int]:
    """
    Get the minimum tier required to outbid a given amount.

    Args:
        amount_cents: Current pin amount in cents

    Returns:
        Next tier above the amount, or None if at/above max tier
    """
    tiers = get_valid_pin_tiers()
    for tier in tiers:
        if tier > amount_cents:
            return tier
    return None  # Already at or above max tier


def get_tier_duration_minutes(amount_cents: int) -> int:
    """
    Get the duration in minutes for a given tier (for Add-to-Pin time extension).

    For explicit tiers, returns the configured duration.
    For generated tiers (beyond explicit list), returns PIN_MAX_EXTENSION_MINUTES.

    Args:
        amount_cents: Tier amount in cents

    Returns:
        Duration in minutes for this tier
    """
    time_tiers = get_time_tiers()

    if amount_cents in time_tiers:
        return time_tiers[amount_cents]

    # For tiers beyond explicit list, use the max extension
    return config.PIN_MAX_EXTENSION_MINUTES


def get_new_pin_duration_minutes() -> int:
    """
    Get the duration for new pins or outbids.
    All new pins/outbids get the same duration regardless of tier.

    Returns:
        Duration in minutes for new pins
    """
    return config.PIN_NEW_PIN_DURATION_MINUTES


def get_tiers_for_frontend() -> List[Dict]:
    """
    Get tier information formatted for frontend consumption.

    Returns:
        List of tier objects with amount_cents and duration_minutes
    """
    tiers = get_valid_pin_tiers()
    result = []

    for amount_cents in tiers:
        result.append({
            'amount_cents': amount_cents,
            'duration_minutes': get_tier_duration_minutes(amount_cents),
        })

    return result


def validate_pin_amount(amount_cents: int, current_sticky_amount: int = 0, is_add_to_pin: bool = False) -> Dict:
    """
    Validate a pin amount and return detailed validation result.

    Args:
        amount_cents: Amount being submitted
        current_sticky_amount: Current sticky pin amount (0 if no sticky)
        is_add_to_pin: True if this is an Add-to-Pin action (extending own pin)

    Returns:
        Dict with 'valid' (bool), 'error' (str or None), and 'details' (dict)
    """
    # Check if valid tier
    if not is_valid_tier(amount_cents):
        valid_tiers = get_valid_pin_tiers()
        return {
            'valid': False,
            'error': f'Invalid tier amount. Valid tiers: {valid_tiers}',
            'details': {'valid_tiers': valid_tiers}
        }

    # For Add-to-Pin, any valid tier works (extends time)
    if is_add_to_pin:
        return {
            'valid': True,
            'error': None,
            'details': {
                'duration_minutes': get_tier_duration_minutes(amount_cents),
                'is_extension': True
            }
        }

    # For new pin/outbid, must be higher than current sticky
    if current_sticky_amount > 0:
        min_required = get_next_tier_above(current_sticky_amount)
        if min_required is None:
            return {
                'valid': False,
                'error': 'Current sticky is at maximum tier and cannot be outbid',
                'details': {'current_sticky_amount': current_sticky_amount}
            }
        if amount_cents < min_required:
            return {
                'valid': False,
                'error': f'Must bid at least ${min_required / 100:.2f} to outbid current sticky (${current_sticky_amount / 100:.2f})',
                'details': {
                    'current_sticky_amount': current_sticky_amount,
                    'minimum_required': min_required
                }
            }

    return {
        'valid': True,
        'error': None,
        'details': {
            'duration_minutes': get_new_pin_duration_minutes(),
            'is_extension': False
        }
    }
