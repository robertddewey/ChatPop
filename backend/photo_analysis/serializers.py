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

    # Custom representation for suggestions
    suggestions = serializers.SerializerMethodField()

    # User information (optional)
    username = serializers.SerializerMethodField()

    class Meta:
        model = PhotoAnalysis
        fields = [
            'id',
            'suggestions',
            'ai_vision_model',
            'token_usage',
            'times_used',
            'username',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'ai_vision_model',
            'token_usage',
            'times_used',
            'created_at',
            'updated_at',
        ]

    def get_suggestions(self, obj):
        """Format suggestions as array of ChatSuggestion objects."""
        suggestions_data = obj.suggestions

        if isinstance(suggestions_data, dict):
            # Extract suggestions array from JSON
            suggestions_list = suggestions_data.get('suggestions', [])
        elif isinstance(suggestions_data, list):
            # Already a list
            suggestions_list = suggestions_data
        else:
            return []

        # Validate and serialize each suggestion
        serializer = ChatSuggestionSerializer(data=suggestions_list, many=True)
        if serializer.is_valid():
            return serializer.data
        return suggestions_list  # Return raw data if validation fails

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

    # Caption fields (for embeddings)
    caption_title = serializers.CharField(read_only=True)
    caption_category = serializers.CharField(read_only=True)
    caption_visible_text = serializers.CharField(read_only=True)
    caption_full = serializers.CharField(read_only=True)
    caption_generated_at = serializers.DateTimeField(read_only=True)

    # Caption API metadata
    caption_model = serializers.CharField(read_only=True)
    caption_token_usage = serializers.JSONField(read_only=True)
    caption_raw_response = serializers.JSONField(read_only=True)

    # Embedding metadata
    caption_embedding_generated_at = serializers.DateTimeField(read_only=True)
    suggestions_embedding_generated_at = serializers.DateTimeField(read_only=True)

    class Meta(PhotoAnalysisSerializer.Meta):
        fields = PhotoAnalysisSerializer.Meta.fields + [
            'expires_at',
            'is_expired',
            'file_size',
            'storage_type',
            'caption_title',
            'caption_category',
            'caption_visible_text',
            'caption_full',
            'caption_generated_at',
            'caption_model',
            'caption_token_usage',
            'caption_raw_response',
            'caption_embedding_generated_at',
            'suggestions_embedding_generated_at',
        ]

    def get_is_expired(self, obj):
        """Check if analysis has expired."""
        return obj.is_expired()


class PhotoAnalysisListSerializer(PhotoAnalysisSerializer):
    """Lightweight serializer for list views."""

    # Only include suggestion count, not full data
    suggestion_count = serializers.SerializerMethodField()

    class Meta(PhotoAnalysisSerializer.Meta):
        fields = [
            'id',
            'suggestion_count',
            'ai_vision_model',
            'times_used',
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
