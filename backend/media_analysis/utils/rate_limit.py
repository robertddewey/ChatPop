"""
Rate limiting utilities for media analysis APIs.
Uses Redis to track upload/request attempts per hour.
Rate limits by user_id (authenticated), session_key (anonymous), or IP address (fallback).
Includes global (cross-user) rate limits to protect API budgets.
"""
from datetime import datetime
from functools import wraps
from typing import Optional, Tuple
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework.request import Request
from constance import config


def get_rate_limit_key(user_id: Optional[int], session_key: Optional[str], ip_address: str) -> str:
    """
    Generate Redis key for rate limiting.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        session_key: Session key for anonymous users (None for authenticated)
        ip_address: IP address of the request (fallback)

    Returns:
        Redis key string for tracking this client

    Example:
        >>> get_rate_limit_key(123, None, "192.168.1.1")
        "media_analysis:rate_limit:user:123"
        >>> get_rate_limit_key(None, "abc123sessionkey", "192.168.1.1")
        "media_analysis:rate_limit:session:abc123sessionkey"
        >>> get_rate_limit_key(None, None, "192.168.1.1")
        "media_analysis:rate_limit:ip:192.168.1.1"
    """
    if user_id:
        return f"media_analysis:rate_limit:user:{user_id}"
    elif session_key:
        return f"media_analysis:rate_limit:session:{session_key}"
    else:
        return f"media_analysis:rate_limit:ip:{ip_address}"


def check_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> Tuple[bool, int, int]:
    """
    Check if the client has exceeded the rate limit.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        session_key: Session key for anonymous users (None for authenticated)
        ip_address: IP address of the request (fallback)

    Returns:
        Tuple of (allowed, current_count, max_limit)
    """
    if user_id:
        max_limit = config.PHOTO_ANALYSIS_USER_LIMIT_PER_HOUR
    else:
        max_limit = config.PHOTO_ANALYSIS_SESSION_LIMIT_PER_HOUR

    cache_key = get_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    allowed = current_count < max_limit

    return allowed, current_count, max_limit


def increment_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> int:
    """
    Increment the rate limit counter for this client.

    Returns:
        New count value after increment
    """
    cache_key = get_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    new_count = current_count + 1

    if current_count == 0:
        cache.set(cache_key, new_count, timeout=3600)
    else:
        cache.set(cache_key, new_count, timeout=cache.ttl(cache_key))

    return new_count


def get_client_identifier(request: Request) -> Tuple[Optional[int], Optional[str], str]:
    """
    Extract client identifiers from request.

    Args:
        request: DRF Request object

    Returns:
        Tuple of (user_id, session_key, ip_address)
    """
    user_id = request.user.id if request.user.is_authenticated else None

    # Get or create session for anonymous users
    session_key = None
    if not user_id:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

    ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip_address:
        ip_address = ip_address.split(',')[0].strip()
    else:
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')

    return user_id, session_key, ip_address


def media_analysis_rate_limit(view_func):
    """
    Decorator to enforce rate limiting on photo analysis API endpoints.

    Usage:
        @media_analysis_rate_limit
        def post(self, request, *args, **kwargs):
            # Your view logic here
            pass

    Returns:
        - 429 Too Many Requests if rate limit exceeded
        - Original view response if allowed
    """
    @wraps(view_func)
    def wrapper(self, request: Request, *args, **kwargs):
        user_id, session_key, ip_address = get_client_identifier(request)

        if ip_address in ['127.0.0.1', '::1', 'localhost']:
            return view_func(self, request, *args, **kwargs)

        # Check global limit first (protects API budget)
        global_allowed, global_reason = check_global_rate_limit('photo')
        if not global_allowed:
            return JsonResponse({
                "error": "Service limit reached",
                "detail": global_reason,
            }, status=429)

        # Check per-user/session limit
        allowed, current_count, max_limit = check_rate_limit(user_id, session_key, ip_address)

        if not allowed:
            cache_key = get_rate_limit_key(user_id, session_key, ip_address)
            retry_after = cache.ttl(cache_key) or 3600

            return JsonResponse({
                "error": "Rate limit exceeded",
                "detail": "You have exceeded the maximum number of uploads per hour. Please try again later.",
                "current": current_count,
                "limit": max_limit,
                "retry_after_seconds": retry_after
            }, status=429)

        # Increment both counters
        increment_rate_limit(user_id, session_key, ip_address)
        increment_global_rate_limit('photo')

        response = view_func(self, request, *args, **kwargs)

        response['X-RateLimit-Limit'] = str(max_limit)
        response['X-RateLimit-Remaining'] = str(max(0, max_limit - current_count - 1))

        return response

    return wrapper


