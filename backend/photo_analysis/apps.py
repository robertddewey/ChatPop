"""Django app configuration for photo_analysis."""
from django.apps import AppConfig


class PhotoAnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'photo_analysis'
    verbose_name = 'Photo Analysis'

    def ready(self):
        """Import signals when app is ready."""
        pass  # Add signal imports here if needed
