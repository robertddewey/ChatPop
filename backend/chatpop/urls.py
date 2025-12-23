"""
URL configuration for chatpop project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from chats import admin_views
from media_analysis import admin_views as media_admin_views

urlpatterns = [
    # Admin monitoring dashboards (must come BEFORE admin/ to avoid catch-all)
    # Chat cache monitor (renamed from /admin/monitoring/)
    path("admin/monitor/chat-cache/", admin_views.chat_cache_dashboard, name="chat_cache_dashboard"),
    path("admin/monitor/chat-cache/api/", admin_views.chat_cache_api, name="chat_cache_api"),

    # Location cache monitor
    path("admin/monitor/location-cache/", media_admin_views.location_cache_dashboard, name="location_cache_dashboard"),
    path("admin/monitor/location-cache/api/", media_admin_views.location_cache_api, name="location_cache_api"),
    path("admin/monitor/location-cache/delete/", media_admin_views.location_cache_delete, name="location_cache_delete"),
    path("admin/monitor/location-cache/preview/", media_admin_views.location_cache_preview, name="location_cache_preview"),
    path("admin/monitor/location-cache/create/", media_admin_views.location_cache_create, name="location_cache_create"),
    path("admin/monitor/location-cache/suggestions/", media_admin_views.location_suggestions_fetch, name="location_suggestions_fetch"),

    # Location analytics (lightning strike map)
    path("admin/monitor/location-cache/analytics/timeslice/", media_admin_views.location_analytics_timeslice, name="location_analytics_timeslice"),
    path("admin/monitor/location-cache/analytics/time-range/", media_admin_views.location_analytics_time_range, name="location_analytics_time_range"),
    path("admin/monitor/location-cache/analytics/point/<uuid:point_id>/", media_admin_views.location_analytics_point_details, name="location_analytics_point_details"),
    path("admin/monitor/location-cache/analytics/lod/", media_admin_views.location_analytics_lod, name="location_analytics_lod"),

    # Legacy redirect (backwards compatibility)
    path("admin/monitoring/", admin_views.chat_cache_dashboard, name="monitoring_dashboard"),
    path("admin/monitoring/api/", admin_views.chat_cache_api, name="monitoring_api"),

    path("admin/", admin.site.urls),

    # API endpoints
    path("api/auth/", include('accounts.urls')),
    path("api/chats/", include('chats.urls')),
    path("api/media-analysis/", include('media_analysis.urls')),

    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve static files in development (for Django admin CSS/JS with Daphne)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
