"""Location provider health probes (TomTom, Google Places).

Both are functional checks: reverse-geocode a fixed coordinate (Times Square)
and verify the response contains the expected fields. This validates the API
key, network, and response shape in one call.
"""

import time
import requests
from django.conf import settings

from .base import ProbeResult


# Fixed reference coordinate (Times Square, NYC) — densely geocoded, stable.
TEST_LAT = 40.7580
TEST_LON = -73.9855
TIMEOUT_SECONDS = 10


def probe_tomtom() -> ProbeResult:
    api_key = getattr(settings, 'TOMTOM_API_KEY', None)
    if not api_key:
        return ProbeResult(
            service='location',
            provider='tomtom',
            status='not_configured',
            message='TOMTOM_API_KEY is not set.',
            configured=False,
        )

    url = f'https://api.tomtom.com/search/2/reverseGeocode/{TEST_LAT},{TEST_LON}.json'
    started = time.monotonic()
    try:
        resp = requests.get(url, params={'key': api_key}, timeout=TIMEOUT_SECONDS)
    except requests.Timeout:
        return ProbeResult(
            service='location', provider='tomtom', status='down',
            message=f'Request timed out after {TIMEOUT_SECONDS}s.',
        )
    except requests.RequestException as e:
        return ProbeResult(
            service='location', provider='tomtom', status='down',
            message=f'Network error: {e}',
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    if resp.status_code == 401 or resp.status_code == 403:
        return ProbeResult(
            service='location', provider='tomtom', status='down',
            message=f'Authentication failed (HTTP {resp.status_code}). Check TOMTOM_API_KEY.',
            latency_ms=latency_ms,
            detail={'http_status': resp.status_code, 'body': resp.text[:500]},
        )
    if not resp.ok:
        return ProbeResult(
            service='location', provider='tomtom', status='down',
            message=f'HTTP {resp.status_code}.',
            latency_ms=latency_ms,
            detail={'body': resp.text[:500]},
        )

    try:
        data = resp.json()
    except ValueError:
        return ProbeResult(
            service='location', provider='tomtom', status='degraded',
            message='Response was not valid JSON.',
            latency_ms=latency_ms,
        )

    addresses = data.get('addresses') or []
    if not addresses:
        return ProbeResult(
            service='location', provider='tomtom', status='degraded',
            message='Response had no addresses — unexpected for a valid coordinate.',
            latency_ms=latency_ms,
        )

    freeform = (addresses[0].get('address') or {}).get('freeformAddress') or '(no freeformAddress)'
    return ProbeResult(
        service='location', provider='tomtom', status='ok',
        message=f'Reverse-geocoded Times Square: {freeform}',
        latency_ms=latency_ms,
    )


def probe_google_places() -> ProbeResult:
    api_key = getattr(settings, 'GOOGLE_PLACES_API_KEY', None)
    if not api_key:
        return ProbeResult(
            service='location',
            provider='google_places',
            status='not_configured',
            message='GOOGLE_PLACES_API_KEY is not set.',
            configured=False,
        )

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {'latlng': f'{TEST_LAT},{TEST_LON}', 'key': api_key}
    started = time.monotonic()
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.Timeout:
        return ProbeResult(
            service='location', provider='google_places', status='down',
            message=f'Request timed out after {TIMEOUT_SECONDS}s.',
        )
    except requests.RequestException as e:
        return ProbeResult(
            service='location', provider='google_places', status='down',
            message=f'Network error: {e}',
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    if not resp.ok:
        return ProbeResult(
            service='location', provider='google_places', status='down',
            message=f'HTTP {resp.status_code}.',
            latency_ms=latency_ms,
            detail={'body': resp.text[:500]},
        )

    try:
        data = resp.json()
    except ValueError:
        return ProbeResult(
            service='location', provider='google_places', status='degraded',
            message='Response was not valid JSON.',
            latency_ms=latency_ms,
        )

    # Google returns structured status. REQUEST_DENIED / INVALID_REQUEST indicate auth/config issues.
    api_status = data.get('status')
    if api_status in ('REQUEST_DENIED', 'INVALID_REQUEST'):
        err = data.get('error_message') or 'no error_message returned'
        return ProbeResult(
            service='location', provider='google_places', status='down',
            message=f'API rejected request (status={api_status}): {err}',
            latency_ms=latency_ms,
            detail={'api_status': api_status, 'error_message': err},
        )
    if api_status != 'OK' or not data.get('results'):
        return ProbeResult(
            service='location', provider='google_places', status='degraded',
            message=f'Unexpected response (status={api_status}).',
            latency_ms=latency_ms,
            detail={'api_status': api_status},
        )

    formatted = data['results'][0].get('formatted_address') or '(no formatted_address)'
    return ProbeResult(
        service='location', provider='google_places', status='ok',
        message=f'Reverse-geocoded Times Square: {formatted}',
        latency_ms=latency_ms,
    )
