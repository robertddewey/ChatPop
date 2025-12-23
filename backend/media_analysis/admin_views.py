"""
Custom admin views for location cache monitoring dashboard.
"""

import json
import logging
from datetime import timedelta
from collections import defaultdict
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from media_analysis.models import LocationSuggestionsCache, LocationAnalysis
from media_analysis.utils.location.geohash_utils import get_cache_key, get_geohash_bounds, encode_location
from media_analysis.utils.location.cache import get_or_fetch_location_suggestions
from constance import config

logger = logging.getLogger(__name__)

# Maximum points per time slice to prevent frontend overload
MAX_POINTS_PER_SLICE = 1000
# Grid precision for sampling (lower = larger grid cells = more aggressive sampling)
SAMPLING_GRID_PRECISION = 4


@staff_member_required
def location_cache_dashboard(request):
    """
    Web-based monitoring dashboard for location cache.
    Displays cache entries with interactive map.
    """
    context = {
        'title': 'Location Cache Monitor',
    }
    return render(request, 'admin/location_cache_dashboard.html', context)


@staff_member_required
def location_cache_api(request):
    """
    JSON API endpoint for location cache data.
    Returns cache entries and metrics for the dashboard.

    Query Parameters:
        page: Page number (default: 1)
        page_size: Entries per page (default: 10, max: 50)
        search: Search term for city, neighborhood, metro_area, or geohash
    """
    # Parse pagination parameters
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(50, max(1, int(request.GET.get('page_size', 10))))
    except (ValueError, TypeError):
        page_size = 10

    search = request.GET.get('search', '').strip()

    # Build query with optional search filter
    queryset = LocationSuggestionsCache.objects.all()

    if search:
        queryset = queryset.filter(
            Q(city_name__icontains=search) |
            Q(neighborhood_name__icontains=search) |
            Q(geohash__icontains=search) |
            Q(suggestions_data__location__metro_area__icontains=search)
        )

    # Get total count before pagination
    total_count = queryset.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    # Apply pagination
    offset = (page - 1) * page_size
    cache_entries = queryset.order_by('-updated_at')[offset:offset + page_size]

    # Calculate metrics from LocationAnalysis (analytics tracking)
    analytics = LocationAnalysis.objects.all()
    total_requests = analytics.count()
    redis_hits = analytics.filter(cache_source='redis').count()
    pg_hits = analytics.filter(cache_source='postgresql').count()
    api_fetches = analytics.filter(cache_source='api').count()

    # Calculate hit rate
    total_cache_hits = redis_hits + pg_hits
    hit_rate = (total_cache_hits / total_requests * 100) if total_requests > 0 else 0

    # Format cache entries for display
    formatted_entries = []

    # First, try PostgreSQL entries
    for entry in cache_entries:
        # Extract base geohash and settings from key
        # Format: geohash:r{radius}:v{max_venues}
        parts = entry.geohash.split(':')
        base_geohash = parts[0]

        # Parse search radius from cache key
        search_radius = config.LOCATION_SEARCH_RADIUS_METERS  # Default
        if len(parts) >= 2 and parts[1].startswith('r'):
            try:
                search_radius = int(parts[1][1:])
            except ValueError:
                pass

        # Decode geohash to get center coordinates (use bounds for precision)
        try:
            bounds = get_geohash_bounds(base_geohash)
            lat, lng = bounds['center_lat'], bounds['center_lng']
        except Exception:
            lat, lng = entry.latitude, entry.longitude
            bounds = None

        # Get suggestions from cache data
        suggestions_data = entry.suggestions_data or {}
        suggestions = suggestions_data.get('suggestions', [])

        # Filter to area types vs venue types
        area_types = ['neighborhood', 'city', 'metro']
        areas = [s for s in suggestions if s.get('type') in area_types]
        venues = [s for s in suggestions if s.get('type') not in area_types]

        formatted_entries.append({
            'geohash': entry.geohash,
            'base_geohash': base_geohash,
            'latitude': lat,
            'longitude': lng,
            'bounds': bounds,
            'search_radius': search_radius,
            'city': entry.city_name or suggestions_data.get('location', {}).get('city', 'Unknown'),
            'neighborhood': entry.neighborhood_name or suggestions_data.get('location', {}).get('neighborhood', ''),
            'metro_area': suggestions_data.get('location', {}).get('metro_area', ''),
            'lookup_count': entry.lookup_count,
            'created_at': entry.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': entry.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'areas': areas,
            'venues': venues,
            'total_suggestions': len(suggestions),
            'source': 'postgresql',
        })

    # Only check Redis for entries not in PostgreSQL when searching by geohash
    # (Redis-only entries are rare edge cases, usually data should be in both)
    redis_only_entries = []
    if search and page == 1:
        # Only on first page of search results, check for Redis-only matches by geohash
        pg_geohashes = {e['base_geohash'] for e in formatted_entries}
        try:
            # Use pattern matching to find Redis keys that might match the search
            redis_keys = cache.keys(f'location:suggestions:*{search}*')
            for redis_key in redis_keys[:20]:  # Limit Redis-only to 20
                try:
                    # Parse the key format: location:suggestions:geohash:r{radius}:v{max_venues}
                    parts = redis_key.split(':')
                    if len(parts) >= 3:
                        base_geohash = parts[2]
                        geohash_key = ':'.join(parts[2:])
                    else:
                        continue

                    # Skip if we already have this from PostgreSQL
                    if base_geohash in pg_geohashes:
                        continue

                    # Only include if geohash matches search (case-insensitive)
                    if search.lower() not in base_geohash.lower():
                        continue

                    cached_data = cache.get(redis_key)
                    if not cached_data:
                        continue

                    if isinstance(cached_data, str):
                        cached_data = json.loads(cached_data)

                    # Parse search radius from cache key
                    search_radius = config.LOCATION_SEARCH_RADIUS_METERS
                    if len(parts) >= 4 and parts[3].startswith('r'):
                        try:
                            search_radius = int(parts[3][1:])
                        except ValueError:
                            pass

                    # Decode geohash to get coordinates
                    try:
                        bounds = get_geohash_bounds(base_geohash)
                        lat, lng = bounds['center_lat'], bounds['center_lng']
                    except Exception:
                        lat, lng = 0, 0
                        bounds = None

                    suggestions = cached_data.get('suggestions', [])
                    location_data = cached_data.get('location', {})

                    area_types = ['neighborhood', 'city', 'metro']
                    areas = [s for s in suggestions if s.get('type') in area_types]
                    venues = [s for s in suggestions if s.get('type') not in area_types]

                    redis_only_entries.append({
                        'geohash': geohash_key,
                        'base_geohash': base_geohash,
                        'latitude': lat,
                        'longitude': lng,
                        'bounds': bounds,
                        'search_radius': search_radius,
                        'city': location_data.get('city', 'Unknown'),
                        'neighborhood': location_data.get('neighborhood', ''),
                        'metro_area': location_data.get('metro_area', ''),
                        'lookup_count': 0,
                        'created_at': 'N/A (Redis-only)',
                        'updated_at': 'N/A (Redis-only)',
                        'areas': areas,
                        'venues': venues,
                        'total_suggestions': len(suggestions),
                        'source': 'redis',
                    })
                except Exception as e:
                    logger.warning(f"Error reading Redis key {redis_key}: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Error searching Redis keys: {e}")

    # Combine PostgreSQL entries with any Redis-only matches
    all_entries = formatted_entries + redis_only_entries

    # Get current settings
    settings_info = {
        'enabled': config.LOCATION_SUGGESTIONS_ENABLED,
        'radius_meters': config.LOCATION_SEARCH_RADIUS_METERS,
        'max_venues': config.LOCATION_MAX_VENUES,
        'cache_ttl_hours': config.LOCATION_CACHE_TTL_HOURS,
        'geohash_precision': config.LOCATION_GEOHASH_PRECISION,
    }

    return JsonResponse({
        'metrics': {
            'total_requests': total_requests,
            'redis_hits': redis_hits,
            'pg_hits': pg_hits,
            'api_fetches': api_fetches,
            'hit_rate': round(hit_rate, 1),
            'total_cache_entries': total_count,
        },
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1,
        },
        'search': search or None,
        'settings': settings_info,
        'entries': all_entries,
    })


