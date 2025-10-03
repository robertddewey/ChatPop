from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from accounts.models import User
from .models import ChatRoom, Message, BackRoom, BackRoomMember, BackRoomMessage, AnonymousUserFingerprint, ChatParticipation
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomUpdateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    BackRoomSerializer, BackRoomMemberSerializer, BackRoomMessageSerializer, BackRoomMessageCreateSerializer,
    ChatParticipationSerializer
)
from .security import ChatSessionValidator


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

        username = serializer.validated_data['username']
        fingerprint = request.data.get('fingerprint')
        user_id = str(request.user.id) if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        # SECURITY CHECK 1: Check if username is reserved by another user
        from accounts.models import User
        reserved_user = User.objects.filter(reserved_username__iexact=username).first()
        if reserved_user and request.user.is_authenticated:
            # Only block registered users from using another user's reserved_username
            # Anonymous users CAN use reserved usernames (they coexist with the registered user)
            if reserved_user.id != request.user.id:
                raise ValidationError(f"Username '{username}' is reserved by another user")

        # SECURITY CHECK 2: Check for existing participation (username persistence)
        if request.user.is_authenticated:
            # Check if this user already joined this chat
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user
            ).first()
            if existing_participation:
                # User already joined - they must use the same username
                if existing_participation.username != username:
                    raise ValidationError(
                        f"You have already joined this chat as '{existing_participation.username}'. "
                        f"You cannot change your username in this chat."
                    )
        elif fingerprint:
            # Check if this fingerprint already joined this chat
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True
            ).first()
            if existing_participation:
                # Fingerprint already joined - they must use the same username
                if existing_participation.username != username:
                    raise ValidationError(
                        f"You have already joined this chat as '{existing_participation.username}'. "
                        f"You cannot change your username in this chat."
                    )

        # SECURITY CHECK 3: Check if username is already taken by another participant
        # (excluding the current user/fingerprint who may be rejoining)
        # NOTE: Anonymous and registered users CAN coexist with the same username
        if request.user.is_authenticated:
            # Registered user: only check for other registered users (not anonymous)
            username_taken = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
                user__isnull=False  # Only check registered users
            ).exclude(user=request.user).exists()
        else:
            # Anonymous user: only check for other anonymous users (not registered)
            username_taken = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
                user__isnull=True  # Only check anonymous users
            ).exclude(fingerprint=fingerprint).exists()

        if username_taken:
            raise ValidationError(f"Username '{username}' is already in use in this chat")

        # Create or update ChatParticipation
        if request.user.is_authenticated:
            # Logged-in user - find/create by user_id
            participation, created = ChatParticipation.objects.get_or_create(
                chat_room=chat_room,
                user=request.user,
                defaults={
                    'username': username,
                    'fingerprint': fingerprint,
                    'ip_address': ip_address,
                }
            )
            if not created:
                # Update last_seen and fingerprint (in case they switched devices)
                participation.fingerprint = fingerprint
                participation.ip_address = ip_address
                participation.save()
        elif fingerprint:
            # Anonymous user - find/create by fingerprint
            participation, created = ChatParticipation.objects.get_or_create(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True,
                defaults={
                    'username': username,
                    'ip_address': ip_address,
                }
            )
            if not created:
                # Update last_seen and IP
                participation.ip_address = ip_address
                participation.save()

        # Create JWT session token
        session_token = ChatSessionValidator.create_session_token(
            chat_code=code,
            username=username,
            user_id=user_id
        )

        # Return chat room info, username, and session token
        return Response({
            'chat_room': ChatRoomSerializer(chat_room).data,
            'username': username,
            'session_token': session_token,
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

        # Validate session token
        session_token = request.data.get('session_token')
        username = request.data.get('username')

        if not session_token:
            raise PermissionDenied("Session token is required")

        # Validate the JWT session token
        session_data = ChatSessionValidator.validate_session_token(
            token=session_token,
            chat_code=code,
            username=username
        )

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


class MyParticipationView(APIView):
    """Get current user's participation in a chat"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        fingerprint = request.query_params.get('fingerprint')

        participation = None

        # For logged-in users, find by user_id
        if request.user.is_authenticated:
            participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user,
                is_active=True
            ).first()
        # For anonymous users, find by fingerprint
        elif fingerprint:
            participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True,
                is_active=True
            ).first()

        if participation:
            # Update last_seen timestamp
            participation.save()  # auto_now updates last_seen_at
            return Response({
                'has_joined': True,
                'username': participation.username,
                'first_joined_at': participation.first_joined_at,
                'last_seen_at': participation.last_seen_at
            })

        return Response({
            'has_joined': False
        })


class UsernameValidationView(APIView):
    """Validate username availability for a specific chat room"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        username = request.data.get('username', '').strip()
        fingerprint = request.data.get('fingerprint')

        if not username:
            raise ValidationError("Username is required")

        # Normalize username for comparison (case-insensitive)
        username_lower = username.lower()

        # Check if username is reserved by someone else
        reserved_by_other = False
        reserved_user = User.objects.filter(reserved_username__iexact=username).first()
        if reserved_user:
            # It's reserved - check if it belongs to current user
            if not (request.user.is_authenticated and request.user.id == reserved_user.id):
                reserved_by_other = True

        # Check if username exists in ChatParticipation for this chat
        existing_participation = ChatParticipation.objects.filter(
            chat_room=chat_room,
            username__iexact=username,
            is_active=True
        ).first()

        in_use_in_chat = False
        if existing_participation:
            # Check if it's their own participation
            if request.user.is_authenticated and existing_participation.user_id == request.user.id:
                in_use_in_chat = False  # It's their own username
            elif not request.user.is_authenticated and fingerprint and existing_participation.fingerprint == fingerprint:
                in_use_in_chat = False  # It's their own username (anonymous)
            else:
                in_use_in_chat = True  # Someone else has this username

        # Determine if user has reserved username
        has_reserved = (
            request.user.is_authenticated and
            request.user.reserved_username and
            request.user.reserved_username.lower() == username_lower
        )

        # Determine availability
        available = not reserved_by_other and not in_use_in_chat

        return Response({
            'available': available,
            'username': username,
            'in_use_in_chat': in_use_in_chat,
            'reserved_by_other': reserved_by_other,
            'has_reserved_badge': has_reserved,
            'message': 'Username validated successfully'
        })


class SuggestUsernameView(APIView):
    """
    Suggest a random username for a chat.
    Rate limited to 20 requests per fingerprint/IP per chat per hour.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        from .username_generator import generate_username

        # Get chat room
        chat_room = get_object_or_404(ChatRoom, code=code)

        # Get fingerprint or IP for rate limiting
        fingerprint = request.data.get('fingerprint')
        if not fingerprint:
            # Fallback to IP-based rate limiting
            fingerprint = get_client_ip(request)

        # Rate limiting key (per chat, per fingerprint/IP)
        rate_limit_key = f"username_suggest_limit:{code}:{fingerprint}"

        # Check rate limit
        current_count = cache.get(rate_limit_key, 0)
        if current_count >= 20:
            return Response({
                'error': 'Suggestion limit reached. You can request up to 20 username suggestions per hour for this chat.',
                'remaining': 0
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Generate username
        username = generate_username(code)

        if not username:
            return Response({
                'error': 'Unable to generate a unique username. Please try entering one manually.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Increment rate limit counter (only on success)
        new_count = current_count + 1
        cache.set(rate_limit_key, new_count, 3600)  # 1 hour TTL

        return Response({
            'username': username,
            'remaining': 20 - new_count
        })
