from rest_framework import serializers
from django.utils import timezone
from .models import ChatRoom, Message, BackRoom, BackRoomMember, BackRoomMessage, Transaction, ChatParticipation
from accounts.serializers import UserSerializer


class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer for ChatRoom model"""
    host = UserSerializer(read_only=True)
    url = serializers.CharField(read_only=True)
    message_count = serializers.SerializerMethodField()
    has_back_room = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'code', 'name', 'description', 'host', 'url',
            'access_mode', 'voice_enabled', 'video_enabled', 'photo_enabled',
            'default_theme', 'theme_locked',
            'message_count', 'has_back_room', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'code', 'host', 'url', 'created_at']

    def get_message_count(self, obj):
        return obj.messages.filter(is_deleted=False).count()

    def get_has_back_room(self, obj):
        return hasattr(obj, 'back_room')


class ChatRoomCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a chat room"""
    class Meta:
        model = ChatRoom
        fields = [
            'name', 'description', 'access_mode', 'access_code',
            'voice_enabled', 'video_enabled', 'photo_enabled',
            'default_theme', 'theme_locked'
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
    username = serializers.CharField(max_length=100, required=True)
    access_code = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_username(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Username cannot be empty")
        return value.strip()


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
            'id', 'chat_room', 'username', 'user', 'message_type', 'content',
            'reply_to', 'reply_to_message',
            'is_pinned', 'pinned_at', 'pinned_until', 'pin_amount_paid',
            'is_from_host', 'username_is_reserved', 'time_until_unpin', 'created_at', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'user', 'message_type', 'is_pinned', 'pinned_at',
            'pinned_until', 'pin_amount_paid', 'created_at', 'is_deleted'
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


class BackRoomSerializer(serializers.ModelSerializer):
    """Serializer for BackRoom model"""
    seats_available = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)

    class Meta:
        model = BackRoom
        fields = [
            'id', 'chat_room', 'price_per_seat', 'max_seats',
            'seats_occupied', 'seats_available', 'is_full',
            'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'chat_room', 'seats_occupied', 'created_at']


class BackRoomMemberSerializer(serializers.ModelSerializer):
    """Serializer for BackRoomMember model"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = BackRoomMember
        fields = [
            'id', 'back_room', 'username', 'user', 'amount_paid',
            'joined_at', 'is_active'
        ]
        read_only_fields = ['id', 'back_room', 'user', 'amount_paid', 'joined_at']


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


class BackRoomMessageSerializer(serializers.ModelSerializer):
    """Serializer for BackRoomMessage with host detection and reply info"""
    user = UserSerializer(read_only=True)
    is_from_host = serializers.SerializerMethodField()
    username_is_reserved = serializers.SerializerMethodField()
    reply_to_message = serializers.SerializerMethodField()

    class Meta:
        model = BackRoomMessage
        fields = [
            'id', 'back_room', 'username', 'user', 'message_type', 'content',
            'reply_to', 'reply_to_message', 'is_from_host', 'username_is_reserved', 'created_at', 'is_deleted'
        ]
        read_only_fields = [
            'id', 'user', 'message_type', 'created_at', 'is_deleted'
        ]

    def get_is_from_host(self, obj):
        return obj.user == obj.back_room.chat_room.host if obj.user else False

    def get_username_is_reserved(self, obj):
        """Check if username matches user's reserved_username"""
        return (
            obj.user and
            obj.user.reserved_username and
            obj.username.lower() == obj.user.reserved_username.lower()
        )

    def get_reply_to_message(self, obj):
        """Return basic info about the message being replied to"""
        if obj.reply_to:
            return {
                'id': str(obj.reply_to.id),
                'username': obj.reply_to.username,
                'content': obj.reply_to.content[:100],  # Truncate for preview
                'is_from_host': obj.reply_to.user == obj.reply_to.back_room.chat_room.host if obj.reply_to.user else False
            }
        return None


class BackRoomMessageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a back room message"""
    reply_to = serializers.UUIDField(required=False, allow_null=True)

    class Meta:
        model = BackRoomMessage
        fields = ['username', 'content', 'reply_to']

    def validate_content(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 5000:
            raise serializers.ValidationError("Message content too long (max 5000 characters)")
        return value.strip()

    def validate_reply_to(self, value):
        """Validate that reply_to message exists and is in the same back room"""
        if value:
            try:
                message = BackRoomMessage.objects.get(id=value)
                # Check that reply is in same back room (will be validated in view)
                return message
            except BackRoomMessage.DoesNotExist:
                raise serializers.ValidationError("Reply message not found")
        return None


class BackRoomMemberSerializer(serializers.ModelSerializer):
    """Serializer for BackRoomMember"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = BackRoomMember
        fields = [
            'id', 'username', 'user', 'amount_paid',
            'joined_at', 'is_active'
        ]
        read_only_fields = ['id', 'user', 'amount_paid', 'joined_at']


class ChatParticipationSerializer(serializers.ModelSerializer):
    """Serializer for ChatParticipation"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = ChatParticipation
        fields = [
            'id', 'chat_room', 'user', 'fingerprint', 'username',
            'first_joined_at', 'last_seen_at', 'is_active'
        ]
        read_only_fields = ['id', 'chat_room', 'user', 'first_joined_at', 'last_seen_at']
