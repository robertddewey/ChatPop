from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserSubscription


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'display_name', 'is_staff', 'subscriber_count', 'subscription_count', 'created_at']
    list_filter = ['is_staff', 'is_active', 'created_at']
    search_fields = ['email', 'display_name']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('display_name', 'first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Notifications', {'fields': ('email_notifications', 'push_notifications')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at', 'last_active')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'display_name'),
        }),
    )

    readonly_fields = ['created_at', 'updated_at', 'last_active']

    def subscriber_count(self, obj):
        """Number of users subscribing to this user"""
        return obj.subscribers.count()
    subscriber_count.short_description = 'Subscribers'

    def subscription_count(self, obj):
        """Number of users this user subscribes to"""
        return obj.subscriptions.count()
    subscription_count.short_description = 'Subscriptions'


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['subscriber', 'subscribed_to', 'notify_on_new_chat', 'notify_on_mentions', 'created_at']
    list_filter = ['notify_on_new_chat', 'notify_on_mentions', 'created_at']
    search_fields = ['subscriber__email', 'subscribed_to__email']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['subscriber', 'subscribed_to']
