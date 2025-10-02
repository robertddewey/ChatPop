from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import ChatRoom, Message, BackRoom, BackRoomMember, BackRoomMessage, AnonymousUserFingerprint
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomUpdateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    BackRoomSerializer, BackRoomMemberSerializer, BackRoomMessageSerializer, BackRoomMessageCreateSerializer
)


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class ChatRoomCreateView(generics.CreateAPIView):
    """Create a new chat room (requires authentication)"""
    serializer_class = ChatRoomCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        chat_room = serializer.save()

        return Response(
            ChatRoomSerializer(chat_room).data,
            status=status.HTTP_201_CREATED
        )


class ChatRoomDetailView(APIView):
    """Get chat room details by code"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Don't expose access_code in response
        serializer = ChatRoomSerializer(chat_room)
        data = serializer.data
        data.pop('access_code', None)

        return Response(data)


class ChatRoomUpdateView(APIView):
    """Update chat room settings (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code)

        # Verify user is the host
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can update chat settings")

        serializer = ChatRoomUpdateSerializer(chat_room, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ChatRoomSerializer(chat_room).data)


class ChatRoomJoinView(APIView):
    """Join a chat room (validates access for private rooms)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        serializer = ChatRoomJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate access code for private rooms
        if chat_room.access_mode == ChatRoom.ACCESS_PRIVATE:
            provided_code = serializer.validated_data.get('access_code', '')
            if provided_code != chat_room.access_code:
                raise PermissionDenied("Invalid access code")

        # Return chat room info and username
        return Response({
            'chat_room': ChatRoomSerializer(chat_room).data,
            'username': serializer.validated_data['username'],
            'message': 'Successfully joined chat room'
        })


class MyChatsView(generics.ListAPIView):
    """List chat rooms hosted by the current user"""
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ChatRoom.objects.filter(host=self.request.user, is_active=True)


class MessageListView(generics.ListAPIView):
    """List messages in a chat room"""
    serializer_class = MessageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        code = self.kwargs['code']
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Get non-deleted messages in chronological order
        return Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        ).order_by('created_at')


class MessageCreateView(generics.CreateAPIView):
    """Send a message to a chat room"""
    serializer_class = MessageCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        serializer = self.get_serializer(
            data=request.data,
            context={'request': request, 'chat_room': chat_room}
        )
        serializer.is_valid(raise_exception=True)
        message = serializer.save()

        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )


class MessagePinView(APIView):
    """Pin a message (requires payment)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        serializer = MessagePinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        duration = serializer.validated_data['duration_minutes']

        # TODO: Process payment with Stripe here
        # For now, just pin the message

        message.pin_message(amount_paid=amount, duration_minutes=duration)

        return Response({
            'message': MessageSerializer(message).data,
            'status': 'Message pinned successfully'
        })


class BackRoomDetailView(APIView):
    """Get back room details for a chat"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        if not hasattr(chat_room, 'back_room'):
            return Response(
                {'detail': 'This chat room does not have a back room'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BackRoomSerializer(chat_room.back_room)
        return Response(serializer.data)


class BackRoomJoinView(APIView):
    """Join a back room (requires payment)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        if not hasattr(chat_room, 'back_room'):
            return Response(
                {'detail': 'This chat room does not have a back room'},
                status=status.HTTP_404_NOT_FOUND
            )

        back_room = chat_room.back_room

        if not back_room.is_active:
            raise ValidationError("Back room is not active")

        if back_room.is_full:
            raise ValidationError("Back room is full")

        username = request.data.get('username')
        if not username:
            raise ValidationError("Username is required")

        # Check if user already joined
        if BackRoomMember.objects.filter(back_room=back_room, username=username, is_active=True).exists():
            raise ValidationError("You have already joined this back room")

        # TODO: Process payment with Stripe here
        # For now, just add the member

        member = BackRoomMember.objects.create(
            back_room=back_room,
            username=username,
            user=request.user if request.user.is_authenticated else None,
            amount_paid=back_room.price_per_seat
        )

        # Update seats occupied
        back_room.seats_occupied += 1
        back_room.save()

        return Response({
            'member': BackRoomMemberSerializer(member).data,
            'message': 'Successfully joined back room'
        }, status=status.HTTP_201_CREATED)