@staff_member_required
@require_POST
def location_cache_delete(request):
    """
    Delete a location cache entry from both Redis and PostgreSQL.
    """
    try:
        data = json.loads(request.body)
        geohash = data.get('geohash')

        if not geohash:
            return JsonResponse({'success': False, 'error': 'Geohash is required'}, status=400)

        # Delete from PostgreSQL
        deleted_count, _ = LocationSuggestionsCache.objects.filter(geohash=geohash).delete()

        # Delete from Redis
        # Extract base geohash and rebuild Redis key
        parts = geohash.split(':')
        base_geohash = parts[0]
        if len(parts) >= 3:
            # Key format: geohash:r{radius}:v{max_venues}
            radius = int(parts[1][1:])  # Remove 'r' prefix
            max_venues = int(parts[2][1:])  # Remove 'v' prefix
            redis_key = get_cache_key(base_geohash, radius, max_venues)
        else:
            redis_key = get_cache_key(base_geohash)

        cache.delete(redis_key)

        logger.info(f"Deleted location cache entry: {geohash}")

        return JsonResponse({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cache entry {geohash} deleted successfully'
        })

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error deleting cache entry: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@staff_member_required
def location_analytics_timeslice(request):
    """
    Time-slice analytics API for "lightning strike map" visualization.

    Returns location analysis points for a specific 5-minute time window,
    with grid-based sampling if points exceed the maximum threshold.

    Query Parameters:
        start_time: ISO 8601 timestamp for slice start (required)
        end_time: ISO 8601 timestamp for slice end (optional, defaults to start + 5 min)

    Response:
        {
            "points": [...],           # Array of location points
            "slice_start": "...",      # ISO timestamp
            "slice_end": "...",        # ISO timestamp
            "total_count": 1234,       # Total points before sampling
            "sampled": true,           # Whether sampling was applied
            "sample_method": "grid",   # Sampling method used (if any)
            "max_points": 1000         # Maximum points returned
        }
    """
    from datetime import datetime
    from django.utils.dateparse import parse_datetime

    # Parse time parameters
    start_time_str = request.GET.get('start_time')
    end_time_str = request.GET.get('end_time')

    if not start_time_str:
        return JsonResponse({
            'success': False,
            'error': 'start_time parameter is required'
        }, status=400)

    try:
        # Parse start time
        start_time = parse_datetime(start_time_str)
        if start_time is None:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))

        # Make timezone-aware if not already
        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time)

        # Parse or calculate end time (default: 5 minutes after start)
        if end_time_str:
            end_time = parse_datetime(end_time_str)
            if end_time is None:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            if timezone.is_naive(end_time):
                end_time = timezone.make_aware(end_time)
        else:
            end_time = start_time + timedelta(minutes=5)

    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid time format: {str(e)}'
        }, status=400)

    # Query LocationAnalysis for this time window
    analyses = LocationAnalysis.objects.filter(
        created_at__gte=start_time,
        created_at__lt=end_time
    ).select_related('user').order_by('-created_at')

    total_count = analyses.count()
    sampled = False
    sample_method = None

    # Apply grid-based sampling if too many points
    if total_count > MAX_POINTS_PER_SLICE:
        sampled = True
        sample_method = 'grid'
        points = _sample_by_grid(analyses, MAX_POINTS_PER_SLICE)
    else:
        points = _format_analysis_points(analyses)

    return JsonResponse({
        'success': True,
        'points': points,
        'slice_start': start_time.isoformat(),
        'slice_end': end_time.isoformat(),
        'total_count': total_count,
        'sampled': sampled,
        'sample_method': sample_method,
        'max_points': MAX_POINTS_PER_SLICE,
    })


