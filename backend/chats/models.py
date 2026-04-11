from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from pgvector.django import VectorField
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

    # Spotlight Messages (host-assigned featured users)
    spotlight_message = models.TextField(
        default='max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl p-3 bg-[#2a1f05] border border-[#3d2e0a]',
        help_text="Spotlighted user message bubble classes"
    )
    spotlight_text = models.TextField(
        default='text-white',
        help_text="Spotlighted user message text color classes"
    )
    spotlight_icon_color = models.CharField(
        max_length=100,
        default='text-yellow-400',
        help_text="Tailwind classes for spotlight star icon and pill colors"
    )

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

    # Icon Colors
    pin_icon_color = models.CharField(max_length=100, default='text-yellow-400', help_text="Tailwind classes for pin icon color")
    crown_icon_color = models.CharField(max_length=100, default='text-yellow-400', help_text="Tailwind classes for crown (host) icon color")
    badge_icon_color = models.CharField(max_length=100, default='text-blue-400', help_text="Tailwind classes for verified badge icon color")
    reply_icon_color = models.CharField(max_length=100, default='text-cyan-400', help_text="Tailwind classes for reply icon color")
    highlight_icon_color = models.CharField(max_length=100, default='text-blue-400', help_text="Tailwind classes for highlight icon color")

    # Reaction Highlight (when user has reacted)
    reaction_highlight_bg = models.CharField(max_length=100, default='bg-zinc-700', help_text="Background classes for highlighted reaction pill")
    reaction_highlight_border = models.CharField(max_length=100, default='border border-zinc-500', help_text="Border classes for highlighted reaction pill")
    reaction_highlight_text = models.CharField(max_length=100, default='text-zinc-200', help_text="Text color classes for highlighted reaction count")

    # Avatar Styling
    avatar_size = models.CharField(max_length=50, null=True, blank=True, help_text="Tailwind size classes for avatar (e.g., 'w-10 h-10'). Null = use default")
    avatar_border = models.CharField(max_length=100, null=True, blank=True, help_text="Optional border/ring classes (e.g., 'ring-2 ring-zinc-700')")
    avatar_spacing = models.CharField(max_length=50, default='mr-3', help_text="Spacing between avatar and message content")

    # Username Styling (per message type)
    my_username = models.CharField(max_length=200, default='text-xs font-semibold text-white', help_text="Tailwind classes for current user's username")
    regular_username = models.CharField(max_length=200, default='text-xs font-semibold text-white', help_text="Tailwind classes for other users' usernames")
    host_username = models.CharField(max_length=200, default='text-sm font-semibold', help_text="Tailwind classes for host username (used with host_text for color)")
    my_host_username = models.CharField(max_length=200, default='text-sm font-semibold text-red-500', help_text="Tailwind classes for host's own username when viewing their own messages")
    pinned_username = models.CharField(max_length=200, default='text-sm font-semibold', help_text="Tailwind classes for pinned message username (used with pinned_text for color)")
    sticky_host_username = models.CharField(max_length=200, default='text-sm font-semibold text-white', help_text="Tailwind classes for host username in sticky area")
    sticky_pinned_username = models.CharField(max_length=200, default='text-sm font-semibold text-white', help_text="Tailwind classes for pinned message username in sticky area")

    # Timestamp Styling (per message type)
    my_timestamp = models.CharField(max_length=200, default='text-xs text-white opacity-60', help_text="Tailwind classes for current user's message timestamp")
    regular_timestamp = models.CharField(max_length=200, default='text-xs text-white opacity-60', help_text="Tailwind classes for other users' message timestamp")
    host_timestamp = models.CharField(max_length=200, default='text-xs opacity-60', help_text="Tailwind classes for host message timestamp (used with host_text for color)")
    pinned_timestamp = models.CharField(max_length=200, default='text-xs opacity-60', help_text="Tailwind classes for pinned message timestamp (used with pinned_text for color)")

    # Reply Preview Styling (shown above input area when replying to a message)
    reply_preview_container = models.CharField(max_length=300, default='flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700', help_text="Tailwind classes for reply preview container")
    reply_preview_icon = models.CharField(max_length=200, default='w-4 h-4 flex-shrink-0 text-blue-500', help_text="Tailwind classes for reply preview icon")
    reply_preview_username = models.CharField(max_length=200, default='text-xs font-semibold text-gray-700 dark:text-gray-300', help_text="Tailwind classes for reply preview username")
    reply_preview_content = models.CharField(max_length=200, default='text-xs text-gray-600 dark:text-gray-400 truncate', help_text="Tailwind classes for reply preview message content")
    reply_preview_close_button = models.CharField(max_length=200, default='p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded', help_text="Tailwind classes for reply preview close button")
    reply_preview_close_icon = models.CharField(max_length=200, default='w-4 h-4 text-gray-500', help_text="Tailwind classes for reply preview close icon (X)")

    # Component Style Overrides (JSON fields for grouped styles)
    modal_styles = models.JSONField(default=dict, blank=True, help_text="Styles for long-press modal and overlays")
    emoji_picker_styles = models.JSONField(default=dict, blank=True, help_text="Styles for emoji reaction picker")
    gift_styles = models.JSONField(default=dict, blank=True, help_text="Styles for gift message cards")
    input_styles = models.JSONField(default=dict, blank=True, help_text="Styles for message input components")
    video_player_styles = models.JSONField(default=dict, blank=True, help_text="Styles for video player overlay")
    ui_styles = models.JSONField(default=dict, blank=True, help_text="Styles for misc UI elements")

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

    SOURCE_MANUAL = 'manual'
    SOURCE_AI = 'ai'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'User-created (manual)'),
        (SOURCE_AI, 'AI-generated (collaborative discovery)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=100,
        db_index=True,
        help_text="URL-safe room identifier (e.g., 'bar-room', 'roberts-storm-chasing-room')"
    )
    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default=SOURCE_MANUAL,
        help_text="How this room was created: manual (user) or ai (photo analysis)"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Embedding for suggestion normalization (collaborative discovery)
    # - Generated from room name and description for better semantic matching
    # - Model: text-embedding-3-small (1536 dimensions)
    # - Use: K-NN matching during photo upload to normalize generic suggestions
    # - Only for AI-generated rooms (source='ai')
    name_embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
        help_text="Embedding of room name and description for suggestion normalization (text-embedding-3-small, 1536d)"
    )

    # Host/Creator (REQUIRED - must be registered user)
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hosted_chats')

    # Access control
    access_mode = models.CharField(max_length=10, choices=ACCESS_CHOICES, default=ACCESS_PUBLIC)
    access_code = models.CharField(max_length=50, blank=True, help_text="Required for private rooms")

    # Media settings
    voice_enabled = models.BooleanField(default=False)
    video_enabled = models.BooleanField(default=False)
    photo_enabled = models.BooleanField(default=True)

    # Broadcast sticky
    broadcast_message = models.ForeignKey(
        'Message',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='broadcast_in',
        help_text="Host-curated broadcast message shown in the top sticky slot. "
                  "Only one per chat. Set by the host via toggle."
    )

    # Theme settings
    theme = models.ForeignKey('ChatTheme', on_delete=models.SET_NULL, null=True, related_name='chat_rooms', help_text="Theme for this chat room")
    theme_locked = models.BooleanField(default=False, help_text="If true, users cannot override the theme")

    # Location-based discovery
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate for location-based discovery"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate for location-based discovery"
    )
    discovery_radius_miles = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum distance in miles for this chat to be discoverable"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'source']),
            models.Index(fields=['host', 'code']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            # Manual rooms: code must be unique per user (allows robert/bar-room and alice/bar-room)
            models.UniqueConstraint(
                fields=['host', 'code'],
                condition=models.Q(source='manual'),
                name='unique_manual_room_per_user'
            ),
            # AI rooms: code must be globally unique (only one /chat/discover/bar-room)
            models.UniqueConstraint(
                fields=['code'],
                condition=models.Q(source='ai'),
                name='unique_ai_room_global'
            ),
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
        """
        Get the chat room URL.

        All rooms use: /chat/{host_username}/{code}
        - Manual rooms: host is the creating user
        - AI rooms: host is the "discover" system user
        """
        # Use host's reserved_username or email prefix
        username = self.host.reserved_username if self.host.reserved_username else self.host.email.split('@')[0]
        return f"/chat/{username}/{self.code}"

    @property
    def message_count(self):
        """Get count of non-deleted messages"""
        return self.messages.filter(is_deleted=False).count()


class Message(models.Model):
    """Chat message model"""
    MESSAGE_NORMAL = 'normal'
    MESSAGE_SYSTEM = 'system'
    MESSAGE_GIFT = 'gift'
    MESSAGE_TYPES = [
        (MESSAGE_NORMAL, 'Normal'),
        (MESSAGE_SYSTEM, 'System Message'),
        (MESSAGE_GIFT, 'Gift Message'),
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
    is_from_host = models.BooleanField(default=False, help_text="Whether this message was sent by the chat room host (using registered identity)")
    content = models.TextField()
    voice_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to voice message audio file")
    voice_duration = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Duration of voice message in seconds")
    voice_waveform = models.JSONField(null=True, blank=True, help_text="Waveform amplitude data as array of floats (0-1)")

    # Photo message
    photo_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to photo file")
    photo_width = models.IntegerField(null=True, blank=True, help_text="Photo width in pixels")
    photo_height = models.IntegerField(null=True, blank=True, help_text="Photo height in pixels")

    # Video message
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to video file")
    video_duration = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Duration of video in seconds")
    video_thumbnail_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL to video thumbnail image")
    video_width = models.IntegerField(null=True, blank=True, help_text="Video width in pixels")
    video_height = models.IntegerField(null=True, blank=True, help_text="Video height in pixels")

    # Pinning
    is_pinned = models.BooleanField(default=False)
    pinned_at = models.DateTimeField(null=True, blank=True)
    sticky_until = models.DateTimeField(null=True, blank=True)
    pin_amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Current session amount - resets when pin expires or is outbid
    current_pin_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Gift tracking
    gift_recipient = models.CharField(max_length=100, blank=True, null=True, help_text="Recipient username for gift messages (denormalized for filter indexing)")
    is_gift_acknowledged = models.BooleanField(default=False)

    # Highlight (host-only, appears in all users' Focus view)
    is_highlight = models.BooleanField(default=False)
    highlighted_at = models.DateTimeField(null=True, blank=True, help_text="When the host highlighted this message. Used for ordering the highlight sticky slot.")

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

    def pin_message(self, amount_paid_cents, duration_minutes=None):
        """
        Pin a message.

        Args:
            amount_paid_cents: Amount paid in cents to pin this message.
                              This determines priority in the sticky section.
            duration_minutes: Optional duration override. If not provided,
                             uses PIN_NEW_PIN_DURATION_MINUTES from constance.
        """
        from decimal import Decimal
        from .utils.pin_tiers import get_new_pin_duration_minutes

        if duration_minutes is None:
            duration_minutes = get_new_pin_duration_minutes()

        amount_dollars = Decimal(amount_paid_cents) / 100

        self.is_pinned = True
        self.pinned_at = timezone.now()
        self.sticky_until = self.pinned_at + timezone.timedelta(minutes=duration_minutes)
        # Current session amount (for bidding)
        self.current_pin_amount = amount_dollars
        # Lifetime total (for analytics)
        self.pin_amount_paid = (self.pin_amount_paid or Decimal('0')) + amount_dollars
        self.save()

    def unpin_message(self):
        """Unpin a message"""
        self.is_pinned = False
        self.pinned_at = None
        self.sticky_until = None
        self.current_pin_amount = Decimal('0')
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
        help_text="Browser fingerprint - stored for ban enforcement only"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django session key - primary identifier for anonymous users"
    )

    # Username locked for this chat
    username = models.CharField(max_length=100, help_text="Username chosen for this chat (locked)")

    # Avatar (stored in S3/local storage, per-chat for anonymous users)
    avatar_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text='URL to avatar image for this chat participation (stored in S3 or local storage)'
    )

    # Theme preference (nullable - if null, use chat room's theme)
    theme = models.ForeignKey(
        'ChatTheme',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='user_preferences',
        help_text="User's preferred theme override (only if chat.theme_locked=False)"
    )

    # Feature intro tracking (for anonymous users — per-chat since no global user record)
    seen_intros = models.JSONField(default=dict, blank=True, help_text="Feature intros dismissed by anonymous user in this chat")

    # Host-assigned spotlight status (per-participation, not per-account)
    is_spotlight = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Host-assigned spotlight status. Spotlighted users get a star icon, "
                  "'Spotlight' pill, and appear in the Focus room filter. Per-participation — "
                  "different identities of the same user are independently spotlighted."
    )

    # IP address tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Last known IP address")

    # True if this participation is a registered user's claimed anonymous
    # identity (user is set, but the username is NOT their reserved_username).
    # A registered user may have at most one non-anonymous participation per
    # chat (their primary registered identity) plus N anonymous identities.
    is_anonymous_identity = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True if this participation is a registered user's claimed "
            "anonymous identity (user is set but username is not their "
            "reserved_username)"
        ),
    )

    # Timestamps
    first_joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, help_text="For future cleanup of inactive users")

    class Meta:
        ordering = ['-last_seen_at']
        constraints = [
            # Only ONE registered (non-anonymous) participation per user per chat.
            models.UniqueConstraint(
                fields=['chat_room', 'user'],
                condition=models.Q(user__isnull=False, is_anonymous_identity=False),
                name='unique_chat_user_registered'
            ),
            # A user may have multiple anonymous identities per chat, but each
            # (user, username) pair must be unique to prevent duplicates.
            models.UniqueConstraint(
                fields=['chat_room', 'user', 'username'],
                condition=models.Q(user__isnull=False),
                name='unique_chat_user_username'
            ),
            # Note: unique_chat_fingerprint removed — fingerprints can collide across
            # different sessions, and session_key is now the primary anonymous identifier
            models.UniqueConstraint(
                fields=['chat_room', 'session_key'],
                condition=models.Q(session_key__isnull=False, user__isnull=True),
                name='unique_chat_session_key'
            ),
        ]
        indexes = [
            models.Index(fields=['chat_room', 'user']),
            models.Index(fields=['chat_room', 'fingerprint']),
            models.Index(fields=['chat_room', 'session_key']),
            models.Index(fields=['chat_room', 'username']),
            models.Index(fields=['-last_seen_at']),
        ]

    def __str__(self):
        identifier = f"User {self.user_id}" if self.user else f"Session {self.session_key[:8]}..." if self.session_key else f"Fingerprint {self.fingerprint[:8]}..."
        return f"{self.username} ({identifier}) in {self.chat_room.code}"


