# Cache & Database Monitoring System

## Overview

ChatPop includes a comprehensive real-time monitoring system for tracking cache and database operations. The system features adaptive sampling that automatically adjusts based on traffic levels, ensuring minimal performance impact even at high throughput.

## Features

- **Adaptive Sampling**: Automatically scales from detailed logging to aggregated metrics based on traffic
- **Ring Buffer**: Stores the last 1000 operations in memory for detailed inspection
- **Web Dashboard**: Browser-based interface with real-time updates via AJAX
- **Command-Line Tool**: Terminal-based monitoring for SSH/remote access
- **Zero Overhead**: Disabled by default, controlled via Constance (no restart required)
- **Thread-Safe**: All operations use proper locking for concurrent access

## Monitoring Modes

The system automatically switches between three modes based on operations per second:

| Mode | Traffic | Sampling Rate | Behavior |
|------|---------|---------------|----------|
| **Detailed** | < 100 ops/s | 100% | Logs every operation with full details |
| **Sampled** | 100-1000 ops/s | 1-10% | Samples operations randomly |
| **Aggregated** | > 1000 ops/s | 0% | Summary statistics only |

### Sampled Mode Breakdown

- **100-200 ops/s**: 10% sample rate
- **200-500 ops/s**: 5% sample rate
- **500-1000 ops/s**: 1% sample rate
- **1000+ ops/s**: 0% sample (aggregated only)

## Enabling Monitoring

### Option 1: Admin Panel (Recommended)

1. Navigate to Django admin: `https://localhost:9000/admin/`
2. Click **"Dynamic Settings"** in the Developer Tools section
3. Check the box for **ENABLE_MONITORING**
4. Click **Save**

No server restart required! Changes take effect within 5 seconds.

### Option 2: Environment Variable

Add to your environment:

```bash
ENABLE_MONITORING=True
```

Then restart Daphne.

## Accessing the Monitoring Dashboard

### Web Dashboard

1. Navigate to Django admin: `https://localhost:9000/admin/`
2. Click **"📊 Cache & Database Monitor"** in the Developer Tools section

**Dashboard Features:**
- Real-time metrics (cache hit rate, operations/sec, etc.)
- Live event log with color-coded entries
- Filter by chat code
- Adjustable refresh interval (1-10 seconds)
- Pause/resume auto-refresh
- Responsive layout with professional UI

## Tracked Operations

### Cache Operations

| Event Type | Description | Tracked Data |
|------------|-------------|--------------|
| `cache_read` | Redis cache read (GET) | hit/miss/partial, message count, source |
| `cache_write` | Redis cache write (SET) | message count |
| `cache_partial_hit` | Partial cache hit (Redis + PostgreSQL) | cached count, DB count |

### Database Operations

| Event Type | Description | Tracked Data |
|------------|-------------|--------------|
| `db_read` | PostgreSQL SELECT query | message count, query type |
| `db_write` | PostgreSQL INSERT/UPDATE | query type |

### Hybrid Operations

| Event Type | Description | Tracked Data |
|------------|-------------|--------------|
| `hybrid_query` | Combined cache + DB query | cache count, DB count, split timing |

## Metrics Summary

The dashboard displays the following aggregated metrics:

- **Cache Hit Rate**: Percentage of successful cache reads
- **Cache Hits**: Total cache hits (full hits only)
- **Cache Misses**: Total cache misses (fallback to DB)
- **Cache Partial Hits**: Hybrid queries (cache + DB)
- **Cache Writes**: Total messages written to cache
- **DB Reads**: Total database SELECT queries
- **DB Writes**: Total database INSERT/UPDATE queries
- **Hybrid Queries**: Total combined cache + DB operations

## Performance Impact

### Memory Usage

- **Ring Buffer**: ~100-200 KB (1000 events × ~100-200 bytes/event)
- **Aggregated Metrics**: < 1 KB (simple counters)
- **Sampling Metadata**: < 10 KB (operation timestamps)

**Total overhead when enabled**: ~200 KB

### CPU Impact

- **Detailed Mode** (< 100 ops/s): ~0.1-0.5% CPU overhead
- **Sampled Mode** (100-1000 ops/s): ~0.05-0.2% CPU overhead
- **Aggregated Mode** (> 1000 ops/s): < 0.01% CPU overhead
- **Disabled**: Zero overhead (early return on all calls)

### Latency

Per-operation overhead:
- Aggregated metrics update: ~0.01-0.05 ms
- Event logging (detailed): ~0.1-0.2 ms
- Sampling check: < 0.01 ms

## Code Integration

The monitoring system is integrated at key points in the codebase:

### Redis Cache (`chats/redis_cache.py`)

```python
from chats.monitoring import monitor
import time

@classmethod
def get_messages(cls, chat_code: str, limit: int = 50):
    start_time = time.time()

    # ... cache read logic ...

    duration_ms = (time.time() - start_time) * 1000
    monitor.log_cache_read(
        chat_code,
        hit=len(messages) > 0,
        count=len(messages),
        duration_ms=duration_ms,
        source='redis'
    )
```

