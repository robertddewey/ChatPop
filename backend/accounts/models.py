from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
import uuid


class UserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model with email authentication.
    All registered users are equal - host/guest is determined at chat room level.
    Must be registered to create chat rooms.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove username, use email instead
    username = None
    email = models.EmailField(unique=True)

    # Reserved username (optional, globally unique, alphanumeric only)
    reserved_username_validator = RegexValidator(
        regex=r'^[a-zA-Z0-9]+$',
        message='Reserved username must contain only alphanumeric characters (a-z, A-Z, 0-9)',
        code='invalid_reserved_username'
    )
    reserved_username = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        unique=True,
        validators=[reserved_username_validator],
        help_text='Optional reserved username (alphanumeric only, no spaces or special characters)'
    )

    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_active = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return self.email

    def get_display_name(self):
        """Return reserved username or email prefix if not set"""
        return self.reserved_username or self.email.split('@')[0]

    def save(self, *args, **kwargs):
        """Normalize reserved_username to lowercase for case-insensitive uniqueness"""
        if self.reserved_username:
            self.reserved_username = self.reserved_username.lower()
        super().save(*args, **kwargs)


class UserSubscription(models.Model):
    """
    Users can subscribe to other users to get notifications when they create chats.
    Any registered user can subscribe to any other registered user.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The user who is subscribing
    subscriber = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')

    # The user being subscribed to
    subscribed_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscribers')

    # Notification preferences for this subscription
    notify_on_new_chat = models.BooleanField(default=True, help_text="Notify when this user creates a new chat")
    notify_on_mentions = models.BooleanField(default=True, help_text="Notify when mentioned in their chats")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['subscriber', 'subscribed_to']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscriber', 'subscribed_to']),
        ]

    def __str__(self):
        return f"{self.subscriber.email} subscribes to {self.subscribed_to.email}"

    def clean(self):
        """Prevent users from subscribing to themselves"""
        from django.core.exceptions import ValidationError
        if self.subscriber == self.subscribed_to:
            raise ValidationError("Users cannot subscribe to themselves")
