"""OpenAI Vision health probe.

Two-stage check:
  1. List models (free, validates API key).
  2. Send a 1x1 PNG through the configured vision model (validates that the
     configured model is accessible and can process images with this key).
"""

import base64
import io
import time

from django.conf import settings

from .base import ProbeResult


MODELS_URL = 'https://api.openai.com/v1/models'
TIMEOUT_SECONDS = 30  # vision call can be slower than a raw list


def _build_1px_png_b64() -> str:
    from PIL import Image
    img = Image.new('RGB', (1, 1), color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


def probe_openai() -> ProbeResult:
    api_key = getattr(settings, 'OPENAI_API_KEY', None)
    if not api_key:
        return ProbeResult(
            service='image', provider='openai', status='not_configured',
            message='OPENAI_API_KEY is not set.',
            configured=False,
        )

    from constance import config
    model = getattr(config, 'PHOTO_ANALYSIS_OPENAI_MODEL', None) or 'gpt-4o-mini'

    # Stage 1: list models — validates the key at zero token cost.
    import requests
    started = time.monotonic()
    try:
        resp = requests.get(
            MODELS_URL,
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        return ProbeResult(
            service='image', provider='openai', status='down',
            message=f'Models list timed out after {TIMEOUT_SECONDS}s.',
        )
    except requests.RequestException as e:
        return ProbeResult(
            service='image', provider='openai', status='down',
            message=f'Network error: {e}',
        )

    models_latency_ms = int((time.monotonic() - started) * 1000)

    if resp.status_code in (401, 403):
        return ProbeResult(
            service='image', provider='openai', status='down',
            message=f'Authentication failed (HTTP {resp.status_code}). Check OPENAI_API_KEY.',
            latency_ms=models_latency_ms,
            detail={'stage': 'models_list'},
        )
    if not resp.ok:
        return ProbeResult(
            service='image', provider='openai', status='down',
            message=f'Models list returned HTTP {resp.status_code}.',
            latency_ms=models_latency_ms,
            detail={'stage': 'models_list', 'body': resp.text[:500]},
        )

    # Stage 2: real vision call on a 1x1 image (proves the configured model works).
    try:
        from openai import OpenAI
    except ImportError:
        return ProbeResult(
            service='image', provider='openai', status='degraded',
            message='Models list OK but openai SDK not installed for vision check.',
            latency_ms=models_latency_ms,
            detail={'stage': 'models_list_only'},
        )

    client = OpenAI(api_key=api_key)
    b64 = _build_1px_png_b64()
    vision_start = time.monotonic()
    try:
        chat = client.chat.completions.create(
            model=model,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'Respond with the single word: OK.'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{b64}'}},
                ],
            }],
            max_tokens=5,
        )
    except Exception as e:  # openai raises varied exception types
        vision_latency_ms = int((time.monotonic() - vision_start) * 1000)
        return ProbeResult(
            service='image', provider='openai', status='down',
            message=f'Vision call failed: {e}',
            latency_ms=models_latency_ms + vision_latency_ms,
            detail={'stage': 'vision_call', 'model': model},
        )

    vision_latency_ms = int((time.monotonic() - vision_start) * 1000)
    try:
        content = chat.choices[0].message.content or ''
    except (AttributeError, IndexError):
        content = ''

    return ProbeResult(
        service='image', provider='openai', status='ok',
        message=f'Vision call succeeded (model={model}). Reply: {content.strip()[:80] or "(empty)"}',
        latency_ms=models_latency_ms + vision_latency_ms,
        detail={
            'model': model,
            'models_list_latency_ms': models_latency_ms,
            'vision_latency_ms': vision_latency_ms,
        },
    )
