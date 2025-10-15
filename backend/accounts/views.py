from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import User, UserSubscription
from .serializers import (
    UserSerializer, UserRegistrationSerializer,
    UserLoginSerializer, UserSubscriptionSerializer
)
from chats.utils.username.validators import validate_username, is_username_globally_available
from chats.utils.username.generator import generate_username
from django.core.cache import cache
from constance import config


class RegisterView(generics.CreateAPIView):
    """Register a new user"""
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Create token for the user
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Login a user"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        login(request, user)

        # Get or create token
        token, created = Token.objects.get_or_create(user=user)

        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        })


class LogoutView(APIView):
    """Logout a user"""
    permission_classes = [permissions.AllowAny]  # Allow anyone to logout

    def post(self, request):
        # Delete the user's token if authenticated
        if request.user.is_authenticated and hasattr(request.user, 'auth_token'):
            request.user.auth_token.delete()

        logout(request)
        return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)


class CurrentUserView(APIView):
    """Get current authenticated user"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """Update current user"""
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class UserSubscriptionListCreateView(generics.ListCreateAPIView):
    """List and create user subscriptions"""
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get subscriptions for the current user"""
        return UserSubscription.objects.filter(subscriber=self.request.user)

    def perform_create(self, serializer):
        """Create subscription with current user as subscriber"""
        subscribed_to_id = serializer.validated_data.get('subscribed_to_id')
        subscribed_to = User.objects.get(id=subscribed_to_id)
        serializer.save(subscriber=self.request.user, subscribed_to=subscribed_to)


class UserSubscriptionDestroyView(generics.DestroyAPIView):
    """Unsubscribe from a user"""
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only allow users to delete their own subscriptions"""
        return UserSubscription.objects.filter(subscriber=self.request.user)


class MySubscribersView(generics.ListAPIView):
    """List users who subscribe to me"""
    serializer_class = UserSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get users subscribed to the current user"""
        return UserSubscription.objects.filter(subscribed_to=self.request.user)


class CheckUsernameView(APIView):
    """Check if a username is available"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        username = request.query_params.get('username', '').strip()

        if not username:
            return Response({'available': False, 'message': 'Username is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate username format and profanity
        try:
            username = validate_username(username)
        except DjangoValidationError as e:
            return Response({
                'available': False,
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check global username availability (User.reserved_username + ChatParticipation.username + Redis reservations)
        available = is_username_globally_available(username)

        # If available, reserve it temporarily in Redis to prevent race conditions
        if available:
            cache_ttl = config.USERNAME_VALIDATION_TTL_MINUTES * 60  # Convert minutes to seconds
            reservation_key = f"username:reserved:{username.lower()}"
            cache.set(reservation_key, True, cache_ttl)

        return Response({
            'available': available,
            'message': 'Username is already taken' if not available else 'Username is available'
        })


class SuggestUsernameView(APIView):
    """Suggest a random username for registration (globally unique)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Get fingerprint from request (fallback to IP if not provided)
        fingerprint = request.data.get('fingerprint')
        if not fingerprint:
            # Fallback to IP address for anonymous registration attempts
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                fingerprint = x_forwarded_for.split(',')[0]
            else:
                fingerprint = request.META.get('REMOTE_ADDR', 'unknown')

        # DEBUG: Log fingerprint value
        print(f"[SUGGEST_USERNAME] Fingerprint: {fingerprint}")

        # Generate username using global limit from Constance config
        # Uses same limit as chat joining for consistency
        username, remaining_attempts = generate_username(fingerprint, chat_code=None, max_attempts=None)

        # DEBUG: Log result
        print(f"[SUGGEST_USERNAME] Generated: {username}, Remaining: {remaining_attempts}")

        if username:
            return Response({
                'username': username,
                'remaining_attempts': remaining_attempts
            }, status=status.HTTP_200_OK)
        else:
            # Rate limit hit - rotate through previously generated usernames
            generated_key = f"username:generated_for_fingerprint:{fingerprint}"
            generated_usernames = cache.get(generated_key, set())

            if generated_usernames:
                # Rotate through previously generated usernames
                usernames_list = sorted(list(generated_usernames))  # Consistent order
                rotation_key = f"username:rotation_index:registration:{fingerprint}"
                current_index = cache.get(rotation_key, 0)

                # Get next username in rotation
                rotated_username = usernames_list[current_index % len(usernames_list)]

                # Update rotation index for next click
                cache_ttl = int(config.USERNAME_RESERVATION_TTL_MINUTES * 60)
                cache.set(rotation_key, (current_index + 1) % len(usernames_list), cache_ttl)

                return Response({
                    'username': rotated_username,
                    'remaining_attempts': 0,
                    'is_rotating': True
                }, status=status.HTTP_200_OK)
            else:
                # No usernames generated yet (shouldn't happen, but handle gracefully)
                return Response({
                    'error': 'Failed to generate username. Please try again later.',
                    'remaining_attempts': remaining_attempts
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
