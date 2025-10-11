from rest_framework import status, generics, permissions, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from constance import config
from accounts.models import User
from .models import ChatRoom, Message, AnonymousUserFingerprint, ChatParticipation, ChatTheme, MessageReaction
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomUpdateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    ChatParticipationSerializer, MessageReactionSerializer, MessageReactionCreateSerializer
)
from .security import ChatSessionValidator
from .redis_cache import MessageCache


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
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            print(f"[JOIN ERROR] Validation failed: {type(e).__name__}: {str(e)}")
            print(f"[JOIN ERROR] Serializer errors: {serializer.errors}")
            raise

        # Validate access code for private rooms
        if chat_room.access_mode == ChatRoom.ACCESS_PRIVATE:
            provided_code = serializer.validated_data.get('access_code', '')
            if provided_code != chat_room.access_code:
                raise PermissionDenied("Invalid access code")

        username = serializer.validated_data['username']
        fingerprint = request.data.get('fingerprint')
        user_id = str(request.user.id) if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        # SECURITY CHECK 1: IP-based rate limiting for anonymous users
        MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT = 3
        if not request.user.is_authenticated and ip_address:
            # Check if this fingerprint already has a participation (they're rejoining)
            existing_fingerprint_participation = None
            if fingerprint:
                existing_fingerprint_participation = ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    fingerprint=fingerprint,
                    user__isnull=True,
                    is_active=True
                ).first()

            # Only enforce limit for NEW participations
            if not existing_fingerprint_participation:
                # Count active anonymous participations from this IP in this chat
                anonymous_count = ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    ip_address=ip_address,
                    user__isnull=True,
                    is_active=True
                ).count()

                if anonymous_count >= MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT:
                    raise ValidationError(
                        "Max anonymous usernames. Log in to continue."
                    )

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
                user=request.user,
                is_active=True
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
                user__isnull=True,
                is_active=True
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