def _format_analysis_points(analyses):
    """
    Format LocationAnalysis queryset into point data for the map.

    Returns list of point dicts with:
    - id, latitude, longitude
    - timestamp (ISO format)
    - ip_address, fingerprint
    - user_id, username (if authenticated)
    - city_name, neighborhood_name
    - cache_source
    """
    points = []
    for analysis in analyses:
        point = {
            'id': str(analysis.id),
            'latitude': analysis.latitude,
            'longitude': analysis.longitude,
            'timestamp': analysis.created_at.isoformat(),
            'ip_address': analysis.ip_address or '',
            'fingerprint': analysis.fingerprint or '',
            'user_id': analysis.user_id,
            'username': analysis.user.username if analysis.user else None,
            'city_name': analysis.city_name or '',
            'neighborhood_name': analysis.neighborhood_name or '',
            'cache_source': analysis.cache_source or 'unknown',
            'geohash': analysis.geohash or '',
        }
        points.append(point)
    return points


def _sample_by_grid(analyses, max_points):
    """
    Sample points using grid-based geohash bucketing.

    Groups points by truncated geohash (lower precision = larger cells),
    then keeps the most recent point from each cell.

    This ensures even geographic distribution in the sampled data.
    """
    # Group points by grid cell (truncated geohash)
    grid_cells = defaultdict(list)

    for analysis in analyses:
        # Use the existing geohash truncated to lower precision for grid cells
        # Precision 4 = ~39km x 20km cells
        if analysis.geohash:
            grid_key = analysis.geohash[:SAMPLING_GRID_PRECISION]
        else:
            # Encode location to get geohash if not stored
            try:
                grid_key = encode_location(
                    analysis.latitude,
                    analysis.longitude,
                    precision=SAMPLING_GRID_PRECISION
                )
            except Exception:
                grid_key = f"{round(analysis.latitude, 1)}_{round(analysis.longitude, 1)}"

        grid_cells[grid_key].append(analysis)

    # Sample from each grid cell
    sampled_analyses = []
    total_cells = len(grid_cells)

    if total_cells == 0:
        return []

    # Calculate how many points to take from each cell
    # Distribute points proportionally based on cell density
    points_per_cell = max(1, max_points // total_cells)

    for grid_key, cell_analyses in grid_cells.items():
        # Sort by timestamp (most recent first) and take up to points_per_cell
        cell_analyses.sort(key=lambda x: x.created_at, reverse=True)
        sampled_analyses.extend(cell_analyses[:points_per_cell])

    # If we still have too many, trim to max_points (keeps most recent overall)
    if len(sampled_analyses) > max_points:
        sampled_analyses.sort(key=lambda x: x.created_at, reverse=True)
        sampled_analyses = sampled_analyses[:max_points]

    return _format_analysis_points(sampled_analyses)


@staff_member_required
def location_analytics_point_details(request, point_id):
    """
    Get detailed information about a specific location analysis point.

    Returns user details, chat participations, and related data.
    """
    try:
        analysis = LocationAnalysis.objects.select_related('user').get(id=point_id)
    except LocationAnalysis.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Point not found'
        }, status=404)

    # Get user's chat participations if they have a user account
    chat_rooms = []
    if analysis.user:
        # Import here to avoid circular imports
        from chats.models import ChatParticipation
        participations = ChatParticipation.objects.filter(
            user=analysis.user
        ).select_related('chat').order_by('-last_seen')[:10]

        chat_rooms = [{
            'code': p.chat.code,
            'name': p.chat.name,
            'last_seen': p.last_seen.isoformat() if p.last_seen else None,
            'is_host': p.is_host,
        } for p in participations]

    # Also check for fingerprint-based participations
    fingerprint_rooms = []
    if analysis.fingerprint:
        from chats.models import ChatParticipation
        fp_participations = ChatParticipation.objects.filter(
            fingerprint=analysis.fingerprint
        ).exclude(
            user=analysis.user if analysis.user else None
        ).select_related('chat').order_by('-last_seen')[:10]

        fingerprint_rooms = [{
            'code': p.chat.code,
            'name': p.chat.name,
            'last_seen': p.last_seen.isoformat() if p.last_seen else None,
            'is_host': p.is_host,
            'username': p.username,
        } for p in fp_participations]

    # Get suggestions associated with this analysis
    suggestions_list = []
    for suggestion in analysis.suggestions.all()[:10]:
        suggestions_list.append({
            'name': suggestion.name,
            'key': suggestion.key,
            'is_proper_noun': suggestion.is_proper_noun,
        })

    return JsonResponse({
        'success': True,
        'point': {
            'id': str(analysis.id),
            'latitude': analysis.latitude,
            'longitude': analysis.longitude,
            'geohash': analysis.geohash,
            'timestamp': analysis.created_at.isoformat(),
            'ip_address': analysis.ip_address or '',
            'fingerprint': analysis.fingerprint or '',
            'city_name': analysis.city_name or '',
            'neighborhood_name': analysis.neighborhood_name or '',
            'cache_source': analysis.cache_source or 'unknown',
            'cache_hit': analysis.cache_hit,
            'selected_suggestion_code': analysis.selected_suggestion_code or '',
            'selected_at': analysis.selected_at.isoformat() if analysis.selected_at else None,
        },
        'user': {
            'id': analysis.user.id if analysis.user else None,
            'username': analysis.user.username if analysis.user else None,
            'email': analysis.user.email if analysis.user else None,
            'date_joined': analysis.user.date_joined.isoformat() if analysis.user else None,
        } if analysis.user else None,
        'chat_rooms': chat_rooms,
        'fingerprint_rooms': fingerprint_rooms,
        'suggestions': suggestions_list,
    })


