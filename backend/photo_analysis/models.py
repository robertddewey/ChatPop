"""
PhotoAnalysis model for storing AI-powered photo analysis results.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from pgvector.django import VectorField


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

    # Seed suggestions (initial AI output before refinement)
    # - Stored for audit trail and refinement input
    # - 10 initial suggestions from GPT-4 Vision
    # - May contain duplicates (e.g., "Bar Room", "Drinking Lounge", "Cheers!")
    # - Used as input for LLM refinement process
    seed_suggestions = models.JSONField(
        null=True,
        blank=True,
        help_text="Initial 10 AI suggestions before refinement (audit trail)"
    )

    # Chat name suggestions (refined output for display/embedding)
    # - 5-7 refined, deduplicated suggestions
    # - Result of LLM-based refinement if enabled, otherwise same as seed_suggestions
    # - Removes true duplicates while preserving distinct entities
    # Format:
    # {
    #   "suggestions": [
    #     {"name": "Veterans Tribute", "key": "veterans-tribute", "description": "..."},
    #     {"name": "Coffee Mug", "key": "coffee-mug", "description": "..."},
    #     ...
    #   ],
    #   "count": 5-7
    # }
    suggestions = models.JSONField(
        help_text="Refined chat name suggestions (used for display and embeddings)"
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

    # === IMAGE CAPTION (For Embeddings) ===

    # Short title extracted from the image
    # - Example: "Budweiser", "Coffee Mug", "Veterans Memorial"
    # - Used for quick reference and display
    caption_title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Short title extracted from image"
    )

    # Category classification of the image
    # - Example: "beer bottle", "coffee mug", "military memorial"
    # - Used for grouping and filtering
    caption_category = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Category classification of the image"
    )

    # Any visible text found in the image
    # - Example: "Budweiser, King of Beers", "Starbucks Coffee"
    # - Extracted using OCR capabilities of vision model
    caption_visible_text = models.TextField(
        null=True,
        blank=True,
        help_text="Visible text, labels, or brand names in the image"
    )

    # Full semantic caption optimized for embedding
    # - Example: "Budweiser beer bottle labeled 'King of Beers' with red and white
    #   logo on a wooden table. A classic American lager brand."
    # - This is the text that gets converted to an embedding vector
    # - One or two concise sentences capturing visual and semantic meaning
    caption_full = models.TextField(
        null=True,
        blank=True,
        help_text="Full semantic caption used for embedding generation"
    )

    # When the caption was generated
    caption_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when caption was generated"
    )

    # === CAPTION API METADATA ===

    # AI model used for caption generation
    # - Separate from ai_vision_model (which is for suggestions)
    # - Example: "gpt-4o-mini", "gpt-4o"
    caption_model = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="AI model used for caption generation (e.g., gpt-4o-mini)"
    )

    # Token usage for caption generation API call
    # - Format: {"prompt_tokens": 850, "completion_tokens": 45, "total_tokens": 895}
    # - Separate from token_usage (which is for suggestions)
    caption_token_usage = models.JSONField(
        null=True,
        blank=True,
        help_text="Caption API token usage for cost tracking"
    )

    # Full raw response from caption generation API
    # - Useful for debugging and reprocessing
    # - Separate from raw_response (which is for suggestions)
    caption_raw_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete caption API response for debugging"
    )

    # === SEMANTIC EMBEDDINGS ===

    # Embedding 1: Semantic/Content (broad clustering)
    # - Generated from: caption_full + caption_visible_text + caption_title + caption_category
    # - Model: text-embedding-3-small (1536 dimensions)
    # - Groups by: visual content (beverages, food, nature, vehicles)
    # - Use: General categorization, future features
    caption_embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Semantic/Content embedding for broad categorization (text-embedding-3-small, 1536d)"
    )

    # When the caption embedding was generated
    caption_embedding_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when caption embedding was generated"
    )

    # Embedding 2: Conversational/Topic (PRIMARY for collaborative discovery)
    # - Generated from: caption_full + caption_visible_text + all 10 suggestion names + all 10 descriptions
    # - Model: text-embedding-3-small (1536 dimensions)
    # - Groups by: conversation potential and social context
    # - Use: Finding existing chat rooms from similar photos
    # - Why: "bar-room", "happy-hour", "brew-talk" all cluster in the same semantic space
    # - Enables collaborative discovery (Person A uploads beer → creates "bar-room",
    #   Person B uploads similar photo → sees "bar-room (1 user)" as recommendation)
    suggestions_embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Conversational/Topic embedding for finding similar chat rooms (text-embedding-3-small, 1536d)"
    )

    # When the suggestions embedding was generated
    suggestions_embedding_generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when suggestions embedding was generated"
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

    # === CHAT CREATION TRACKING ===

    # Which suggestion the user selected (if any)
    # - Stores the chat code/slug directly (e.g., 'bar-room', 'coffee-chat')
    # - Used for finding similar photos that created discover rooms
    # - Null = user hasn't selected a suggestion yet
    selected_suggestion_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        db_index=True,
        help_text="Chat code user selected (e.g., 'bar-room')"
    )

    # When the user made their selection
    selected_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user selected a suggestion"
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
