"""Shared types and dispatch for external-API health probes."""

from dataclasses import dataclass, asdict, field
from typing import Any, Callable, Optional


Status = str  # 'ok' | 'degraded' | 'down' | 'not_configured' | 'error'


@dataclass
class ProbeResult:
    service: str                        # 'location' | 'audio' | 'image'
    provider: str                       # 'tomtom' | 'google_places' | 'acrcloud' | 'openai'
    status: Status
    message: str                        # human-readable one-liner
    configured: bool = True
    latency_ms: Optional[int] = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# Registry populated lazily to avoid import-time side effects.
def _get_registry() -> dict[str, Callable[[], ProbeResult]]:
    from . import location, audio, vision
    return {
        'tomtom': location.probe_tomtom,
        'google_places': location.probe_google_places,
        'acrcloud': audio.probe_acrcloud,
        'openai': vision.probe_openai,
    }


# Public catalogue: providers and category→providers mapping.
PROVIDERS = ('tomtom', 'google_places', 'acrcloud', 'openai')
CATEGORIES = {
    'location': ('tomtom', 'google_places'),
    'audio': ('acrcloud',),
    'image': ('openai',),
}


def resolve_providers(selector: str = 'all') -> tuple[str, ...]:
    """Resolve a user-facing selector into the list of providers to probe.

    Valid selectors: 'all', a category name ('location'/'audio'/'image'),
    or a specific provider name.
    """
    if selector == 'all':
        return PROVIDERS
    if selector in CATEGORIES:
        return CATEGORIES[selector]
    if selector in PROVIDERS:
        return (selector,)
    raise ValueError(
        f"Unknown selector '{selector}'. Use 'all', one of "
        f"{list(CATEGORIES)}, or one of {list(PROVIDERS)}."
    )


def run_probes(selector: str = 'all') -> list[ProbeResult]:
    """Run the selected probes and return results in provider order."""
    registry = _get_registry()
    providers = resolve_providers(selector)
    return [registry[p]() for p in providers]