@staff_member_required
def location_analytics_time_range(request):
    """
    Get the available time range for location analytics data.

    Returns the earliest and latest timestamps in the LocationAnalysis table,
    useful for initializing the playback controls.
    """
    from django.db.models import Min, Max

    stats = LocationAnalysis.objects.aggregate(
        earliest=Min('created_at'),
        latest=Max('created_at'),
    )

    if not stats['earliest'] or not stats['latest']:
        return JsonResponse({
            'success': True,
            'has_data': False,
            'earliest': None,
            'latest': None,
            'total_count': 0,
        })

    total_count = LocationAnalysis.objects.count()

    return JsonResponse({
        'success': True,
        'has_data': True,
        'earliest': stats['earliest'].isoformat(),
        'latest': stats['latest'].isoformat(),
        'total_count': total_count,
    })


# Zoom level to geohash precision mapping for LOD
# Lower precision = larger cells = fewer clusters when zoomed out
ZOOM_TO_PRECISION = {
    # Zoom 0-4: World/continent view - very coarse clustering
    0: 2, 1: 2, 2: 2, 3: 2, 4: 2,
    # Zoom 5-6: Country view
    5: 3, 6: 3,
    # Zoom 7-8: State/region view
    7: 4, 8: 4,
    # Zoom 9-10: Metro area view
    9: 5, 10: 5,
    # Zoom 11-12: City/neighborhood view
    11: 6, 12: 6,
    # Zoom 13+: Street level - full precision (individual points)
    13: 7, 14: 7, 15: 8, 16: 8, 17: 9, 18: 9,
}

