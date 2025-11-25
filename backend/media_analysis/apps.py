"""Django app configuration for media_analysis."""
from django.apps import AppConfig


class MediaAnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'media_analysis'
    verbose_name = 'Media Analysis'

    def ready(self):
        """Import signals when app is ready."""
        pass  # Add signal imports here if needed