class MessageListView(APIView):
    """
    List messages in a chat room.

    Uses hybrid Redis/PostgreSQL strategy:
    - Fetches from Redis cache first (fast, last 500 messages or 24h)
    - Falls back to PostgreSQL if Redis miss or requesting older messages
    - Supports pagination via `before` query param (Unix timestamp)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Query params
        limit = int(request.query_params.get('limit', 50))
        before_timestamp = request.query_params.get('before')  # Unix timestamp for pagination

        # Always fetch from PostgreSQL for REST API
        # Redis is only used for WebSocket broadcast (real-time messaging)
        # This ensures complete message history with no gaps or cache complexity
        messages = self._fetch_from_db(chat_room, limit, before_timestamp, request)

        # Fetch pinned messages from Redis (pinned messages are ephemeral)
        pinned_messages = MessageCache.get_pinned_messages(code)

        return Response({
            'messages': messages,
            'pinned_messages': pinned_messages,
            'source': 'postgresql',  # Always PostgreSQL for REST API
            'count': len(messages),
            'history_limits': {
                'max_days': config.MESSAGE_HISTORY_MAX_DAYS,
                'max_count': config.MESSAGE_HISTORY_MAX_COUNT
            }
        })

    def _fetch_from_db(self, chat_room, limit, before_timestamp=None, request=None):
        """
        Fallback: fetch messages from PostgreSQL.

        Returns: List of message dicts (serialized)
        """
        queryset = Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        ).select_related('user', 'reply_to').prefetch_related('reactions')

        # Filter by timestamp if paginating
        if before_timestamp:
            from datetime import datetime
            before_dt = datetime.fromtimestamp(float(before_timestamp))
            queryset = queryset.filter(created_at__lt=before_dt)

        # Order and limit (newest first to get last N messages)
        messages = queryset.order_by('-created_at')[:limit]

        # Serialize (with username_is_reserved computation)
        serialized = []
        for msg in messages:
            username_is_reserved = MessageCache._compute_username_is_reserved(msg)

            # Convert relative voice_url to absolute URL if present
            voice_url = msg.voice_url
            if voice_url and request:
                voice_url = request.build_absolute_uri(voice_url)

            # Build reply_to_message object if there's a reply
            reply_to_message = None
            if msg.reply_to:
                reply_to_message = {
                    'id': str(msg.reply_to.id),
                    'username': msg.reply_to.username,
                    'content': msg.reply_to.content[:100] if msg.reply_to.content else "",
                    'is_from_host': msg.reply_to.message_type == "host",
                }

            # Compute reaction summary (top 3 reactions with counts)
            from collections import defaultdict
            reactions_list = msg.reactions.all()
            emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0, 'users': []})

            for reaction in reactions_list:
                emoji = reaction.emoji
                emoji_counts[emoji]['emoji'] = emoji
                emoji_counts[emoji]['count'] += 1
                emoji_counts[emoji]['users'].append(reaction.username)

            top_reactions = sorted(emoji_counts.values(), key=lambda x: x['count'], reverse=True)[:3]

            serialized.append({
                'id': str(msg.id),
                'chat_code': msg.chat_room.code,
                'username': msg.username,
                'username_is_reserved': username_is_reserved,
                'user_id': msg.user.id if msg.user else None,
                'message_type': msg.message_type,
                'is_from_host': msg.message_type == "host",
                'content': msg.content,
                'voice_url': voice_url,
                'voice_duration': float(msg.voice_duration) if msg.voice_duration else None,
                'voice_waveform': msg.voice_waveform,
                'reply_to_id': str(msg.reply_to.id) if msg.reply_to else None,
                'reply_to_message': reply_to_message,
                'is_pinned': msg.is_pinned,
                'pinned_at': msg.pinned_at.isoformat() if msg.pinned_at else None,
                'pinned_until': msg.pinned_until.isoformat() if msg.pinned_until else None,
                'pin_amount_paid': str(msg.pin_amount_paid) if msg.pin_amount_paid else "0.00",
                'created_at': msg.created_at.isoformat(),
                'is_deleted': msg.is_deleted,
                'reactions': top_reactions,
            })

        # Reverse to chronological order (oldest first) to match Redis behavior
        serialized.reverse()

        return serialized


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


class MyParticipationView(APIView):
    """Get current user's participation in a chat"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        fingerprint = request.query_params.get('fingerprint')

        participation = None

        # Dual sessions: Priority 1 - logged-in user participation
        if request.user.is_authenticated:
            # Find participation REGARDLESS of is_active status
            # We need to check for blocks even on inactive users
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                user=request.user
            ).first()
            # Don't fallback to anonymous if logged in
        # Priority 2 - Anonymous user (fingerprint-based)
        elif fingerprint:
            # Find participation REGARDLESS of is_active status
            # We need to check for blocks even on inactive users
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True
            ).first()

        if participation:
            # Check if this username is a reserved username
            username_is_reserved = False
            if participation.user and participation.user.reserved_username:
                username_is_reserved = (participation.username.lower() == participation.user.reserved_username.lower())

            # Serialize theme if present (BEFORE save to preserve select_related)
            theme_data = None
            if participation.theme:
                from .serializers import ChatThemeSerializer
                theme_data = ChatThemeSerializer(participation.theme).data

            # Update last_seen timestamp (do this AFTER accessing theme)
            participation.save()  # auto_now updates last_seen_at

            return Response({
                'has_joined': True,
                'username': participation.username,
                'username_is_reserved': username_is_reserved,
                'first_joined_at': participation.first_joined_at,
                'last_seen_at': participation.last_seen_at,
                'theme': theme_data
            })

        return Response({
            'has_joined': False
        })


