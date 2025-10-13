"""
User-to-user blocking views (registered users only)
"""
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import JSONParser, FormParser
from django.shortcuts import get_object_or_404
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import UserBlock
from .utils.performance.cache import UserBlockCache


class UserBlockView(APIView):
    """Block a user site-wide (registered users only)"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def post(self, request):
        """Block a user by username"""
        blocked_username = request.data.get('username', '').strip()

        if not blocked_username:
            raise ValidationError({"username": ["Username is required"]})

        # Prevent self-blocking (case-insensitive)
        if blocked_username.lower() == request.user.reserved_username.lower():
            raise ValidationError({"username": ["You cannot block yourself"]})

        # Validate username exists in system (defense in depth against SQL injection)
        # Check if username exists in ChatParticipation (any chat)
        from .models import ChatParticipation
        username_exists = ChatParticipation.objects.filter(username=blocked_username).exists()

        # Silently succeed if username doesn't exist (prevents user enumeration)
        if not username_exists:
            return Response({
                'success': True,
                'message': f'User {blocked_username} has been blocked',
                'created': False,
                'block_id': None
            }, status=status.HTTP_200_OK)

        # Create or get existing block
        block, created = UserBlock.objects.get_or_create(
            blocker=request.user,
            blocked_username=blocked_username
        )

        # Add to Redis cache (dual-write)
        UserBlockCache.add_blocked_username(request.user.id, blocked_username)

        # Broadcast block update to all of the user's active WebSocket connections
        # This ensures all devices/tabs get updated immediately
        channel_layer = get_channel_layer()
        user_group_name = f'user_{request.user.id}_notifications'

        async_to_sync(channel_layer.group_send)(
            user_group_name,
            {
                'type': 'block_update',
                'action': 'add',
                'blocked_username': blocked_username
            }
        )

        return Response({
            'success': True,
            'message': f'User {blocked_username} has been blocked',
            'created': created,
            'block_id': str(block.id)
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class UserUnblockView(APIView):
    """Unblock a user site-wide (registered users only)"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def post(self, request):
        """Unblock a user by username"""
        blocked_username = request.data.get('username', '').strip()

        if not blocked_username:
            raise ValidationError({"username": ["Username is required"]})

        # Find and delete the block
        try:
            block = UserBlock.objects.get(
                blocker=request.user,
                blocked_username=blocked_username
            )
            block.delete()

            # Remove from Redis cache (dual-write)
            UserBlockCache.remove_blocked_username(request.user.id, blocked_username)

            # Broadcast unblock update to all of the user's active WebSocket connections
            channel_layer = get_channel_layer()
            user_group_name = f'user_{request.user.id}_notifications'

            async_to_sync(channel_layer.group_send)(
                user_group_name,
                {
                    'type': 'block_update',
                    'action': 'remove',
                    'blocked_username': blocked_username
                }
            )

            return Response({
                'success': True,
                'message': f'User {blocked_username} has been unblocked'
            })

        except UserBlock.DoesNotExist:
            raise ValidationError({"username": [f"You haven't blocked {blocked_username}"]})


class UserBlockListView(APIView):
    """Get list of all users blocked by the current user"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List all blocked users"""
        blocks = UserBlock.objects.filter(blocker=request.user).order_by('-created_at')

        blocked_users = [
            {
                'id': str(block.id),
                'username': block.blocked_username,
                'blocked_at': block.created_at.isoformat()
            }
            for block in blocks
        ]

        return Response({
            'blocked_users': blocked_users,
            'count': len(blocked_users)
        })
