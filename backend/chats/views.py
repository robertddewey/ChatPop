from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from .models import ChatRoom, Message, BackRoom, BackRoomMember
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    BackRoomSerializer, BackRoomMemberSerializer
)


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

        # Get non-deleted messages
        # Order by: host messages first, then pinned messages, then by creation time (oldest first)
        from django.db.models import Case, When, Value, IntegerField

        return Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        ).annotate(
            priority=Case(
                When(message_type=Message.MESSAGE_HOST, then=Value(0)),
                When(is_pinned=True, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        ).order_by('priority', 'created_at')


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
