"""
URL Configuration for Media Analysis API.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PhotoAnalysisViewSet, MusicAnalysisViewSet

# Create DRF router
router = DefaultRouter()
router.register(r'photo', PhotoAnalysisViewSet, basename='photo-analysis')
router.register(r'music', MusicAnalysisViewSet, basename='music-analysis')

app_name = 'media_analysis'

urlpatterns = [
    path('', include(router.urls)),
]

# This creates the following endpoints:
#
# Photo Analysis:
# POST   /api/media-analysis/photo/upload/           - Upload and analyze photo
# GET    /api/media-analysis/photo/                  - List analyses
# GET    /api/media-analysis/photo/recent/           - Recent analyses for user
# GET    /api/media-analysis/photo/{id}/             - Get specific analysis
# GET    /api/media-analysis/photo/{id}/image/       - Get image file (proxy)
#
# Music Analysis:
# POST   /api/media-analysis/music/recognize/        - Recognize song from audio
# GET    /api/media-analysis/music/recent/           - Recent analyses for user
# GET    /api/media-analysis/music/{id}/             - Get specific analysis
