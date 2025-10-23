"""
Rate limiting utilities for photo analysis API.
Uses Redis to track upload attempts per hour.
"""
from functools import wraps
from typing import Optional, Tuple
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework.request import Request
from constance import config


def get_rate_limit_key(user_id: Optional[int], fingerprint: Optional[str], ip_address: str) -> str:
    """
    Generate Redis key for rate limiting.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        fingerprint: Browser fingerprint (None if not provided)
        ip_address: IP address of the request

    Returns:
        Redis key string for tracking this client

    Example:
        >>> get_rate_limit_key(123, "abc123", "192.168.1.1")
        "photo_analysis:rate_limit:user:123"
        >>> get_rate_limit_key(None, "abc123", "192.168.1.1")
        "photo_analysis:rate_limit:fp:abc123"
        >>> get_rate_limit_key(None, None, "192.168.1.1")
        "photo_analysis:rate_limit:ip:192.168.1.1"
    """
    # Priority: user_id > fingerprint > ip_address
    if user_id:
        return f"photo_analysis:rate_limit:user:{user_id}"
    elif fingerprint:
        return f"photo_analysis:rate_limit:fp:{fingerprint}"
    else:
        return f"photo_analysis:rate_limit:ip:{ip_address}"


def check_rate_limit(
    user_id: Optional[int],
    fingerprint: Optional[str],
    ip_address: str
) -> Tuple[bool, int, int]:
    """
    Check if the client has exceeded the rate limit.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        fingerprint: Browser fingerprint (None if not provided)
        ip_address: IP address of the request

    Returns:
        Tuple of (allowed, current_count, max_limit)
        - allowed: True if request should be allowed, False if rate limited
        - current_count: Number of uploads in current hour
        - max_limit: Maximum allowed uploads per hour

    Example:
        >>> allowed, count, limit = check_rate_limit(123, "abc", "192.168.1.1")
        >>> if not allowed:
        >>>     print(f"Rate limited: {count}/{limit}")
    """
    # Determine rate limit based on authentication
    if user_id:
        max_limit = config.PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED
    else:
        max_limit = config.PHOTO_ANALYSIS_RATE_LIMIT_ANONYMOUS

    # Generate cache key
    cache_key = get_rate_limit_key(user_id, fingerprint, ip_address)

    # Get current count from Redis
    current_count = cache.get(cache_key, 0)

    # Check if limit exceeded
    allowed = current_count < max_limit

    return allowed, current_count, max_limit


def increment_rate_limit(
    user_id: Optional[int],
    fingerprint: Optional[str],
    ip_address: str
) -> int:
    """
    Increment the rate limit counter for this client.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        fingerprint: Browser fingerprint (None if not provided)
        ip_address: IP address of the request

    Returns:
        New count value after increment

    Note:
        Sets 1-hour expiration if this is the first increment.

    Example:
        >>> new_count = increment_rate_limit(123, "abc", "192.168.1.1")
        >>> print(f"Uploads this hour: {new_count}")
    """
    cache_key = get_rate_limit_key(user_id, fingerprint, ip_address)

    # Get current count
    current_count = cache.get(cache_key, 0)

    # Increment
    new_count = current_count + 1

    # Set with 1-hour expiration (3600 seconds)
    # If key already exists with TTL, this preserves the original TTL
    if current_count == 0:
        # First increment - set with expiration
        cache.set(cache_key, new_count, timeout=3600)
    else:
        # Subsequent increment - update value only
        cache.set(cache_key, new_count, timeout=cache.ttl(cache_key))

    return new_count


