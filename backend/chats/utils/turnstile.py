"""
Cloudflare Turnstile bot detection verification.
Used as a decorator on views that need bot protection.
"""
import requests
from functools import wraps
from django.conf import settings
from django.http import JsonResponse
from rest_framework.request import Request


def get_client_ip(request):
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def verify_turnstile_token(token: str, ip_address: str) -> bool:
    """
    Verify a Turnstile token with Cloudflare's siteverify API.

    Args:
        token: The turnstile response token from the frontend
        ip_address: Client IP address for additional validation

    Returns:
        True if verification passed, False otherwise
    """
    secret_key = settings.CLOUDFLARE_TURNSTILE_SECRET_KEY
    if not secret_key:
        return True  # No-op in development

    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret_key,
                'response': token,
                'remoteip': ip_address,
            },
            timeout=5
        )
        result = response.json()
        return result.get('success', False)
    except Exception:
        # If Cloudflare is down, fail open (don't block legitimate users)
        return True


def require_turnstile(view_func):
    """
    Decorator to require Cloudflare Turnstile session verification.

    Checks that the session has been verified via /api/auth/verify-human/.
    No-op when CLOUDFLARE_TURNSTILE_SECRET_KEY is empty (development).
    """
    @wraps(view_func)
    def wrapper(self, request: Request, *args, **kwargs):
        # Skip if Turnstile is not configured (development mode)
        if not settings.CLOUDFLARE_TURNSTILE_SECRET_KEY:
            return view_func(self, request, *args, **kwargs)

        # Check session flag
        if request.session.get('turnstile_verified'):
            return view_func(self, request, *args, **kwargs)

        return JsonResponse(
            {"error": "Human verification required", "detail": "Please complete the verification check."},
            status=403
        )

    return wrapper
