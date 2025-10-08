from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import string
import random


def generate_chat_code(length=8):
    """Generate a unique chat room code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


class ChatTheme(models.Model):
    """Theme configuration for chat rooms"""
    # Metadata
    theme_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique theme identifier (e.g., 'dark-mode')")
    name = models.CharField(max_length=100, help_text="Display name for the theme")
    is_dark_mode = models.BooleanField(default=True, help_text="Whether this is a dark theme")

    # Mobile browser theme colors
    theme_color_light = models.CharField(max_length=7, default='#ffffff', help_text="Hex color for light system mode")
    theme_color_dark = models.CharField(max_length=7, default='#18181b', help_text="Hex color for dark system mode")

    # Layout & Container
    container = models.TextField(help_text="Main container Tailwind classes")
    header = models.TextField(help_text="Header bar Tailwind classes")
    header_title = models.TextField(help_text="Header title text Tailwind classes")
    header_title_fade = models.TextField(help_text="Gradient fade for title")
    header_subtitle = models.TextField(help_text="Subtitle text Tailwind classes")

    # Messages Area
    sticky_section = models.TextField(help_text="Sticky messages container classes")
    messages_area = models.TextField(help_text="Scrollable messages container classes")
    messages_area_container = models.TextField(default='bg-white', help_text="Background classes for messages area container (parent of pattern layer)")
    messages_area_bg = models.TextField(blank=True, help_text="Background pattern/SVG configuration")

    # Host Messages
    host_message = models.TextField(help_text="Regular host message bubble classes")
    sticky_host_message = models.TextField(help_text="Sticky host message bubble classes")
    host_text = models.TextField(help_text="Host message text color classes")
    host_message_fade = models.TextField(help_text="Gradient fade for host messages")

    # Pinned Messages
    pinned_message = models.TextField(help_text="Regular pinned message bubble classes")
    sticky_pinned_message = models.TextField(help_text="Sticky pinned message bubble classes")
    pinned_text = models.TextField(help_text="Pinned message text color classes")
    pinned_message_fade = models.TextField(help_text="Gradient fade for pinned messages")

    # Regular Messages
    regular_message = models.TextField(help_text="Regular user message bubble classes")
    regular_text = models.TextField(help_text="Regular message text color classes")

    # My Messages (current user)
    my_message = models.TextField(default='max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-blue-500 shadow-md', help_text="Message bubble classes for current user's own messages")
    my_text = models.TextField(default='text-white', help_text="Text color classes for current user's own messages")

    # Voice Message Player Styling (JSON fields for flexibility)
    voice_message_styles = models.JSONField(default=dict, blank=True, help_text="Styling for other users' voice messages (playButton, playIconColor, waveformActive, waveformInactive)")
    my_voice_message_styles = models.JSONField(default=dict, blank=True, help_text="Styling for current user's voice messages")
    host_voice_message_styles = models.JSONField(default=dict, blank=True, help_text="Styling for host voice messages")
    pinned_voice_message_styles = models.JSONField(default=dict, blank=True, help_text="Styling for pinned voice messages")

    # Filter Buttons
    filter_button_active = models.TextField(help_text="Active filter button style")
    filter_button_inactive = models.TextField(help_text="Inactive filter button style")

    # Input Area
    input_area = models.TextField(help_text="Message input container classes")
    input_field = models.TextField(help_text="Message input field classes")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Chat Theme'
        verbose_name_plural = 'Chat Themes'

    def __str__(self):
        return f"{self.name} ({self.theme_id})"


class ChatRoom(models.Model):
    """Main chat room model"""
    ACCESS_PUBLIC = 'public'
    ACCESS_PRIVATE = 'private'
    ACCESS_CHOICES = [
        (ACCESS_PUBLIC, 'Public'),
        (ACCESS_PRIVATE, 'Private'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=8, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Host/Creator (REQUIRED - must be registered user)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_chats')

    # Access control
    access_mode = models.CharField(max_length=10, choices=ACCESS_CHOICES, default=ACCESS_PUBLIC)
    access_code = models.CharField(max_length=50, blank=True, help_text="Required for private rooms")

    # Media settings
    voice_enabled = models.BooleanField(default=False)
    video_enabled = models.BooleanField(default=False)
    photo_enabled = models.BooleanField(default=True)

    # Theme settings
    theme = models.ForeignKey('ChatTheme', on_delete=models.SET_NULL, null=True, related_name='chat_rooms', help_text="Theme for this chat room")
    theme_locked = models.BooleanField(default=False, help_text="If true, users cannot override the theme")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.code:
            # Generate unique code
            while True:
                code = generate_chat_code()
                if not ChatRoom.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def url(self):
        """Get the chat room URL"""
        return f"/chat/{self.code}"

    @property
    def message_count(self):
        """Get count of non-deleted messages"""
        return self.messages.filter(is_deleted=False).count()


class Message(models.Model):
    """Chat message model"""
    MESSAGE_NORMAL = 'normal'
    MESSAGE_HOST = 'host'
    MESSAGE_SYSTEM = 'system'
    MESSAGE_TYPES = [
        (MESSAGE_NORMAL, 'Normal'),
        (MESSAGE_HOST, 'Host Message'),
        (MESSAGE_SYSTEM, 'System Message'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')

    # User info (username required, user optional for guests)
    username = models.CharField(max_length=100, help_text="Display name in chat")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages', help_text="Optional: registered user")

    # Reply tracking
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies', help_text="Message this is replying to")

    # Message content
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default=MESSAGE_NORMAL)
    content = models.TextField()
    voice_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to voice message audio file")
    voice_duration = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Duration of voice message in seconds")
    voice_waveform = models.JSONField(null=True, blank=True, help_text="Waveform amplitude data as array of floats (0-1)")

    # Pinning
    is_pinned = models.BooleanField(default=False)
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_until = models.DateTimeField(null=True, blank=True)
    pin_amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chat_room', '-created_at']),
            models.Index(fields=['chat_room', 'is_pinned', '-pinned_at']),
        ]

    def __str__(self):
        return f"{self.username}: {self.content[:50]}"

    def pin_message(self, amount_paid, duration_minutes=60):
        """Pin a message for a duration"""
        self.is_pinned = True
        self.pinned_at = timezone.now()
        self.pinned_until = self.pinned_at + timezone.timedelta(minutes=duration_minutes)
        self.pin_amount_paid = amount_paid
        self.save()

    def unpin_message(self):
        """Unpin a message"""
        self.is_pinned = False
        self.pinned_at = None
        self.pinned_until = None
        self.save()


class ChatParticipation(models.Model):
    """Track user participation in chats - username is locked after first join"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='participations')

    # Identity (at least one must be present)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_participations',
        help_text="Logged-in users: primary identifier"
    )
    fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Browser fingerprint - primary for anonymous, stored for logged-in"
    )

    # Username locked for this chat
    username = models.CharField(max_length=100, help_text="Username chosen for this chat (locked)")

    # Theme preference (nullable - if null, use chat room's theme)
    theme = models.ForeignKey(
        'ChatTheme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences',
        help_text="User's preferred theme override (only if chat.theme_locked=False)"
    )

    # IP address tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Last known IP address")

    # Timestamps
    first_joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="For future cleanup of inactive users")

    class Meta:
        ordering = ['-last_seen_at']
        constraints = [
            models.UniqueConstraint(
                fields=['chat_room', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_chat_user'
            ),
            models.UniqueConstraint(
                fields=['chat_room', 'fingerprint'],
                condition=models.Q(user__isnull=True),
                name='unique_chat_fingerprint'
            ),
        ]
        indexes = [
            models.Index(fields=['chat_room', 'user']),
            models.Index(fields=['chat_room', 'fingerprint']),
            models.Index(fields=['chat_room', 'username']),
            models.Index(fields=['-last_seen_at']),
        ]

    def __str__(self):
        identifier = f"User {self.user_id}" if self.user else f"Fingerprint {self.fingerprint[:8]}..."
        return f"{self.username} ({identifier}) in {self.chat_room.code}"


class AnonymousUserFingerprint(models.Model):
    """Track anonymous user browser fingerprints for username persistence"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='fingerprints')

    # Fingerprint from FingerprintJS
    fingerprint = models.CharField(max_length=255, db_index=True, help_text="Browser fingerprint hash")
    username = models.CharField(max_length=100, help_text="Username associated with this fingerprint")

    # IP address tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Last known IP address")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen = models.DateTimeField(auto_now=True, help_text="Last time this fingerprint was used")

    class Meta:
        ordering = ['-last_seen']
        unique_together = ['chat_room', 'fingerprint']
        indexes = [
            models.Index(fields=['fingerprint', 'chat_room']),
            models.Index(fields=['chat_room', '-last_seen']),
        ]

    def __str__(self):
        return f"{self.username} ({self.fingerprint[:8]}...) in {self.chat_room.code}"


class Transaction(models.Model):
    """Track all payments in the system"""
    TRANSACTION_PIN = 'pin'
    TRANSACTION_TIP = 'tip'
    TRANSACTION_TYPES = [
        (TRANSACTION_PIN, 'Message Pin'),
        (TRANSACTION_TIP, 'Tip to Host'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='transactions')

    # Transaction details
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # User info
    username = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, help_text="Optional: registered user")

    # Stripe info
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_charge_id = models.CharField(max_length=255, blank=True)

    # Related objects
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chat_room', '-created_at']),
            models.Index(fields=['stripe_payment_intent_id']),
        ]

    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} by {self.username}"