def get_client_identifier(request: Request) -> Tuple[Optional[int], Optional[str], str]:
    """
    Extract client identifiers from request.

    Args:
        request: DRF Request object

    Returns:
        Tuple of (user_id, fingerprint, ip_address)

    Example:
        >>> user_id, fingerprint, ip = get_client_identifier(request)
    """
    # Get user ID if authenticated
    user_id = request.user.id if request.user.is_authenticated else None

    # Get fingerprint from request data or headers
    fingerprint = None
    try:
        if hasattr(request, 'data') and isinstance(request.data, dict):
            fingerprint = request.data.get('fingerprint')
    except Exception:
        # If data parsing fails (e.g., in tests or unsupported media type),
        # try to get from POST dict or fall back to headers
        pass

    # Try Django request POST dict if not found
    if not fingerprint:
        # DRF Request wraps Django request in _request attribute
        django_request = getattr(request, '_request', request)
        if hasattr(django_request, 'POST'):
            fingerprint = django_request.POST.get('fingerprint')

    if not fingerprint:
        fingerprint = request.META.get('HTTP_X_FINGERPRINT')

    # Get IP address
    # Check for X-Forwarded-For header (proxy/load balancer)
    ip_address = request.META.get('HTTP_X_FORWARDED_FOR')
    if ip_address:
        # X-Forwarded-For can contain multiple IPs, take the first one
        ip_address = ip_address.split(',')[0].strip()
    else:
        # Fall back to REMOTE_ADDR
        ip_address = request.META.get('REMOTE_ADDR', '0.0.0.0')

    return user_id, fingerprint, ip_address


def photo_analysis_rate_limit(view_func):
    """
    Decorator to enforce rate limiting on photo analysis API endpoints.

    Usage:
        @photo_analysis_rate_limit
        def post(self, request, *args, **kwargs):
            # Your view logic here
            pass

    Returns:
        - 429 Too Many Requests if rate limit exceeded
        - Original view response if allowed

    Response Format (rate limited):
        {
            "error": "Rate limit exceeded",
            "detail": "You have exceeded the maximum number of uploads per hour.",
            "current": 10,
            "limit": 10,
            "retry_after_seconds": 1234
        }
    """
    @wraps(view_func)
    def wrapper(self, request: Request, *args, **kwargs):
        # Skip rate limiting if disabled in settings
        if not config.PHOTO_ANALYSIS_ENABLE_RATE_LIMITING:
            return view_func(self, request, *args, **kwargs)

        # Get client identifiers
        user_id, fingerprint, ip_address = get_client_identifier(request)

        # Check rate limit
        allowed, current_count, max_limit = check_rate_limit(
            user_id, fingerprint, ip_address
        )

        if not allowed:
            # Get cache key to check TTL
            cache_key = get_rate_limit_key(user_id, fingerprint, ip_address)
            retry_after = cache.ttl(cache_key) or 3600  # Default 1 hour

            return JsonResponse({
                "error": "Rate limit exceeded",
                "detail": "You have exceeded the maximum number of uploads per hour. Please try again later.",
                "current": current_count,
                "limit": max_limit,
                "retry_after_seconds": retry_after
            }, status=429)

        # Increment counter before processing request
        increment_rate_limit(user_id, fingerprint, ip_address)

        # Call the original view
        response = view_func(self, request, *args, **kwargs)

        # Add rate limit headers to response
        response['X-RateLimit-Limit'] = str(max_limit)
        response['X-RateLimit-Remaining'] = str(max(0, max_limit - current_count - 1))

        return response

    return wrapper


def get_remaining_uploads(
    user_id: Optional[int],
    fingerprint: Optional[str],
    ip_address: str
) -> Tuple[int, int, int]:
    """
    Get the number of remaining uploads for this client.

    Args:
        user_id: Authenticated user ID (None for anonymous)
        fingerprint: Browser fingerprint (None if not provided)
        ip_address: IP address of the request

    Returns:
        Tuple of (remaining, used, limit)

    Example:
        >>> remaining, used, limit = get_remaining_uploads(123, "abc", "192.168.1.1")
        >>> print(f"You have {remaining} uploads remaining out of {limit}")
    """
    allowed, current_count, max_limit = check_rate_limit(
        user_id, fingerprint, ip_address
    )

    remaining = max(0, max_limit - current_count)

    return remaining, current_count, max_limit