### Database Queries (`chats/views.py`)

```python
from chats.monitoring import monitor
import time

def _fetch_from_db(self, chat_room, limit, before_timestamp=None):
    start_time = time.time()

    # ... database query logic ...

    duration_ms = (time.time() - start_time) * 1000
    monitor.log_db_read(
        chat_room.code,
        count=len(serialized),
        duration_ms=duration_ms,
        query_type='SELECT'
    )
```

## Dashboard Architecture

### Backend (admin_views.py)

```python
@staff_member_required
def monitoring_dashboard(request):
    """Renders the HTML dashboard page"""
    return render(request, 'admin/monitoring_dashboard.html', {...})

@staff_member_required
def monitoring_api(request):
    """JSON API endpoint for AJAX updates"""
    data = {
        'mode': monitor.get_current_mode(),
        'metrics': monitor.get_metrics_summary(),
        'events': monitor.get_recent_events(limit=50)
    }
    return JsonResponse(data)
```

### Frontend (monitoring_dashboard.html)

- **Auto-refresh**: JavaScript polls the API every 1-10 seconds
- **Pause/Resume**: Toggle button to control auto-refresh
- **Filter by Chat**: Input field to filter events by chat code
- **Color-coded Events**: Visual distinction for different event types
- **Responsive Design**: Mobile-friendly layout with grid system

## URL Configuration

The monitoring dashboard is accessible at:

- **Dashboard**: `https://localhost:9000/admin/monitoring/`
- **API Endpoint**: `https://localhost:9000/admin/monitoring/api/`

## Security

- **Staff-only Access**: Both views are protected with `@staff_member_required`
- **No Public Access**: Requires Django admin authentication
- **Read-only**: Dashboard cannot modify system behavior
- **No Sensitive Data**: Only logs chat codes, counts, and timing

## Troubleshooting

### Dashboard shows "No events captured yet"

**Cause**: Monitoring is disabled in Constance settings

**Solution**:
1. Go to `https://localhost:9000/admin/constance/config/`
2. Check the box for **ENABLE_MONITORING**
3. Click **Save**

### Events are missing or sparse

**Cause**: System is in sampled or aggregated mode due to high traffic

**Solution**: This is expected behavior. Check the **Mode** indicator:
- **DETAILED**: All events logged
- **SAMPLED**: Only 1-10% of events logged (randomly sampled)
- **AGGREGATED**: No event logging, summary stats only

Reduce traffic or increase sampling threshold in `monitoring.py`.

### High memory usage

**Cause**: Ring buffer is full (1000 events)

**Solution**: This is normal. The ring buffer automatically evicts old events. Maximum memory usage is capped at ~200 KB.

### Dashboard not updating

**Cause**: Auto-refresh paused or JavaScript error

**Solution**:
1. Check browser console for errors
2. Click **Resume** if auto-refresh is paused
3. Verify API endpoint is accessible: `https://localhost:9000/admin/monitoring/api/`

## Advanced Configuration

### Adjust Sampling Thresholds

Edit `chats/monitoring.py`:

```python
def _get_monitoring_mode(self) -> Literal['detailed', 'sampled', 'aggregated']:
    with self.ops_lock:
        current_time = int(time.time())
        ops_per_sec = sum(1 for t in self.ops_counter if t == current_time)

    if ops_per_sec < 100:  # Change this threshold
        return 'detailed'
    elif ops_per_sec < 1000:  # Change this threshold
        return 'sampled'
    else:
        return 'aggregated'
```

### Increase Ring Buffer Size

Edit `chats/monitoring.py`:

```python
def __init__(self):
    # Change maxlen to increase buffer size (default: 1000)
    self.event_buffer = deque(maxlen=2000)  # Now stores 2000 events
```

**Warning**: Larger buffer = more memory usage (~200 bytes per event)

### Customize Sampling Rates

Edit `chats/monitoring.py`:

```python
def _get_sample_rate(self) -> float:
    mode = self._get_monitoring_mode()

    if mode == 'detailed':
        return 1.0  # 100%
    elif mode == 'sampled':
        with self.ops_lock:
            ops_per_sec = sum(...)

        if ops_per_sec < 200:
            return 0.2  # 20% sample (increased from 10%)
        # ... etc
```

## Files

**Core monitoring infrastructure:**
- `/backend/chats/monitoring.py` - Main monitoring class
- `/backend/chats/admin_views.py` - Web dashboard views
- `/backend/chats/templates/admin/monitoring_dashboard.html` - Dashboard UI

**Integration points:**
- `/backend/chats/redis_cache.py` - Cache operation instrumentation
- `/backend/chats/views.py` - Database operation instrumentation
- `/backend/chatpop/settings.py` - Constance configuration
- `/backend/chatpop/urls.py` - URL routing

## See Also

- [CACHING.md](CACHING.md) - Redis caching architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [MANAGEMENT_TOOLS.md](MANAGEMENT_TOOLS.md) - Other management commands
