"""
Django Admin configuration for Photo Analysis.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import PhotoAnalysis


@admin.register(PhotoAnalysis)
class PhotoAnalysisAdmin(admin.ModelAdmin):
    """Admin interface for PhotoAnalysis model."""

    list_display = [
        'id_short',
        'created_at',
        'ai_vision_model',
        'suggestion_count',
        'times_used',
        'user_display',
        'storage_type',
        'is_expired_display',
        'view_image_link',
    ]

    list_filter = [
        'storage_type',
        'ai_vision_model',
        'created_at',
    ]

    search_fields = [
        'id',
        'user__username',
        'fingerprint',
        'ip_address',
        'file_hash',
        'image_phash',
    ]

    readonly_fields = [
        'id',
        'image_phash',
        'file_hash',
        'file_size',
        'image_path',
        'storage_type',
        'suggestions_display',
        'raw_response_display',
        'ai_vision_model',
        'token_usage_display',
        'user',
        'fingerprint',
        'ip_address',
        'times_used',
        'created_at',
        'updated_at',
        'expires_at',
        'image_preview',
    ]

    fieldsets = (
        ('Identification', {
            'fields': ('id', 'created_at', 'updated_at')
        }),
        ('Image Info', {
            'fields': ('image_preview', 'image_path', 'storage_type', 'file_size', 'expires_at')
        }),
        ('Fingerprints', {
            'fields': ('image_phash', 'file_hash')
        }),
        ('Analysis Results', {
            'fields': ('suggestions_display', 'ai_vision_model', 'token_usage_display')
        }),
        ('Usage Tracking', {
            'fields': ('user', 'fingerprint', 'ip_address', 'times_used')
        }),
        ('Raw Data', {
            'fields': ('raw_response_display',),
            'classes': ('collapse',)
        }),
    )

    def id_short(self, obj):
        """Display shortened UUID."""
        return str(obj.id)[:8]
    id_short.short_description = 'ID'

    def user_display(self, obj):
        """Display user or fingerprint."""
        if obj.user:
            return f"{obj.user.username} (ID: {obj.user.id})"
        elif obj.fingerprint:
            return f"Anonymous ({obj.fingerprint[:12]}...)"
        return "Unknown"
    user_display.short_description = 'User'

    def suggestion_count(self, obj):
        """Display number of suggestions."""
        suggestions_data = obj.suggestions
        if isinstance(suggestions_data, dict):
            return suggestions_data.get('count', len(suggestions_data.get('suggestions', [])))
        elif isinstance(suggestions_data, list):
            return len(suggestions_data)
        return 0
    suggestion_count.short_description = 'Suggestions'

    def is_expired_display(self, obj):
        """Display expiration status."""
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        elif obj.expires_at:
            return format_html('<span style="color: green;">Active</span>')
        return format_html('<span style="color: gray;">Never</span>')
    is_expired_display.short_description = 'Status'

    def view_image_link(self, obj):
        """Display link to view the image."""
        try:
            url = reverse('photo_analysis:photo-analysis-image-proxy', kwargs={'pk': obj.id})
            return format_html('<a href="{}" target="_blank">View Image</a>', url)
        except Exception:
            return "N/A"
    view_image_link.short_description = 'Image'

    def suggestions_display(self, obj):
        """Display suggestions in a formatted way."""
        suggestions_data = obj.suggestions

        if isinstance(suggestions_data, dict):
            suggestions_list = suggestions_data.get('suggestions', [])
        elif isinstance(suggestions_data, list):
            suggestions_list = suggestions_data
        else:
            return "No suggestions"

        html = '<ul style="margin: 0; padding-left: 20px;">'
        for suggestion in suggestions_list:
            if isinstance(suggestion, dict):
                name = suggestion.get('name', 'N/A')
                key = suggestion.get('key', 'N/A')
                description = suggestion.get('description', 'N/A')
                html += f'<li><strong>{name}</strong> ({key})<br><small>{description}</small></li>'
        html += '</ul>'

        return format_html(html)
    suggestions_display.short_description = 'Suggestions'

    def token_usage_display(self, obj):
        """Display token usage information."""
        if not obj.token_usage:
            return "N/A"

        prompt_tokens = obj.token_usage.get('prompt_tokens', 0)
        completion_tokens = obj.token_usage.get('completion_tokens', 0)
        total_tokens = obj.token_usage.get('total_tokens', 0)

        return format_html(
            '<strong>Total:</strong> {}<br>'
            '<strong>Prompt:</strong> {}<br>'
            '<strong>Completion:</strong> {}',
            total_tokens, prompt_tokens, completion_tokens
        )
    token_usage_display.short_description = 'Token Usage'

    def raw_response_display(self, obj):
        """Display raw response in a formatted way."""
        import json
        if not obj.raw_response:
            return "N/A"

        try:
            formatted_json = json.dumps(obj.raw_response, indent=2)
            return format_html('<pre style="max-height: 400px; overflow: auto;">{}</pre>', formatted_json)
        except Exception:
            return str(obj.raw_response)
    raw_response_display.short_description = 'Raw API Response'

    def image_preview(self, obj):
        """Display image preview in admin."""
        try:
            url = reverse('photo_analysis:photo-analysis-image-proxy', kwargs={'pk': obj.id})
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 300px;" />',
                url
            )
        except Exception:
            return "Image not available"
    image_preview.short_description = 'Image Preview'

    def has_add_permission(self, request):
        """Disable adding through admin (only via API)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make read-only (can only view, not edit)."""
        return False
