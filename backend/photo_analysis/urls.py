"""
URL Configuration for Photo Analysis API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PhotoAnalysisViewSet

# Create DRF router
router = DefaultRouter()
router.register(r'', PhotoAnalysisViewSet, basename='photo-analysis')

app_name = 'photo_analysis'

urlpatterns = [
    path('', include(router.urls)),
]

# This creates the following endpoints:
# POST   /api/photo-analysis/upload/           - Upload and analyze photo
# GET    /api/photo-analysis/                  - List analyses
# GET    /api/photo-analysis/recent/           - Recent analyses for user
# GET    /api/photo-analysis/{id}/             - Get specific analysis
# GET    /api/photo-analysis/{id}/image/       - Get image file (proxy)
