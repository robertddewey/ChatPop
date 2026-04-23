"""
External API health probes.

Each probe returns a ProbeResult with status = ok | degraded | down | not_configured.
"""

from .base import ProbeResult, run_probes, PROVIDERS, CATEGORIES

__all__ = ['ProbeResult', 'run_probes', 'PROVIDERS', 'CATEGORIES']
