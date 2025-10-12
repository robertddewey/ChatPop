"""
Custom admin views for ChatPop monitoring dashboard.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from chats.monitoring import monitor
from datetime import datetime
import time


@staff_member_required
def monitoring_dashboard(request):
    """
    Web-based monitoring dashboard for cache and database operations.
    Displays real-time metrics and recent events.
    """
    context = {
        'title': 'Cache & Database Monitor',
    }
    return render(request, 'admin/monitoring_dashboard.html', context)


@staff_member_required
def monitoring_api(request):
    """
    JSON API endpoint for monitoring data.
    Used by the dashboard for real-time updates via AJAX.
    """
    chat_code = request.GET.get('chat_code')
    limit = int(request.GET.get('limit', 50))

    # Get current monitoring mode
    mode_info = monitor.get_current_mode()

    # Get aggregated metrics
    metrics = monitor.get_metrics_summary()

    # Calculate cache hit rate
    cache_hits = metrics.get('cache_hit_count', 0)
    cache_misses = metrics.get('cache_miss_count', 0)
    cache_partial = metrics.get('cache_partial_hit_count', 0)
    total_cache_reads = cache_hits + cache_misses + cache_partial
    hit_rate = (cache_hits / total_cache_reads * 100) if total_cache_reads > 0 else 0

    # Get recent events
    events = monitor.get_recent_events(limit=limit, chat_code=chat_code)

    # Format events for display
    formatted_events = []
    for event in events:
        formatted_event = {
            'timestamp': datetime.fromtimestamp(event['timestamp']).strftime('%H:%M:%S.%f')[:-3],
            'type': event['type'],
            'chat_code': event.get('chat_code', 'N/A'),
            'duration_ms': event.get('duration_ms', 0),
        }

        # Add type-specific data
        if event['type'] == 'cache_read':
            formatted_event['hit'] = event.get('hit', False)
            formatted_event['partial'] = event.get('partial', False)
            formatted_event['count'] = event.get('count', 0)
            formatted_event['source'] = event.get('source', 'redis')
        elif event['type'] == 'cache_write':
            formatted_event['count'] = event.get('count', 0)
        elif event['type'] == 'db_read':
            formatted_event['count'] = event.get('count', 0)
            formatted_event['query_type'] = event.get('query_type', 'SELECT')
        elif event['type'] == 'db_write':
            formatted_event['query_type'] = event.get('query_type', 'INSERT')
        elif event['type'] == 'hybrid_query':
            formatted_event['cache_count'] = event.get('cache_count', 0)
            formatted_event['db_count'] = event.get('db_count', 0)
            formatted_event['total_count'] = event.get('total_count', 0)
            formatted_event['cache_ms'] = event.get('cache_ms', 0)
            formatted_event['db_ms'] = event.get('db_ms', 0)

        formatted_events.append(formatted_event)

    return JsonResponse({
        'mode': mode_info['mode'],
        'sample_rate': mode_info['sample_rate'],
        'ops_per_sec': mode_info['ops_per_sec'],
        'enabled': mode_info['enabled'],
        'metrics': {
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_partial_hits': cache_partial,
            'cache_writes': metrics.get('cache_write_count', 0),
            'db_reads': metrics.get('db_read_count', 0),
            'db_writes': metrics.get('db_write_count', 0),
            'hybrid_queries': metrics.get('hybrid_query_count', 0),
            'hit_rate': round(hit_rate, 1),
        },
        'events': formatted_events,
        'timestamp': time.time(),
    })
