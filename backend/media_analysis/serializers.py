"""
DRF Serializers for Photo Analysis API.
"""
from rest_framework import serializers
from .models import PhotoAnalysis


class ChatSuggestionSerializer(serializers.Serializer):
    """Serializer for individual chat room name suggestions."""
    name = serializers.CharField(
        max_length=100,
        help_text="Title Case chat name (e.g., 'Curious Cat')"
    )
    key = serializers.CharField(
        max_length=100,
        help_text="URL-safe key (e.g., 'curious-cat')"
    )
    description = serializers.CharField(
        max_length=500,
        help_text="Short description of the chat topic"
    )


class PhotoAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for PhotoAnalysis model."""

    # Read-only fields
    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    # Suggestions field (extracts from database JSON structure)
    suggestions = serializers.SerializerMethodField(
        help_text="Array of AI-generated chat name suggestions"
    )

    # User information (optional)
    username = serializers.SerializerMethodField(
        help_text="Username of the user who uploaded this photo (if authenticated)"
    )

    class Meta:
        model = PhotoAnalysis
        fields = [
            'id',
            'suggestions',
            'username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
        ]

    def get_suggestions(self, obj):
        """
        Extract and format suggestions from database JSON field.

        Returns:
            list[dict]: Array of suggestion objects with name, key, and description fields.
        """
        suggestions_data = obj.suggestions

        if isinstance(suggestions_data, dict):
            # Extract suggestions array from JSON
            suggestions_list = suggestions_data.get('suggestions', [])
        elif isinstance(suggestions_data, list):
            # Already a list
            suggestions_list = suggestions_data
        else:
            suggestions_list = []

        # Validate and serialize each suggestion
        serializer = ChatSuggestionSerializer(data=suggestions_list, many=True)
        if serializer.is_valid():
            return serializer.data
        else:
            # Return raw data if validation fails
            return suggestions_list

    def get_username(self, obj):
        """Get username if user is authenticated."""
        if obj.user:
            return obj.user.username
        return None


class PhotoUploadSerializer(serializers.Serializer):
    """Serializer for photo upload and analysis request."""

    image = serializers.ImageField(
        required=True,
        help_text="Image file to analyze (JPEG, PNG, WebP, etc.)"
    )
    fingerprint = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Browser fingerprint for anonymous tracking"
    )

    def validate_image(self, value):
        """Validate image file size and type."""
        from django.conf import settings
        from constance import config

        # Check file size
        max_size_mb = config.PHOTO_ANALYSIS_MAX_FILE_SIZE_MB
        max_size_bytes = max_size_mb * 1024 * 1024

        if value.size > max_size_bytes:
            raise serializers.ValidationError(
                f"Image file too large. Maximum size is {max_size_mb}MB."
            )

        # Check file type (by extension and content type)
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/heic', 'image/mpo']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported image type: {value.content_type}. "
                f"Allowed types: JPEG, PNG, WebP, GIF, HEIC, MPO."
            )

        return value


class PhotoAnalysisDetailSerializer(PhotoAnalysisSerializer):
    """Extended serializer with additional details for single object retrieval."""

    # Include expiration info
    expires_at = serializers.DateTimeField(read_only=True)
    is_expired = serializers.SerializerMethodField()

    # File hashes (for debugging/deduplication)
    image_phash = serializers.CharField(read_only=True)
    file_hash = serializers.CharField(read_only=True)
    file_size = serializers.IntegerField(read_only=True)

    # Seed suggestions (original 10 AI suggestions from Vision API - for debugging)
    seed_suggestions = serializers.SerializerMethodField(
        help_text="Original 10 AI suggestions from Vision API (audit trail for debugging)"
    )

    # Room selection tracking
    selected_suggestion_code = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    selected_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta(PhotoAnalysisSerializer.Meta):
        fields = PhotoAnalysisSerializer.Meta.fields + [
            'expires_at',
            'is_expired',
            'image_phash',
            'file_hash',
            'file_size',
            'seed_suggestions',
            'selected_suggestion_code',
            'selected_at',
        ]

    def get_is_expired(self, obj):
        """Check if analysis has expired."""
        return obj.is_expired()

    def get_seed_suggestions(self, obj):
        """
        Extract and format seed suggestions from database JSON field.

        Seed suggestions are the initial 10 AI-generated suggestions from Vision API.
        Used for debugging and audit trail.

        Returns:
            list[dict]: Array of seed suggestion objects with name, key, and description fields.
                        Returns None if seed_suggestions field is null (older records).
        """
        if not obj.seed_suggestions:
            return None

        seed_suggestions_data = obj.seed_suggestions

        if isinstance(seed_suggestions_data, dict):
            # Extract suggestions array from JSON
            suggestions_list = seed_suggestions_data.get('suggestions', [])
        elif isinstance(seed_suggestions_data, list):
            # Already a list
            suggestions_list = seed_suggestions_data
        else:
            return None

        # Validate and serialize each suggestion
        serializer = ChatSuggestionSerializer(data=suggestions_list, many=True)
        if serializer.is_valid():
            return serializer.data
        else:
            # Return raw data if validation fails
            return suggestions_list


class PhotoAnalysisListSerializer(PhotoAnalysisSerializer):
    """Lightweight serializer for list views."""

    # Only include suggestion count, not full data
    suggestion_count = serializers.SerializerMethodField()

    class Meta(PhotoAnalysisSerializer.Meta):
        fields = [
            'id',
            'suggestion_count',
            'username',
            'created_at',
        ]

    def get_suggestion_count(self, obj):
        """Return number of suggestions."""
        suggestions_data = obj.suggestions

        if isinstance(suggestions_data, dict):
            return suggestions_data.get('count', len(suggestions_data.get('suggestions', [])))
        elif isinstance(suggestions_data, list):
            return len(suggestions_data)
        return 0


class PhotoUploadResponseSerializer(serializers.Serializer):
    """
    Response serializer for /upload/ endpoint.

    This documents the complete response structure including:
    - cached: Whether this is a cached result
    - analysis: Full PhotoAnalysis object with blended suggestions

    The analysis.suggestions field contains blended suggestions with metadata:
    - source: 'existing_room', 'popular', or 'ai'
    - has_room: boolean indicating if a room already exists
    - active_users: number of active users (for existing rooms)
    - popularity_score: frequency count (for popular suggestions)
    - room_id, room_code, room_url: room details (for existing rooms)
    """
    cached = serializers.BooleanField(
        help_text="Whether this analysis was cached (true) or freshly generated (false)"
    )
    analysis = PhotoAnalysisDetailSerializer(
        help_text="Complete photo analysis with AI suggestions and embeddings"
    )
