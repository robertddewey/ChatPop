from rest_framework import serializers
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import ChatRoom, Message, Transaction, ChatParticipation, ChatTheme
from .validators import validate_username
from accounts.serializers import UserSerializer


class ChatThemeSerializer(serializers.ModelSerializer):
    """Serializer for ChatTheme model"""
    theme_color = serializers.SerializerMethodField()

    class Meta:
        model = ChatTheme
        fields = [
            'theme_id', 'name', 'is_dark_mode', 'theme_color',
            'container', 'header', 'header_title', 'header_title_fade', 'header_subtitle',
            'sticky_section', 'messages_area', 'messages_area_container', 'messages_area_bg',
            'host_message', 'sticky_host_message', 'host_text', 'host_message_fade',
            'pinned_message', 'sticky_pinned_message', 'pinned_text', 'pinned_message_fade',
            'regular_message', 'regular_text',
            'my_message', 'my_text',
            'voice_message_styles', 'my_voice_message_styles', 'host_voice_message_styles', 'pinned_voice_message_styles',
            'filter_button_active', 'filter_button_inactive',
            'input_area', 'input_field'
        ]

    def get_theme_color(self, obj):
        """Return theme_color as an object with light and dark values"""
        return {
            'light': obj.theme_color_light,
            'dark': obj.theme_color_dark
        }


class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer for ChatRoom model"""
    host = UserSerializer(read_only=True)
    url = serializers.CharField(read_only=True)
    message_count = serializers.SerializerMethodField()
    theme = ChatThemeSerializer(read_only=True)

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'code', 'name', 'description', 'host', 'url',
            'access_mode', 'voice_enabled', 'video_enabled', 'photo_enabled',
            'theme', 'theme_locked',
            'message_count', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'code', 'host', 'url', 'created_at']

    def get_message_count(self, obj):
        return obj.messages.filter(is_deleted=False).count()


class ChatRoomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a chat room"""
    theme_id = serializers.CharField(write_only=True, required=False, default='dark-mode')

    class Meta:
        model = ChatRoom
        fields = [
            'name', 'description', 'access_mode', 'access_code',
            'voice_enabled', 'video_enabled', 'photo_enabled',
            'theme_id', 'theme_locked'
        ]

    def validate_access_code(self, value):
        """Ensure access code is provided for private rooms"""
        access_mode = self.initial_data.get('access_mode')
        if access_mode == ChatRoom.ACCESS_PRIVATE and not value:
            raise serializers.ValidationError("Access code is required for private rooms")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['host'] = request.user

        # Get theme by theme_id
        theme_id = validated_data.pop('theme_id', 'dark-mode')
        try:
            theme = ChatTheme.objects.get(theme_id=theme_id)
            validated_data['theme'] = theme
        except ChatTheme.DoesNotExist:
            # Fallback to dark-mode if theme not found
            validated_data['theme'] = ChatTheme.objects.get(theme_id='dark-mode')

        return super().create(validated_data)


class ChatRoomUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating chat room settings (host only)"""
    class Meta:
        model = ChatRoom
        fields = [
            'name', 'description', 'access_mode', 'access_code',
            'voice_enabled', 'video_enabled', 'photo_enabled',
            'default_theme', 'theme_locked', 'is_active'
        ]

    def validate_access_code(self, value):
        """Ensure access code is provided for private rooms"""
        access_mode = self.initial_data.get('access_mode', self.instance.access_mode if self.instance else None)
        if access_mode == ChatRoom.ACCESS_PRIVATE and not value:
            raise serializers.ValidationError("Access code is required for private rooms")
        return value

    def validate(self, attrs):
        """Additional validation for room updates"""
        # If changing to private mode, ensure access code is set
        if 'access_mode' in attrs and attrs['access_mode'] == ChatRoom.ACCESS_PRIVATE:
            access_code = attrs.get('access_code', self.instance.access_code if self.instance else None)
            if not access_code:
                raise serializers.ValidationError({
                    'access_code': 'Access code is required for private rooms'
                })
        return attrs


class ChatRoomJoinSerializer(serializers.Serializer):
    """Serializer for joining a chat room"""
    username = serializers.CharField(max_length=15, required=True)
    access_code = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_username(self, value):
        """Validate username format using shared validator"""
        try:
            value = validate_username(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(str(e))
        return value


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for Message model"""
    user = UserSerializer(read_only=True)
    is_from_host = serializers.SerializerMethodField()
    username_is_reserved = serializers.SerializerMethodField()
    time_until_unpin = serializers.SerializerMethodField()
    reply_to_message = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'chat_room', 'username', 'user', 'message_type', 'content', 'voice_url',
            'voice_duration', 'voice_waveform',
            'reply_to', 'reply_to_message',
            'is_pinned', 'pinned_at', 'pinned_until', 'pin_amount_paid',
            'is_from_host', 'username_is_reserved', 'time_until_unpin', 'created_at', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'user', 'message_type', 'voice_url', 'voice_duration', 'voice_waveform',
            'is_pinned', 'pinned_at', 'pinned_until', 'pin_amount_paid', 'created_at', 'is_deleted'
        ]

    def get_is_from_host(self, obj):
        return obj.user == obj.chat_room.host if obj.user else False

    def get_username_is_reserved(self, obj):
        """Check if username matches user's reserved_username"""
        return (
            obj.user and
            obj.user.reserved_username and
            obj.username.lower() == obj.user.reserved_username.lower()
        )

    def get_time_until_unpin(self, obj):
        if obj.is_pinned and obj.pinned_until:
            remaining = (obj.pinned_until - timezone.now()).total_seconds()
            return max(0, int(remaining))
        return None

    def get_reply_to_message(self, obj):
        """Return basic info about the message being replied to"""
        if obj.reply_to:
            return {
                'id': str(obj.reply_to.id),
                'username': obj.reply_to.username,
                'content': obj.reply_to.content[:100],  # Truncate for preview
                'is_from_host': obj.reply_to.user == obj.reply_to.chat_room.host if obj.reply_to.user else False
            }
        return None


class MessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a message"""
    reply_to = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = Message
        fields = ['username', 'content', 'reply_to']

    def validate_content(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 5000:
            raise serializers.ValidationError("Message content too long (max 5000 characters)")
        return value.strip()

    def validate_reply_to(self, value):
        """Validate that reply_to message exists and is in the same chat room"""
        if value:
            chat_room = self.context.get('chat_room')
            try:
                message = Message.objects.get(id=value, chat_room=chat_room, is_deleted=False)
                return message
            except Message.DoesNotExist:
                raise serializers.ValidationError("Reply target message not found")
        return None

    def create(self, validated_data):
        request = self.context.get('request')
        chat_room = self.context.get('chat_room')

        validated_data['chat_room'] = chat_room

        # Link to user if authenticated
        if request and request.user.is_authenticated:
            validated_data['user'] = request.user
            # If user is host, mark as host message
            if request.user == chat_room.host:
                validated_data['message_type'] = Message.MESSAGE_HOST

        return super().create(validated_data)


class MessagePinSerializer(serializers.Serializer):
    """Serializer for pinning a message"""
    duration_minutes = serializers.IntegerField(min_value=1, max_value=1440, default=60)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0.50)


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction model"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'chat_room', 'transaction_type', 'amount', 'status',
            'username', 'user', 'stripe_payment_intent_id',
            'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'chat_room', 'status', 'user',
            'stripe_payment_intent_id', 'created_at', 'completed_at'
        ]


class ChatParticipationSerializer(serializers.ModelSerializer):
    """Serializer for ChatParticipation"""
    user = UserSerializer(read_only=True)
    theme = ChatThemeSerializer(read_only=True)

    class Meta:
        model = ChatParticipation
        fields = [
            'id', 'chat_room', 'user', 'fingerprint', 'username', 'theme',
            'first_joined_at', 'last_seen_at', 'is_active'
        ]
        read_only_fields = ['id', 'chat_room', 'user', 'first_joined_at', 'last_seen_at']
