from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, UserSubscription


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    subscriber_count = serializers.SerializerMethodField()
    subscription_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'reserved_username', 'first_name', 'last_name',
            'email_notifications', 'push_notifications',
            'subscriber_count', 'subscription_count',
            'created_at', 'last_active'
        ]
        read_only_fields = ['id', 'created_at', 'last_active', 'subscriber_count', 'subscription_count']

    def get_subscriber_count(self, obj):
        return obj.subscribers.count()

    def get_subscription_count(self, obj):
        return obj.subscriptions.count()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'reserved_username', 'first_name', 'last_name']

    def validate_reserved_username(self, value):
        """Validate reserved username format and uniqueness"""
        if value:
            # Check alphanumeric
            if not value.isalnum():
                raise serializers.ValidationError("Reserved username must contain only alphanumeric characters (a-z, A-Z, 0-9)")
            # Check uniqueness (case-insensitive)
            if User.objects.filter(reserved_username__iexact=value).exists():
                raise serializers.ValidationError("This username is already reserved")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            reserved_username=validated_data.get('reserved_username', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError("Invalid email or password")
            if not user.is_active:
                raise serializers.ValidationError("User account is disabled")
            data['user'] = user
        else:
            raise serializers.ValidationError("Must include email and password")

        return data


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for UserSubscription model"""
    subscriber = UserSerializer(read_only=True)
    subscribed_to = UserSerializer(read_only=True)
    subscribed_to_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            'id', 'subscriber', 'subscribed_to', 'subscribed_to_id',
            'notify_on_new_chat', 'notify_on_mentions', 'created_at'
        ]
        read_only_fields = ['id', 'subscriber', 'created_at']

    def validate_subscribed_to_id(self, value):
        """Ensure the user exists"""
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist")
        return value

    def validate(self, data):
        """Prevent self-subscription"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if str(request.user.id) == str(data.get('subscribed_to_id')):
                raise serializers.ValidationError({"subscribed_to_id": "Cannot subscribe to yourself"})
        return data
