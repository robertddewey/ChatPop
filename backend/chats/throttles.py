"""
Custom DRF throttle classes for chat views.
"""
from rest_framework.throttling import SimpleRateThrottle


class MyParticipationRateThrottle(SimpleRateThrottle):
    """
    Throttle the MyParticipationView endpoint.

    Identification priority:
      1. Authenticated user (request.user.id)
      2. Django session_key (anonymous users with a session)
      3. Client IP (last-resort fallback)

    Rate is read at request time from Constance
    (MY_PARTICIPATION_RATE_LIMIT_PER_MINUTE) so it can be tuned without
    a deploy. Falls back to 60/min if Constance is unavailable.
    """
    scope = 'my_participation'

    def get_rate(self):
        try:
            from constance import config
            limit = int(getattr(config, 'MY_PARTICIPATION_RATE_LIMIT_PER_MINUTE', 60) or 60)
        except Exception:
            limit = 60
        return f"{limit}/min"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"user:{request.user.id}"
        else:
            session_key = getattr(getattr(request, 'session', None), 'session_key', None)
            if session_key:
                ident = f"sess:{session_key}"
            else:
                ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}
