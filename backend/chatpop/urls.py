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

urlpatterns = [
    # Admin monitoring dashboard (must come BEFORE admin/ to avoid catch-all)
    path("admin/monitoring/", admin_views.monitoring_dashboard, name="monitoring_dashboard"),
    path("admin/monitoring/api/", admin_views.monitoring_api, name="monitoring_api"),

    path("admin/", admin.site.urls),

    # API endpoints
    path("api/auth/", include('accounts.urls')),
    path("api/chats/", include('chats.urls')),
    path("api/photo-analysis/", include('photo_analysis.urls')),

    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve static files in development (for Django admin CSS/JS with Daphne)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