# Maximum clusters to return (keeps response size bounded)
MAX_LOD_CLUSTERS = 500


def _zoom_to_precision(zoom):
    """Convert Leaflet zoom level to geohash precision."""
    zoom = int(zoom)
    if zoom in ZOOM_TO_PRECISION:
        return ZOOM_TO_PRECISION[zoom]
    elif zoom < 0:
        return 2
    else:
        return 9  # Max precision for very high zoom


@staff_member_required
def location_analytics_lod(request):
    """
    Level of Detail (LOD) analytics API for zoom-aware lightning strike map.

    Returns location analysis points clustered by geohash precision based on zoom level.
    At low zoom (zoomed out), returns coarse clusters. At high zoom, returns individual points.

    Query Parameters:
        zoom: Map zoom level (0-18, required)
        north: Bounding box north latitude (optional, for viewport filtering)
        south: Bounding box south latitude (optional)
        east: Bounding box east longitude (optional)
        west: Bounding box west longitude (optional)
        hours: Hours of history to include (default: 1)

    Response:
        {
            "clusters": [
                {
                    "geohash": "dpsd",
                    "latitude": 41.123,
                    "longitude": -87.456,
                    "count": 15,
                    "newest_timestamp": "2024-01-15T10:30:00Z",
                    "oldest_timestamp": "2024-01-15T09:45:00Z",
                    "city_name": "Chicago"
                },
                ...
            ],
            "zoom": 5,
            "precision": 3,
            "total_points": 1234,
            "cluster_count": 87,
            "time_range": {
                "start": "2024-01-15T09:30:00Z",
                "end": "2024-01-15T10:30:00Z"
            }
        }
    """
    from django.db.models import Count, Max, Min, Avg
    from django.db.models.functions import Substr

    # Parse zoom level (required)
    zoom_str = request.GET.get('zoom')
    if not zoom_str:
        return JsonResponse({
            'success': False,
            'error': 'zoom parameter is required'
        }, status=400)

    try:
        zoom = int(zoom_str)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'zoom must be an integer'
        }, status=400)

    # Parse optional viewport bounds
    north = request.GET.get('north')
    south = request.GET.get('south')
    east = request.GET.get('east')
    west = request.GET.get('west')

    has_bounds = all([north, south, east, west])
    if has_bounds:
        try:
            north = float(north)
            south = float(south)
            east = float(east)
            west = float(west)
        except ValueError:
            has_bounds = False

    # Parse hours parameter (default: 1 hour)
    hours_str = request.GET.get('hours', '1')
    try:
        hours = float(hours_str)
    except ValueError:
        hours = 1.0

    # Calculate time range
    end_time = timezone.now()
    start_time = end_time - timedelta(hours=hours)

    # Determine geohash precision based on zoom
    precision = _zoom_to_precision(zoom)

    # Build base query
    queryset = LocationAnalysis.objects.filter(
        created_at__gte=start_time,
        created_at__lte=end_time,
    )

    # Apply viewport bounds if provided
    if has_bounds:
        queryset = queryset.filter(
            latitude__gte=south,
            latitude__lte=north,
            longitude__gte=west,
            longitude__lte=east,
        )

    # Get total count before clustering
    total_points = queryset.count()

    # At high zoom levels (precision >= 7), return individual points instead of clusters
    if precision >= 7:
        # Return individual points (limit to MAX_LOD_CLUSTERS)
        points = queryset.order_by('-created_at')[:MAX_LOD_CLUSTERS]
        clusters = []
        for point in points:
            clusters.append({
                'geohash': point.geohash or '',
                'latitude': point.latitude,
                'longitude': point.longitude,
                'count': 1,
                'newest_timestamp': point.created_at.isoformat(),
                'oldest_timestamp': point.created_at.isoformat(),
                'city_name': point.city_name or '',
                'is_cluster': False,
            })
    else:
        # Cluster by truncated geohash
        clustered = queryset.annotate(
            geohash_cell=Substr('geohash', 1, precision)
        ).values('geohash_cell').annotate(
            count=Count('id'),
            newest_timestamp=Max('created_at'),
            oldest_timestamp=Min('created_at'),
            avg_lat=Avg('latitude'),
            avg_lng=Avg('longitude'),
        ).order_by('-newest_timestamp')[:MAX_LOD_CLUSTERS]

        clusters = []
        for cluster in clustered:
            # Get a sample city name for this cluster
            sample = queryset.filter(
                geohash__startswith=cluster['geohash_cell']
            ).exclude(city_name='').first()

            clusters.append({
                'geohash': cluster['geohash_cell'],
                'latitude': cluster['avg_lat'],
                'longitude': cluster['avg_lng'],
                'count': cluster['count'],
                'newest_timestamp': cluster['newest_timestamp'].isoformat(),
                'oldest_timestamp': cluster['oldest_timestamp'].isoformat(),
                'city_name': sample.city_name if sample else '',
                'is_cluster': cluster['count'] > 1,
            })

    return JsonResponse({
        'success': True,
        'clusters': clusters,
        'zoom': zoom,
        'precision': precision,
        'total_points': total_points,
        'cluster_count': len(clusters),
        'time_range': {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
        },
    })


