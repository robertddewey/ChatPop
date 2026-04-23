from django.contrib import admin
from .models import ChatRoom, Message, Transaction, ChatTheme


admin.site.site_header = "ChatPop Administration"
admin.site.index_title = "ChatPop Admin"


@admin.register(ChatTheme)
class ChatThemeAdmin(admin.ModelAdmin):
    list_display = ['name', 'theme_id', 'is_dark_mode', 'created_at']
    list_filter = ['is_dark_mode', 'created_at']
    search_fields = ['name', 'theme_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'host', 'access_mode', 'is_active', 'created_at']
    list_filter = ['access_mode', 'is_active', 'voice_enabled', 'video_enabled', 'created_at']
    search_fields = ['name', 'code', 'host__email', 'description']
    readonly_fields = ['id', 'code', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'code', 'name', 'description', 'is_active')
        }),
        ('Host Information', {
            'fields': ('host',)
        }),
        ('Access Control', {
            'fields': ('access_mode', 'access_code')
        }),
        ('Media Settings', {
            'fields': ('voice_enabled', 'video_enabled', 'photo_enabled')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['username', 'chat_room', 'message_type', 'content_preview', 'is_pinned', 'created_at']
    list_filter = ['message_type', 'is_pinned', 'is_deleted', 'created_at']
    search_fields = ['username', 'content', 'chat_room__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['username', 'transaction_type', 'amount', 'status', 'chat_room', 'created_at']
    list_filter = ['transaction_type', 'status', 'created_at']
    search_fields = ['username', 'stripe_payment_intent_id', 'stripe_charge_id', 'chat_room__name']
    readonly_fields = ['id', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'


