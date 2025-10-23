"""
PhotoAnalysis model for storing AI-powered photo analysis results.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class PhotoAnalysis(models.Model):
    """
    Stores photo analysis results from AI vision models.
    Enables deduplication, caching, and analytics tracking.
    """

    # Primary Key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    # === IMAGE IDENTIFICATION ===

    # Perceptual Hash (pHash) - detects similar images
    # - Can detect images that are slightly modified, resized, or compressed
    # - Example: "d879f4f8e3b0c1a2" (16-character hex string)
    # - Indexed for fast similarity lookups
    image_phash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Perceptual hash (pHash) for detecting similar images"
    )

    # File Hash (MD5) - exact file match detection
    # - Only matches identical files byte-for-byte
    # - Example: "098f6bcd4621d373cade4e832627b4f6"
    # - Indexed for fast exact match lookups
    file_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="MD5 hash for exact file match detection"
    )

    # File size for additional deduplication verification
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )

    # === IMAGE STORAGE ===

    # Storage path in S3 or local media directory
    # - Example S3: "photo_analysis/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
    # - Example Local: "photo_analysis/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
    # - Files are accessed via Django proxy endpoint for security
    image_path = models.CharField(
        max_length=512,
        help_text="Storage path (S3 or local media directory)"
    )

    # Storage type indicator ('s3' or 'local')
    storage_type = models.CharField(
        max_length=10,
        choices=[('s3', 'S3'), ('local', 'Local')],
        default='local',
        help_text="Where the image is stored"
    )

    # Image expiration timestamp (for auto-cleanup)
    # - Set based on PHOTO_ANALYSIS_IMAGE_TTL_HOURS setting
    # - Null = permanent storage
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When to delete the image (null = never)"
    )

    # === ANALYSIS RESULTS ===

    # Chat name suggestions (JSON array of objects)
    # Format:
    # {
    #   "suggestions": [
    #     {"name": "Veterans Tribute", "key": "veterans-tribute", "description": "..."},
    #     {"name": "Coffee Mug", "key": "coffee-mug", "description": "..."},
    #     ...
    #   ],
    #   "count": 10
    # }
    suggestions = models.JSONField(
        help_text="AI-generated chat name suggestions"
    )

    # Full raw response from the AI vision model
    # - Useful for debugging and reprocessing
    # - Includes all metadata from the API response
    raw_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete API response for debugging/reprocessing"
    )

    # === AI MODEL METADATA ===

    # AI vision model identifier
    # - Initially: "gpt-4-vision-preview", "gpt-4o", etc.
    # - Future: Could reference a separate AIModel table via ForeignKey
    # - Kept as string for flexibility (may switch providers)
    ai_vision_model = models.CharField(
        max_length=100,
        default="gpt-4o",
        help_text="AI vision model used for analysis (e.g., gpt-4o, claude-3-opus)"
    )

    # Token usage for cost tracking
    # - Format: {"prompt_tokens": 1234, "completion_tokens": 567, "total_tokens": 1801}
    token_usage = models.JSONField(
        null=True,
        blank=True,
        help_text="API token usage for cost tracking"
    )

    # === USAGE TRACKING ===

    # User who uploaded the photo (if authenticated)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='photo_analyses',
        help_text="Authenticated user who uploaded the photo"
    )

    # Browser fingerprint (for anonymous users and tracking)
    # - Matches the fingerprint system used in ChatParticipation
    # - Allows tracking even for unauthenticated users
    fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Browser fingerprint for tracking anonymous users"
    )

    # IP address for rate limiting and analytics
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IP address for rate limiting"
    )

    # Number of times this analysis was used to create chats
    times_used = models.PositiveIntegerField(
        default=0,
        help_text="How many chats were created from these suggestions"
    )

    # === TIMESTAMPS ===

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'photo_analysis'
        verbose_name = 'Photo Analysis'
        verbose_name_plural = 'Photo Analyses'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['image_phash', 'created_at']),
            models.Index(fields=['file_hash', 'created_at']),
            models.Index(fields=['fingerprint', 'ip_address']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"PhotoAnalysis {self.id} - {self.ai_vision_model}"

    def is_expired(self):
        """Check if the analysis has expired."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    def increment_usage(self):
        """Increment the usage counter when a chat is created from this analysis."""
        self.times_used += 1
        self.save(update_fields=['times_used', 'updated_at'])