class MessageReaction(models.Model):
    """Track emoji reactions to messages"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')

    # Emoji character (e.g., "👍", "❤️", "😂")
    emoji = models.CharField(max_length=10, help_text="Emoji character")

    # User identity (one must be present)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='message_reactions',
        help_text="Logged-in user who reacted"
    )
    fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Anonymous user fingerprint (legacy, ban enforcement)"
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django session key - primary identifier for anonymous reactions"
    )

    # Username at time of reaction (for display)
    username = models.CharField(max_length=100, help_text="Username at time of reaction")

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message', 'emoji']),
            models.Index(fields=['message', 'user', 'emoji']),
            models.Index(fields=['message', 'fingerprint', 'emoji']),
            models.Index(fields=['message', 'session_key', 'emoji']),
        ]
        constraints = [
            # One reaction per emoji per logged-in user per message
            models.UniqueConstraint(
                fields=['message', 'user', 'emoji'],
                condition=models.Q(user__isnull=False),
                name='unique_message_user_emoji_reaction'
            ),
            # One reaction per emoji per anonymous user per message (session-based)
            models.UniqueConstraint(
                fields=['message', 'session_key', 'emoji'],
                condition=models.Q(session_key__isnull=False, user__isnull=True),
                name='unique_message_session_emoji_reaction'
            ),
        ]

    def __str__(self):
        identifier = f"User {self.user_id}" if self.user else f"Session {self.session_key[:8]}..." if self.session_key else f"Fingerprint {self.fingerprint[:8]}..."
        return f"{self.emoji} on message {self.message_id} by {identifier}"


class ChatBlock(models.Model):
    """
    Block users from accessing a specific chat.

    Multiple identifiers can be set in a single ban record for comprehensive blocking:
    - blocked_username: Blocks anyone using that username
    - blocked_fingerprint: Blocks that specific device/browser
    - blocked_user: Blocks that registered user account
    - blocked_ip_address: Tracks IP (for future IP-based blocking)

    Ban checking uses OR logic - if ANY identifier matches, user is blocked.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who is being blocked (at least one must be set)
    blocked_username = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        help_text="Case-insensitive username block"
    )
    blocked_fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Browser fingerprint block"
    )
    blocked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='chat_blocks',
        help_text="Registered user account block"
    )
    blocked_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address block"
    )
    blocked_session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        help_text="Django session key block"
    )

    # Ban tier determines how the block is enforced
    BAN_TIER_SESSION = 'session'
    BAN_TIER_FINGERPRINT_IP = 'fingerprint_ip'
    BAN_TIER_IP = 'ip'
    BAN_TIER_CHOICES = [
        (BAN_TIER_SESSION, 'Session Ban'),
        (BAN_TIER_FINGERPRINT_IP, 'Device + IP Ban'),
        (BAN_TIER_IP, 'Total IP Ban'),
    ]
    ban_tier = models.CharField(
        max_length=20,
        choices=BAN_TIER_CHOICES,
        default=BAN_TIER_SESSION,
        help_text="Ban enforcement level: session (clearable), fingerprint+IP (device), or IP (network)"
    )

    # Who created the block
    blocked_by = models.ForeignKey(
        'ChatParticipation',
        on_delete=models.CASCADE,
        related_name='blocks_created',
        help_text="Who created the block (usually host)"
    )

    # Which chat this block applies to
    chat_room = models.ForeignKey(
        'ChatRoom',
        on_delete=models.CASCADE,
        related_name='blocks'
    )

    # Metadata
    blocked_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, help_text="Optional note for host")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional: for timed blocks"
    )

    class Meta:
        ordering = ['-blocked_at']
        indexes = [
            models.Index(fields=['chat_room', 'blocked_username']),
            models.Index(fields=['chat_room', 'blocked_fingerprint']),
            models.Index(fields=['chat_room', 'blocked_user']),
            models.Index(fields=['chat_room', 'blocked_session_key']),
            models.Index(fields=['chat_room', 'ban_tier']),
            models.Index(fields=['expires_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['chat_room', 'blocked_username'],
                condition=models.Q(blocked_username__isnull=False),
                name='unique_chat_username_block'
            ),
            # No fingerprint constraint — multiple banned users can share the same fingerprint
            models.UniqueConstraint(
                fields=['chat_room', 'blocked_user'],
                condition=models.Q(blocked_user__isnull=False),
                name='unique_chat_user_block'
            ),
        ]

    def __str__(self):
        identifiers = []
        if self.blocked_username:
            identifiers.append(f"username:{self.blocked_username}")
        if self.blocked_fingerprint:
            identifiers.append(f"fingerprint:{self.blocked_fingerprint[:8]}")
        if self.blocked_user:
            identifiers.append(f"user:{self.blocked_user_id}")
        identifier_str = ", ".join(identifiers) if identifiers else "unknown"
        return f"Block in {self.chat_room.code}: {identifier_str}"


class UserBlock(models.Model):
    """User-to-user blocking (registered users only)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who is blocking (must be registered user)
    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocking',
        help_text="Registered user who is blocking"
    )

    # Who is being blocked (username-based, works for both registered and anonymous)
    blocked_username = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Username being blocked (case-sensitive)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['blocker', 'blocked_username']
        indexes = [
            models.Index(fields=['blocker', 'blocked_username']),
        ]

    def __str__(self):
        return f"{self.blocker.username} blocks {self.blocked_username}"


class SiteBan(models.Model):
    """
    Site-wide ban for users, preventing access to ALL chats.

    Staff/admins can ban by user account, IP address, or fingerprint.
    At least one identifier must be set. Multiple can be set for comprehensive blocking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who is being banned (at least one must be set)
    banned_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='site_bans',
        help_text="Registered user account ban"
    )
    banned_ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IP address ban"
    )
    banned_fingerprint = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        help_text="Browser fingerprint ban"
    )
    banned_session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text="Django session key ban"
    )

    # Who created the ban (must be staff)
    banned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='site_bans_issued',
        help_text="Staff member who issued the ban"
    )

    # Metadata
    reason = models.TextField(help_text="Reason for the ban")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the ban expires (null = permanent)"
    )
    is_active = models.BooleanField(default=True, help_text="Whether ban is currently active")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Site Ban'
        verbose_name_plural = 'Site Bans'
        indexes = [
            models.Index(fields=['banned_user']),
            models.Index(fields=['banned_ip_address']),
            models.Index(fields=['banned_fingerprint']),
            models.Index(fields=['banned_session_key']),
            models.Index(fields=['is_active', 'expires_at']),
        ]

    def __str__(self):
        identifiers = []
        if self.banned_user:
            identifiers.append(f"user:{self.banned_user.username}")
        if self.banned_ip_address:
            identifiers.append(f"ip:{self.banned_ip_address}")
        if self.banned_fingerprint:
            identifiers.append(f"fingerprint:{self.banned_fingerprint[:8]}...")
        identifier_str = ", ".join(identifiers) if identifiers else "unknown"
        return f"Site Ban: {identifier_str}"

    def is_expired(self):
        """Check if the ban has expired."""
        if not self.expires_at:
            return False  # Permanent ban
        return timezone.now() > self.expires_at

    @classmethod
    def is_banned(cls, user=None, ip_address=None, fingerprint=None, session_key=None, chat_room=None):
        """
        Check if any of the provided identifiers are banned.
        Host of the chat_room (if provided) is always exempt.

        Returns the active SiteBan if found, None otherwise.
        """
        from django.db.models import Q

        # Host exemption: if user is the host of the chat, they're never banned
        if chat_room and user and hasattr(chat_room, 'host') and chat_room.host == user:
            return None

        if not any([user, ip_address, fingerprint, session_key]):
            return None

        # Build query for active, non-expired bans
        query = Q(is_active=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))

        # Add identifier conditions (OR logic)
        identifier_query = Q()
        if user:
            identifier_query |= Q(banned_user=user)
        if ip_address:
            identifier_query |= Q(banned_ip_address=ip_address)
        if fingerprint:
            identifier_query |= Q(banned_fingerprint=fingerprint)
        if session_key:
            identifier_query |= Q(banned_session_key=session_key)

        return cls.objects.filter(query & identifier_query).first()