class UpdateMyThemeView(APIView):
    """Update user's theme preference for a chat"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Check if theme is locked
        if chat_room.theme_locked:
            return Response(
                {'detail': 'Theme is locked for this chat'},
                status=status.HTTP_403_FORBIDDEN
            )

        theme_id = request.data.get('theme_id')
        fingerprint = request.data.get('fingerprint')

        # Get the theme
        theme = None
        if theme_id:
            try:
                theme = ChatTheme.objects.get(theme_id=theme_id)
            except ChatTheme.DoesNotExist:
                return Response(
                    {'detail': 'Theme not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Find the user's participation
        participation = None
        if request.user.is_authenticated:
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                user=request.user,
                is_active=True
            ).first()
        elif fingerprint:
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True,
                is_active=True
            ).first()

        if not participation:
            return Response(
                {'detail': 'You must join the chat before setting a theme'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update theme
        participation.theme = theme
        participation.save()

        # Serialize theme if present
        theme_data = None
        if participation.theme:
            from .serializers import ChatThemeSerializer
            theme_data = ChatThemeSerializer(participation.theme).data

        return Response({
            'success': True,
            'theme': theme_data
        })


class CheckRateLimitView(APIView):
    """Check if user can join chat (rate limit check for anonymous users)"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        fingerprint = request.query_params.get('fingerprint')

        # Logged-in users are always allowed
        if request.user.is_authenticated:
            return Response({
                'can_join': True,
                'is_rate_limited': False
            })

        # Anonymous users: check rate limit
        ip_address = get_client_ip(request)
        MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT = 3

        if not ip_address:
            # No IP detected, allow join
            return Response({
                'can_join': True,
                'is_rate_limited': False
            })

        # Check if this fingerprint already has a participation (they're rejoining)
        existing_fingerprint_participation = None
        if fingerprint:
            existing_fingerprint_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True,
                is_active=True
            ).first()

        # If they already have a participation, they can rejoin
        if existing_fingerprint_participation:
            return Response({
                'can_join': True,
                'is_rate_limited': False,
                'existing_username': existing_fingerprint_participation.username
            })

        # Count active anonymous participations from this IP in this chat
        anonymous_count = ChatParticipation.objects.filter(
            chat_room=chat_room,
            ip_address=ip_address,
            user__isnull=True,
            is_active=True
        ).count()

        is_rate_limited = anonymous_count >= MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT

        return Response({
            'can_join': not is_rate_limited,
            'is_rate_limited': is_rate_limited,
            'anonymous_count': anonymous_count,
            'max_allowed': MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT
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


class MessageReactionToggleView(APIView):
    """
    Toggle a reaction on a message (add or remove).
    If user already reacted, remove the reaction.
    If user hasn't reacted, add the new reaction (replacing any existing reaction).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Validate session token
        session_token = request.data.get('session_token')
        username = request.data.get('username')
        fingerprint = request.data.get('fingerprint')

        print(f"[REACTION DEBUG] session_token present: {bool(session_token)}")
        print(f"[REACTION DEBUG] username: {username}")
        print(f"[REACTION DEBUG] fingerprint: {fingerprint}")

        if not session_token:
            print("[REACTION DEBUG] No session token provided")
            raise PermissionDenied("Session token is required")

        # Validate the JWT session token
        try:
            session_data = ChatSessionValidator.validate_session_token(
                token=session_token,
                chat_code=code,
                username=username
            )
            print(f"[REACTION DEBUG] Session validation successful: {session_data}")
        except Exception as e:
            print(f"[REACTION DEBUG] Session validation failed: {type(e).__name__}: {str(e)}")
            raise

        # Validate emoji
        serializer = MessageReactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emoji = serializer.validated_data['emoji']

        # Determine user identity
        user = request.user if request.user.is_authenticated else None
        fingerprint_value = fingerprint if not user else None

        # Check if user already has ANY reaction on this message
        if user:
            existing_reaction = MessageReaction.objects.filter(
                message=message,
                user=user
            ).first()
        else:
            existing_reaction = MessageReaction.objects.filter(
                message=message,
                fingerprint=fingerprint_value
            ).first()

        # If clicking the same emoji, remove it (toggle off)
        if existing_reaction and existing_reaction.emoji == emoji:
            existing_reaction.delete()
            action = 'removed'
            reaction_data = None
        # If user has a different reaction, update it
        elif existing_reaction:
            existing_reaction.emoji = emoji
            existing_reaction.save()
            action = 'updated'
            reaction_data = MessageReactionSerializer(existing_reaction).data
        else:
            # Create new reaction
            existing_reaction = MessageReaction.objects.create(
                message=message,
                emoji=emoji,
                user=user,
                fingerprint=fingerprint_value,
                username=username
            )
            action = 'added'
            reaction_data = MessageReactionSerializer(existing_reaction).data

        # Convert UUIDs to strings for WebSocket serialization
        if reaction_data:
            reaction_data['id'] = str(reaction_data['id'])
            reaction_data['message'] = str(reaction_data['message'])
            if reaction_data.get('user'):
                reaction_data['user'] = str(reaction_data['user'])

        # Broadcast reaction update via WebSocket
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{code}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_reaction',
                'reaction_data': {
                    'type': 'reaction',
                    'action': action,
                    'message_id': str(message_id),
                    'emoji': emoji,
                    'username': username,
                    'reaction': reaction_data
                }
            }
        )

        return Response({
            'action': action,
            'message': f'Reaction {action}',
            'emoji': emoji,
            'reaction': reaction_data
        }, status=status.HTTP_201_CREATED if action == 'added' else status.HTTP_200_OK)


class MessageReactionsListView(APIView):
    """Get all reactions for a specific message"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id):
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        reactions = MessageReaction.objects.filter(message=message).order_by('-created_at')
        serializer = MessageReactionSerializer(reactions, many=True)

        # Group reactions by emoji with counts
        from collections import defaultdict
        emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0, 'users': []})

        for reaction in reactions:
            emoji = reaction.emoji
            emoji_counts[emoji]['emoji'] = emoji
            emoji_counts[emoji]['count'] += 1
            emoji_counts[emoji]['users'].append(reaction.username)

        # Sort by count (descending) and take top 3
        top_reactions = sorted(emoji_counts.values(), key=lambda x: x['count'], reverse=True)[:3]

        return Response({
            'reactions': serializer.data,
            'summary': top_reactions,
            'total_count': len(reactions)
        })


