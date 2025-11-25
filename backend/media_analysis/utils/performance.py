"""
Performance tracking utility for photo analysis pipeline.

Provides context managers for timing operations when MEDIA_ANALYSIS_PERFORMANCE_TRACKING
is enabled in Django settings. Designed to identify bottlenecks in API calls and
database operations.

Usage:
    from media_analysis.utils.performance import perf_track, perf_summary

    # Track individual operations
    with perf_track("Caption generation (GPT-4 Vision)"):
        result = call_openai_vision_api()

    # Track and collect metrics for summary
    tracker = PerformanceTracker()
    with tracker.track("Caption generation"):
        # ... operation

    # Log summary with percentages
    tracker.log_summary("photo analysis")
"""

import logging
import time
from contextlib import contextmanager
from typing import Dict, Optional

from django.conf import settings

logger = logging.getLogger(__name__)


def is_performance_tracking_enabled() -> bool:
    """Check if performance tracking is enabled in Django settings."""
    return getattr(settings, 'MEDIA_ANALYSIS_PERFORMANCE_TRACKING', False)


@contextmanager
def perf_track(operation_name: str, metadata: Optional[str] = None):
    """
    Context manager for tracking operation duration.

    Logs performance metrics when MEDIA_ANALYSIS_PERFORMANCE_TRACKING is True.
    Has zero overhead when tracking is disabled.

    Args:
        operation_name: Description of the operation being timed
        metadata: Optional metadata to include (e.g., "10 results", "6 output")

    Example:
        with perf_track("Caption generation (GPT-4 Vision)"):
            result = generate_caption(image)

        with perf_track("K-NN search", metadata=f"{len(results)} results"):
            results = PhotoAnalysis.objects.filter(...)
    """
    if not is_performance_tracking_enabled():
        yield
        return

    start_time = time.time()
    try:
        yield
    finally:
        elapsed = time.time() - start_time

        # Format log message
        log_msg = f"[PERF] {operation_name}: {elapsed:.2f}s"
        if metadata:
            log_msg += f" ({metadata})"

        logger.info(log_msg)


class PerformanceTracker:
    """
    Tracks multiple operations and generates summary with percentages.

    Use this when you want to see relative time spent on different operations.

    Example:
        tracker = PerformanceTracker()

        with tracker.track("Caption generation"):
            # ... operation

        with tracker.track("Refinement LLM", metadata="10 input → 6 output"):
            # ... operation

        tracker.log_summary("photo analysis")  # Logs total time + percentages
    """

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.metadata: Dict[str, str] = {}
        self.enabled = is_performance_tracking_enabled()

    @contextmanager
    def track(self, operation_name: str, metadata: Optional[str] = None):
        """
        Track an operation and store its duration.

        Args:
            operation_name: Description of the operation
            metadata: Optional metadata to include in summary
        """
        if not self.enabled:
            yield
            return

        start_time = time.time()
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            self.timings[operation_name] = elapsed
            if metadata:
                self.metadata[operation_name] = metadata

            # Log individual operation
            log_msg = f"[PERF] {operation_name}: {elapsed:.2f}s"
            if metadata:
                log_msg += f" ({metadata})"
            logger.info(log_msg)

    def log_summary(self, operation_label: str = "operation"):
        """
        Log summary with total time and percentage breakdown.

        Args:
            operation_label: Label for the overall operation (e.g., "photo analysis")
        """
        if not self.enabled or not self.timings:
            return

        total_time = sum(self.timings.values())

        # Log separator
        logger.info("[PERF] " + "─" * 45)
        logger.info(f"[PERF] TOTAL {operation_label}: {total_time:.2f}s")

        # Sort by time (longest first)
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)

        # Log each operation with percentage
        for op_name, elapsed in sorted_timings:
            percentage = (elapsed / total_time) * 100
            logger.info(f"[PERF]   └─ {op_name}: {percentage:.1f}%")