class Transaction(models.Model):
    """Track all payments in the system"""
    TRANSACTION_PIN = 'pin'
    TRANSACTION_TIP = 'tip'
    TRANSACTION_GIFT = 'gift'
    TRANSACTION_TYPES = [
        (TRANSACTION_PIN, 'Message Pin'),
        (TRANSACTION_TIP, 'Tip to Host'),
        (TRANSACTION_GIFT, 'Gift'),
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


class GiftCatalogItem(models.Model):
    """Catalog of available gifts (loaded from fixtures)"""
    CATEGORY_FOOD = 'food'
    CATEGORY_FUN = 'fun'
    CATEGORY_LOVE = 'love'
    CATEGORY_ANIMALS = 'animals'
    CATEGORY_PREMIUM = 'premium'
    CATEGORY_CHOICES = [
        (CATEGORY_FOOD, 'Food & Drink'),
        (CATEGORY_FUN, 'Fun'),
        (CATEGORY_LOVE, 'Love'),
        (CATEGORY_ANIMALS, 'Animals'),
        (CATEGORY_PREMIUM, 'Premium'),
    ]

    gift_id = models.CharField(max_length=50, unique=True, db_index=True, help_text="Stable identifier e.g. 'gift_coffee'")
    emoji = models.CharField(max_length=10, help_text="Emoji character")
    name = models.CharField(max_length=100, help_text="Display name")
    price_cents = models.PositiveIntegerField(help_text="Price in cents")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True, help_text="Soft-disable without removing")
    sort_order = models.PositiveIntegerField(default=0, help_text="Display ordering within category")

    class Meta:
        ordering = ['category', 'sort_order', 'price_cents']
        verbose_name = 'Gift Catalog Item'
        verbose_name_plural = 'Gift Catalog Items'

    def __str__(self):
        return f"{self.emoji} {self.name} (${self.price_cents / 100:.2f})"


class Gift(models.Model):
    """Individual gift sent between users"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='gifts')
    gift_catalog_item = models.ForeignKey(GiftCatalogItem, on_delete=models.PROTECT, related_name='sent_gifts')

    # Denormalized snapshot at send time
    gift_id = models.CharField(max_length=50, help_text="Gift catalog ID at send time")
    emoji = models.CharField(max_length=10)
    name = models.CharField(max_length=100)
    price_cents = models.PositiveIntegerField()

    # Sender
    sender_username = models.CharField(max_length=100)
    sender_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='gifts_sent')

    # Recipient
    recipient_username = models.CharField(max_length=100)
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='gifts_received')

    # Related message
    message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name='gift')

    # Acknowledgment
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_username', 'chat_room', 'is_acknowledged']),
            models.Index(fields=['chat_room', '-created_at']),
        ]

    def __str__(self):
        return f"{self.emoji} {self.name} from {self.sender_username} to {self.recipient_username}"