class VoiceUploadView(APIView):
    """
    Upload a voice message.
    Available to all chat participants if voice_enabled=True on the chat room.
    Saves to local storage or S3 based on configuration.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, code):
        from .storage import save_voice_message, get_voice_message_url
        from .security import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied

        # Get chat room
        chat_room = get_object_or_404(ChatRoom, code=code)

        # Check if voice messages are enabled for this chat
        if not chat_room.voice_enabled:
            return Response({
                'error': 'Voice messages are not enabled for this chat room'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate session token (works for both authenticated and anonymous users)
        session_token = request.data.get('session_token') or request.headers.get('X-Chat-Session-Token')

        if not session_token:
            return Response({
                'error': 'Session token required to upload voice messages'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
        except PermissionDenied:
            return Response({
                'error': 'Invalid session token'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get uploaded file
        voice_file = request.FILES.get('voice_message')
        if not voice_file:
            return Response({
                'error': 'No voice message file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 10MB)
        if voice_file.size > 10 * 1024 * 1024:
            return Response({
                'error': 'Voice message too large (max 10MB)'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type (audio files only)
        allowed_types = ['audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/ogg', 'audio/wav']
        if voice_file.content_type not in allowed_types:
            return Response({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            import logging
            logger = logging.getLogger(__name__)

            # Log incoming file info
            logger.info(f"[VoiceUpload] Received file with content_type: {voice_file.content_type}, size: {voice_file.size} bytes")

            # Track the actual content type for file extension
            actual_content_type = voice_file.content_type

            # iOS Safari workaround: Transcode WebM to M4A for compatibility
            # iOS Safari MediaRecorder produces WebM/Opus that iOS cannot play
            if voice_file.content_type == 'audio/webm':
                from .audio_utils import transcode_webm_to_m4a
                logger.info(f"[VoiceUpload] ✅ TRANSCODING WebM to M4A for iOS compatibility...")
                voice_file = transcode_webm_to_m4a(voice_file)
                transcoded_size = len(voice_file.read())
                logger.info(f"[VoiceUpload] ✅ TRANSCODING COMPLETE, new file size: {transcoded_size} bytes")
                voice_file.seek(0)  # Reset file pointer after read
                actual_content_type = 'audio/mp4'  # Transcoded file is M4A/AAC
            else:
                logger.info(f"[VoiceUpload] ⏭️ Skipping transcoding (content_type is {voice_file.content_type}, not audio/webm)")

            # Save file to storage with correct extension based on content type
            storage_path, storage_type = save_voice_message(voice_file, content_type=actual_content_type)
            logger.info(f"[VoiceUpload] Saved to storage: {storage_path} (content_type: {actual_content_type})")

            # Get proxy URL for accessing the file (relative path)
            # The URL route is: path('media/<path:storage_path>', VoiceStreamView.as_view())
            # So we just need the storage_path part: voice_messages/filename.m4a
            voice_url = get_voice_message_url(storage_path)

            return Response({
                'voice_url': voice_url,
                'storage_path': storage_path,
                'storage_type': storage_type
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Failed to upload voice message: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VoiceStreamView(APIView):
    """
    Stream/download a voice message through Django proxy.
    Provides access control - only chat participants can access voice messages.
    """
    permission_classes = [permissions.AllowAny]

    def options(self, request, storage_path):
        """Handle CORS preflight requests"""
        from django.http import HttpResponse

        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'X-Chat-Session-Token, Content-Type'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        return response

    def get(self, request, storage_path):
        from django.http import HttpResponse, Http404, JsonResponse
        from .storage import MediaStorage
        from .security import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied
        import os
        import re
        import logging

        logger = logging.getLogger(__name__)

        # Log incoming request
        logger.info(f"🎵 [VoiceStream] Incoming request for: {storage_path}")
        logger.info(f"🎵 [VoiceStream] Range header: {request.META.get('HTTP_RANGE', 'NONE')}")
        logger.info(f"🎵 [VoiceStream] User-Agent: {request.META.get('HTTP_USER_AGENT', 'NONE')[:100]}")

        # Extract chat code and validate session
        # Storage path format: voice_messages/<uuid>.webm
        # We need to validate that user has access to the chat

        # Get session token from query params or headers
        session_token = request.GET.get('session_token') or request.headers.get('X-Chat-Session-Token')

        if not session_token:
            logger.warning(f"🎵 [VoiceStream] No session token provided for: {storage_path}")
            return JsonResponse({
                'error': 'Session token required to access voice messages'
            }, status=401)

        # Validate session (this will raise PermissionDenied if invalid)
        try:
            session_data = ChatSessionValidator.validate_session_token(session_token)
            chat_code = session_data.get('chat_code')
            logger.info(f"🎵 [VoiceStream] Session validated for chat: {chat_code}")

            # Get chat room to verify it exists
            chat_room = get_object_or_404(ChatRoom, code=chat_code)

            # Check if file exists in storage
            if not MediaStorage.file_exists(storage_path):
                logger.error(f"🎵 [VoiceStream] File not found: {storage_path}")
                raise Http404("Voice message not found")

            # Get file from storage
            file_obj = MediaStorage.get_file(storage_path)
            if not file_obj:
                logger.error(f"🎵 [VoiceStream] Failed to get file object: {storage_path}")
                raise Http404("Voice message not found")

            # Determine content type from file extension
            content_type = 'audio/webm'  # default
            if storage_path.endswith('.m4a') or storage_path.endswith('.mp4'):
                content_type = 'audio/mp4'
            elif storage_path.endswith('.mp3') or storage_path.endswith('.mpeg'):
                content_type = 'audio/mpeg'
            elif storage_path.endswith('.ogg'):
                content_type = 'audio/ogg'
            elif storage_path.endswith('.wav'):
                content_type = 'audio/wav'

            # Get file size
            file_obj.seek(0, os.SEEK_END)
            file_size = file_obj.tell()
            file_obj.seek(0)
            logger.info(f"🎵 [VoiceStream] File size: {file_size} bytes, Content-Type: {content_type}")

            # Parse Range header for iOS Safari compatibility
            range_header = request.META.get('HTTP_RANGE', '')

            if range_header:
                logger.info(f"🎵 [VoiceStream] Processing Range Request: {range_header}")
                # Parse range header (format: "bytes=start-end")
                range_match = re.match(r'bytes=(\d+)-(\d*)', range_header)
                if range_match:
                    start = int(range_match.group(1))
                    end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
                    logger.info(f"🎵 [VoiceStream] Range: bytes {start}-{end}/{file_size}")

                    # Validate range
                    if start >= file_size or end >= file_size or start > end:
                        logger.error(f"🎵 [VoiceStream] Invalid range: {start}-{end} for file size {file_size}")
                        response = HttpResponse(status=416)  # Range Not Satisfiable
                        response['Content-Range'] = f'bytes */{file_size}'
                        return response

                    # Read the requested range
                    file_obj.seek(start)
                    chunk_size = end - start + 1
                    content = file_obj.read(chunk_size)
                    logger.info(f"🎵 [VoiceStream] Returning 206 Partial Content: {chunk_size} bytes")

                    # Return HTTP 206 Partial Content
                    response = HttpResponse(content, content_type=content_type, status=206)
                    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
                    response['Content-Length'] = str(chunk_size)
                else:
                    logger.warning(f"🎵 [VoiceStream] Invalid range format: {range_header}, returning full file")
                    # Invalid range format, return full file
                    content = file_obj.read()
                    response = HttpResponse(content, content_type=content_type)
                    response['Content-Length'] = str(file_size)
            else:
                logger.info(f"🎵 [VoiceStream] No Range header, returning full file ({file_size} bytes)")
                # No range header, return full file
                content = file_obj.read()
                response = HttpResponse(content, content_type=content_type)
                response['Content-Length'] = str(file_size)

            # Common headers for all responses
            response['Content-Disposition'] = f'inline; filename="{storage_path.split("/")[-1]}"'
            response['Cache-Control'] = 'private, max-age=3600'  # Cache for 1 hour
            response['Accept-Ranges'] = 'bytes'

            # Add CORS headers for audio element playback
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
            response['Access-Control-Allow-Headers'] = 'X-Chat-Session-Token, Content-Type, Range'
            response['Access-Control-Expose-Headers'] = 'Content-Range, Accept-Ranges, Content-Length'

            logger.info(f"🎵 [VoiceStream] Success! Returning {response.status_code} response")
            return response

        except PermissionDenied:
            logger.error(f"🎵 [VoiceStream] Permission denied for: {storage_path}")
            return JsonResponse({
                'error': 'Invalid session token'
            }, status=401)
        except Http404:
            logger.error(f"🎵 [VoiceStream] File not found (404): {storage_path}")
            return JsonResponse({
                'error': 'Voice message not found'
            }, status=404)
        except Exception as e:
            logger.error(f"🎵 [VoiceStream] Unexpected error for {storage_path}: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'error': f'Failed to stream voice message: {str(e)}'
            }, status=500)


class BlockUserView(APIView):
    """Block a user from the chat (host only)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code):
        from .blocking_utils import block_participation
        from .security import ChatSessionValidator
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"[BLOCK] Starting block request for chat {code}")
        logger.info(f"[BLOCK] Request data: {request.data}")

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)
        logger.info(f"[BLOCK] Chat room found: {chat_room.id}, host: {chat_room.host}")

        # Validate session token
        session_token = request.data.get('session_token')
        logger.info(f"[BLOCK] Session token present: {bool(session_token)}")
        if not session_token:
            logger.error("[BLOCK] Session token is required")
            raise ValidationError("Session token is required")

        try:
            session_data = ChatSessionValidator.validate_session_token(
                token=session_token,
                chat_code=code
            )
            logger.info(f"[BLOCK] Session validated: {session_data}")
        except Exception as e:
            logger.error(f"[BLOCK] Session validation failed: {str(e)}")
            raise PermissionDenied(f"Invalid session: {str(e)}")

        # Get the host's participation (who is doing the blocking)
        host_participation = None
        if session_data.get('user_id'):
            # Logged-in user
            logger.info(f"[BLOCK] Looking for logged-in host participation: user_id={session_data['user_id']}")
            host_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user_id=session_data['user_id']
            ).first()
        else:
            # Anonymous user (by fingerprint)
            logger.info(f"[BLOCK] Looking for anonymous host participation: fingerprint={session_data.get('fingerprint')}")
            host_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=session_data.get('fingerprint'),
                user__isnull=True
            ).first()

        logger.info(f"[BLOCK] Host participation found: {host_participation}")
        if not host_participation:
            logger.error("[BLOCK] No host participation found")
            raise ValidationError("You must be in the chat to block users")

        # Verify user is the host
        logger.info(f"[BLOCK] Checking host: participation.user={host_participation.user}, chat_room.host={chat_room.host}")
        if host_participation.user != chat_room.host:
            logger.error(f"[BLOCK] User is not the host: {host_participation.user} != {chat_room.host}")
            raise PermissionDenied("Only the host can block users")

        # Get participation to block (by ID or username)
        participation_id = request.data.get('participation_id')
        username = request.data.get('username')
        logger.info(f"[BLOCK] Looking for participation to block: id={participation_id}, username={username}")

        if not participation_id and not username:
            logger.error("[BLOCK] Neither participation_id nor username provided")
            raise ValidationError("Either participation_id or username is required")

        # Get the participation to block
        # NOTE: We do NOT filter by is_active=True because we want to block users
        # even if they've left the chat (to prevent them from rejoining)
        if participation_id:
            logger.info(f"[BLOCK] Searching by participation_id: {participation_id}")
            participation = get_object_or_404(
                ChatParticipation,
                id=participation_id,
                chat_room=chat_room
            )
        else:
            # Find by username (case-insensitive)
            logger.info(f"[BLOCK] Searching by username: {username}")
            participation = get_object_or_404(
                ChatParticipation,
                username__iexact=username,
                chat_room=chat_room
            )

        logger.info(f"[BLOCK] Participation to block found: {participation}")

        try:
            # Block the user across all identifiers
            logger.info(f"[BLOCK] Calling block_participation with chat_room={chat_room.id}, participation={participation.id}, blocked_by={host_participation.id}")
            blocks_created = block_participation(
                chat_room=chat_room,
                participation=participation,
                blocked_by=host_participation
            )
            logger.info(f"[BLOCK] block_participation succeeded, created {len(blocks_created)} blocks")

            # NOTE: We do NOT set is_active=False here because:
            # 1. ChatBlock table is the source of truth for blocking
            # 2. We want MyParticipationView to find the participation and return is_blocked=true
            # 3. This allows the frontend to show a proper "You've been blocked" message
            # The user will be evicted via WebSocket event below

            # Send WebSocket event to evict the blocked user
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            room_group_name = f'chat_{chat_room.code}'

            # Send eviction event to the chat room
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'user_blocked',
                    'username': participation.username,
                    'message': 'You have been removed from this chat by the host.',
                }
            )

            return Response({
                'success': True,
                'message': f'User {participation.username} has been blocked',
                'blocks_created': len(blocks_created),
                'blocked_identifiers': [
                    'username' if participation.username else None,
                    'fingerprint' if participation.fingerprint else None,
                    'user_account' if participation.user else None
                ]
            })

        except ValueError as e:
            logger.error(f"[BLOCK] ValueError: {str(e)}")
            raise ValidationError(str(e))
        except Exception as e:
            logger.error(f"[BLOCK] Unexpected error: {type(e).__name__}: {str(e)}")
            logger.exception("[BLOCK] Full traceback:")
            raise ValidationError(f"Failed to block user: {str(e)}")


