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


class BackRoom(models.Model):
    """Paid back room for exclusive access to host"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat_room = models.OneToOneField(ChatRoom, on_delete=models.CASCADE, related_name='back_room')

    # Pricing and capacity
    price_per_seat = models.DecimalField(max_digits=10, decimal_places=2)
    max_seats = models.PositiveIntegerField()
    seats_occupied = models.PositiveIntegerField(default=0)

    # Settings
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"BackRoom for {self.chat_room.name}"

    @property
    def seats_available(self):
        return self.max_seats - self.seats_occupied

    @property
    def is_full(self):
        return self.seats_occupied >= self.max_seats


class BackRoomMember(models.Model):
    """Track members who have paid for back room access"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    back_room = models.ForeignKey(BackRoom, on_delete=models.CASCADE, related_name='members')

    username = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, help_text="Optional: registered user")

    # Payment info
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_payment_id = models.CharField(max_length=255, blank=True)

    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-joined_at']
        unique_together = ['back_room', 'username']

    def __str__(self):
        return f"{self.username} in {self.back_room}"


class Transaction(models.Model):
    """Track all payments in the system"""
    TRANSACTION_PIN = 'pin'
    TRANSACTION_BACKROOM = 'backroom'
    TRANSACTION_TIP = 'tip'
    TRANSACTION_TYPES = [
        (TRANSACTION_PIN, 'Message Pin'),
        (TRANSACTION_BACKROOM, 'Back Room Access'),
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
    back_room_member = models.ForeignKey(BackRoomMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')

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
