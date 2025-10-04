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
from chats.validators import validate_username
from chats.username_generator import generate_username


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

        # Check if username exists (case-insensitive)
        exists = User.objects.filter(reserved_username__iexact=username).exists()

        return Response({
            'available': not exists,
            'message': 'Username is already taken' if exists else 'Username is available'
        })


class SuggestUsernameView(APIView):
    """Suggest a random username for registration"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Generate username without chat code (for registration)
        username = generate_username(chat_code=None)

        if username:
            return Response({
                'username': username
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to generate username. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