class UnblockUserView(APIView):
    """Unblock a user from the chat (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code):
        from .blocking_utils import unblock_participation

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Verify user is the host
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can unblock users")

        # Get participation to unblock (by ID or username)
        participation_id = request.data.get('participation_id')
        username = request.data.get('username')

        if not participation_id and not username:
            raise ValidationError("Either participation_id or username is required")

        # Get the participation to unblock (allow inactive participations)
        if participation_id:
            participation = get_object_or_404(
                ChatParticipation,
                id=participation_id,
                chat_room=chat_room
            )
        else:
            # Find by username (case-insensitive)
            participation = get_object_or_404(
                ChatParticipation,
                username__iexact=username,
                chat_room=chat_room
            )

        # Unblock the user
        count = unblock_participation(chat_room, participation)

        # Reactivate the participation if it was deactivated
        if not participation.is_active:
            participation.is_active = True
            participation.save()

        return Response({
            'success': True,
            'message': f'User {participation.username} has been unblocked',
            'blocks_removed': count
        })


class BlockedUsersListView(APIView):
    """Get list of blocked users in a chat (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code):
        from .blocking_utils import get_blocked_users

        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Verify user is the host
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can view blocked users")

        # Get all blocked users
        blocked_users = get_blocked_users(chat_room)

        return Response({
            'blocked_users': blocked_users,
            'count': len(blocked_users)
        })
