"""
Real-time monitoring system for cache and database operations.

This module provides adaptive monitoring that scales from low to high traffic:
- Low traffic (<100 ops/s): Logs every operation in detail
- Medium traffic (100-1000 ops/s): Samples 1-10% of operations
- High traffic (>1000 ops/s): Aggregated metrics only

Features:
- Ring buffer for recent events (last 1000 operations)
- Aggregated metrics (always tracked, minimal overhead)
- Adaptive sampling based on current traffic
- Zero overhead when monitoring is disabled

Usage:
    from .monitoring import monitor

    # Log a cache operation
    monitor.log_cache_read('ABC123', hit=True, count=50, duration_ms=2.3)

    # Log a database operation
    monitor.log_db_read('ABC123', count=20, duration_ms=15.2)

    # View recent events
    events = monitor.get_recent_events(limit=100)
"""

import time
import threading
import random
from collections import deque, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Literal
from django.conf import settings


class CacheMonitor:
    """
    Monitors cache and database operations with adaptive sampling.

    Thread-safe monitoring system that tracks:
    - Cache reads (hits, misses, partial hits)
    - Cache writes
    - Database reads
    - Database writes
    - Hybrid queries (cache + database)
    """

    def __init__(self):
        # Ring buffer for detailed events (last 1000 operations)
        self.event_buffer = deque(maxlen=1000)
        self.buffer_lock = threading.Lock()

        # Aggregated metrics (reset every second)
        self.metrics = defaultdict(int)
        self.metrics_lock = threading.Lock()

        # Operations counter for adaptive sampling
        self.ops_counter = deque(maxlen=10)  # Last 10 seconds
        self.ops_lock = threading.Lock()

        # Monitoring mode (cached, refreshed on check)
        self._enabled_cache = None
        self._enabled_cache_time = 0

    @property
    def enabled(self):
        """Check if monitoring is enabled (uses Constance with caching)"""
        # Cache the setting for 5 seconds to avoid repeated database hits
        current_time = time.time()
        if self._enabled_cache is None or (current_time - self._enabled_cache_time) > 5:
            try:
                from constance import config
                self._enabled_cache = config.ENABLE_MONITORING
            except:
                # Fallback to settings if Constance not available
                self._enabled_cache = getattr(settings, 'ENABLE_MONITORING', False)
            self._enabled_cache_time = current_time
        return self._enabled_cache

    def _get_monitoring_mode(self) -> Literal['detailed', 'sampled', 'aggregated']:
        """
        Determine monitoring mode based on current traffic.

        Returns:
            'detailed': Log every operation (low traffic)
            'sampled': Sample 1-10% of operations (medium traffic)
            'aggregated': Summary stats only (high traffic)
        """
        with self.ops_lock:
            current_time = int(time.time())
            # Count operations in current second
            ops_per_sec = sum(1 for t in self.ops_counter if t == current_time)

        if ops_per_sec < 100:
            return 'detailed'
        elif ops_per_sec < 1000:
            return 'sampled'
        else:
            return 'aggregated'

    def _get_sample_rate(self) -> float:
        """
        Get sampling rate based on current traffic.

        Returns:
            1.0 (100%) for low traffic
            0.1-0.01 (10%-1%) for medium traffic
            0.0 (0%) for high traffic
        """
        mode = self._get_monitoring_mode()

        if mode == 'detailed':
            return 1.0
        elif mode == 'sampled':
            with self.ops_lock:
                current_time = int(time.time())
                ops_per_sec = sum(1 for t in self.ops_counter if t == current_time)

            if ops_per_sec < 200:
                return 0.1  # 10% sample
            elif ops_per_sec < 500:
                return 0.05  # 5% sample
            else:
                return 0.01  # 1% sample
        else:
            return 0.0  # No sampling

    def _should_log_event(self) -> bool:
        """Decide whether to log this event based on sampling rate."""
        sample_rate = self._get_sample_rate()
        return random.random() < sample_rate

    def _increment_ops_counter(self):
        """Track operation for adaptive sampling."""
        with self.ops_lock:
            self.ops_counter.append(int(time.time()))

    def _log_event(self, event: Dict):
        """Add event to ring buffer (thread-safe)."""
        if not self.enabled:
            return

        with self.buffer_lock:
            self.event_buffer.append(event)

    def _update_metrics(self, metric_type: str, duration_ms: float = 0):
        """Update aggregated metrics (always tracked, minimal overhead)."""
        with self.metrics_lock:
            self.metrics[f'{metric_type}_count'] += 1
            if duration_ms > 0:
                self.metrics[f'{metric_type}_total_ms'] += duration_ms

    # Public API: Cache operations

    def log_cache_read(self, chat_code: str, hit: bool, count: int, duration_ms: float,
                       source: str = 'redis', partial: bool = False):
        """
        Log a cache read operation.

        Args:
            chat_code: Chat room code
            hit: True if cache hit, False if miss
            count: Number of messages returned
            duration_ms: Operation duration in milliseconds
            source: 'redis' or 'hybrid_redis_postgresql'
            partial: True if partial cache hit
        """
        self._increment_ops_counter()

        # Always update aggregated metrics (fast)
        if hit:
            if partial:
                self._update_metrics('cache_partial_hit', duration_ms)
            else:
                self._update_metrics('cache_hit', duration_ms)
        else:
            self._update_metrics('cache_miss', duration_ms)

        # Conditionally log detailed event
        if self._should_log_event():
            event = {
                'timestamp': time.time(),
                'type': 'cache_read',
                'chat_code': chat_code,
                'hit': hit,
                'partial': partial,
                'count': count,
                'duration_ms': round(duration_ms, 2),
                'source': source
            }
            self._log_event(event)

    def log_cache_write(self, chat_code: str, count: int, duration_ms: float):
        """
        Log a cache write operation.

        Args:
            chat_code: Chat room code
            count: Number of messages written
            duration_ms: Operation duration in milliseconds
        """
        self._increment_ops_counter()
        self._update_metrics('cache_write', duration_ms)

        if self._should_log_event():
            event = {
                'timestamp': time.time(),
                'type': 'cache_write',
                'chat_code': chat_code,
                'count': count,
                'duration_ms': round(duration_ms, 2)
            }
            self._log_event(event)

    def log_db_read(self, chat_code: str, count: int, duration_ms: float,
                    query_type: str = 'SELECT'):
        """
        Log a database read operation.

        Args:
            chat_code: Chat room code
            count: Number of messages returned
            duration_ms: Operation duration in milliseconds
            query_type: SQL query type (SELECT, etc.)
        """
        self._increment_ops_counter()
        self._update_metrics('db_read', duration_ms)

        if self._should_log_event():
            event = {
                'timestamp': time.time(),
                'type': 'db_read',
                'chat_code': chat_code,
                'count': count,
                'duration_ms': round(duration_ms, 2),
                'query_type': query_type
            }
            self._log_event(event)

    def log_db_write(self, chat_code: str, duration_ms: float, query_type: str = 'INSERT'):
        """
        Log a database write operation.

        Args:
            chat_code: Chat room code
            duration_ms: Operation duration in milliseconds
            query_type: SQL query type (INSERT, UPDATE, etc.)
        """
        self._increment_ops_counter()
        self._update_metrics('db_write', duration_ms)

        if self._should_log_event():
            event = {
                'timestamp': time.time(),
                'type': 'db_write',
                'chat_code': chat_code,
                'duration_ms': round(duration_ms, 2),
                'query_type': query_type
            }
            self._log_event(event)

    def log_hybrid_query(self, chat_code: str, cache_count: int, db_count: int,
                        total_duration_ms: float, cache_ms: float, db_ms: float):
        """
        Log a hybrid query (cache + database).

        Args:
            chat_code: Chat room code
            cache_count: Messages from cache
            db_count: Messages from database
            total_duration_ms: Total query duration
            cache_ms: Cache portion duration
            db_ms: Database portion duration
        """
        self._increment_ops_counter()
        self._update_metrics('hybrid_query', total_duration_ms)

        if self._should_log_event():
            event = {
                'timestamp': time.time(),
                'type': 'hybrid_query',
                'chat_code': chat_code,
                'cache_count': cache_count,
                'db_count': db_count,
                'total_count': cache_count + db_count,
                'duration_ms': round(total_duration_ms, 2),
                'cache_ms': round(cache_ms, 2),
                'db_ms': round(db_ms, 2)
            }
            self._log_event(event)

    # Public API: Query methods

    def get_recent_events(self, limit: int = 100, chat_code: Optional[str] = None) -> List[Dict]:
        """
        Get recent events from ring buffer.

        Args:
            limit: Maximum number of events to return
            chat_code: Optional filter by chat code

        Returns:
            List of event dicts (newest first)
        """
        with self.buffer_lock:
            events = list(self.event_buffer)

        # Filter by chat code if specified
        if chat_code:
            events = [e for e in events if e.get('chat_code') == chat_code]

        # Return newest first, limited
        return list(reversed(events))[:limit]

    def get_metrics_summary(self) -> Dict:
        """
        Get aggregated metrics summary.

        Returns:
            Dict with metrics like:
            {
                'cache_hit_count': 42,
                'cache_hit_total_ms': 105.6,
                'db_read_count': 5,
                ...
            }
        """
        with self.metrics_lock:
            return dict(self.metrics)

    def reset_metrics(self):
        """Reset aggregated metrics (called by background thread every second)."""
        with self.metrics_lock:
            self.metrics.clear()

    def get_current_mode(self) -> Dict:
        """
        Get current monitoring mode and stats.

        Returns:
            {
                'mode': 'detailed' | 'sampled' | 'aggregated',
                'sample_rate': 1.0 | 0.1 | 0.01 | 0.0,
                'ops_per_sec': 123,
                'enabled': True | False
            }
        """
        with self.ops_lock:
            current_time = int(time.time())
            ops_per_sec = sum(1 for t in self.ops_counter if t == current_time)

        mode = self._get_monitoring_mode()
        sample_rate = self._get_sample_rate()

        return {
            'mode': mode,
            'sample_rate': sample_rate,
            'ops_per_sec': ops_per_sec,
            'enabled': self.enabled
        }


# Global singleton instance
monitor = CacheMonitor()