@staff_member_required
def location_cache_preview(request):
    """
    Preview endpoint for "Create Cache Point" feature.

    Takes lat/lng coordinates and returns the geohash + bounds that would be
    used for caching, based on current Constance settings.

    Query Parameters:
        lat: Latitude (required)
        lng: Longitude (required)

    Response:
        {
            "success": true,
            "geohash": "dpsd8h",
            "bounds": {
                "min_lat": 41.123,
                "max_lat": 41.456,
                "min_lng": -87.789,
                "max_lng": -87.456,
                "center_lat": 41.289,
                "center_lng": -87.622
            },
            "settings": {
                "precision": 6,
                "radius_meters": 1000,
                "max_venues": 10
            },
            "cache_key": "dpsd8h:r1000:v10"
        }
    """
    lat_str = request.GET.get('lat')
    lng_str = request.GET.get('lng')

    if not lat_str or not lng_str:
        return JsonResponse({
            'success': False,
            'error': 'lat and lng parameters are required'
        }, status=400)

    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'lat and lng must be valid numbers'
        }, status=400)

    # Validate coordinate ranges
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return JsonResponse({
            'success': False,
            'error': 'Invalid coordinates: lat must be -90 to 90, lng must be -180 to 180'
        }, status=400)

    # Get current settings from Constance
    precision = config.LOCATION_GEOHASH_PRECISION
    radius_meters = config.LOCATION_SEARCH_RADIUS_METERS
    max_venues = config.LOCATION_MAX_VENUES

    # Encode the location to get geohash
    geohash = encode_location(lat, lng, precision=precision)

    # Get bounds for the geohash
    bounds = get_geohash_bounds(geohash)

    # Build the cache key that would be used
    cache_key = get_cache_key(geohash, radius_meters, max_venues)

    # Check if this location is already cached
    existing_cache = LocationSuggestionsCache.objects.filter(geohash=f"{geohash}:r{radius_meters}:v{max_venues}").first()

    return JsonResponse({
        'success': True,
        'latitude': lat,
        'longitude': lng,
        'geohash': geohash,
        'bounds': bounds,
        'settings': {
            'precision': precision,
            'radius_meters': radius_meters,
            'max_venues': max_venues,
        },
        'cache_key': f"{geohash}:r{radius_meters}:v{max_venues}",
        'already_cached': existing_cache is not None,
        'existing_entry': {
            'lookup_count': existing_cache.lookup_count,
            'updated_at': existing_cache.updated_at.isoformat(),
        } if existing_cache else None,
    })


