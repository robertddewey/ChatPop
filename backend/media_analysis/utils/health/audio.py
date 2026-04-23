"""ACRCloud audio-recognition health probe.

Sends a ~3s sine-wave WAV clip. ACRCloud can fingerprint a pure tone and
will return "no match" (code 1001) — that proves both the HMAC signature
and the API key work, without ever matching a real song.
"""

import base64
import hashlib
import hmac
import io
import math
import struct
import time
import wave

import requests
from django.conf import settings

from .base import ProbeResult


TIMEOUT_SECONDS = 10


def _build_tone_wav(duration_seconds: float = 3.0, frequency: float = 440.0,
                     sample_rate: int = 8000) -> bytes:
    """Build a mono 16-bit sine-wave WAV in memory (~48 KB at defaults)."""
    amplitude = 16000
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        total_frames = int(sample_rate * duration_seconds)
        frames = bytearray()
        for i in range(total_frames):
            value = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            frames.extend(struct.pack('<h', value))
        w.writeframes(bytes(frames))
    return buf.getvalue()


def _build_signature(access_key: str, secret_key: str, timestamp: str) -> str:
    method = 'POST'
    uri = '/v1/identify'
    data_type = 'audio'
    signature_version = '1'
    string_to_sign = f'{method}\n{uri}\n{access_key}\n{data_type}\n{signature_version}\n{timestamp}'
    digest = hmac.new(
        secret_key.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode('utf-8')


def probe_acrcloud() -> ProbeResult:
    access_key = getattr(settings, 'ACRCLOUD_ACCESS_KEY', None)
    secret_key = getattr(settings, 'ACRCLOUD_SECRET_KEY', None)
    host = getattr(settings, 'ACRCLOUD_HOST', None)

    if not access_key or not secret_key or not host:
        missing = [k for k, v in (
            ('ACRCLOUD_ACCESS_KEY', access_key),
            ('ACRCLOUD_SECRET_KEY', secret_key),
            ('ACRCLOUD_HOST', host),
        ) if not v]
        return ProbeResult(
            service='audio', provider='acrcloud', status='not_configured',
            message=f'Missing settings: {", ".join(missing)}',
            configured=False,
        )

    sample = _build_tone_wav()
    timestamp = str(int(time.time()))
    signature = _build_signature(access_key, secret_key, timestamp)

    endpoint = f'https://{host}/v1/identify'
    files = {'sample': ('silence.wav', sample, 'audio/wav')}
    data = {
        'access_key': access_key,
        'data_type': 'audio',
        'signature_version': '1',
        'signature': signature,
        'sample_bytes': str(len(sample)),
        'timestamp': timestamp,
    }

    started = time.monotonic()
    try:
        resp = requests.post(endpoint, files=files, data=data, timeout=TIMEOUT_SECONDS)
    except requests.Timeout:
        return ProbeResult(
            service='audio', provider='acrcloud', status='down',
            message=f'Request timed out after {TIMEOUT_SECONDS}s.',
        )
    except requests.RequestException as e:
        return ProbeResult(
            service='audio', provider='acrcloud', status='down',
            message=f'Network error: {e}',
        )

    latency_ms = int((time.monotonic() - started) * 1000)

    if not resp.ok:
        return ProbeResult(
            service='audio', provider='acrcloud', status='down',
            message=f'HTTP {resp.status_code}.',
            latency_ms=latency_ms,
            detail={'body': resp.text[:500]},
        )

    try:
        payload = resp.json()
    except ValueError:
        return ProbeResult(
            service='audio', provider='acrcloud', status='degraded',
            message='Response was not valid JSON.',
            latency_ms=latency_ms,
        )

    status = payload.get('status') or {}
    code = status.get('code')
    msg = status.get('msg') or '(no msg)'

    # ACRCloud status codes:
    #   0     = match found
    #   1001  = no result (EXPECTED for silence — auth succeeded)
    #   2000+ = errors (invalid key, signature mismatch, etc.)
    if code in (0, 1001):
        return ProbeResult(
            service='audio', provider='acrcloud', status='ok',
            message=f'ACRCloud auth OK ({msg}).',
            latency_ms=latency_ms,
            detail={'status_code': code},
        )

    return ProbeResult(
        service='audio', provider='acrcloud', status='down',
        message=f'ACRCloud rejected request (code={code}): {msg}',
        latency_ms=latency_ms,
        detail={'status_code': code, 'status_msg': msg},
    )
