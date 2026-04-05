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
from chats.utils.turnstile import require_turnstile, verify_turnstile_token, get_client_ip
from django.core.cache import cache
from django.conf import settings
from constance import config


class RegisterView(generics.CreateAPIView):
    """Register a new user"""
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @require_turnstile
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

        # Use Django session key for reservation ownership (avoids shared-IP collisions)
        if not request.session.session_key:
            request.session.create()
        identity_key = request.session.session_key

        # Check global username availability (User.reserved_username + ChatParticipation.username + Redis reservations)
        # Pass identity_key to allow same user to re-check their own reservation
        available = is_username_globally_available(username, fingerprint=identity_key)

        # If available, reserve it temporarily in Redis with session ownership
        if available:
            cache_ttl = config.USERNAME_REGISTRATION_HOLD_TTL_MINUTES * 60  # Convert minutes to seconds
            reservation_key = f"username:reserved:{username.lower()}"
            cache.set(reservation_key, identity_key, cache_ttl)

        return Response({
            'available': available,
            'message': 'Username is already taken' if not available else 'Username is available'
        })


class SuggestUsernameView(APIView):
    """Suggest a random username for registration (globally unique)"""
    permission_classes = [permissions.AllowAny]

    @require_turnstile
    def post(self, request):
        # Use Django session key for rate limiting (avoids shared-IP collisions)
        if not request.session.session_key:
            request.session.create()
        identity_key = request.session.session_key

        # Generate username with higher limit for registration (100 vs chat's 10)
        # Registration gets more attempts since it's a one-time action
        username, remaining_attempts = generate_username(identity_key, chat_code=None, max_attempts=100)

        if username:
            return Response({
                'username': username,
                'remaining_attempts': remaining_attempts
            }, status=status.HTTP_200_OK)
        else:
            # Rate limit hit - rotate through previously generated usernames
            generated_key = f"username:generated_for_session:{identity_key}"
            generated_usernames = cache.get(generated_key, set())

            if generated_usernames:
                # Rotate through previously generated usernames
                usernames_list = sorted(list(generated_usernames))  # Consistent order
                rotation_key = f"username:rotation_index:registration:{identity_key}"
                current_index = cache.get(rotation_key, 0)

                # Get next username in rotation
                rotated_username = usernames_list[current_index % len(usernames_list)]

                # Update rotation index for next click
                cache_ttl = int(config.USERNAME_REGISTRATION_HOLD_TTL_MINUTES * 60)
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


class VerifyHumanView(APIView):
    """Verify a user is human via Cloudflare Turnstile. Called once per session."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Already verified this session
        if request.session.get('turnstile_verified'):
            return Response({'verified': True, 'already_verified': True})

        # No-op if Turnstile not configured
        if not settings.CLOUDFLARE_TURNSTILE_SECRET_KEY:
            request.session['turnstile_verified'] = True
            return Response({'verified': True})

        token = request.data.get('turnstile_token', '')
        if not token:
            return Response(
                {'verified': False, 'error': 'Token required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        ip_address = get_client_ip(request)
        if verify_turnstile_token(token, ip_address):
            if not request.session.session_key:
                request.session.create()
            request.session['turnstile_verified'] = True
            return Response({'verified': True})
        else:
            return Response(
                {'verified': False, 'error': 'Verification failed'},
                status=status.HTTP_403_FORBIDDEN
            )