@staff_member_required
def location_suggestions_fetch(request):
    """
    Fetch location suggestions for a given coordinate.

    Returns the suggestions that would be shown to a user at this location,
    ranked by distance from the coordinates.

    Query Parameters:
        latitude: Latitude (required)
        longitude: Longitude (required)
    """
    lat_str = request.GET.get('latitude')
    lng_str = request.GET.get('longitude')

    if not lat_str or not lng_str:
        return JsonResponse({
            'success': False,
            'error': 'latitude and longitude parameters are required'
        }, status=400)

    try:
        lat = float(lat_str)
        lng = float(lng_str)
    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'latitude and longitude must be valid numbers'
        }, status=400)

    # Validate coordinate ranges
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return JsonResponse({
            'success': False,
            'error': 'Invalid coordinates'
        }, status=400)

    try:
        result = get_or_fetch_location_suggestions(lat, lng)

        if result:
            return JsonResponse({
                'success': True,
                'suggestions': result.get('suggestions', []),
                'location': result.get('location', {}),
                'cached': result.get('cached', False),
                'cache_source': result.get('cache_source', 'unknown'),
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No suggestions available for this location'
            })

    except Exception as e:
        logger.error(f"Error fetching suggestions: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
@require_POST
def location_cache_create(request):
    """
    Create a cache entry by triggering the location suggest API.

    This simulates a frontend device at the given location, calling the same
    API endpoint that real users would call.

    POST Body:
        {
            "latitude": 41.123,
            "longitude": -87.456
        }

    Response:
        Same as /api/media-analysis/location/suggest/ endpoint
    """
    try:
        data = json.loads(request.body)
        lat = data.get('latitude')
        lng = data.get('longitude')

        if lat is None or lng is None:
            return JsonResponse({
                'success': False,
                'error': 'latitude and longitude are required'
            }, status=400)

        lat = float(lat)
        lng = float(lng)

        # Validate coordinate ranges
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            return JsonResponse({
                'success': False,
                'error': 'Invalid coordinates'
            }, status=400)

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid request: {str(e)}'
        }, status=400)

    # Import the location service to trigger the same flow as the API
    from media_analysis.utils.location import get_or_fetch_location_suggestions

    try:
        # Call the location suggestions service (same as the API endpoint)
        result = get_or_fetch_location_suggestions(lat, lng)

        if result is None:
            return JsonResponse({
                'success': False,
                'error': 'Location suggestions unavailable (feature may be disabled)'
            }, status=503)

        # Optionally create a LocationAnalysis record to track this admin action
        location_info = result.get('location', {})
        geohash = location_info.get('geohash', '')

        LocationAnalysis.objects.create(
            latitude=lat,
            longitude=lng,
            geohash=geohash,
            city_name=location_info.get('city') or '',
            neighborhood_name=location_info.get('neighborhood') or '',
            user=request.user,
            fingerprint=f'admin:{request.user.username}',
            ip_address=request.META.get('REMOTE_ADDR'),
            cache_hit=result.get('cached', False),
            cache_source=result.get('cache_source', 'api'),
        )

        return JsonResponse({
            'success': True,
            'message': 'Cache entry created successfully',
            'cached': result.get('cached', False),
            'cache_source': result.get('cache_source', 'api'),
            'location': result.get('location', {}),
            'suggestions_count': len(result.get('suggestions', [])),
            'suggestions': result.get('suggestions', []),
        })

    except Exception as e:
        logger.error(f"Error creating cache entry: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