def get_remaining_uploads(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> Tuple[int, int, int]:
    """
    Get the number of remaining uploads for this client.

    Returns:
        Tuple of (remaining, used, limit)
    """
    allowed, current_count, max_limit = check_rate_limit(user_id, session_key, ip_address)
    remaining = max(0, max_limit - current_count)
    return remaining, current_count, max_limit


# ============================================================================
# Location-specific rate limiting
# ============================================================================

def get_location_rate_limit_key(user_id: Optional[int], session_key: Optional[str], ip_address: str) -> str:
    """
    Generate Redis key for location rate limiting.
    Uses a separate namespace from photo analysis.
    """
    if user_id:
        return f"location:rate_limit:user:{user_id}"
    elif session_key:
        return f"location:rate_limit:session:{session_key}"
    else:
        return f"location:rate_limit:ip:{ip_address}"


def check_location_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> Tuple[bool, int, int]:
    """
    Check if the client has exceeded the location rate limit.

    Returns:
        Tuple of (allowed, current_count, max_limit)
    """
    if user_id:
        max_limit = config.LOCATION_ANALYSIS_USER_LIMIT_PER_HOUR
    else:
        max_limit = config.LOCATION_ANALYSIS_SESSION_LIMIT_PER_HOUR

    cache_key = get_location_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    allowed = current_count < max_limit

    return allowed, current_count, max_limit


def increment_location_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> int:
    """
    Increment the location rate limit counter for this client.

    Returns:
        New count value after increment
    """
    cache_key = get_location_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    new_count = current_count + 1

    if current_count == 0:
        cache.set(cache_key, new_count, timeout=3600)
    else:
        cache.set(cache_key, new_count, timeout=cache.ttl(cache_key))

    return new_count


def location_rate_limit_check(view_func):
    """
    Decorator to check location rate limiting WITHOUT incrementing the counter.

    The counter should only be incremented when an actual API call is made,
    not on cache hits. Use increment_location_rate_limit() in the cache layer
    when making an API call.
    """
    @wraps(view_func)
    def wrapper(self, request: Request, *args, **kwargs):
        user_id, session_key, ip_address = get_client_identifier(request)

        if ip_address in ['127.0.0.1', '::1', 'localhost']:
            return view_func(self, request, *args, **kwargs)

        # Check global limit first (protects API budget)
        global_allowed, global_reason = check_global_rate_limit('location')
        if not global_allowed:
            return JsonResponse({
                "error": "Service limit reached",
                "detail": global_reason,
            }, status=429)

        # Check per-user/session limit (does NOT increment - that happens in cache layer)
        allowed, current_count, max_limit = check_location_rate_limit(user_id, session_key, ip_address)

        if not allowed:
            cache_key = get_location_rate_limit_key(user_id, session_key, ip_address)
            retry_after = cache.ttl(cache_key) or 3600

            return JsonResponse({
                "error": "Rate limit exceeded",
                "detail": "You have exceeded the maximum number of location requests per hour. Please try again later.",
                "current": current_count,
                "limit": max_limit,
                "retry_after_seconds": retry_after
            }, status=429)

        response = view_func(self, request, *args, **kwargs)

        response['X-RateLimit-Limit'] = str(max_limit)
        response['X-RateLimit-Remaining'] = str(max(0, max_limit - current_count))

        return response

    return wrapper


# ============================================================================
# Music-specific rate limiting
# ============================================================================

def get_music_rate_limit_key(user_id: Optional[int], session_key: Optional[str], ip_address: str) -> str:
    """
    Generate Redis key for music rate limiting.
    Uses a separate namespace from photo and location analysis.
    """
    if user_id:
        return f"music:rate_limit:user:{user_id}"
    elif session_key:
        return f"music:rate_limit:session:{session_key}"
    else:
        return f"music:rate_limit:ip:{ip_address}"


def check_music_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> Tuple[bool, int, int]:
    """
    Check if the client has exceeded the music rate limit.

    Returns:
        Tuple of (allowed, current_count, max_limit)
    """
    if user_id:
        max_limit = config.MUSIC_ANALYSIS_USER_LIMIT_PER_HOUR
    else:
        max_limit = config.MUSIC_ANALYSIS_SESSION_LIMIT_PER_HOUR

    cache_key = get_music_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    allowed = current_count < max_limit

    return allowed, current_count, max_limit


def increment_music_rate_limit(
    user_id: Optional[int],
    session_key: Optional[str],
    ip_address: str
) -> int:
    """
    Increment the music rate limit counter for this client.

    Returns:
        New count value after increment
    """
    cache_key = get_music_rate_limit_key(user_id, session_key, ip_address)
    current_count = cache.get(cache_key, 0)
    new_count = current_count + 1

    if current_count == 0:
        cache.set(cache_key, new_count, timeout=3600)
    else:
        cache.set(cache_key, new_count, timeout=cache.ttl(cache_key))

    return new_count


def music_analysis_rate_limit(view_func):
    """
    Decorator to enforce rate limiting on music recognition API endpoints.
    """
    @wraps(view_func)
    def wrapper(self, request: Request, *args, **kwargs):
        user_id, session_key, ip_address = get_client_identifier(request)

        if ip_address in ['127.0.0.1', '::1', 'localhost']:
            return view_func(self, request, *args, **kwargs)

        # Check global limit first (protects API budget)
        global_allowed, global_reason = check_global_rate_limit('music')
        if not global_allowed:
            return JsonResponse({
                "error": "Service limit reached",
                "detail": global_reason,
            }, status=429)

        # Check per-user/session limit
        allowed, current_count, max_limit = check_music_rate_limit(user_id, session_key, ip_address)

        if not allowed:
            cache_key = get_music_rate_limit_key(user_id, session_key, ip_address)
            retry_after = cache.ttl(cache_key) or 3600

            return JsonResponse({
                "error": "Rate limit exceeded",
                "detail": "You have exceeded the maximum number of music recognition requests per hour. Please try again later.",
                "current": current_count,
                "limit": max_limit,
                "retry_after_seconds": retry_after
            }, status=429)

        # Increment both counters
        increment_music_rate_limit(user_id, session_key, ip_address)
        increment_global_rate_limit('music')

        response = view_func(self, request, *args, **kwargs)

        response['X-RateLimit-Limit'] = str(max_limit)
        response['X-RateLimit-Remaining'] = str(max(0, max_limit - current_count - 1))

        return response

    return wrapper


# ============================================================================
# Global (cross-user) rate limiting
# ============================================================================

def get_global_rate_limit_key(service: str, period: str) -> str:
    """Generate Redis key for global rate limiting."""
    now = datetime.utcnow()
    if period == 'hourly':
        time_bucket = now.strftime('%Y-%m-%d-%H')
    else:  # daily
        time_bucket = now.strftime('%Y-%m-%d')
    return f"media_analysis:global:{service}:{period}:{time_bucket}"


def check_global_rate_limit(service: str) -> Tuple[bool, str]:
    """
    Check if global rate limit is exceeded for a service.
    Returns (allowed, reason).
    """
    # Check hourly limit
    hourly_key = get_global_rate_limit_key(service, 'hourly')
    hourly_config_key = f"{service.upper()}_ANALYSIS_GLOBAL_LIMIT_PER_HOUR"
    hourly_limit = getattr(config, hourly_config_key, 500)
    hourly_count = cache.get(hourly_key, 0)
    if hourly_count >= hourly_limit:
        return False, "Service temporarily at capacity. Please try again later."

    # Check daily limit
    daily_key = get_global_rate_limit_key(service, 'daily')
    daily_config_key = f"{service.upper()}_ANALYSIS_GLOBAL_LIMIT_PER_DAY"
    daily_limit = getattr(config, daily_config_key, 5000)
    daily_count = cache.get(daily_key, 0)
    if daily_count >= daily_limit:
        return False, "Daily service limit reached. Please try again tomorrow."

    return True, ""


def increment_global_rate_limit(service: str):
    """Increment global rate limit counters for a service."""
    # Increment hourly counter
    hourly_key = get_global_rate_limit_key(service, 'hourly')
    hourly_count = cache.get(hourly_key, 0)
    if hourly_count == 0:
        cache.set(hourly_key, 1, timeout=3600)
    else:
        cache.set(hourly_key, hourly_count + 1, timeout=cache.ttl(hourly_key))

    # Increment daily counter
    daily_key = get_global_rate_limit_key(service, 'daily')
    daily_count = cache.get(daily_key, 0)
    if daily_count == 0:
        cache.set(daily_key, 1, timeout=86400)
    else:
        cache.set(daily_key, daily_count + 1, timeout=cache.ttl(daily_key))