class FingerprintUsernameView(APIView):
    """Get or set username by fingerprint for anonymous users"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        """Get username for a fingerprint if it exists"""
        # Check if fingerprinting is enabled
        if not settings.ANONYMOUS_USER_FINGERPRINT:
            return Response(
                {'detail': 'Fingerprinting is disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        fingerprint = request.query_params.get('fingerprint')

        if not fingerprint:
            raise ValidationError("Fingerprint is required")

        # Look up username by fingerprint
        try:
            fp_record = AnonymousUserFingerprint.objects.get(
                chat_room=chat_room,
                fingerprint=fingerprint
            )
            # Update last_seen timestamp and IP address
            fp_record.ip_address = get_client_ip(request)
            fp_record.save(update_fields=['last_seen', 'ip_address'])

            return Response({
                'username': fp_record.username,
                'found': True
            })
        except AnonymousUserFingerprint.DoesNotExist:
            return Response({
                'username': None,
                'found': False
            })

    def post(self, request, code):
        """Set username for a fingerprint"""
        # Check if fingerprinting is enabled
        if not settings.ANONYMOUS_USER_FINGERPRINT:
            return Response(
                {'detail': 'Fingerprinting is disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        fingerprint = request.data.get('fingerprint')
        username = request.data.get('username')

        if not fingerprint:
            raise ValidationError("Fingerprint is required")
        if not username:
            raise ValidationError("Username is required")

        # Get client IP address
        ip_address = get_client_ip(request)

        # Create or update fingerprint record
        fp_record, created = AnonymousUserFingerprint.objects.update_or_create(
            chat_room=chat_room,
            fingerprint=fingerprint,
            defaults={'username': username, 'ip_address': ip_address}
        )

        return Response({
            'username': fp_record.username,
            'created': created,
            'message': 'Username saved successfully'
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class BackRoomMessagesView(APIView):
    """Get messages for a back room (members and host only)"""

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code)

        try:
            back_room = chat_room.back_room
        except BackRoom.DoesNotExist:
            return Response(
                {'detail': 'Back room does not exist for this chat'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is host or back room member
        is_host = request.user.is_authenticated and request.user == chat_room.host
        is_member = BackRoomMember.objects.filter(
            back_room=back_room,
            is_active=True,
            username=request.data.get('username')  # Get username from request
        ).exists()

        if not (is_host or is_member):
            raise PermissionDenied("Only back room members and the host can view messages")

        messages = BackRoomMessage.objects.filter(
            back_room=back_room,
            is_deleted=False
        ).select_related('user', 'reply_to').order_by('created_at')

        serializer = BackRoomMessageSerializer(messages, many=True)
        return Response(serializer.data)


class BackRoomMessageSendView(APIView):
    """Send a message to the back room (members and host only)"""

    def post(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code)

        try:
            back_room = chat_room.back_room
        except BackRoom.DoesNotExist:
            return Response(
                {'detail': 'Back room does not exist for this chat'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = BackRoomMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']

        # Check if user is host or back room member
        is_host = request.user.is_authenticated and request.user == chat_room.host
        is_member = BackRoomMember.objects.filter(
            back_room=back_room,
            is_active=True,
            username=username
        ).exists()

        if not (is_host or is_member):
            raise PermissionDenied("Only back room members and the host can send messages")

        # Determine message type
        message_type = BackRoomMessage.MESSAGE_HOST if is_host else BackRoomMessage.MESSAGE_NORMAL

        # Create the message
        message = BackRoomMessage.objects.create(
            back_room=back_room,
            username=username,
            user=request.user if request.user.is_authenticated else None,
            content=serializer.validated_data['content'],
            message_type=message_type,
            reply_to=serializer.validated_data.get('reply_to')
        )

        response_serializer = BackRoomMessageSerializer(message)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class BackRoomMembersView(APIView):
    """Get back room members (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code)

        # Verify user is the host
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can view back room members")

        try:
            back_room = chat_room.back_room
        except BackRoom.DoesNotExist:
            return Response(
                {'detail': 'Back room does not exist for this chat'},
                status=status.HTTP_404_NOT_FOUND
            )

        members = BackRoomMember.objects.filter(
            back_room=back_room,
            is_active=True
        ).select_related('user').order_by('-joined_at')

        serializer = BackRoomMemberSerializer(members, many=True)
        return Response(serializer.data)
