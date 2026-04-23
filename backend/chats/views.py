from decimal import Decimal
from rest_framework import status, generics, permissions, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from constance import config
from accounts.models import User
from .models import ChatRoom, Message, ChatParticipation, ChatTheme, MessageReaction, ChatBlock
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomUpdateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    ChatParticipationSerializer, MessageReactionSerializer, MessageReactionCreateSerializer,
    GiftCatalogItemSerializer, SendGiftSerializer, AcknowledgeGiftSerializer
)
from .utils.security.auth import ChatSessionValidator
from .utils.turnstile import require_turnstile
from .utils.performance.cache import MessageCache
from .utils.performance.monitoring import monitor
from .utils.pin_tiers import (
    get_valid_pin_tiers, get_tiers_for_frontend, get_next_tier_above,
    get_tier_duration_minutes, get_new_pin_duration_minutes, validate_pin_amount, is_valid_tier
)
from chatpop.utils.media import save_voice_message, get_voice_message_url, transcode_webm_to_m4a
import time


def get_client_ip(request):
    """Get the client's IP address from the request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_chat_room_by_url(code, username=None):
    """
    Get chat room by code and username.

    All rooms use the same URL pattern: /{username}/{code}/
    - Manual rooms: host is the creating user
    - AI/Discover rooms: host is the 'discover' system user

    For backwards compatibility, if username is None, defaults to 'discover'.

    Args:
        code: The chat room code (URL slug)
        username: The host's reserved_username (case-insensitive). Defaults to 'discover'.

    Returns:
        ChatRoom instance

    Raises:
        Http404: If chat room not found
    """
    from django.http import Http404

    # Default to 'discover' for backwards compatibility with old routes
    if not username:
        username = 'discover'

    # Unified lookup: all rooms by username + code
    chat_room = ChatRoom.objects.filter(
        host__reserved_username__iexact=username,
        code=code,
        is_active=True
    ).select_related('host', 'theme').first()

    if not chat_room:
        raise Http404("Chat room not found")

    return chat_room


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


class ChatConfigView(APIView):
    """
    Get chat configuration options for frontend.

    Returns settings needed for chat creation UI, including
    location-based discovery radius options.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        import json
        # Parse JSON array of integers
        radius_options = json.loads(config.CHAT_DISCOVERY_RADIUS_OPTIONS)
        return Response({
            'discovery_radius_options': radius_options,
        })


class NearbyDiscoverableChatsView(APIView):
    """
    Get nearby discoverable chat rooms based on user's location.

    Uses Haversine formula to calculate distances and filters chats where:
    - distance <= chat's discovery_radius_miles (chat wants to be found at this distance)
    - distance <= user's selected radius (user is searching this far)

    Returns paginated results ordered by distance (closest first).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from django.db.models import F, FloatField
        from django.db.models.functions import Cast, Radians, Sin, Cos, ACos
        from .serializers import NearbyDiscoverableChatSerializer
        import math

        # Validate required parameters
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        radius = request.data.get('radius', 1)  # Default 1 mile
        offset = request.data.get('offset', 0)
        limit = request.data.get('limit', 20)

        if latitude is None or longitude is None:
            return Response(
                {'error': 'latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            latitude = float(latitude)
            longitude = float(longitude)
            radius = int(radius)
            offset = int(offset)
            limit = min(int(limit), 50)  # Cap at 50 per request
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid parameter types'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate radius is in allowed options
        import json
        allowed_radii = json.loads(config.CHAT_DISCOVERY_RADIUS_OPTIONS)
        if radius not in allowed_radii:
            return Response(
                {'error': f'radius must be one of: {allowed_radii}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Constants for Haversine formula
        EARTH_RADIUS_MILES = 3959

        # Convert user's coordinates to radians
        user_lat_rad = math.radians(latitude)
        user_lon_rad = math.radians(longitude)

        # Get all location-discoverable chats
        # Filter to only active chats with location set
        queryset = ChatRoom.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False,
            discovery_radius_miles__isnull=False
        ).select_related('host')

        # Check if host has joined (same as ChatRoomDetailView)
        queryset = queryset.filter(
            participations__user=F('host')
        ).distinct()

        # Calculate distance using Haversine formula in Python
        # (PostgreSQL annotation would be more efficient for large datasets,
        # but this is clearer and works for moderate numbers of chats)
        results = []
        for chat in queryset:
            chat_lat_rad = math.radians(float(chat.latitude))
            chat_lon_rad = math.radians(float(chat.longitude))

            # Haversine formula
            dlat = chat_lat_rad - user_lat_rad
            dlon = chat_lon_rad - user_lon_rad
            a = math.sin(dlat / 2) ** 2 + math.cos(user_lat_rad) * math.cos(chat_lat_rad) * math.sin(dlon / 2) ** 2
            c = 2 * math.asin(math.sqrt(a))
            distance_miles = EARTH_RADIUS_MILES * c

            # Two-way check:
            # 1. User must be within chat's discovery radius
            # 2. Chat must be within user's selected radius
            if distance_miles <= chat.discovery_radius_miles and distance_miles <= radius:
                chat.distance_miles = round(distance_miles, 1)
                results.append(chat)

        # Sort by distance (closest first)
        results.sort(key=lambda x: x.distance_miles)

        # Apply pagination
        total_count = len(results)
        paginated_results = results[offset:offset + limit]

        # Batch fetch message activity for all paginated rooms
        from media_analysis.utils.message_activity import get_message_activity_for_rooms
        room_ids = [str(chat.id) for chat in paginated_results]
        activity_data = get_message_activity_for_rooms(room_ids) if room_ids else {}

        # Add activity data to each room
        for chat in paginated_results:
            activity = activity_data.get(str(chat.id))
            chat.messages_24h = activity.messages_24h if activity else 0
            chat.messages_10min = activity.messages_10min if activity else 0

        # Serialize
        serializer = NearbyDiscoverableChatSerializer(paginated_results, many=True)

        return Response({
            'chats': serializer.data,
            'total_count': total_count,
            'offset': offset,
            'limit': limit,
            'has_more': offset + limit < total_count
        })


class ChatRoomDetailView(APIView):
    """Get chat room details by code (and username for manual rooms)"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

        # AI-generated rooms (discover) are always accessible - skip host join check
        # For manual rooms, check if host has joined first
        if chat_room.source != ChatRoom.SOURCE_AI:
            # Check if host has joined
            # Only allow non-host users to see the chat if host has joined
            host_has_joined = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=chat_room.host,
                is_anonymous_identity=False,
            ).exists()

            # If host hasn't joined, only allow the host to see the chat
            if not host_has_joined:
                is_host = request.user.is_authenticated and request.user == chat_room.host
                if not is_host:
                    # Return 404 to hide the chat from non-host users
                    from django.http import Http404
                    raise Http404("Chat room not found")

        # Don't expose access_code in response
        serializer = ChatRoomSerializer(chat_room)
        data = serializer.data
        data.pop('access_code', None)

        return Response(data)


class ChatRoomUpdateView(APIView):
    """Update chat room settings (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

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

    @require_turnstile
    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

        # AI-generated rooms (discover) are always joinable - skip host join check
        if chat_room.source != ChatRoom.SOURCE_AI:
            # Check if host has joined
            # Only allow non-host users to join if host has joined first
            host_has_joined = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=chat_room.host,
                is_anonymous_identity=False,
            ).exists()

            # If host hasn't joined, only allow the host to join
            if not host_has_joined:
                is_host = request.user.is_authenticated and request.user == chat_room.host
                if not is_host:
                    # Return 404 to hide the chat from non-host users
                    from django.http import Http404
                    raise Http404("Chat room not found")

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
        avatar_seed = serializer.validated_data.get('avatar_seed', None)
        user_id = str(request.user.id) if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        # Ensure Django session exists (primary identifier for anonymous users,
        # also needed when logged-in users join with anonymous identity)
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key

        # SECURITY CHECK 0: Verify username was generated by system OR is user's reserved_username
        # This applies to BOTH anonymous and logged-in users for new participations
        if request.user.is_authenticated:
            # Logged-in user: Check if this is a NEW participation (not rejoining)
            # Only consider their REGISTERED participation here.
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user,
                is_anonymous_identity=False,
                is_active=True
            ).first()

            # If NO existing participation, verify username is valid
            if not existing_participation:
                # Check if username is their reserved_username (case-insensitive)
                is_own_reserved = (
                    request.user.reserved_username and
                    username.lower() == request.user.reserved_username.lower()
                )

                if not is_own_reserved:
                    # Check if username belongs to their anonymous participation (same session)
                    anonymous_self = None
                    if session_key:
                        anonymous_self = ChatParticipation.objects.filter(
                            chat_room=chat_room, session_key=session_key,
                            user__isnull=True, username__iexact=username
                        ).first()

                    if anonymous_self:
                        pass  # Allowed — reclaiming own anonymous identity
                    elif session_key:
                        # Not their reserved username and not reclaiming anonymous - must be generated
                        generated_key = f"username:generated_for_session:{session_key}"
                        generated_usernames = cache.get(generated_key, set())
                        generated_usernames_lower = {u.lower() for u in generated_usernames}

                        if username.lower() not in generated_usernames_lower:
                            raise ValidationError(
                                "Invalid username. Please use your reserved username or the suggest username feature."
                            )
                    else:
                        # No session and not using reserved username - reject
                        raise ValidationError(
                            "Invalid username. Please use your reserved username or the suggest username feature."
                        )

        elif session_key:
            # Anonymous user: Check if this is a NEW participation (not rejoining)
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True,
                is_active=True
            ).first()

            # If NO existing participation, verify username was generated for this session
            if not existing_participation:
                # SECURITY: Check if username is reserved by a registered user FIRST
                from accounts.models import User as UserModel
                if UserModel.objects.filter(reserved_username__iexact=username).exists():
                    raise ValidationError(
                        f"Username '{username}' is reserved. Please log in to use this username."
                    )

                # Check Redis to verify this username was generated for this session
                generated_key = f"username:generated_for_session:{session_key}"
                generated_usernames = cache.get(generated_key, set())

                # Case-insensitive check (usernames stored with original capitalization)
                generated_usernames_lower = {u.lower() for u in generated_usernames}
                if username.lower() not in generated_usernames_lower:
                    raise ValidationError(
                        "Invalid username. Please use the suggest username feature to get a valid username."
                    )

        # SECURITY CHECK 1a: Check for site-wide ban
        from .models import SiteBan
        site_ban = SiteBan.is_banned(
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip_address,
            fingerprint=fingerprint,
            session_key=session_key,
            chat_room=chat_room
        )
        if site_ban:
            raise PermissionDenied("You have been banned from this site.")

        # SECURITY CHECK 1b: Check if user is blocked from this chat
        from .utils.security.blocking import check_if_blocked
        is_blocked, block_message = check_if_blocked(
            chat_room=chat_room,
            username=username,
            fingerprint=fingerprint,
            session_key=session_key,
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip_address
        )
        if is_blocked:
            raise PermissionDenied(block_message or "You have been blocked from this chat.")

        # SECURITY CHECK 1: IP-based rate limiting for anonymous users
        if not request.user.is_authenticated and ip_address:
            # Check if this session already has a participation (they're rejoining)
            existing_session_participation = None
            if session_key:
                existing_session_participation = ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    session_key=session_key,
                    user__isnull=True,
                    is_active=True
                ).first()

        # SECURITY CHECK 1: Check if username is reserved by another user
        from accounts.models import User
        reserved_user = User.objects.filter(reserved_username__iexact=username).first()
        if reserved_user:
            if not request.user.is_authenticated:
                raise ValidationError(
                    f"Username '{username}' is reserved. Please log in to use this username."
                )
            elif reserved_user.id != request.user.id:
                raise ValidationError(f"Username '{username}' is reserved by another user")

        # SECURITY CHECK 2: Check for existing participation (username persistence)
        if request.user.is_authenticated:
            # Check if this user already joined this chat as their REGISTERED identity
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user,
                is_anonymous_identity=False,
                is_active=True
            ).first()
            if existing_participation:
                # User already joined - they must use the same username
                # UNLESS they're switching to one of their own anonymous identities
                if existing_participation.username != username:
                    # Check if they own a claimed anonymous identity with this username
                    is_own_anonymous = ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        user=request.user,
                        is_anonymous_identity=True,
                        username__iexact=username,
                    ).exists()
                    # Fallback: unclaimed anon on the current session
                    if not is_own_anonymous and session_key:
                        is_own_anonymous = ChatParticipation.objects.filter(
                            chat_room=chat_room, session_key=session_key,
                            user__isnull=True, username__iexact=username
                        ).exists()
                    if not is_own_anonymous:
                        raise ValidationError(
                            f"You previously joined as \"{existing_participation.username}\". "
                            f"Please use that username to rejoin."
                        )
        elif session_key:
            # Check if this session already joined this chat
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True,
                is_active=True
            ).first()
            if existing_participation:
                # Session already joined - they must use the same username
                if existing_participation.username != username:
                    raise ValidationError(
                        f"You have already joined this chat as '{existing_participation.username}'. "
                        f"You cannot change your username in this chat."
                    )

        # SECURITY CHECK 3: Check if username is already taken by another participant
        # (excluding the current user/session who may be rejoining)
        # Usernames must be unique per chat room regardless of authentication status
        if request.user.is_authenticated:
            # Registered user: check for ANY other participant (registered or anonymous).
            # Exclude all participations they own (registered + claimed anonymous).
            qs = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
            ).exclude(user=request.user)
            # Also exclude unclaimed anon on their current session
            if session_key:
                qs = qs.exclude(session_key=session_key, user__isnull=True)
            username_taken = qs.exists()
        else:
            # Anonymous user: check for ANY other participant (registered or anonymous)
            qs = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
            )
            if session_key:
                qs = qs.exclude(session_key=session_key)
            username_taken = qs.exists()

        if username_taken:
            raise ValidationError(f"Username '{username}' is already in use in this chat")

        # Track whether user is joining with their anonymous identity
        is_anonymous_identity = False

        # Create or update ChatParticipation
        if request.user.is_authenticated:
            # Check if reclaiming an anonymous identity:
            #   1. an already-claimed anonymous identity owned by this user, OR
            #   2. an unclaimed anonymous participation on the current session,
            #      which we will claim atomically below.
            anonymous_self = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user,
                is_anonymous_identity=True,
                username__iexact=username,
            ).first()
            if not anonymous_self and session_key:
                anonymous_self = ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    session_key=session_key,
                    user__isnull=True,
                    username__iexact=username,
                ).first()

            if anonymous_self:
                # Reuse anonymous participation. Mark it as a claimed
                # anonymous identity owned by this user (single source of truth).
                is_anonymous_identity = True
                participation = anonymous_self
                participation.ip_address = ip_address
                participation.user = request.user
                participation.is_anonymous_identity = True
                # Before updating session_key, clear it from any OTHER anon
                # participations in this chat that currently hold the same
                # (chat_room, session_key) pair — otherwise the unique
                # constraint will fire. Those other anons remain discoverable
                # because they are still linked to the user via the FK.
                if session_key and participation.session_key != session_key:
                    ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        session_key=session_key,
                        user__isnull=True,
                    ).exclude(id=participation.id).update(session_key=None)
                participation.session_key = session_key  # Update session_key
                participation.save()
                created = False
            else:
                # Logged-in user — find/create their REGISTERED participation.
                participation, created = ChatParticipation.objects.get_or_create(
                    chat_room=chat_room,
                    user=request.user,
                    is_anonymous_identity=False,
                    defaults={
                        'username': username,
                        'fingerprint': fingerprint,
                        'session_key': session_key,
                        'ip_address': ip_address,
                    }
                )
                if not created:
                    # Update last_seen, fingerprint, and session_key
                    participation.fingerprint = fingerprint
                    participation.session_key = session_key
                    participation.ip_address = ip_address
                    participation.save()

                # Generate avatar at join time for logged-in users
                if created:
                    self._generate_avatar_for_participation(participation, chat_room, request.user, avatar_seed=avatar_seed)
        elif session_key:
            # Anonymous user - find/create by session_key (primary identifier)
            participation, created = ChatParticipation.objects.get_or_create(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True,
                defaults={
                    'username': username,
                    'fingerprint': fingerprint,  # Stored for ban enforcement
                    'ip_address': ip_address,
                }
            )
            if not created:
                # Update last_seen, IP, and fingerprint
                participation.fingerprint = fingerprint
                participation.ip_address = ip_address
                participation.save()

            # Generate avatar at join time for anonymous users
            if created and not participation.avatar_url:
                self._generate_avatar_for_participation(participation, chat_room, avatar_seed=avatar_seed)

        # Phase 2d: Also claim any unclaimed orphan anon on the current session
        # (e.g. user logged in mid-session and joined as their registered identity
        # — make sure their prior anon participation in this chat gets linked).
        # Claim is atomic: set user + is_anonymous_identity directly on the row.
        if request.user.is_authenticated and session_key:
            orphan_anons = ChatParticipation.objects.filter(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True,
            )
            for orphan in orphan_anons:
                if not participation or orphan.id != participation.id:
                    orphan.user = request.user
                    orphan.is_anonymous_identity = True
                    orphan.save(update_fields=['user', 'is_anonymous_identity'])

        # Create JWT session token
        # If user is joining with anonymous identity, exclude user_id from token
        # to prevent anonymous messages from being marked as host messages
        token_user_id = None if is_anonymous_identity else user_id
        session_token = ChatSessionValidator.create_session_token(
            chat_code=code,
            username=username,
            user_id=token_user_id,
            fingerprint=fingerprint,
            session_key=session_key
        )

        # Return chat room info, username, and session token
        return Response({
            'chat_room': ChatRoomSerializer(chat_room).data,
            'username': username,
            'session_token': session_token,
            'message': 'Successfully joined chat room'
        })

    def _generate_avatar_for_participation(self, participation, chat_room, user=None, avatar_seed=None):
        """
        Generate and store avatar at join time.

        ALWAYS populates ChatParticipation.avatar_url with the appropriate URL:
        - Registered user using reserved_username: proxy URL (allows avatar changes)
        - Registered user using different username: direct storage URL
        - Anonymous user: direct storage URL

        If avatar_seed is provided, it is used as the DiceBear seed. For
        reserved-username users, the seed is honored ONLY when User.avatar_url
        is empty — the reserved avatar is stable once set and must not be
        overwritten by subsequent joins.
        """
        from chatpop.utils.media import generate_and_store_avatar

        seed = avatar_seed or participation.username

        # If logged-in user using their reserved_username
        if user and user.reserved_username:
            if participation.username.lower() == user.reserved_username.lower():
                # Only set User.avatar_url if none exists — reserved avatars are
                # stable once chosen. Join flow never overwrites them.
                if not user.avatar_url:
                    avatar_url = generate_and_store_avatar(seed)
                    if avatar_url:
                        user.avatar_url = avatar_url
                        user.save(update_fields=['avatar_url'])

                # Store proxy URL in ChatParticipation (points to User.avatar_url)
                participation.avatar_url = f'/api/chats/media/avatars/user/{user.id}'
                participation.save(update_fields=['avatar_url'])
                return

        # For anonymous users or registered users using different username:
        # Generate and store direct URL on ChatParticipation
        if not participation.avatar_url:
            avatar_url = generate_and_store_avatar(seed)
            if avatar_url:
                participation.avatar_url = avatar_url
                participation.save(update_fields=['avatar_url'])


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

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

        # Query params
        limit = int(request.query_params.get('limit', config.MESSAGE_LIST_DEFAULT_LIMIT))
        before_timestamp = request.query_params.get('before')  # Unix timestamp for pagination
        session_token = request.query_params.get('session_token')
        filter_mode = request.query_params.get('filter')  # 'focus' or 'gifts'
        filter_username = request.query_params.get('filter_username')  # username for filter

        # Extract current user's identity from session token (for has_reacted)
        current_session_key = None
        current_user_id = None
        current_username = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                current_session_key = session_data.get('session_key')
                current_user_id = session_data.get('user_id')
                current_username = session_data.get('username')
            except Exception:
                pass  # Invalid token - just proceed without has_reacted

        # Enforce maximum limit from Constance settings (security: prevent unlimited message requests)
        max_limit = config.MESSAGE_HISTORY_MAX_COUNT
        if limit > max_limit:
            limit = max_limit

        # Check if Redis caching is enabled (Constance dynamic setting)
        cache_enabled = config.REDIS_CACHE_ENABLED

        # Try Redis cache first (if enabled and no pagination)
        messages = []
        source = 'postgresql'  # Default source

        if cache_enabled:
            # Route to filter-specific cache reads when filter is set
            if filter_mode == 'highlight':
                messages = MessageCache.get_highlight_messages(
                    chat_room.id, limit=limit,
                    before_timestamp=float(before_timestamp) if before_timestamp else None
                )
            elif filter_mode == 'photo':
                messages = MessageCache.get_photo_messages(
                    chat_room.id, limit=limit,
                    before_timestamp=float(before_timestamp) if before_timestamp else None
                )
            elif filter_mode == 'video':
                messages = MessageCache.get_video_messages(
                    chat_room.id, limit=limit,
                    before_timestamp=float(before_timestamp) if before_timestamp else None
                )
            elif filter_mode == 'audio':
                messages = MessageCache.get_audio_messages(
                    chat_room.id, limit=limit,
                    before_timestamp=float(before_timestamp) if before_timestamp else None
                )
            elif filter_mode and filter_username:
                if filter_mode == 'focus':
                    # If any spotlight users exist, bypass cache for focus mode
                    # so spotlighted messages are included (cache index doesn't
                    # know about spotlight). Returning [] forces partial-cache
                    # path to fall through to _fetch_from_db below.
                    has_spotlight = ChatParticipation.objects.filter(
                        chat_room=chat_room, is_spotlight=True
                    ).exists()
                    if has_spotlight:
                        messages = []
                    else:
                        messages = MessageCache.get_focus_messages(
                            chat_room.id, filter_username, limit=limit,
                            before_timestamp=float(before_timestamp) if before_timestamp else None
                        )
                elif filter_mode == 'gifts':
                    messages = MessageCache.get_gift_messages(
                        chat_room.id, username=filter_username, limit=limit,
                        before_timestamp=float(before_timestamp) if before_timestamp else None
                    )
            elif before_timestamp:
                # Pagination request - try cache first with before_timestamp
                messages = MessageCache.get_messages_before(chat_room.id, before_timestamp=float(before_timestamp), limit=limit)
            else:
                # Initial load - get most recent messages
                messages = MessageCache.get_messages(chat_room.id, limit=limit)

            print(f"DEBUG: cache_enabled={cache_enabled}, messages from cache: {len(messages) if messages else 0}")

            if messages:
                # Cache hit (full or partial)
                if len(messages) < limit and not before_timestamp:
                    # Partial cache hit on initial load - fetch remaining messages from database
                    from datetime import datetime

                    # Boundary timestamp = the score field used by THIS filter's index.
                    # Highlight room is sorted by highlighted_at (since 2026-04-15);
                    # other rooms are sorted by created_at. Mismatching score and
                    # boundary causes the DB query to return messages that are
                    # already in the cache (duplicate IDs in the response).
                    if filter_mode == 'highlight' and messages[0].get('highlighted_at'):
                        oldest_cached_timestamp = datetime.fromisoformat(
                            messages[0]['highlighted_at']
                        ).timestamp()
                    else:
                        oldest_cached_timestamp = datetime.fromisoformat(
                            messages[0]['created_at']
                        ).timestamp()
                    remaining_limit = limit - len(messages)

                    # Fetch older messages from database
                    older_messages = self._fetch_from_db(
                        chat_room,
                        limit=remaining_limit,
                        before_timestamp=oldest_cached_timestamp,
                        request=request,
                        current_user_id=current_user_id,
                        filter_mode=filter_mode,
                        filter_username=filter_username,
                        current_session_key=current_session_key
                    )

                    # Backfill cache with the older messages we just fetched
                    # This prevents repeated DB queries for the same messages
                    self._backfill_cache(chat_room, older_messages)

                    # Prepend older messages (they come chronologically before cached ones)
                    # Dedup as a safety net: any future score-vs-boundary mismatch
                    # would otherwise leak duplicate IDs to the frontend and cause
                    # React "duplicate key" warnings in MainChatView.
                    cached_ids = {m['id'] for m in messages}
                    older_messages = [m for m in older_messages if m['id'] not in cached_ids]
                    messages = older_messages + messages
                    source = 'hybrid_redis_postgresql'
                else:
                    # Full cache hit (initial load or pagination)
                    source = 'redis'

                # Convert relative voice URLs to absolute URLs
                for msg in messages:
                    if msg.get('voice_url') and request:
                        msg['voice_url'] = request.build_absolute_uri(msg['voice_url'])

                # Fetch reactions for all messages (batch operation for performance)
                message_ids = [msg['id'] for msg in messages]
                reactions_by_message = MessageCache.batch_get_reactions(chat_room.id, message_ids)

                # Get current user's reactions for has_reacted (single query)
                user_reactions = {}  # message_id -> set of emojis
                if current_session_key or current_user_id:
                    q_filter = Q()
                    if current_session_key:
                        q_filter |= Q(session_key=current_session_key)
                    if current_user_id:
                        q_filter |= Q(user_id=current_user_id)

                    user_reaction_records = MessageReaction.objects.filter(
                        Q(message_id__in=message_ids) & q_filter
                    ).values('message_id', 'emoji')
                    for record in user_reaction_records:
                        msg_id = str(record['message_id'])
                        if msg_id not in user_reactions:
                            user_reactions[msg_id] = set()
                        user_reactions[msg_id].add(record['emoji'])

                # Attach reactions to each message with has_reacted
                for msg in messages:
                    msg_id = msg['id']
                    reactions = reactions_by_message.get(msg_id, [])
                    user_emojis = user_reactions.get(msg_id, set())
                    # Add has_reacted to each reaction
                    for reaction in reactions:
                        reaction['has_reacted'] = reaction['emoji'] in user_emojis
                    msg['reactions'] = reactions

                # Batch fetch banned usernames (ONE query for all messages)
                unique_usernames_cached = set(msg.get('username', '') for msg in messages)
                from django.utils import timezone as tz
                banned_usernames_cached = set(
                    ChatBlock.objects.filter(
                        chat_room=chat_room,
                        blocked_username__in=[u.lower() for u in unique_usernames_cached if u]
                    ).filter(
                        Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
                    ).values_list('blocked_username', flat=True)
                )
                spotlight_usernames_cached = set(
                    ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        is_spotlight=True,
                        username__in=[u for u in unique_usernames_cached if u],
                    ).values_list('username', flat=True)
                )
                for msg in messages:
                    msg['is_banned'] = msg.get('username', '').lower() in banned_usernames_cached
                    msg['is_spotlight'] = msg.get('username', '') in spotlight_usernames_cached
            else:
                # Cache miss - fall back to PostgreSQL and backfill cache
                print(f"DEBUG: Cache miss! Calling _fetch_from_db, limit={limit}, before_timestamp={before_timestamp}")
                messages = self._fetch_from_db(chat_room, limit, before_timestamp, request, current_user_id, filter_mode, filter_username, current_session_key)
                source = 'postgresql_fallback'
                print(f"DEBUG: _fetch_from_db returned {len(messages)} messages")

                # Backfill cache: Add fetched messages to Redis
                # This ensures subsequent requests hit the cache
                print(f"DEBUG: About to call _backfill_cache with {len(messages)} messages")
                self._backfill_cache(chat_room, messages)
                print(f"DEBUG: _backfill_cache completed")
        else:
            # Cache disabled - always use PostgreSQL
            messages = self._fetch_from_db(chat_room, limit, before_timestamp, request, current_user_id, filter_mode, filter_username, current_session_key)

        # Filter blocked users for authenticated users
        should_show_full = None
        blocked_usernames = None
        if request.user and request.user.is_authenticated:
            from .utils.performance.cache import UserBlockCache

            # Load blocked usernames (uses existing Redis/PostgreSQL cache)
            blocked_usernames = UserBlockCache.get_blocked_usernames(request.user.id)

            # Filter messages in Python
            if blocked_usernames:
                # Registered participation username used ONLY for block-filtering logic
                # (gift-to-me check). Do not use for notification identity — that comes
                # from the session token's username, which may be an anonymous identity.
                filter_username = None
                participation = ChatParticipation.objects.filter(
                    chat_room=chat_room, user=request.user, is_anonymous_identity=False
                ).first()
                if participation:
                    filter_username = participation.username

                blocked_lower = {u.lower() for u in blocked_usernames}
                current_lower = (filter_username or '').lower()

                def should_show_full(msg):
                    author = msg.get('username', '') or ''
                    author_lower = author.lower()
                    author_blocked = author in blocked_usernames or author_lower in blocked_lower
                    if author_blocked:
                        if msg.get('is_highlight'):
                            return True
                        if msg.get('message_type') == 'gift' and (msg.get('gift_recipient') or '').lower() == current_lower:
                            return True
                        return False
                    # Hide gifts TO muted users (unless I'm the sender)
                    if msg.get('message_type') == 'gift':
                        recipient = (msg.get('gift_recipient') or '').lower()
                        if recipient and recipient in blocked_lower:
                            if author_lower != current_lower:
                                return False
                    return True

                messages = [m for m in messages if should_show_full(m)]

        # Fetch pinned messages from Redis (pinned messages are ephemeral)
        pinned_messages = MessageCache.get_pinned_messages(chat_room.id)

        # Apply same mute filter to pinned messages
        if should_show_full is not None:
            pinned_messages = [m for m in pinned_messages if should_show_full(m)]

        # Broadcast sticky message
        broadcast_sticky_data = None
        if chat_room.broadcast_message_id:
            try:
                from rest_framework.renderers import JSONRenderer
                import json as json_module
                bm = chat_room.broadcast_message
                if bm and not bm.is_deleted:
                    broadcast_sticky_data = json_module.loads(JSONRenderer().render(MessageSerializer(bm).data))
            except Exception:
                pass

        # Room notification indicators from Redis (O(1) per room, no SQL)
        room_notifications = {}
        if not filter_mode and (current_username or current_user_id or current_session_key):
            from .utils.performance.cache import RoomNotificationCache
            notif_identity = RoomNotificationCache.resolve_participation_id(
                chat_room, username=current_username, user_id=current_user_id, session_key=current_session_key
            )
            if notif_identity:
                room_notifications = RoomNotificationCache.has_unseen(str(chat_room.id), notif_identity)

        return Response({
            'messages': messages,
            'pinned_messages': pinned_messages,
            'broadcast_message': broadcast_sticky_data,
            'room_notifications': room_notifications,
            'source': source,  # Shows where data came from (redis/postgresql/postgresql_fallback)
            'cache_enabled': cache_enabled,
            'count': len(messages),
            'history_limits': {
                'max_days': config.MESSAGE_HISTORY_MAX_DAYS,
                'max_count': config.MESSAGE_HISTORY_MAX_COUNT
            }
        })

    def _fetch_from_db(self, chat_room, limit, before_timestamp=None, request=None, current_user_id=None, filter_mode=None, filter_username=None, current_session_key=None):
        """
        Fallback: fetch messages from PostgreSQL.

        Returns: List of message dicts (serialized)
        """
        start_time = time.time()

        queryset = Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        ).select_related('user', 'reply_to').prefetch_related('reactions')

        # Apply filter mode
        if filter_mode == 'highlight':
            queryset = queryset.filter(is_highlight=True)
        elif filter_mode == 'photo':
            # Non-gift messages with a populated photo_url
            queryset = queryset.exclude(message_type='gift').filter(photo_url__isnull=False).exclude(photo_url='')
        elif filter_mode == 'video':
            queryset = queryset.exclude(message_type='gift').filter(video_url__isnull=False).exclude(video_url='')
        elif filter_mode == 'audio':
            queryset = queryset.exclude(message_type='gift').filter(voice_url__isnull=False).exclude(voice_url='')
        elif filter_mode and filter_username:
            if filter_mode == 'focus':
                spotlight_usernames_in_chat = list(
                    ChatParticipation.objects.filter(
                        chat_room=chat_room, is_spotlight=True
                    ).values_list('username', flat=True)
                )
                queryset = queryset.filter(
                    Q(is_from_host=True) |
                    Q(username__iexact=filter_username) |
                    Q(reply_to__username__iexact=filter_username) |
                    Q(username__in=spotlight_usernames_in_chat)
                )
            elif filter_mode == 'gifts':
                queryset = queryset.filter(
                    Q(message_type='gift') & (
                        Q(username__iexact=filter_username) |
                        Q(gift_recipient__iexact=filter_username)
                    )
                )

        # Filter by timestamp if paginating. For highlight mode, the boundary
        # is highlighted_at (matches the cache index score). For everything
        # else it is created_at. Mismatching these introduces duplicates in
        # the partial-hit response (older_messages overlaps cached messages).
        if before_timestamp:
            from datetime import datetime, timezone as dt_timezone
            before_dt = datetime.fromtimestamp(float(before_timestamp), tz=dt_timezone.utc)
            if filter_mode == 'highlight':
                queryset = queryset.filter(highlighted_at__lt=before_dt)
            else:
                queryset = queryset.filter(created_at__lt=before_dt)

        # Order and limit (newest first to get last N messages). Highlight room
        # is ordered by highlighted_at to match its cache index score.
        order_field = '-highlighted_at' if filter_mode == 'highlight' else '-created_at'
        messages = queryset.order_by(order_field)[:limit]

        # Force query execution for accurate timing
        message_count = len(messages)

        # Batch fetch reactions from cache for all messages (SOLVES N+1 PROBLEM)
        message_ids = [str(msg.id) for msg in messages]
        reactions_by_message = MessageCache.batch_get_reactions(chat_room.id, message_ids)

        # Get current user's reactions for has_reacted (single query)
        user_reactions = {}  # message_id -> set of emojis
        if current_session_key or current_user_id:
            q_filter = Q()
            if current_session_key:
                q_filter |= Q(session_key=current_session_key)
            if current_user_id:
                q_filter |= Q(user_id=current_user_id)

            user_reaction_records = MessageReaction.objects.filter(
                Q(message_id__in=message_ids) & q_filter
            ).values('message_id', 'emoji')
            for record in user_reaction_records:
                msg_id = str(record['message_id'])
                if msg_id not in user_reactions:
                    user_reactions[msg_id] = set()
                user_reactions[msg_id].add(record['emoji'])

        # Batch fetch avatar URLs (ONE query - solves N+1 problem)
        # ChatParticipation.avatar_url is always populated at join time
        unique_usernames = list(set(msg.username for msg in messages))
        participations = ChatParticipation.objects.filter(
            chat_room=chat_room,
            username__in=unique_usernames
        )

        # Build avatar_map: username (lowercase) -> avatar_url
        from chatpop.utils.media import get_fallback_dicebear_url

        avatar_map = {}
        for p in participations:
            if p.avatar_url:
                avatar_map[p.username.lower()] = p.avatar_url
            # else: not in map, will fallback to DiceBear (orphaned data)

        # Batch fetch banned usernames (ONE query)
        from django.utils import timezone as tz
        banned_usernames_db = set(
            ChatBlock.objects.filter(
                chat_room=chat_room,
                blocked_username__in=[u.lower() for u in unique_usernames if u]
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
            ).values_list('blocked_username', flat=True)
        )

        # Batch fetch spotlighted usernames (ONE query)
        spotlight_usernames_db = set(
            ChatParticipation.objects.filter(
                chat_room=chat_room,
                is_spotlight=True,
                username__in=[u for u in unique_usernames if u],
            ).values_list('username', flat=True)
        )

        # Serialize (with username_is_reserved, avatar_url, and is_banned)
        serialized = []
        for msg in messages:
            username_is_reserved = MessageCache._compute_username_is_reserved(msg)
            # Lookup avatar from map, fallback to DiceBear if not found
            avatar_url = avatar_map.get(msg.username.lower()) or get_fallback_dicebear_url(msg.username)

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
                    'is_from_host': msg.reply_to.is_from_host,
                }

            # Get cached reactions (or fallback to database if cache miss)
            msg_id_str = str(msg.id)
            cached_reactions = reactions_by_message.get(msg_id_str, [])

            if cached_reactions:
                # Use cached reactions (already top 20 format)
                top_reactions = cached_reactions
            else:
                # Cache miss: fallback to database query (compute reaction summary)
                from collections import defaultdict
                reactions_list = msg.reactions.order_by('-created_at')
                emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0, 'latest': None})

                for reaction in reactions_list:
                    emoji = reaction.emoji
                    emoji_counts[emoji]['emoji'] = emoji
                    emoji_counts[emoji]['count'] += 1
                    if emoji_counts[emoji]['latest'] is None:
                        emoji_counts[emoji]['latest'] = reaction.created_at

                all_sorted = sorted(emoji_counts.values(), key=lambda x: (-x['count'], -(x['latest'].timestamp() if x['latest'] else 0)))
                top_reactions = [{'emoji': r['emoji'], 'count': r['count']} for r in all_sorted[:20]]

                # Cache the computed reactions for next time
                if top_reactions:
                    MessageCache.set_message_reactions(chat_room.id, msg_id_str, top_reactions)

            # Add has_reacted + include user's reactions not in top 20
            user_emojis = user_reactions.get(msg_id_str, set())
            top_emojis = {r['emoji'] for r in top_reactions}
            for reaction in top_reactions:
                reaction['has_reacted'] = reaction['emoji'] in user_emojis
            # Append user's own reactions that didn't make the top 20
            for user_emoji in user_emojis:
                if user_emoji not in top_emojis:
                    top_reactions.append({'emoji': user_emoji, 'count': 1, 'has_reacted': True})

            # Use the canonical cache serializer so fields stay consistent with the
            # Redis path (photo_url, video_url, is_highlight, gift_recipient, etc.).
            msg_dict = MessageCache._serialize_message(msg, username_is_reserved, avatar_url)
            # Override voice_url with the absolute-URL version computed above
            msg_dict['voice_url'] = voice_url
            # Fields this path adds on top (not part of the cached serialization)
            msg_dict['is_banned'] = msg.username.lower() in banned_usernames_db
            msg_dict['is_spotlight'] = msg.username in spotlight_usernames_db
            msg_dict['reactions'] = top_reactions
            serialized.append(msg_dict)

        # Reverse to chronological order (oldest first) to match Redis behavior
        serialized.reverse()

        # Monitor: Database read
        duration_ms = (time.time() - start_time) * 1000
        monitor.log_db_read(
            chat_room.code,
            count=len(serialized),
            duration_ms=duration_ms,
            query_type='SELECT'
        )

        return serialized

    def _backfill_cache(self, chat_room, message_dicts):
        """
        Backfill Redis cache with messages fetched from PostgreSQL.

        This prevents repeated cache misses for the same chat.
        Only called on initial load (cache miss), not pagination.

        Args:
            chat_room: ChatRoom instance
            message_dicts: List of serialized message dicts from _fetch_from_db()
        """
        from constance import config

        print(f"DEBUG: _backfill_cache called with chat_room={chat_room.code}, {len(message_dicts)} messages")
        print(f"DEBUG: REDIS_CACHE_ENABLED={config.REDIS_CACHE_ENABLED}")

        if not config.REDIS_CACHE_ENABLED:
            print(f"DEBUG: Cache disabled, returning without backfill")
            return

        if not message_dicts:
            print(f"DEBUG: No messages to backfill, returning")
            return

        # Extract message IDs from the serialized dicts
        message_ids = [msg['id'] for msg in message_dicts]

        # Fetch Message instances from database
        # Use select_related to avoid N+1 queries
        messages = Message.objects.filter(
            id__in=message_ids,
            chat_room=chat_room
        ).select_related('user', 'reply_to')

        # Add each message to cache
        cached_count = 0
        print(f"DEBUG: Starting to cache {len(messages)} messages...")
        for message in messages:
            try:
                success = MessageCache.add_message(message)
                if success:
                    cached_count += 1
                    print(f"DEBUG: Cached message {message.id} successfully")
                else:
                    print(f"DEBUG: Failed to cache message {message.id} (add_message returned False)")
            except Exception as e:
                print(f"⚠️  Failed to backfill message {message.id} to cache: {e}")

        if cached_count > 0:
            print(f"✅ Backfilled {cached_count}/{len(message_ids)} messages to Redis cache for chat {chat_room.code}")
        else:
            print(f"DEBUG: NO MESSAGES WERE CACHED! cached_count=0")


class MessageCreateView(generics.CreateAPIView):
    """Send a message to a chat room"""
    serializer_class = MessageCreateSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

        # Validate session token
        session_token = request.data.get('session_token')
        username = request.data.get('username')

        if not session_token:
            raise PermissionDenied("Session token is required")

        # Validate the JWT session token
        session_data = ChatSessionValidator.validate_session_token(
            token=session_token,
            chat_code=code,
            username=username,
            request=request,
        )

        # NOTE: Ban checks removed from per-message flow for performance.
        # Bans are enforced at:
        # 1. Join time (ChatRoomJoinView) - blocks initial access
        # 2. WebSocket connect (ChatConsumer.connect) - blocks reconnection
        # 3. WebSocket kick (user_kicked event) - immediately evicts banned users
        # This eliminates 3 DB queries per message while maintaining security.

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


class PinTiersView(APIView):
    """
    Get available pin tiers and current sticky info for a chat.
    Use this to display tier options before the user selects a message.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, username=None):
        """Get pin tiers and current sticky status."""
        chat_room = get_chat_room_by_url(code, username)

        # Get current highest pin value from cache
        current_pin_cents = MessageCache.get_current_pin_value_cents(chat_room.id)
        current_pin_cents = int(current_pin_cents) if current_pin_cents else 0

        # Get minimum required tier to outbid
        min_required_cents = get_next_tier_above(current_pin_cents) if current_pin_cents > 0 else get_valid_pin_tiers()[0]

        # Get top pinned message info
        top_pinned = MessageCache.get_top_pinned_message(chat_room.id)

        return Response({
            'current_pin_cents': current_pin_cents,
            'minimum_required_cents': min_required_cents,
            'duration_minutes': get_new_pin_duration_minutes(),
            'tiers': get_tiers_for_frontend(),
            'has_active_sticky': top_pinned is not None,
            'top_pinned_message_id': top_pinned.get('id') if top_pinned else None,
        })


class MessagePinView(APIView):
    """
    Pin a message (requires payment).

    To take the sticky spot, you must bid at least the next tier above the current sticky.
    Duration is fixed at PIN_NEW_PIN_DURATION_MINUTES (default 1 hour).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id, username=None):
        """Get current pin requirements and available tiers for a message."""
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        now = timezone.now()

        # Get current top sticky from cache
        top_pinned = MessageCache.get_top_pinned_message(chat_room.id)
        if top_pinned:
            try:
                current_pin_cents = int(float(top_pinned.get('current_pin_amount', 0)) * 100)
            except (ValueError, TypeError):
                current_pin_cents = 0
        else:
            current_pin_cents = 0

        # Check if THIS message is the current sticky holder
        is_current_sticky = top_pinned and top_pinned.get('id') == str(message.id)

        # Check if this message was pinned but outbid (has time remaining but not top)
        is_outbid = (
            message.is_pinned and
            message.sticky_until and
            message.sticky_until > now and
            not is_current_sticky
        )

        # Get user's existing investment (only valid if not expired)
        # This is the lazy expiration check - investment "resets" when sticky_until passes
        my_investment_cents = 0
        if is_outbid and message.current_pin_amount:
            my_investment_cents = int(float(message.current_pin_amount) * 100)

        # Get minimum required total to win the sticky (next tier above current)
        min_total_cents = None
        if not is_current_sticky and current_pin_cents > 0:
            min_total_cents = get_next_tier_above(current_pin_cents)
        elif not is_current_sticky:
            min_total_cents = get_valid_pin_tiers()[0]

        # For reclaim: calculate minimum tier to ADD (total needed minus existing investment)
        min_add_cents = None
        if is_outbid and min_total_cents:
            # Need to add enough to reach min_total_cents
            delta = min_total_cents - my_investment_cents
            if delta <= 0:
                # Already have enough investment, just need smallest tier
                min_add_cents = get_valid_pin_tiers()[0]
            else:
                # Find smallest tier >= delta
                tiers = get_valid_pin_tiers()
                for tier in tiers:
                    if tier >= delta:
                        min_add_cents = tier
                        break
                # If no tier found (delta > max tier), use the delta rounded up
                if min_add_cents is None:
                    min_add_cents = delta

        # Calculate time remaining if outbid (for reclaim time stacking)
        time_remaining_seconds = None
        if is_outbid and message.sticky_until:
            time_remaining_seconds = max(0, int((message.sticky_until - now).total_seconds()))

        return Response({
            'current_pin_cents': current_pin_cents,
            'minimum_required_cents': min_total_cents,  # Total needed to win
            'minimum_add_cents': min_add_cents,  # For reclaim: min tier to add
            'my_investment_cents': my_investment_cents,  # User's existing investment
            'duration_minutes': get_new_pin_duration_minutes(),
            'tiers': get_tiers_for_frontend(),
            'is_current_sticky': is_current_sticky,
            'is_outbid': is_outbid,
            'time_remaining_seconds': time_remaining_seconds,
        })

    def post(self, request, code, message_id, username=None):
        """Pin a message by paying to take the sticky spot."""
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Block pinning banned users' messages
        from django.utils import timezone as tz
        active_ban = ChatBlock.objects.filter(
            chat_room=chat_room,
        ).filter(
            Q(blocked_username__iexact=message.username) |
            Q(blocked_user=message.user) if message.user_id else Q(blocked_username__iexact=message.username)
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
        ).exists()
        if active_ban:
            return Response(
                {'error': 'Cannot pin a message from a banned user'},
                status=status.HTTP_403_FORBIDDEN
            )

        now = timezone.now()

        serializer = MessagePinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount_cents = serializer.validated_data['amount_cents']

        # Get current top sticky
        top_pinned_before = MessageCache.get_top_pinned_message(chat_room.id)
        if top_pinned_before:
            try:
                current_pin_cents = int(float(top_pinned_before.get('current_pin_amount', 0)) * 100)
            except (ValueError, TypeError):
                current_pin_cents = 0
        else:
            current_pin_cents = 0

        # Check if this is a "reclaim" - message was outbid but has time remaining
        is_reclaim = (
            message.is_pinned and
            message.sticky_until and
            message.sticky_until > now and
            top_pinned_before and
            top_pinned_before.get('id') != str(message.id)
        )

        # Get existing investment for reclaim scenarios
        my_investment_cents = 0
        if is_reclaim and message.current_pin_amount:
            my_investment_cents = int(float(message.current_pin_amount) * 100)

        # For reclaim: the total bid is existing investment + new payment
        # For new pin: the total bid is just the payment
        total_bid_cents = my_investment_cents + amount_cents if is_reclaim else amount_cents

        # Validate that total bid beats the current sticky
        min_required_cents = get_next_tier_above(current_pin_cents) if current_pin_cents > 0 else get_valid_pin_tiers()[0]

        if total_bid_cents < min_required_cents:
            return Response({
                'error': f'Total bid ${total_bid_cents/100:.2f} does not meet minimum ${min_required_cents/100:.2f}',
                'current_pin_cents': current_pin_cents,
                'minimum_required_cents': min_required_cents,
                'my_investment_cents': my_investment_cents,
                'tiers': get_tiers_for_frontend(),
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate that amount_cents is a valid tier
        if not is_valid_tier(amount_cents):
            return Response({
                'error': f'${amount_cents/100:.2f} is not a valid tier',
                'tiers': get_tiers_for_frontend(),
            }, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Process payment with Stripe here
        # For now, just pin the message

        # NOTE: We intentionally do NOT reset current_pin_amount on outbid messages.
        # The outbid user's investment remains until their sticky_until expires,
        # allowing them to "reclaim" by adding to their existing investment.
        # Expiration check happens lazily at read time.

        # Calculate duration based on whether this is a reclaim or new pin
        if is_reclaim:
            # Reclaim: stack tier's time extension on remaining time
            time_remaining_seconds = max(0, (message.sticky_until - now).total_seconds())
            tier_extension_minutes = get_tier_duration_minutes(amount_cents)
            total_seconds = time_remaining_seconds + (tier_extension_minutes * 60)
            total_minutes = int(total_seconds / 60)
            # Pass the combined total (existing + new) as the pin amount
            message.pin_message(amount_paid_cents=total_bid_cents, duration_minutes=total_minutes)
        else:
            # Standard new pin: use default duration
            message.pin_message(amount_paid_cents=amount_cents)

        # Update both caches: main messages list and pinned messages
        MessageCache.update_message(message)
        MessageCache.add_pinned_message(message)

        # Get updated top pinned message to return
        top_pinned = MessageCache.get_top_pinned_message(chat_room.id)
        is_top_pin = top_pinned and top_pinned.get('id') == str(message.id)

        # Broadcast pin update via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from rest_framework.renderers import JSONRenderer
        import json as json_module

        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'

        # Convert serializer data to JSON-safe format (UUIDs become strings)
        serialized_data = MessageSerializer(message).data
        json_safe_data = json_module.loads(JSONRenderer().render(serialized_data))

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_pinned',
                'message': json_safe_data,
                'is_top_pin': is_top_pin,
            }
        )

        return Response({
            'success': True,
            'message': MessageSerializer(message).data,
            'is_top_pin': is_top_pin,
            'amount_cents': amount_cents,
            'duration_minutes': get_new_pin_duration_minutes(),
        })


class AddToPinView(APIView):
    """
    Add to an existing sticky pinned message.

    This increases the pin amount AND extends the duration based on tier.
    Only available for the current sticky holder (active, non-expired pin).
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id, username=None):
        """Get tier info for adding to a pinned message."""
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        now = timezone.now()
        is_expired = message.sticky_until and message.sticky_until < now
        time_remaining_seconds = 0
        if message.sticky_until and not is_expired:
            time_remaining_seconds = int((message.sticky_until - now).total_seconds())

        return Response({
            'is_pinned': message.is_pinned,
            'is_expired': is_expired,
            'current_pin_cents': int(message.current_pin_amount * 100) if message.current_pin_amount else 0,
            'time_remaining_seconds': time_remaining_seconds,
            'tiers': get_tiers_for_frontend(),
        })

    def post(self, request, code, message_id, username=None):
        """Add value and time to an existing pinned message."""
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Block adding to pins on banned users' messages
        from django.utils import timezone as tz
        active_ban = ChatBlock.objects.filter(
            chat_room=chat_room,
        ).filter(
            Q(blocked_username__iexact=message.username) |
            Q(blocked_user=message.user) if message.user_id else Q(blocked_username__iexact=message.username)
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
        ).exists()
        if active_ban:
            return Response(
                {'error': 'Cannot pin a message from a banned user'},
                status=status.HTTP_403_FORBIDDEN
            )

        now = timezone.now()
        is_expired = message.sticky_until and message.sticky_until < now

        # Validate message is currently the active sticky (not expired)
        if not message.is_pinned:
            return Response({
                'error': 'Message is not currently pinned',
                'action_hint': 'Use Pin Message to pin this message'
            }, status=status.HTTP_400_BAD_REQUEST)

        if is_expired:
            return Response({
                'error': 'Pin has expired. Use Re-pin to start a new pin session.',
                'action_hint': 'Use Re-pin (Pin Message) to start fresh'
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = MessagePinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        add_cents = serializer.validated_data['amount_cents']

        # Validate tier
        validation = validate_pin_amount(add_cents, is_add_to_pin=True)
        if not validation['valid']:
            return Response({
                'error': validation['error'],
                'tiers': get_tiers_for_frontend(),
            }, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Process payment with Stripe here

        add_amount = Decimal(add_cents) / 100

        # Get time extension for this tier
        extension_minutes = get_tier_duration_minutes(add_cents)

        # Capture previous values before modification
        previous_session_amount = message.current_pin_amount or Decimal('0')
        previous_sticky_until = message.sticky_until

        # Update lifetime total
        message.pin_amount_paid = (message.pin_amount_paid or Decimal('0')) + add_amount

        # Add to current session amount (increases defense against outbid)
        message.current_pin_amount = (message.current_pin_amount or Decimal('0')) + add_amount

        # Extend time from current expiry (stacks)
        message.sticky_until = message.sticky_until + timezone.timedelta(minutes=extension_minutes)

        # Update pinned_at to reflect the latest pin action
        message.pinned_at = timezone.now()

        message.save(update_fields=['pin_amount_paid', 'current_pin_amount', 'sticky_until', 'pinned_at'])

        # Update both caches: main messages list and pinned messages
        MessageCache.update_message(message)
        MessageCache.add_pinned_message(message)

        # Broadcast pin update via WebSocket
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from rest_framework.renderers import JSONRenderer
        import json as json_module

        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'

        # Convert serializer data to JSON-safe format (UUIDs become strings)
        serialized_data = MessageSerializer(message).data
        json_safe_data = json_module.loads(JSONRenderer().render(serialized_data))

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_pinned',
                'message': json_safe_data,
                'is_top_pin': True,  # After add-to-pin, message is still top pin
            }
        )

        # Calculate new time remaining
        new_time_remaining_seconds = int((message.sticky_until - now).total_seconds())

        return Response({
            'success': True,
            'message': MessageSerializer(message).data,
            'previous_cents': int(previous_session_amount * 100),
            'added_cents': add_cents,
            'new_session_cents': int(message.current_pin_amount * 100),
            'extension_minutes': extension_minutes,
            'new_time_remaining_seconds': new_time_remaining_seconds,
        })


class MessageHighlightView(APIView):
    """Toggle highlight status on a message (host-only, free action)."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id, username=None):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from rest_framework.renderers import JSONRenderer
        import json as json_module

        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        session_data = ChatSessionValidator.validate_session_token(
            token=session_token, chat_code=code, request=request,
        )

        # Host-only: verify the session user is the room host
        user_id = session_data.get('user_id')
        if not user_id or str(chat_room.host_id) != str(user_id):
            raise PermissionDenied("Only the host can highlight messages")

        # Toggle highlight
        message.is_highlight = not message.is_highlight
        if message.is_highlight:
            message.highlighted_at = timezone.now()
        else:
            message.highlighted_at = None
        message.save(update_fields=['is_highlight', 'highlighted_at'])

        # Update Redis cache
        MessageCache.update_message(message)
        if message.is_highlight:
            MessageCache.add_to_highlight_index(message)
            # Notify all users (except actor) about new highlight content
            from .utils.performance.cache import RoomNotificationCache
            actor_participation_id = RoomNotificationCache.resolve_participation_id(
                chat_room, username=session_data.get('username'), user_id=user_id
            )
            RoomNotificationCache.mark_new_content(str(chat_room.id), 'highlight', actor_user_id=actor_participation_id)
        else:
            MessageCache.remove_from_highlight_index(chat_room.id, str(message.id))

        # Broadcast via WebSocket
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'

        serialized_data = MessageSerializer(message).data
        json_safe_data = json_module.loads(JSONRenderer().render(serialized_data))

        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_highlight',
                'message': json_safe_data,
                'is_highlight': message.is_highlight,
            }
        )

        return Response({
            'success': True,
            'is_highlight': message.is_highlight,
        })


class BroadcastStickyView(APIView):
    """Toggle broadcast sticky — host-only, one at a time."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id, username=None):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from rest_framework.renderers import JSONRenderer
        import json as json_module

        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")
        session_data = ChatSessionValidator.validate_session_token(
            token=session_token, chat_code=code, request=request,
        )

        # Host-only
        user_id = session_data.get('user_id')
        if not user_id or str(chat_room.host_id) != str(user_id):
            raise PermissionDenied("Only the host can broadcast messages")

        # Toggle: if this message is already the broadcast, clear it. Otherwise set it.
        if chat_room.broadcast_message_id == message.id:
            # Unbroadcast
            chat_room.broadcast_message = None
            chat_room.save(update_fields=['broadcast_message'])

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{code}',
                {'type': 'broadcast_sticky_update', 'message': None}
            )
            return Response({'success': True, 'action': 'unbroadcast'})
        else:
            # Broadcast (replaces any existing broadcast)
            chat_room.broadcast_message = message
            chat_room.save(update_fields=['broadcast_message'])

            serialized = MessageSerializer(message).data
            json_safe = json_module.loads(JSONRenderer().render(serialized))

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{code}',
                {'type': 'broadcast_sticky_update', 'message': json_safe}
            )
            return Response({'success': True, 'action': 'broadcast', 'message_id': str(message.id)})


class RefreshSessionView(APIView):
    """Refresh an expiring or expired JWT session token.
    Logged-in users: validates auth_token, issues new JWT silently.
    Anonymous users: validates session_key match."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        old_token = request.data.get('session_token')

        if not old_token:
            return Response({"error": "no_token"}, status=status.HTTP_400_BAD_REQUEST)

        # Decode without verifying expiration (the whole point of refresh)
        payload = ChatSessionValidator.decode_token_ignore_expiry(old_token)
        if not payload:
            return Response({"error": "invalid_token"}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify chat_code matches
        if payload.get('chat_code') != code:
            return Response({"error": "token_mismatch"}, status=status.HTTP_401_UNAUTHORIZED)

        token_username = payload.get('username')
        token_user_id = payload.get('user_id')
        token_fingerprint = payload.get('fingerprint')
        token_session_key = payload.get('session_key')
        ip_address = get_client_ip(request)

        if token_user_id:
            # Logged-in user: verify they're still authenticated
            if not request.user.is_authenticated or str(request.user.id) != token_user_id:
                return Response({"error": "auth_required"}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            # Anonymous user: verify session_key matches
            if not token_session_key:
                # Old token without session_key — cannot safely refresh (no way to
                # verify the caller is the original owner). Force rejoin to get a proper token.
                return Response({"error": "token_upgrade_required"}, status=status.HTTP_401_UNAUTHORIZED)
            current_session_key = request.session.session_key
            if not current_session_key or current_session_key != token_session_key:
                return Response({"error": "session_mismatch"}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify participation still exists and user isn't banned
        from chats.models import ChatParticipation, SiteBan
        participation = ChatParticipation.objects.filter(
            chat_room=chat_room, username=token_username, is_active=True
        ).first()
        if not participation:
            return Response({"error": "no_participation"}, status=status.HTTP_401_UNAUTHORIZED)

        site_ban = SiteBan.is_banned(
            user=request.user if request.user.is_authenticated else None,
            ip_address=ip_address,
            fingerprint=token_fingerprint,
            session_key=token_session_key,
            chat_room=chat_room
        )
        if site_ban:
            return Response({"error": "banned"}, status=status.HTTP_403_FORBIDDEN)

        # Issue new JWT with current session_key
        current_session_key = request.session.session_key or token_session_key
        new_token = ChatSessionValidator.create_session_token(
            chat_code=code,
            username=token_username,
            user_id=token_user_id,
            fingerprint=token_fingerprint,
            session_key=current_session_key
        )

        return Response({"session_token": new_token, "username": token_username})



# FingerprintUsernameView removed — username persistence now uses Django sessions


class MyParticipationView(APIView):
    """Get current user's participation in a chat"""
    from .throttles import MyParticipationRateThrottle
    permission_classes = [permissions.AllowAny]
    throttle_classes = [MyParticipationRateThrottle]

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        fingerprint = request.query_params.get('fingerprint')
        session_key = request.session.session_key if not request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        participation = None
        anonymous_participations_list = []  # list of ChatParticipation

        # SECURITY (defense-in-depth): Only treat the request as authenticated
        # if DRF's auth pipeline actually ran a successful authenticator.
        # This guards against any future bug that might populate request.user
        # without a real authentication backend (which would otherwise allow
        # silent leakage of linked anonymous identities).
        is_truly_authenticated = (
            request.user.is_authenticated
            and getattr(request, 'successful_authenticator', None) is not None
        )
        if request.user.is_authenticated and not is_truly_authenticated:
            import logging
            logging.getLogger(__name__).warning(
                "MyParticipationView: request.user authenticated but "
                "successful_authenticator is None — treating as anonymous for safety"
            )

        # Dual sessions: Priority 1 - logged-in user participation
        if is_truly_authenticated:
            # Their REGISTERED participation (one and only one).
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                user=request.user,
                is_anonymous_identity=False,
            ).first()
            # ALL claimed anonymous identities owned by this user in this chat.
            anonymous_participations_list = list(
                ChatParticipation.objects.select_related('theme').filter(
                    chat_room=chat_room,
                    user=request.user,
                    is_anonymous_identity=True,
                ).order_by('first_joined_at')
            )
            linked_ids = {p.id for p in anonymous_participations_list}

            # Fallback: check current session (anonymous user just logged in).
            # Atomically claim by setting user + is_anonymous_identity on the row.
            # The user__isnull=True filter automatically guards against stealing
            # an already-claimed identity.
            current_session = request.session.session_key
            if current_session:
                session_anon = ChatParticipation.objects.select_related('theme').filter(
                    chat_room=chat_room,
                    session_key=current_session,
                    user__isnull=True,
                ).first()
                if session_anon and session_anon.id not in linked_ids:
                    # SECURITY: Refuse to claim a session-anon identity if the
                    # authenticated user is banned from this chat at the account level.
                    # Otherwise a banned user could launder a new anon identity by
                    # simply logging in after joining anonymously.
                    from .utils.security.blocking import check_if_blocked as _pre_check
                    pre_blocked, _ = _pre_check(
                        chat_room=chat_room,
                        username=session_anon.username,
                        user=request.user,
                    )
                    if not pre_blocked:
                        session_anon.user = request.user
                        session_anon.is_anonymous_identity = True
                        session_anon.save(update_fields=['user', 'is_anonymous_identity'])
                        anonymous_participations_list.append(session_anon)
                        linked_ids.add(session_anon.id)
            # SECURITY: No fingerprint-based identity claim. Fingerprints are forgeable
            # and used ONLY for ban enforcement, never to claim a participation.
        # Priority 2 - Anonymous user (session_key only, no fingerprint fallback)
        else:
            if session_key:
                participation = ChatParticipation.objects.select_related('theme').filter(
                    chat_room=chat_room,
                    session_key=session_key,
                    user__isnull=True
                ).first()

        if participation:
            # Check if this username is a reserved username
            username_is_reserved = False
            if participation.user and participation.user.reserved_username:
                username_is_reserved = (participation.username.lower() == participation.user.reserved_username.lower())
            elif not participation.user:
                # For anonymous participations, check if ANY registered user has reserved this username
                username_is_reserved = User.objects.filter(
                    reserved_username__iexact=participation.username
                ).exists()

            # Check if user is blocked
            from .utils.security.blocking import check_if_blocked
            is_blocked, _ = check_if_blocked(
                chat_room=chat_room,
                username=participation.username,
                fingerprint=fingerprint,
                session_key=session_key,
                user=request.user if is_truly_authenticated else None,
                ip_address=ip_address
            )

            # Serialize theme if present (BEFORE save to preserve select_related)
            theme_data = None
            if participation.theme:
                from .serializers import ChatThemeSerializer
                theme_data = ChatThemeSerializer(participation.theme).data

            # Update last_seen timestamp (do this AFTER accessing theme)
            participation.save()  # auto_now updates last_seen_at

            # Get seen_intros: global for registered users, per-chat for anonymous
            if is_truly_authenticated:
                seen_intros = request.user.seen_intros or {}
            else:
                seen_intros = participation.seen_intros or {}

            response_data = {
                'has_joined': True,
                'username': participation.username,
                'username_is_reserved': username_is_reserved,
                'avatar_url': participation.avatar_url,
                'first_joined_at': participation.first_joined_at,
                'last_seen_at': participation.last_seen_at,
                'theme': theme_data,
                'is_blocked': is_blocked,
                'seen_intros': seen_intros
            }

            # Include anonymous participations info if any exist (for identity chooser)
            extra_anons = [p for p in anonymous_participations_list if p.id != participation.id]
            if extra_anons:
                anon_list_payload = [{
                    'username': p.username,
                    'avatar_url': p.avatar_url,
                    'first_joined_at': p.first_joined_at,
                    'participation_id': str(p.id),
                } for p in extra_anons]
                response_data['anonymous_participations'] = anon_list_payload
                # Backwards-compat singular field
                response_data['anonymous_participation'] = anon_list_payload[0]

            return Response(response_data)

        # Authenticated user with only anonymous participation(s) (logged in after joining anonymously)
        if anonymous_participations_list:
            from .utils.security.blocking import check_if_blocked
            is_blocked, _ = check_if_blocked(
                chat_room=chat_room,
                username=None,
                fingerprint=fingerprint,
                user=request.user,
                ip_address=ip_address
            )
            seen_intros = request.user.seen_intros or {}
            anon_list_payload = [{
                'username': p.username,
                'avatar_url': p.avatar_url,
                'first_joined_at': p.first_joined_at,
                'participation_id': str(p.id),
            } for p in anonymous_participations_list]

            return Response({
                'has_joined': False,
                'is_blocked': is_blocked,
                'seen_intros': seen_intros,
                'anonymous_participations': anon_list_payload,
                # Backwards-compat singular field
                'anonymous_participation': anon_list_payload[0],
            })

        # No participation found - check if first-time visitor is blocked
        # This allows frontend to show "You are blocked" message immediately
        from .utils.security.blocking import check_if_blocked
        is_blocked, _ = check_if_blocked(
            chat_room=chat_room,
            username=None,  # No username yet (they haven't joined)
            fingerprint=fingerprint,
            user=request.user if is_truly_authenticated else None,
            ip_address=ip_address
        )

        return Response({
            'has_joined': False,
            'is_blocked': is_blocked
        })


class DismissIntroView(APIView):
    """Dismiss a feature intro so it won't show again"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, key, username=None):
        chat_room = get_chat_room_by_url(code, username)
        fingerprint = request.data.get('fingerprint')

        # Registered user: store globally on User model
        if request.user.is_authenticated:
            user = request.user
            if not user.seen_intros:
                user.seen_intros = {}
            user.seen_intros[key] = True
            user.save(update_fields=['seen_intros'])
            return Response({'success': True})

        # Anonymous user: store on ChatParticipation (session_key primary, fingerprint fallback)
        session_key = request.session.session_key
        participation = None
        if session_key:
            participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True
            ).first()
        if participation:
                if not participation.seen_intros:
                    participation.seen_intros = {}
                participation.seen_intros[key] = True
                participation.save(update_fields=['seen_intros'])
                return Response({'success': True})

        return Response({'success': False, 'error': 'No participation found'}, status=400)


class MarkRoomReadView(APIView):
    """Mark a room as read (Redis SET-based notification indicators)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from .utils.performance.cache import RoomNotificationCache
        chat_room = get_chat_room_by_url(code, username)
        room = request.data.get('room')
        if room not in RoomNotificationCache.VALID_ROOMS:
            return Response({'error': 'Invalid room'}, status=status.HTTP_400_BAD_REQUEST)

        # Identify user by participation ID (stable across session refreshes)
        session_token = request.data.get('session_token')
        identity = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                identity = RoomNotificationCache.resolve_participation_id(
                    chat_room,
                    username=session_data.get('username'),
                    user_id=session_data.get('user_id'),
                    session_key=session_data.get('session_key'),
                )
            except Exception:
                pass
        if not identity:
            return Response({'error': 'No identity'}, status=status.HTTP_400_BAD_REQUEST)

        RoomNotificationCache.mark_seen(str(chat_room.id), room, identity)
        return Response({'success': True})


class UpdateMyThemeView(APIView):
    """Update user's theme preference for a chat"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

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

        # Find the user's participation (session_key primary, fingerprint fallback)
        participation = None
        if request.user.is_authenticated:
            participation = ChatParticipation.objects.select_related('theme').filter(
                chat_room=chat_room,
                user=request.user,
                is_anonymous_identity=False,
                is_active=True
            ).first()
        else:
            session_key = request.session.session_key
            if session_key:
                participation = ChatParticipation.objects.select_related('theme').filter(
                    chat_room=chat_room,
                    session_key=session_key,
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


class UsernameValidationView(APIView):
    """Validate username availability for a specific chat room"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from chats.utils.username.validators import validate_username
        from django.core.exceptions import ValidationError as DjangoValidationError

        chat_room = get_chat_room_by_url(code, username)
        username = request.data.get('username', '').strip()
        fingerprint = request.data.get('fingerprint')

        if not username:
            raise ValidationError("Username is required")

        # Validate username format and profanity (MUST come before availability checks)
        try:
            username = validate_username(username)
        except DjangoValidationError as e:
            return Response({
                'available': False,
                'username': username,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

        # Normalize username for comparison (case-insensitive)
        username_lower = username.lower()

        # Check if username is reserved by someone else
        reserved_by_other = False
        reserved_user = User.objects.filter(reserved_username__iexact=username).first()
        if reserved_user:
            # It's reserved - check if it belongs to current user
            if not (request.user.is_authenticated and request.user.id == reserved_user.id):
                reserved_by_other = True

        # Check if username is temporarily reserved in Redis by another user
        if not reserved_by_other:
            reservation_key = f"username:reserved:{username_lower}"
            if cache.get(reservation_key):
                # Username is reserved in Redis - treat as unavailable
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
            elif not request.user.is_authenticated and (
                (request.session.session_key and existing_participation.session_key == request.session.session_key) or
                (fingerprint and existing_participation.fingerprint == fingerprint)
            ):
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

        # If available, reserve it temporarily in Redis to prevent race conditions
        if available:
            cache_ttl = config.USERNAME_ANONYMOUS_DICE_HOLD_TTL_MINUTES * 60  # Convert minutes to seconds
            reservation_key = f"username:reserved:{username_lower}"
            cache.set(reservation_key, True, cache_ttl)

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
    Rate limited to 20 requests per session/IP per chat per hour.
    """
    permission_classes = [permissions.AllowAny]

    @require_turnstile
    def post(self, request, code, username=None):
        from .utils.username.generator import generate_username
        import logging
        logger = logging.getLogger(__name__)

        # Get chat room
        chat_room = get_chat_room_by_url(code, username)

        # Get identity for rate limiting (session_key primary, fingerprint fallback)
        fingerprint = request.data.get('fingerprint')
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        identity_key = session_key or fingerprint or get_client_ip(request)

        # Check if this session already has a participation in this room
        # If so, return their existing username immediately (they're a returning user)
        existing_participation = None
        if session_key:
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                session_key=session_key,
                user__isnull=True,
                is_active=True
            ).first()

        if existing_participation:
            # Defense in depth: don't return reserved usernames to unauthenticated users
            is_reserved = User.objects.filter(
                reserved_username__iexact=existing_participation.username
            ).exists()
            if is_reserved and not request.user.is_authenticated:
                logger.info(f"[USERNAME_SUGGEST] Returning user has reserved username '{existing_participation.username}' - falling through to generation")
            else:
                logger.info(f"[USERNAME_SUGGEST] Returning user detected - identity_key={identity_key}, existing_username={existing_participation.username}")
                return Response({
                    'username': existing_participation.username,
                    'is_returning': True,
                    'remaining': 0,
                    'generation_remaining': 0
                })

        # Rate limiting key (per chat, per session/fingerprint/IP)
        rate_limit_key = f"username_suggest_limit:{code}:{identity_key}"
        current_count = cache.get(rate_limit_key, 0)

        logger.info(f"[USERNAME_SUGGEST] Starting - identity_key={identity_key}, chat_code={code}, current_count={current_count}")

        # Check chat-specific generation rate limit FIRST (before generating!)
        # NOTE: Rotation does NOT count against this limit (handled below)
        max_generations_per_chat = config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT
        if current_count >= max_generations_per_chat:
            # Per-chat rate limit hit - offer rotation through previously generated usernames
            logger.info(f"[USERNAME_PER_CHAT_LIMIT] Per-chat limit hit: current_count={current_count}, max={max_generations_per_chat}")

            # Get all usernames generated for this fingerprint IN THIS CHAT
            generated_per_chat_key = f"username:generated_for_chat:{code}:{identity_key}"
            generated_usernames = cache.get(generated_per_chat_key, set())
            logger.info(f"[USERNAME_PER_CHAT_LIMIT] Generated usernames from Redis (per-chat): {generated_usernames} (count: {len(generated_usernames)})")

            # Filter to only include usernames that are still available
            # NOTE: We skip Redis reservation check since those are the user's own usernames
            available_usernames = []
            for uname in generated_usernames:
                username_lower = uname.lower()

                # Check if reserved by a registered user
                is_reserved = User.objects.filter(reserved_username__iexact=username_lower).exists()
                logger.info(f"[USERNAME_PER_CHAT_LIMIT] {uname}: reserved_by_user={is_reserved}")
                if is_reserved:
                    continue

                # Check if used in any chat
                in_chat = ChatParticipation.objects.filter(username__iexact=username_lower).exists()
                logger.info(f"[USERNAME_PER_CHAT_LIMIT] {uname}: in_chat={in_chat}")
                if in_chat:
                    continue

                # Available! Add to list
                logger.info(f"[USERNAME_PER_CHAT_LIMIT] {uname}: AVAILABLE - adding to list")
                available_usernames.append(uname)  # Preserve original capitalization

            if available_usernames:
                # Sort alphabetically for consistent rotation
                available_usernames.sort()
                logger.info(f"[USERNAME_ROTATION_DEBUG] Available usernames after sort: {available_usernames}")

                # Get rotation index for this identity IN THIS CHAT
                rotation_key = f"username:rotation_index:{code}:{identity_key}"
                current_index = cache.get(rotation_key, 0)
                logger.info(f"[USERNAME_ROTATION_DEBUG] rotation_key={rotation_key}")
                logger.info(f"[USERNAME_ROTATION_DEBUG] current_index from Redis: {current_index}")
                logger.info(f"[USERNAME_ROTATION_DEBUG] len(available_usernames): {len(available_usernames)}")

                # Get the next username in rotation
                selected_username = available_usernames[current_index % len(available_usernames)]
                logger.info(f"[USERNAME_ROTATION_DEBUG] selected_username: {selected_username}")

                # Increment rotation index for next time
                next_index = (current_index + 1) % len(available_usernames)
                logger.info(f"[USERNAME_ROTATION_DEBUG] next_index calculated: {next_index}")
                cache.set(rotation_key, next_index, 3600)  # 1 hour TTL
                logger.info(f"[USERNAME_ROTATION_DEBUG] cache.set() called, verifying...")
                verify_index = cache.get(rotation_key, 'KEY_NOT_FOUND')
                logger.info(f"[USERNAME_ROTATION_DEBUG] Verification - index after set: {verify_index}")

                # Calculate generation_remaining for response (global limit)
                attempts_key = f"username:generation_attempts:{identity_key}"
                global_attempts = cache.get(attempts_key, 0)
                global_max = config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL
                generation_remaining = max(0, global_max - global_attempts)

                # Return the username (rotation does NOT count against per-chat limit)
                logger.info(f"[USERNAME_PER_CHAT_LIMIT] Returning rotated username: {selected_username}")
                return Response({
                    'username': selected_username,
                    'remaining': 0,  # Per-chat generation limit exhausted
                    'generation_remaining': generation_remaining  # Global limit still available
                })
            else:
                # No previous usernames available (all taken or TTL expired)
                logger.info(f"[USERNAME_PER_CHAT_LIMIT] No available usernames for rotation")
                # Need to get generation_remaining to include in error response
                attempts_key = f"username:generation_attempts:{identity_key}"
                global_attempts = cache.get(attempts_key, 0)
                global_max = config.MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL
                generation_remaining = max(0, global_max - global_attempts)

                return Response({
                    'error': f'Generation limit reached. You can generate up to {max_generations_per_chat} NEW usernames per hour for this chat.',
                    'remaining': 0,
                    'generation_remaining': generation_remaining
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # Per-chat limit not hit - proceed with NEW username generation
        logger.info(f"[USERNAME_SUGGEST] Per-chat limit OK ({current_count}/{max_generations_per_chat}), generating new username...")

        # Generate username with identity_key (session_key preferred)
        username, generation_remaining = generate_username(identity_key, code)

        logger.info(f"[USERNAME_SUGGEST] After generate_username - username={username}, generation_remaining={generation_remaining}")

        if not username:
            # If rate limited (0 attempts left), rotate through previous usernames they can reuse
            if generation_remaining == 0:
                # Get all usernames generated for this fingerprint IN THIS CHAT
                generated_per_chat_key = f"username:generated_for_chat:{code}:{identity_key}"
                generated_usernames = cache.get(generated_per_chat_key, set())
                logger.info(f"[USERNAME_ROTATION] Identity key: {identity_key}")
                logger.info(f"[USERNAME_ROTATION] Generated usernames from Redis (per-chat): {generated_usernames} (count: {len(generated_usernames)})")

                # Filter to only include usernames that are still available
                # (not taken by someone else since generation)
                # NOTE: We skip Redis reservation check since those are the user's own usernames
                available_usernames = []
                for uname in generated_usernames:
                    username_lower = uname.lower()

                    # Check if reserved by a registered user
                    is_reserved = User.objects.filter(reserved_username__iexact=username_lower).exists()
                    logger.info(f"[USERNAME_ROTATION] {uname}: reserved_by_user={is_reserved}")
                    if is_reserved:
                        continue

                    # Check if used in any chat
                    in_chat = ChatParticipation.objects.filter(username__iexact=username_lower).exists()
                    logger.info(f"[USERNAME_ROTATION] {uname}: in_chat={in_chat}")
                    if in_chat:
                        continue

                    # Available! Add to list
                    logger.info(f"[USERNAME_ROTATION] {uname}: AVAILABLE - adding to list")
                    available_usernames.append(uname)  # Preserve original capitalization

                if available_usernames:
                    # Sort alphabetically for consistent rotation
                    available_usernames.sort()

                    # Get rotation index for this identity IN THIS CHAT
                    rotation_key = f"username:rotation_index:{code}:{identity_key}"
                    current_index = cache.get(rotation_key, 0)

                    # Get the next username in rotation
                    selected_username = available_usernames[current_index % len(available_usernames)]

                    # Increment rotation index for next time
                    next_index = (current_index + 1) % len(available_usernames)
                    cache.set(rotation_key, next_index, 3600)  # 1 hour TTL

                    # Return the username (rotation does NOT count against per-chat limit)
                    return Response({
                        'username': selected_username,
                        'remaining': config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT - current_count,  # Chat-specific generation limit
                        'generation_remaining': 0  # Still rate limited globally, but rotating through previous usernames
                    })
                else:
                    # No previous usernames available (all taken or TTL expired)
                    return Response({
                        'error': 'Maximum username generation attempts exceeded. No previously generated usernames are available.',
                        'generation_remaining': 0
                    }, status=status.HTTP_429_TOO_MANY_REQUESTS)

            # Return error with remaining attempts from the new generation limit
            return Response({
                'error': 'Unable to generate a unique username. Please try again later.',
                'generation_remaining': generation_remaining
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Increment rate limit counter (only on NEW generation success)
        # NOTE: This is the chat-specific generation rate limit (configurable via Constance)
        # separate from the global generation rate limit in generate_username()
        # Rotation does NOT increment this counter (returns early above)
        new_count = current_count + 1
        cache.set(rate_limit_key, new_count, 3600)  # 1 hour TTL

        return Response({
            'username': username,
            'remaining': config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT - new_count,  # Chat-specific generation limit remaining
            'generation_remaining': generation_remaining  # Global generation limit remaining
        })


class MessageReactionToggleView(APIView):
    """
    Toggle a reaction on a message (add or remove).
    If user already reacted, remove the reaction.
    If user hasn't reacted, add the new reaction (replacing any existing reaction).
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id, username=None):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Validate session token
        session_token = request.data.get('session_token')
        username = request.data.get('username')
        fingerprint = request.data.get('fingerprint')

        if not session_token:
            raise PermissionDenied("Session token is required")

        # Validate the JWT session token
        try:
            session_data = ChatSessionValidator.validate_session_token(
                token=session_token,
                chat_code=code,
                username=username,
                request=request,
            )
        except Exception as e:
            raise

        # Validate emoji
        serializer = MessageReactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emoji = serializer.validated_data['emoji']

        # Determine user identity
        user = request.user if request.user.is_authenticated else None
        session_key_value = session_data.get('session_key') if not user else None

        # Anonymous users must have a valid session_key for reaction dedup
        if not user and not session_key_value:
            raise PermissionDenied("Session expired. Please refresh the page to continue reacting.")

        # Check if user already has a reaction with THIS SPECIFIC emoji
        if user:
            existing_reaction = MessageReaction.objects.filter(
                message=message,
                user=user,
                emoji=emoji
            ).first()
        else:
            existing_reaction = MessageReaction.objects.filter(
                message=message,
                session_key=session_key_value,
                emoji=emoji
            ).first()

        # Toggle: if exists, remove it; if not, add it
        if existing_reaction:
            existing_reaction.delete()
            action = 'removed'
            reaction_data = None
            # Atomic Redis decrement (O(1), no Postgres recount)
            MessageCache.decrement_reaction(chat_room.id, str(message_id), emoji)
        else:
            existing_reaction = MessageReaction.objects.create(
                message=message,
                emoji=emoji,
                user=user,
                session_key=session_key_value,
                username=username
            )
            action = 'added'
            reaction_data = MessageReactionSerializer(existing_reaction).data
            # Atomic Redis increment (O(1), no Postgres recount)
            MessageCache.increment_reaction(chat_room.id, str(message_id), emoji)

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


class MessageDetailView(APIView):
    """Fetch a single message by ID.

    Powers the reply-preview popup: clicking a reply preview (or chain-walking
    through nested replies) needs the parent message data without paginating
    through the timeline. Cache-first; falls back to PostgreSQL.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id, username=None):
        chat_room = get_chat_room_by_url(code, username)
        session_token = request.query_params.get('session_token')

        # Identity (for has_reacted)
        current_session_key = None
        current_user_id = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                current_session_key = session_data.get('session_key')
                current_user_id = session_data.get('user_id')
            except Exception:
                pass  # Invalid token — proceed without has_reacted

        # Cache-first
        msg_dict = MessageCache.get_message_by_id(chat_room.id, str(message_id))
        source = 'redis'

        if msg_dict is None:
            # Cache miss: fall back to PostgreSQL via the canonical serializer
            try:
                msg = Message.objects.select_related('user', 'reply_to', 'chat_room').get(
                    id=message_id, chat_room=chat_room, is_deleted=False,
                )
            except Message.DoesNotExist:
                return Response({'detail': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)
            username_is_reserved = MessageCache._compute_username_is_reserved(msg)
            msg_dict = MessageCache._serialize_message(msg, username_is_reserved)
            source = 'postgresql'
        else:
            # Defensive: cache hit may include a soft-deleted message if
            # eviction hasn't caught up. Don't surface deleted messages.
            if msg_dict.get('is_deleted'):
                return Response({'detail': 'Message not found'}, status=status.HTTP_404_NOT_FOUND)

        # Convert relative voice URL to absolute
        if msg_dict.get('voice_url') and request:
            msg_dict['voice_url'] = request.build_absolute_uri(msg_dict['voice_url'])

        # Attach reactions + has_reacted (same logic as MessageListView)
        reactions = MessageCache.batch_get_reactions(chat_room.id, [msg_dict['id']]).get(msg_dict['id'], [])
        if current_session_key or current_user_id:
            q_filter = Q()
            if current_session_key:
                q_filter |= Q(session_key=current_session_key)
            if current_user_id:
                q_filter |= Q(user_id=current_user_id)
            user_emojis = set(
                MessageReaction.objects.filter(
                    Q(message_id=msg_dict['id']) & q_filter
                ).values_list('emoji', flat=True)
            )
            for r in reactions:
                r['has_reacted'] = r['emoji'] in user_emojis
        else:
            for r in reactions:
                r['has_reacted'] = False
        msg_dict['reactions'] = reactions

        # is_banned + is_spotlight (same logic as the list view)
        author_lower = msg_dict.get('username', '').lower()
        from django.utils import timezone as tz
        msg_dict['is_banned'] = ChatBlock.objects.filter(
            chat_room=chat_room, blocked_username=author_lower,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())).exists()
        msg_dict['is_spotlight'] = ChatParticipation.objects.filter(
            chat_room=chat_room, is_spotlight=True, username=msg_dict.get('username', ''),
        ).exists()

        return Response({'message': msg_dict, 'source': source})


class MessageReactionsListView(APIView):
    """Get all reactions for a specific message"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id, username=None):
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Get current user's session_key and user_id for has_reacted
        session_token = request.query_params.get('session_token')
        current_session_key = None
        current_user_id = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                current_session_key = session_data.get('session_key')
                current_user_id = session_data.get('user_id')
            except Exception:
                pass

        reactions = MessageReaction.objects.filter(message=message).order_by('-created_at')
        serializer = MessageReactionSerializer(reactions, many=True)

        # Group reactions by emoji with counts and most recent timestamp
        from collections import defaultdict
        emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0, 'latest': None})
        user_emojis = set()  # Track current user's emojis

        for reaction in reactions:
            emoji = reaction.emoji
            emoji_counts[emoji]['emoji'] = emoji
            emoji_counts[emoji]['count'] += 1
            # Track most recent reaction time (reactions ordered by -created_at)
            if emoji_counts[emoji]['latest'] is None:
                emoji_counts[emoji]['latest'] = reaction.created_at
            # Check if this is the current user's reaction (by session_key or user_id)
            is_user_reaction = (
                (current_session_key and reaction.session_key == current_session_key) or
                (current_user_id and reaction.user_id and str(reaction.user_id) == current_user_id)
            )
            if is_user_reaction:
                user_emojis.add(emoji)

        # Build summary: top 20 by popularity (tiebreak: most recent first) + user's extras
        all_sorted = sorted(emoji_counts.values(), key=lambda x: (-x['count'], -(x['latest'].timestamp() if x['latest'] else 0)))
        top_20 = all_sorted[:20]
        # Include any user reactions not already in top 20
        top_emojis = {r['emoji'] for r in top_20}
        user_extras = [r for r in all_sorted if r['emoji'] in user_emojis and r['emoji'] not in top_emojis]
        top_reactions = top_20 + user_extras

        # Add has_reacted and strip internal 'latest' field
        for reaction in top_reactions:
            reaction['has_reacted'] = reaction['emoji'] in user_emojis
            reaction.pop('latest', None)

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

    def post(self, request, code, username=None):
        from .utils.security.auth import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied

        # Get chat room
        chat_room = get_chat_room_by_url(code, username)

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
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code, request=request)
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
        from chatpop.utils.media import MediaStorage
        from .utils.security.auth import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied
        import os
        import re
        import logging

        logger = logging.getLogger(__name__)

        # Log incoming request
        logger.info(f"🎵 [VoiceStream] Incoming request for: {storage_path}")
        logger.info(f"🎵 [VoiceStream] Range header: {request.META.get('HTTP_RANGE', 'NONE')}")
        logger.info(f"🎵 [VoiceStream] User-Agent: {request.META.get('HTTP_USER_AGENT', 'NONE')[:100]}")

        # Check if this is a public file (avatars are public - no auth required)
        # In DEBUG mode, also allow media_analysis files (for dev photo picker)
        from django.conf import settings
        is_public_file = storage_path.startswith('avatars/') or (
            settings.DEBUG and storage_path.startswith('media_analysis/')
        )

        if is_public_file:
            logger.info(f"🎵 [VoiceStream] Public file access (avatar): {storage_path}")
        else:
            # Extract chat code and validate session for non-public files
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
            except PermissionDenied:
                logger.error(f"🎵 [VoiceStream] Permission denied for: {storage_path}")
                return JsonResponse({
                    'error': 'Invalid session token'
                }, status=401)

        try:
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
            content_type = 'application/octet-stream'  # default
            ext = storage_path.lower().split('.')[-1] if '.' in storage_path else ''

            # Audio types
            if ext in ('m4a', 'mp4') and 'voice' in storage_path:
                content_type = 'audio/mp4'
            elif ext == 'webm' and 'voice' in storage_path:
                content_type = 'audio/webm'
            elif ext in ('mp3', 'mpeg'):
                content_type = 'audio/mpeg'
            elif ext == 'ogg':
                content_type = 'audio/ogg'
            elif ext == 'wav':
                content_type = 'audio/wav'
            # Image types
            elif ext in ('jpg', 'jpeg'):
                content_type = 'image/jpeg'
            elif ext == 'png':
                content_type = 'image/png'
            elif ext == 'webp':
                content_type = 'image/webp'
            elif ext == 'gif':
                content_type = 'image/gif'
            elif ext in ('heic', 'heif'):
                content_type = 'image/heic'
            elif ext == 'svg':
                content_type = 'image/svg+xml'
            # Video types
            elif ext == 'mp4':
                content_type = 'video/mp4'
            elif ext == 'webm':
                content_type = 'video/webm'
            elif ext == 'mov':
                content_type = 'video/quicktime'
            elif ext == 'm4v':
                content_type = 'video/x-m4v'

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
            # Public files (avatars) can be cached publicly, other files are private
            if is_public_file:
                response['Cache-Control'] = 'public, max-age=86400'  # Cache avatars for 24 hours
            else:
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


class UserAvatarView(APIView):
    """
    Proxy endpoint for registered user avatars.

    URL: /api/chats/media/avatars/user/{user_id}

    This endpoint allows registered users to change their avatar without
    invalidating cached messages. The URL stays constant, but the underlying
    avatar file can change.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        from django.http import HttpResponseRedirect, Http404
        from accounts.models import User
        from chatpop.utils.media import get_fallback_dicebear_url

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise Http404("User not found")

        # If user has stored avatar, redirect to it
        if user.avatar_url:
            # avatar_url is stored as relative path like /api/chats/media/avatars/uuid.svg
            # Redirect to the actual file
            return HttpResponseRedirect(user.avatar_url)

        # Fallback to DiceBear URL if no stored avatar
        if user.reserved_username:
            fallback_url = get_fallback_dicebear_url(user.reserved_username)
            return HttpResponseRedirect(fallback_url)

        # No reserved_username either - return 404
        raise Http404("User has no avatar")


class PhotoUploadView(APIView):
    """
    Upload a photo message.
    Available to all chat participants if photo_enabled=True on the chat room.
    Compresses images to max 1920px, 80% quality JPEG.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, code, username=None):
        from .utils.security.auth import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied
        from chatpop.utils.media import save_photo_message, get_photo_message_url, PHOTO_CONTENT_TYPE_TO_EXT
        from PIL import Image
        from io import BytesIO
        from django.core.files.base import ContentFile
        import logging
        logger = logging.getLogger(__name__)

        # Get chat room
        chat_room = get_chat_room_by_url(code, username)

        # Check if photo messages are enabled for this chat
        if not chat_room.photo_enabled:
            return Response({
                'error': 'Photo messages are not enabled for this chat room'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate session token
        session_token = request.data.get('session_token') or request.headers.get('X-Chat-Session-Token')
        if not session_token:
            return Response({
                'error': 'Session token required to upload photos'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code, request=request)
        except PermissionDenied:
            return Response({
                'error': 'Invalid session token'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get uploaded file
        photo_file = request.FILES.get('photo')
        if not photo_file:
            return Response({
                'error': 'No photo file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (configurable via constance)
        max_file_size_mb = config.PHOTO_MAX_FILE_SIZE_MB
        if photo_file.size > max_file_size_mb * 1024 * 1024:
            return Response({
                'error': f'Photo too large (max {max_file_size_mb}MB)'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = list(PHOTO_CONTENT_TYPE_TO_EXT.keys())
        if photo_file.content_type not in allowed_types:
            return Response({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"[PhotoUpload] Received file: {photo_file.content_type}, {photo_file.size} bytes")

            # Open image with Pillow
            img = Image.open(photo_file)

            # Apply EXIF orientation (fixes sideways mobile photos)
            from PIL import ImageOps
            try:
                transposed = ImageOps.exif_transpose(img)
                if transposed is not None:
                    img = transposed
            except Exception as exif_error:
                logger.warning(f"[PhotoUpload] EXIF transpose failed (ignoring): {exif_error}")

            # Convert RGBA to RGB (remove alpha channel for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Get original dimensions
            original_width, original_height = img.size

            # Resize if larger than configured max dimension
            max_dimension = config.PHOTO_MAX_DIMENSION
            if original_width > max_dimension or original_height > max_dimension:
                if original_width > original_height:
                    new_width = max_dimension
                    new_height = int(original_height * (max_dimension / original_width))
                else:
                    new_height = max_dimension
                    new_width = int(original_width * (max_dimension / original_height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                logger.info(f"[PhotoUpload] Resized from {original_width}x{original_height} to {new_width}x{new_height}")

            # Get final dimensions
            final_width, final_height = img.size

            # Save as JPEG with 80% quality
            output = BytesIO()
            img.save(output, format='JPEG', quality=80, optimize=True)
            output.seek(0)

            compressed_size = len(output.getvalue())
            logger.info(f"[PhotoUpload] Compressed to {compressed_size} bytes")

            # Save to storage
            storage_path, storage_type = save_photo_message(
                ContentFile(output.read()),
                content_type='image/jpeg'
            )

            photo_url = get_photo_message_url(storage_path)

            return Response({
                'photo_url': photo_url,
                'width': final_width,
                'height': final_height,
                'storage_path': storage_path,
                'storage_type': storage_type
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Failed to upload photo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VideoUploadView(APIView):
    """
    Upload a video message.
    Available to all chat participants if video_enabled=True on the chat room.
    Validates duration (max 30 seconds) and generates thumbnail.
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request, code, username=None):
        from .utils.security.auth import ChatSessionValidator
        from rest_framework.exceptions import PermissionDenied
        from chatpop.utils.media import (
            save_video_message, save_video_thumbnail,
            get_video_message_url, VIDEO_CONTENT_TYPE_TO_EXT
        )
        from django.core.files.base import ContentFile
        import subprocess
        import tempfile
        import os
        import logging
        import json
        logger = logging.getLogger(__name__)

        # Get chat room
        chat_room = get_chat_room_by_url(code, username)

        # Check if video messages are enabled for this chat
        if not chat_room.video_enabled:
            return Response({
                'error': 'Video messages are not enabled for this chat room'
            }, status=status.HTTP_403_FORBIDDEN)

        # Validate session token
        session_token = request.data.get('session_token') or request.headers.get('X-Chat-Session-Token')
        if not session_token:
            return Response({
                'error': 'Session token required to upload videos'
            }, status=status.HTTP_401_UNAUTHORIZED)

        try:
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code, request=request)
        except PermissionDenied:
            return Response({
                'error': 'Invalid session token'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Get uploaded file
        video_file = request.FILES.get('video')
        if not video_file:
            return Response({
                'error': 'No video file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 50MB)
        if video_file.size > 50 * 1024 * 1024:
            return Response({
                'error': 'Video too large (max 50MB)'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = list(VIDEO_CONTENT_TYPE_TO_EXT.keys())
        if video_file.content_type not in allowed_types:
            return Response({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            logger.info(f"[VideoUpload] Received file: {video_file.content_type}, {video_file.size} bytes")

            # Save to temp file for ffprobe/ffmpeg processing
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
                for chunk in video_file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                # Get video duration using ffprobe
                probe_cmd = [
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', '-show_streams', tmp_path
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                probe_data = json.loads(probe_result.stdout)
                duration = float(probe_data.get('format', {}).get('duration', 0))

                # Extract video dimensions from the video stream
                video_width = None
                video_height = None
                for stream in probe_data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        video_width = int(stream['width']) if 'width' in stream else None
                        video_height = int(stream['height']) if 'height' in stream else None
                        # Check for rotation (phone videos record landscape with rotation metadata)
                        rotation = 0
                        # Check tags first (older ffprobe)
                        rotation_tag = stream.get('tags', {}).get('rotate', '0')
                        rotation = int(rotation_tag)
                        # Check side_data_list (newer ffprobe)
                        if rotation == 0:
                            for sd in stream.get('side_data_list', []):
                                if 'rotation' in sd:
                                    rotation = int(sd['rotation'])
                                    break
                        # Swap dimensions for 90/270 degree rotations
                        if video_width and video_height and abs(rotation) in (90, 270):
                            video_width, video_height = video_height, video_width
                        break

                logger.info(f"[VideoUpload] Video duration: {duration} seconds, dimensions: {video_width}x{video_height}")

                # Validate duration (max 30 seconds)
                if duration > 30:
                    return Response({
                        'error': 'Video too long (max 30 seconds)'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Generate thumbnail from first frame
                thumb_path = tmp_path + '_thumb.jpg'
                thumb_cmd = [
                    'ffmpeg', '-y', '-i', tmp_path,
                    '-vframes', '1', '-f', 'image2',
                    '-vf', 'scale=480:-1',  # Scale to 480px width
                    thumb_path
                ]
                subprocess.run(thumb_cmd, capture_output=True)

                # Save video to storage
                video_file.seek(0)
                storage_path, storage_type = save_video_message(
                    video_file,
                    content_type=video_file.content_type
                )
                video_url = get_video_message_url(storage_path)

                # Save thumbnail to storage
                thumbnail_url = None
                if os.path.exists(thumb_path):
                    with open(thumb_path, 'rb') as thumb_file:
                        # Extract video filename from storage path
                        video_filename = os.path.basename(storage_path)
                        thumb_storage_path, _ = save_video_thumbnail(
                            ContentFile(thumb_file.read()),
                            video_filename
                        )
                        thumbnail_url = get_video_message_url(thumb_storage_path)
                    os.unlink(thumb_path)

            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            return Response({
                'video_url': video_url,
                'duration': round(duration, 2),
                'thumbnail_url': thumbnail_url,
                'width': video_width,
                'height': video_height,
                'storage_path': storage_path,
                'storage_type': storage_type
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Failed to upload video: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BlockUserView(APIView):
    """Block a user from the chat (host only)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from .utils.security.blocking import block_participation
        from .utils.security.auth import ChatSessionValidator
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"[BLOCK] Starting block request for chat {code}")
        logger.info(f"[BLOCK] Request data: {request.data}")

        chat_room = get_chat_room_by_url(code, username)
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
                chat_code=code,
                request=request,
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
            # Anonymous user (by session_key, fallback to fingerprint)
            session_key = session_data.get('session_key')
            logger.info(f"[BLOCK] Looking for anonymous host participation: session_key={session_key}")
            host_participation = None
            if session_key:
                host_participation = ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    session_key=session_key,
                    user__isnull=True
                ).first()
            # SECURITY: No fingerprint fallback for identity lookup. Fingerprints are
            # forgeable and only used for ban enforcement.

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
        # Accept both 'username' and 'blocked_username' for backwards compatibility
        username = request.data.get('blocked_username') or request.data.get('username')
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
            # Block the user across all identifiers (consolidated into single ChatBlock row)
            # Get IP address from participation (saved when they joined) for tracking
            ip_address = participation.ip_address
            ban_tier = request.data.get('ban_tier', 'session')
            if ban_tier not in ('session', 'fingerprint_ip', 'ip'):
                ban_tier = 'session'
            logger.info(f"[BLOCK] Calling block_participation with chat_room={chat_room.id}, participation={participation.id}, blocked_by={host_participation.id}, ip_address={ip_address}, ban_tier={ban_tier}")
            block_created = block_participation(
                chat_room=chat_room,
                participation=participation,
                blocked_by=host_participation,
                ip_address=ip_address,
                ban_tier=ban_tier
            )
            logger.info(f"[BLOCK] block_participation succeeded, created consolidated block with ID: {block_created.id}")

            # Ban cascade: a banned user should never be in the spotlight.
            try:
                if block_created.blocked_user_id:
                    ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        user_id=block_created.blocked_user_id,
                        is_spotlight=True,
                    ).update(is_spotlight=False)
                else:
                    ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        username__iexact=participation.username,
                        is_spotlight=True,
                    ).update(is_spotlight=False)
            except Exception as e:
                logger.warning(f"[BLOCK] Failed to clear spotlight on ban: {e}")

            # Ban cascade: auto-unpin all pinned messages authored by the banned user.
            # A banned user's content should not be elevated in the sticky area.
            try:
                banned_usernames = [participation.username.lower()]
                if block_created.blocked_user_id:
                    banned_usernames = list(
                        ChatParticipation.objects.filter(
                            chat_room=chat_room,
                            user_id=block_created.blocked_user_id,
                        ).values_list('username', flat=True)
                    )
                    banned_usernames = [u.lower() for u in banned_usernames if u]

                pinned_msgs = Message.objects.filter(
                    chat_room=chat_room,
                    is_pinned=True,
                    is_deleted=False,
                    username__iregex=r'^(' + '|'.join(banned_usernames) + r')$',
                ) if banned_usernames else Message.objects.none()

                for msg in pinned_msgs:
                    msg.is_pinned = False
                    msg.pinned_at = None
                    msg.sticky_until = None
                    msg.save(update_fields=['is_pinned', 'pinned_at', 'sticky_until'])
                    MessageCache.update_message(msg)
                    MessageCache.remove_pinned_message(chat_room.id, str(msg.id))
                    logger.info(f"[BLOCK] Auto-unpinned message {msg.id} by banned user")

                # Broadcast updated pinned list so all clients reflect the change
                if pinned_msgs.exists() or True:  # Always send to clear stale client state
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    remaining_pins = MessageCache.get_pinned_messages(chat_room.id)
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        f'chat_{chat_room.code}',
                        {
                            'type': 'message_unpinned',
                            'message_id': '',  # Multiple unpinned; clients use pinned_messages list
                            'pinned_messages': remaining_pins,
                        }
                    )
            except Exception as e:
                logger.warning(f"[BLOCK] Failed to auto-unpin on ban: {e}")

            # Ban cascade: unhighlight all messages by banned user
            try:
                highlighted_by_banned = Message.objects.filter(
                    chat_room=chat_room,
                    is_highlight=True,
                    username__in=[u for u in banned_usernames],
                )
                if highlighted_by_banned.exists():
                    for msg in highlighted_by_banned:
                        msg.is_highlight = False
                        msg.save(update_fields=['is_highlight'])
                        MessageCache.update_message(msg)
                        MessageCache.remove_from_highlight_index(chat_room.id, str(msg.id))
                    logger.info(f"[BLOCK] Unhighlighted messages by banned user")
            except Exception as e:
                logger.warning(f"[BLOCK] Failed to unhighlight on ban: {e}")

            # Ban cascade: clear broadcast if it's from the banned user
            try:
                if chat_room.broadcast_message_id:
                    bm = chat_room.broadcast_message
                    if bm and bm.username.lower() in [u.lower() for u in banned_usernames]:
                        chat_room.broadcast_message = None
                        chat_room.save(update_fields=['broadcast_message'])
                        from channels.layers import get_channel_layer
                        from asgiref.sync import async_to_sync
                        channel_layer_bc = get_channel_layer()
                        async_to_sync(channel_layer_bc.group_send)(
                            f'chat_{chat_room.code}',
                            {'type': 'broadcast_sticky_update', 'message': None}
                        )
                        logger.info(f"[BLOCK] Cleared broadcast sticky from banned user")
            except Exception as e:
                logger.warning(f"[BLOCK] Failed to clear broadcast on ban: {e}")

            # SECURITY: Revoke all outstanding JWT tokens for this user in this chat.
            # For account-level bans, bump epoch for EVERY linked identity (reserved + anon)
            # so the user cannot continue posting under any of their other identities.
            try:
                ChatSessionValidator.bump_epoch(chat_room.code, participation.username)
                if block_created.blocked_user_id:
                    linked_usernames = ChatParticipation.objects.filter(
                        chat_room=chat_room,
                        user_id=block_created.blocked_user_id,
                    ).values_list('username', flat=True)
                    for linked_username in linked_usernames:
                        if linked_username and linked_username != participation.username:
                            try:
                                ChatSessionValidator.bump_epoch(chat_room.code, linked_username)
                            except Exception as e:
                                logger.warning(f"[BLOCK] Failed to bump JWT epoch for linked identity {linked_username}: {e}")
            except Exception as e:
                logger.warning(f"[BLOCK] Failed to bump JWT epoch: {e}")

            # Determine which identifiers were blocked
            blocked_identifiers = []
            if block_created.blocked_username:
                blocked_identifiers.append('username')
            if block_created.blocked_fingerprint:
                blocked_identifiers.append('fingerprint')
            if block_created.blocked_user:
                blocked_identifiers.append('user_account')
            if block_created.blocked_ip_address:
                blocked_identifiers.append('ip_address')

            logger.info(f"[BLOCK] Blocked identifiers: {blocked_identifiers}")

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

            # Determine all usernames to kick (account-level ban cascades to linked identities)
            usernames_to_kick = [participation.username]
            if block_created.blocked_user_id:
                linked_usernames = list(ChatParticipation.objects.filter(
                    chat_room=chat_room,
                    user_id=block_created.blocked_user_id,
                ).values_list('username', flat=True))
                for linked_username in linked_usernames:
                    if linked_username and linked_username not in usernames_to_kick:
                        usernames_to_kick.append(linked_username)

            # Send eviction events to each banned identity
            for kick_username in usernames_to_kick:
                async_to_sync(channel_layer.group_send)(
                    room_group_name,
                    {
                        'type': 'user_kicked',
                        'username': kick_username,
                        'message': 'You have been removed from this chat by the host.',
                    }
                )

            # Notify all clients that this user is now banned (for badge updates)
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'user_ban_status',
                    'username': participation.username,
                    'is_banned': True,
                }
            )

            return Response({
                'success': True,
                'message': f'User {participation.username} has been blocked',
                'block_id': str(block_created.id),
                'blocked_identifiers': blocked_identifiers
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

    def post(self, request, code, username=None):
        from .utils.security.blocking import unblock_participation

        chat_room = get_chat_room_by_url(code, username)

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

        # Notify all clients that this user is unbanned (for badge updates)
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'user_ban_status',
                'username': participation.username,
                'is_banned': False,
            }
        )

        return Response({
            'success': True,
            'message': f'User {participation.username} has been unblocked',
            'blocks_removed': count
        })


class BlockedUsersListView(APIView):
    """Get list of blocked users in a chat (host only)"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code, username=None):
        from .utils.security.blocking import get_blocked_users

        chat_room = get_chat_room_by_url(code, username)

        # Verify user is the host
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can view blocked users")

        # Get all blocked users
        blocked_users = get_blocked_users(chat_room)

        return Response({
            'blocked_users': blocked_users,
            'count': len(blocked_users)
        })


class MutedUsersInChatView(APIView):
    """Get list of users the current user has muted that participate in this chat."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, code, username=None):
        from .models import UserBlock
        from .utils.performance.cache import UserBlockCache

        chat_room = get_chat_room_by_url(code, username)
        blocked_usernames = UserBlockCache.get_blocked_usernames(request.user.id)

        if not blocked_usernames:
            return Response({'muted_users': [], 'count': 0})

        participants = set(ChatParticipation.objects.filter(
            chat_room=chat_room,
            username__in=blocked_usernames
        ).values_list('username', flat=True))

        if not participants:
            return Response({'muted_users': [], 'count': 0})

        blocks = UserBlock.objects.filter(
            blocker=request.user,
            blocked_username__in=participants
        ).order_by('-created_at')

        return Response({
            'muted_users': [
                {'username': b.blocked_username, 'muted_at': b.created_at.isoformat()}
                for b in blocks
            ],
            'count': blocks.count()
        })


# ========================
# Spotlight Views
# ========================

def _dispatch_spotlight_event(chat_room, action, target_username):
    """Broadcast a spotlight add/remove event to all WS clients in the room."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'chat_{chat_room.code}',
            {
                'type': 'spotlight_update',
                'action': action,
                'username': target_username,
            }
        )
    except Exception:
        # Best-effort WebSocket dispatch — never fail the request because of WS dispatch
        pass


class SpotlightListView(APIView):
    """
    List all currently-spotlighted participations in a chat.

    Available to ALL chat viewers — clients need this to render stars/pills
    consistently for spotlighted users.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        ps = ChatParticipation.objects.filter(
            chat_room=chat_room, is_spotlight=True
        ).order_by('-last_seen_at')
        spotlight_users = [{
            'username': p.username,
            'avatar_url': p.avatar_url,
            'last_seen_at': p.last_seen_at.isoformat() if p.last_seen_at else None,
        } for p in ps]
        return Response({
            'spotlight_users': spotlight_users,
            'count': len(spotlight_users),
        })


def _is_username_banned_in_chat(chat_room, target_username):
    """Return True if target_username has any active username-level ChatBlock."""
    from django.utils import timezone as tz
    return ChatBlock.objects.filter(
        chat_room=chat_room,
        blocked_username__iexact=target_username,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
    ).exists()


def _is_user_banned_in_chat(chat_room, user_id):
    """Return True if user_id has any active account-level ChatBlock."""
    if not user_id:
        return False
    from django.utils import timezone as tz
    return ChatBlock.objects.filter(
        chat_room=chat_room,
        blocked_user_id=user_id,
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
    ).exists()


class SpotlightAddView(APIView):
    """Host-only: add a participation to the spotlight."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can manage the spotlight.")

        target_username = (request.data.get('username') or '').strip()
        if not target_username:
            raise ValidationError("username is required")

        # Disallow spotlighting the host themselves
        host_reserved = (chat_room.host.reserved_username or '')
        if host_reserved and target_username.lower() == host_reserved.lower():
            raise ValidationError("Cannot spotlight the chat host.")

        try:
            participation = ChatParticipation.objects.get(
                chat_room=chat_room,
                username__iexact=target_username,
            )
        except ChatParticipation.DoesNotExist:
            return Response(
                {'detail': 'Participation not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Reject banned users (username-level OR account-level)
        if _is_username_banned_in_chat(chat_room, participation.username) or \
                _is_user_banned_in_chat(chat_room, participation.user_id):
            raise ValidationError("Cannot spotlight a banned user.")

        if participation.is_spotlight:
            return Response({
                'success': True,
                'already_spotlighted': True,
                'username': participation.username,
            })

        participation.is_spotlight = True
        participation.save(update_fields=['is_spotlight'])

        _dispatch_spotlight_event(chat_room, 'add', participation.username)

        return Response({
            'success': True,
            'username': participation.username,
        })


class SpotlightRemoveView(APIView):
    """Host-only: remove a participation from the spotlight."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can manage the spotlight.")

        target_username = (request.data.get('username') or '').strip()
        if not target_username:
            raise ValidationError("username is required")

        try:
            participation = ChatParticipation.objects.get(
                chat_room=chat_room,
                username__iexact=target_username,
            )
        except ChatParticipation.DoesNotExist:
            return Response(
                {'detail': 'Participation not found'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not participation.is_spotlight:
            return Response({
                'success': True,
                'already_removed': True,
                'username': participation.username,
            })

        participation.is_spotlight = False
        participation.save(update_fields=['is_spotlight'])

        _dispatch_spotlight_event(chat_room, 'remove', participation.username)

        return Response({
            'success': True,
            'username': participation.username,
        })


class ParticipantSearchView(APIView):
    """
    Host-only autocomplete: search this chat's participations by username prefix.

    Excludes:
      - The host themselves
      - Already-spotlighted participations
      - Banned users (username-level OR account-level)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_throttles(self):
        from .throttles import ParticipantSearchRateThrottle
        return [ParticipantSearchRateThrottle()]

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        if request.user != chat_room.host:
            raise PermissionDenied("Only the host can search participants.")

        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'results': []})

        from django.utils import timezone as tz

        host_reserved = (chat_room.host.reserved_username or '')
        qs = ChatParticipation.objects.filter(
            chat_room=chat_room,
            username__istartswith=q,
            is_spotlight=False,
        )
        if host_reserved:
            qs = qs.exclude(username__iexact=host_reserved)

        # Compute active bans for exclusion (small N per chat)
        active_blocks = ChatBlock.objects.filter(
            chat_room=chat_room,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=tz.now())
        )
        banned_usernames_lower = set(
            (u or '').lower()
            for u in active_blocks.values_list('blocked_username', flat=True)
            if u
        )
        banned_user_ids = set(
            active_blocks.exclude(blocked_user__isnull=True)
            .values_list('blocked_user_id', flat=True)
        )

        candidates = list(qs.order_by('-last_seen_at')[:50])
        results = []
        seen = set()
        for p in candidates:
            key = p.username.lower()
            if key in seen:
                continue
            if key in banned_usernames_lower:
                continue
            if p.user_id and p.user_id in banned_user_ids:
                continue
            seen.add(key)
            results.append({
                'username': p.username,
                'avatar_url': p.avatar_url,
                'last_seen_at': p.last_seen_at.isoformat() if p.last_seen_at else None,
            })
            if len(results) >= 10:
                break

        return Response({'results': results})



class MessageDeleteView(APIView):
    """Soft delete a message (host only)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id, username=None):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"[MESSAGE_DELETE] Starting delete request for message {message_id} in chat {code}")

        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        try:
            session_data = ChatSessionValidator.validate_session_token(
                token=session_token,
                chat_code=code,
                request=request,
            )
            logger.info(f"[MESSAGE_DELETE] Session validated: {session_data}")
        except Exception as e:
            logger.error(f"[MESSAGE_DELETE] Session validation failed: {str(e)}")
            raise PermissionDenied(f"Invalid session: {str(e)}")

        # Verify user is the host
        if not request.user.is_authenticated or request.user != chat_room.host:
            logger.error(f"[MESSAGE_DELETE] User is not the host")
            raise PermissionDenied("Only the host can delete messages")

        # Check if already deleted
        if message.is_deleted:
            return Response({
                'success': True,
                'message': 'Message was already deleted',
                'already_deleted': True
            })

        # Soft delete: Set is_deleted flag to True
        message.is_deleted = True
        message.save()
        logger.info(f"[MESSAGE_DELETE] Message {message_id} marked as deleted in database")

        # Remove from Redis cache
        MessageCache.remove_message(chat_room.id, str(message_id))
        logger.info(f"[MESSAGE_DELETE] Message {message_id} removed from cache")

        # If deleted message was highlighted, clear the highlight
        if message.is_highlight:
            message.is_highlight = False
            message.save(update_fields=['is_highlight'])
            logger.info(f"[MESSAGE_DELETE] Cleared highlight for deleted message {message_id}")

        # If deleted message was the broadcast, clear it
        if chat_room.broadcast_message_id == message.id:
            chat_room.broadcast_message = None
            chat_room.save(update_fields=['broadcast_message'])

        # Broadcast deletion event via WebSocket — include the authoritative pinned
        # messages list so all clients show the correct next pin if the deleted
        # message was pinned.
        remaining_pins = MessageCache.get_pinned_messages(chat_room.id)
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{code}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_deleted',
                'message_id': str(message_id),
                'pinned_messages': remaining_pins,
            }
        )
        logger.info(f"[MESSAGE_DELETE] Deletion event broadcast via WebSocket")

        return Response({
            'success': True,
            'message': 'Message deleted successfully',
            'message_id': str(message_id)
        })


class MessageUnpinView(APIView):
    """Unpin a message (host only). Removes pin status but keeps the message visible."""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, message_id, username=None):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        ChatSessionValidator.validate_session_token(
            token=session_token,
            chat_code=code,
            request=request,
        )

        # Verify user is the host
        if not request.user.is_authenticated or request.user != chat_room.host:
            raise PermissionDenied("Only the host can unpin messages")

        if not message.is_pinned:
            return Response({
                'success': True,
                'message': 'Message was not pinned',
                'already_unpinned': True
            })

        # Unpin the message
        message.is_pinned = False
        message.pinned_at = None
        message.sticky_until = None
        # Keep pin_amount_paid for record-keeping
        message.save()

        # Update cache — update the message data AND remove from the pinned sorted set
        # so the bid floor resets to the next valid pin's amount.
        MessageCache.update_message(message)
        MessageCache.remove_pinned_message(chat_room.id, str(message_id))

        # Broadcast unpin event via WebSocket — include the authoritative pinned
        # messages list so all clients can immediately show the correct next pin
        # without relying on local state (which may not have all pins loaded).
        remaining_pins = MessageCache.get_pinned_messages(chat_room.id)
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chat_{code}',
            {
                'type': 'message_unpinned',
                'message_id': str(message_id),
                'pinned_messages': remaining_pins,
            }
        )

        return Response({
            'success': True,
            'message': 'Message unpinned successfully',
            'message_id': str(message_id)
        })


# ==============================================================================
# USER-TO-USER BLOCKING (Site-Wide Personal Muting - UserBlock)
# ==============================================================================
# These views handle site-wide user-to-user blocking (registered users only).
# UserBlock: Personal muting across ALL chats (like Twitter/Discord block).
# Different from ChatBlock (above), which is chat-specific host moderation.
# ==============================================================================


class UserBlockView(APIView):
    """Block a user site-wide (registered users only)"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.JSONParser, parsers.FormParser]

    def post(self, request):
        """Block a user by username"""
        from .models import UserBlock
        from .utils.performance.cache import UserBlockCache
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        blocked_username = request.data.get('username', '').strip()

        if not blocked_username:
            raise ValidationError({"username": ["Username is required"]})

        # Prevent self-blocking (case-insensitive)
        if blocked_username.lower() == request.user.reserved_username.lower():
            raise ValidationError({"username": ["You cannot block yourself"]})

        # Validate username exists in system (defense in depth against SQL injection)
        # Check if username exists in ChatParticipation (any chat)
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
    parser_classes = [parsers.JSONParser, parsers.FormParser]

    def post(self, request):
        """Unblock a user by username"""
        from .models import UserBlock
        from .utils.performance.cache import UserBlockCache
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
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
        from .models import UserBlock

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


class ChatRoomCreateFromPhotoView(APIView):
    """
    Create a chat room from a photo analysis suggestion (AI-generated rooms).

    Security: Only accepts media_analysis_id and suggestion_index.
    All room data (name, description, theme) is pulled from the
    server-side PhotoAnalysis record to prevent client tampering.

    Note: Uses system user as host - discover rooms are community-owned,
    not controlled by any individual user.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from media_analysis.models import PhotoAnalysis
        from .serializers import ChatRoomCreateFromPhotoSerializer
        from django.contrib.auth import get_user_model
        import logging

        User = get_user_model()
        logger = logging.getLogger(__name__)

        # Validate input (media_analysis_id + room_code)
        serializer = ChatRoomCreateFromPhotoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        media_analysis_id = serializer.validated_data['media_analysis_id']
        room_code = serializer.validated_data['room_code']

        try:
            # Fetch PhotoAnalysis record (server-side source of truth)
            media_analysis = PhotoAnalysis.objects.get(id=media_analysis_id)

            # Build allowed room codes set: AI suggestions + similar_rooms
            allowed_codes = {}  # code -> suggestion_data (name, description)

            # Add all AI-generated suggestions
            suggestions = media_analysis.suggestions.get('suggestions', [])
            for suggestion in suggestions:
                key = suggestion['key']
                allowed_codes[key] = {
                    'name': suggestion['name'],
                    'description': suggestion.get('description', '')
                }

            # Add similar room codes (if embedding exists)
            # Note: Similarity search is optional and may not be implemented yet
            similar_room_codes = set()
            if media_analysis.suggestions_embedding is not None:
                try:
                    from media_analysis.utils.room_matching import find_similar_rooms
                    similar_rooms = find_similar_rooms(
                        embedding_vector=media_analysis.suggestions_embedding,
                        exclude_photo_id=str(media_analysis.id)
                    )
                    for room in similar_rooms:
                        similar_room_codes.add(room.room_code)
                        # Similar rooms don't need metadata - they already exist
                except (ImportError, Exception) as e:
                    logger.warning(f"Similarity search skipped (non-fatal): {str(e)}")

            # Validate room_code is in allowed set
            is_ai_suggestion = room_code in allowed_codes
            is_similar_room = room_code in similar_room_codes

            if not (is_ai_suggestion or is_similar_room):
                raise ValidationError(
                    f"Invalid room selection. Room code '{room_code}' is not in the list of "
                    f"suggestions or similar rooms for this photo analysis."
                )

            logger.info(f"User selected room code '{room_code}' (AI suggestion: {is_ai_suggestion}, similar room: {is_similar_room})")

            # Check if room already exists
            existing_chat = ChatRoom.objects.filter(
                code=room_code,
                source=ChatRoom.SOURCE_AI,
                is_active=True
            ).first()

            # Track selection REGARDLESS of whether room already exists
            media_analysis.selected_suggestion_code = room_code
            media_analysis.selected_at = timezone.now()
            media_analysis.save(update_fields=['selected_suggestion_code', 'selected_at', 'updated_at'])

            if existing_chat:
                # Room already exists - user is joining existing room
                logger.info(f"User joining existing room '{room_code}' (ID: {existing_chat.id})")
                return Response({
                    'created': False,
                    'chat_room': ChatRoomSerializer(existing_chat).data,
                    'message': 'Joined existing chat room'
                }, status=status.HTTP_200_OK)

            # Room doesn't exist - create it (only possible for AI suggestions)
            if not is_ai_suggestion:
                # This should never happen - similar rooms must already exist
                raise ValidationError(
                    f"Room '{room_code}' does not exist. Cannot create from similar room."
                )

            # Get the discover system user (created via fixture)
            # UUID: 00000000-0000-0000-0000-000000000001
            try:
                system_user = User.objects.get(reserved_username='discover')
            except User.DoesNotExist:
                # Fallback: create if fixture wasn't loaded
                system_user, created = User.objects.get_or_create(
                    email='discover@system.chatpop.app',
                    defaults={
                        'reserved_username': 'discover',
                        'is_active': False,  # Cannot login
                    }
                )
                if created:
                    system_user.set_unusable_password()
                    system_user.save()
                    logger.info("Created discover system user (fixture not loaded)")

            # Get default theme for AI rooms (dark-mode)
            theme = ChatTheme.objects.filter(theme_id='dark-mode').first()
            if not theme:
                # Fallback to any theme if dark-mode doesn't exist
                theme = ChatTheme.objects.first()

            # Extract suggestion data for new room
            suggestion_data = allowed_codes[room_code]
            chat_name = suggestion_data['name']
            chat_description = suggestion_data['description']

            # Create the chat room with server-validated data
            chat_room = ChatRoom.objects.create(
                code=room_code,
                name=chat_name,
                description=chat_description,
                host=system_user,  # System user owns all discover rooms
                source=ChatRoom.SOURCE_AI,  # Mark as AI-generated
                access_mode=ChatRoom.ACCESS_PUBLIC,  # AI rooms are always public
                theme=theme,
                theme_locked=False,  # Users can change theme
                photo_enabled=True,
                voice_enabled=False,
                video_enabled=False,
                is_active=True
            )

            logger.info(f"Created new room '{room_code}' (ID: {chat_room.id}) from photo analysis")

            return Response({
                'created': True,
                'chat_room': ChatRoomSerializer(chat_room).data,
                'message': 'Chat room created successfully'
            }, status=status.HTTP_201_CREATED)

        except PhotoAnalysis.DoesNotExist:
            raise ValidationError("Photo analysis not found")
        except Exception as e:
            logger.error(f"Failed to create/join chat from photo: {str(e)}", exc_info=True)
            raise ValidationError(f"Failed to process room selection: {str(e)}")


class ChatRoomCreateFromLocationView(APIView):
    """
    Create a chat room from a location analysis suggestion (AI-generated rooms).

    Security: Only accepts location_analysis_id and room_code.
    All room data (name, description, theme) is pulled from the
    server-side LocationAnalysis and Suggestion records to prevent client tampering.

    Note: Uses system user as host - discover rooms are community-owned,
    not controlled by any individual user.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from media_analysis.models import LocationAnalysis, Suggestion
        from .serializers import ChatRoomCreateFromLocationSerializer
        from django.contrib.auth import get_user_model
        import logging

        User = get_user_model()
        logger = logging.getLogger(__name__)

        # Validate input (location_analysis_id + room_code)
        serializer = ChatRoomCreateFromLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        location_analysis_id = serializer.validated_data['location_analysis_id']
        room_code = serializer.validated_data['room_code']

        try:
            # Fetch LocationAnalysis record (server-side source of truth)
            location_analysis = LocationAnalysis.objects.get(id=location_analysis_id)

            # Build allowed room codes from linked suggestions
            allowed_codes = {}  # code -> suggestion_data (name, description)
            for suggestion in location_analysis.suggestions.all():
                allowed_codes[suggestion.key] = {
                    'name': suggestion.name,
                    'description': suggestion.description or f"Chat about {suggestion.name}"
                }

            # Validate room_code is in allowed set
            if room_code not in allowed_codes:
                raise ValidationError(
                    f"Invalid room selection. Room code '{room_code}' is not in the list of "
                    f"suggestions for this location analysis."
                )

            logger.info(f"User selected location room code '{room_code}'")

            # Check if room already exists
            existing_chat = ChatRoom.objects.filter(
                code=room_code,
                source=ChatRoom.SOURCE_AI,
                is_active=True
            ).first()

            # Track selection REGARDLESS of whether room already exists
            location_analysis.selected_suggestion_code = room_code
            location_analysis.selected_at = timezone.now()
            location_analysis.save(update_fields=['selected_suggestion_code', 'selected_at'])

            if existing_chat:
                # Room already exists - user is joining existing room
                logger.info(f"User joining existing location room '{room_code}' (ID: {existing_chat.id})")
                return Response({
                    'created': False,
                    'chat_room': ChatRoomSerializer(existing_chat).data,
                    'message': 'Joined existing chat room'
                }, status=status.HTTP_200_OK)

            # Room doesn't exist - create it
            # Get the discover system user (created via fixture)
            try:
                system_user = User.objects.get(reserved_username='discover')
            except User.DoesNotExist:
                # Fallback: create if fixture wasn't loaded
                system_user, created = User.objects.get_or_create(
                    email='discover@system.chatpop.app',
                    defaults={
                        'reserved_username': 'discover',
                        'is_active': False,  # Cannot login
                    }
                )
                if created:
                    system_user.set_unusable_password()
                    system_user.save()
                    logger.info("Created discover system user (fixture not loaded)")

            # Get default theme for AI rooms (dark-mode)
            theme = ChatTheme.objects.filter(theme_id='dark-mode').first()
            if not theme:
                # Fallback to any theme if dark-mode doesn't exist
                theme = ChatTheme.objects.first()

            # Extract suggestion data for new room
            suggestion_data = allowed_codes[room_code]
            chat_name = suggestion_data['name']
            chat_description = suggestion_data['description']

            # Create the chat room with server-validated data
            chat_room = ChatRoom.objects.create(
                code=room_code,
                name=chat_name,
                description=chat_description,
                host=system_user,  # System user owns all discover rooms
                source=ChatRoom.SOURCE_AI,  # Mark as AI-generated
                access_mode=ChatRoom.ACCESS_PUBLIC,  # AI rooms are always public
                theme=theme,
                theme_locked=False,  # Users can change theme
                photo_enabled=True,
                voice_enabled=False,
                video_enabled=False,
                is_active=True
            )

            logger.info(f"Created new location room '{room_code}' (ID: {chat_room.id})")

            return Response({
                'created': True,
                'chat_room': ChatRoomSerializer(chat_room).data,
                'message': 'Chat room created successfully'
            }, status=status.HTTP_201_CREATED)

        except LocationAnalysis.DoesNotExist:
            raise ValidationError("Location analysis not found")
        except Exception as e:
            logger.error(f"Failed to create/join chat from location: {str(e)}", exc_info=True)
            raise ValidationError(f"Failed to process room selection: {str(e)}")


class ChatRoomCreateFromMusicView(APIView):
    """
    Create a chat room from a music analysis suggestion (AI-generated rooms).

    Security: Only accepts music_analysis_id and room_code.
    All room data (name, description, theme) is pulled from the
    server-side MusicAnalysis and Suggestion records to prevent client tampering.

    Note: Uses system user as host - discover rooms are community-owned,
    not controlled by any individual user.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from media_analysis.models import MusicAnalysis, Suggestion
        from .serializers import ChatRoomCreateFromMusicSerializer
        from django.contrib.auth import get_user_model
        import logging

        User = get_user_model()
        logger = logging.getLogger(__name__)

        # Validate input (music_analysis_id + room_code)
        serializer = ChatRoomCreateFromMusicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        music_analysis_id = serializer.validated_data['music_analysis_id']
        room_code = serializer.validated_data['room_code']

        try:
            # Fetch MusicAnalysis record (server-side source of truth)
            music_analysis = MusicAnalysis.objects.get(id=music_analysis_id)

            # Build allowed room codes from linked suggestions
            allowed_codes = {}  # code -> suggestion_data (name, description)
            for suggestion in music_analysis.suggestions.all():
                allowed_codes[suggestion.key] = {
                    'name': suggestion.name,
                    'description': suggestion.description or f"Chat about {suggestion.name}"
                }

            # Validate room_code is in allowed set
            if room_code not in allowed_codes:
                raise ValidationError(
                    f"Invalid room selection. Room code '{room_code}' is not in the list of "
                    f"suggestions for this music analysis."
                )

            logger.info(f"User selected music room code '{room_code}'")

            # Check if room already exists
            existing_chat = ChatRoom.objects.filter(
                code=room_code,
                source=ChatRoom.SOURCE_AI,
                is_active=True
            ).first()

            # Track selection REGARDLESS of whether room already exists
            music_analysis.selected_suggestion_code = room_code
            music_analysis.selected_at = timezone.now()
            music_analysis.save(update_fields=['selected_suggestion_code', 'selected_at'])

            if existing_chat:
                # Room already exists - user is joining existing room
                logger.info(f"User joining existing music room '{room_code}' (ID: {existing_chat.id})")
                return Response({
                    'created': False,
                    'chat_room': ChatRoomSerializer(existing_chat).data,
                    'message': 'Joined existing chat room'
                }, status=status.HTTP_200_OK)

            # Room doesn't exist - create it
            # Get the discover system user (created via fixture)
            try:
                system_user = User.objects.get(reserved_username='discover')
            except User.DoesNotExist:
                # Fallback: create if fixture wasn't loaded
                system_user, created = User.objects.get_or_create(
                    email='discover@system.chatpop.app',
                    defaults={
                        'reserved_username': 'discover',
                        'is_active': False,  # Cannot login
                    }
                )
                if created:
                    system_user.set_unusable_password()
                    system_user.save()
                    logger.info("Created discover system user (fixture not loaded)")

            # Get default theme for AI rooms (dark-mode)
            theme = ChatTheme.objects.filter(theme_id='dark-mode').first()
            if not theme:
                # Fallback to any theme if dark-mode doesn't exist
                theme = ChatTheme.objects.first()

            # Extract suggestion data for new room
            suggestion_data = allowed_codes[room_code]
            chat_name = suggestion_data['name']
            chat_description = suggestion_data['description']

            # Create the chat room with server-validated data
            chat_room = ChatRoom.objects.create(
                code=room_code,
                name=chat_name,
                description=chat_description,
                host=system_user,  # System user owns all discover rooms
                source=ChatRoom.SOURCE_AI,  # Mark as AI-generated
                access_mode=ChatRoom.ACCESS_PUBLIC,  # AI rooms are always public
                theme=theme,
                theme_locked=False,  # Users can change theme
                photo_enabled=True,
                voice_enabled=False,
                video_enabled=False,
                is_active=True
            )

            logger.info(f"Created new music room '{room_code}' (ID: {chat_room.id})")

            return Response({
                'created': True,
                'chat_room': ChatRoomSerializer(chat_room).data,
                'message': 'Chat room created successfully'
            }, status=status.HTTP_201_CREATED)

        except MusicAnalysis.DoesNotExist:
            raise ValidationError("Music analysis not found")
        except Exception as e:
            logger.error(f"Failed to create/join chat from music: {str(e)}", exc_info=True)
            raise ValidationError(f"Failed to process room selection: {str(e)}")


class PhotoAnalysisView(APIView):
    """
    Analyze an uploaded photo with OpenAI Vision API and generate chat topic suggestions.

    Local Mode (no AWS keys): Saves to media/ directory, processes with OpenAI directly
    Production Mode (AWS keys): Returns S3 upload URL for frontend to upload directly
    """
    permission_classes = [permissions.AllowAny]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        import base64
        import json
        import re
        import logging

        logger = logging.getLogger(__name__)

        # Check if OpenAI is configured
        if not settings.OPENAI_API_KEY:
            return Response({
                'error': 'OpenAI API is not configured. Please set OPENAI_API_KEY in your environment.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # Get uploaded file
        photo = request.FILES.get('photo')
        if not photo:
            return Response({
                'error': 'No photo file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
        if photo.content_type not in allowed_types:
            return Response({
                'error': f'Invalid file type. Allowed types: {", ".join(allowed_types)}'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size (max 20MB - OpenAI limit)
        if photo.size > 20 * 1024 * 1024:
            return Response({
                'error': 'Photo too large (max 20MB)'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Read and encode image to base64
            photo_data = photo.read()
            img_base64 = base64.b64encode(photo_data).decode('utf-8')

            # Determine MIME type from file extension
            mime_type = photo.content_type
            logger.info(f"[PHOTO_ANALYSIS] Encoding {mime_type} image ({len(photo_data)} bytes)")

            # Call OpenAI Vision API
            from openai import OpenAI
            from constance import config
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Get prompt from Constance (editable in Django admin)
            prompt = config.PHOTO_ANALYSIS_PROMPT

            logger.info("[PHOTO_ANALYSIS] Calling OpenAI Vision API...")

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective vision model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{img_base64}",
                                    "detail": "low"  # Low detail for faster/cheaper analysis
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.8,  # Higher temperature for more creative suggestions
                response_format={"type": "json_object"}  # Force JSON output
            )

            # Parse response
            result_text = response.choices[0].message.content.strip()
            logger.info(f"[PHOTO_ANALYSIS] OpenAI response: {result_text}")

            # Extract JSON from markdown code blocks if present
            import json
            import re

            # Remove markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(1)

            result = json.loads(result_text)

            # Validate response structure
            if 'suggestions' not in result or not isinstance(result['suggestions'], list):
                raise ValueError("Invalid response format from OpenAI")

            # Ensure we have at least 3 suggestions (OpenAI should return 10)
            suggestions = result['suggestions']
            if len(suggestions) < 3:
                raise ValueError("Insufficient suggestions generated")

            logger.info(f"[PHOTO_ANALYSIS] Successfully generated {len(suggestions)} suggestions")

            return Response({
                'suggestions': suggestions,
                'count': len(suggestions)
            }, status=status.HTTP_200_OK)

        except json.JSONDecodeError as e:
            logger.error(f"[PHOTO_ANALYSIS] JSON decode error: {str(e)}, raw response: {result_text}")
            return Response({
                'error': 'Failed to parse AI response. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"[PHOTO_ANALYSIS] Error: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Failed to analyze photo: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# ADMIN/STAFF MODERATION VIEWS
# =============================================================================

class IsStaffUser(permissions.BasePermission):
    """Allow only staff/superuser access."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


class AdminChatDetailView(APIView):
    """
    Get chat room details by UUID for admin moderation.
    Staff can view any chat without joining.
    """
    permission_classes = [IsStaffUser]

    def get(self, request, room_id):
        from .serializers import ChatRoomSerializer

        chat_room = get_object_or_404(ChatRoom, id=room_id)

        # Get chat URL for reference
        is_ai_generated = chat_room.source == ChatRoom.SOURCE_AI
        if is_ai_generated:
            chat_url = f"/chat/discover/{chat_room.code}"
        else:
            chat_url = f"/chat/{chat_room.host.reserved_username}/{chat_room.code}"

        return Response({
            'chat_room': ChatRoomSerializer(chat_room).data,
            'chat_url': chat_url,
            'is_ai_generated': is_ai_generated,
        })


class AdminMessageListView(APIView):
    """
    Get messages for a chat room by UUID for admin moderation.
    Returns all messages including deleted ones for transparency.
    Includes participation data (IP, fingerprint) for ban functionality.
    """
    permission_classes = [IsStaffUser]

    def get(self, request, room_id):
        from .serializers import MessageSerializer

        chat_room = get_object_or_404(ChatRoom, id=room_id)

        # Get messages from cache or database (include all, even deleted for admin view)
        messages = Message.objects.filter(chat_room=chat_room).select_related('user').order_by('created_at')

        # Optional: limit for pagination
        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))
        messages = messages[offset:offset + limit]

        # Build a map of username -> participation data for this chat
        participations = ChatParticipation.objects.filter(chat_room=chat_room)
        participation_map = {}
        for p in participations:
            participation_map[p.username.lower()] = {
                'user_id': str(p.user.id) if p.user else None,
                'fingerprint': p.fingerprint,
                'ip_address': p.ip_address,
            }

        # Serialize messages and add participation data
        message_data = MessageSerializer(messages, many=True).data
        for msg in message_data:
            username_lower = msg.get('username', '').lower()
            if username_lower in participation_map:
                msg['participation'] = participation_map[username_lower]
            else:
                msg['participation'] = None

        return Response({
            'messages': message_data,
            'count': len(message_data),
        })


class AdminMessageDeleteView(APIView):
    """
    Delete a message as admin/staff.
    Same as host deletion but available to all staff.
    """
    permission_classes = [IsStaffUser]

    def post(self, request, room_id, message_id):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        import logging
        logger = logging.getLogger(__name__)

        chat_room = get_object_or_404(ChatRoom, id=room_id)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room)

        logger.info(f"[ADMIN_DELETE] Staff {request.user.username} deleting message {message_id}")

        # Check if already deleted
        if message.is_deleted:
            return Response({
                'success': True,
                'message': 'Message was already deleted',
                'already_deleted': True
            })

        # Soft delete
        message.is_deleted = True
        message.save()
        logger.info(f"[ADMIN_DELETE] Message {message_id} marked as deleted")

        # Remove from Redis cache
        MessageCache.remove_message(chat_room.id, str(message_id))
        logger.info(f"[ADMIN_DELETE] Message {message_id} removed from cache")

        # Broadcast deletion via WebSocket
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_deleted',
                'message_id': str(message_id)
            }
        )

        return Response({
            'success': True,
            'message': 'Message deleted',
            'deleted_by': request.user.username,
        })


class AdminMessageUnpinView(APIView):
    """
    Unpin a message as admin/staff.
    Removes pinned status and updates cache.
    """
    permission_classes = [IsStaffUser]

    def post(self, request, room_id, message_id):
        import logging
        logger = logging.getLogger(__name__)

        chat_room = get_object_or_404(ChatRoom, id=room_id)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room)

        if not message.is_pinned:
            return Response({
                'success': True,
                'message': 'Message was not pinned',
                'already_unpinned': True
            })

        logger.info(f"[ADMIN_UNPIN] Staff {request.user.username} unpinning message {message_id}")

        # Unpin the message
        message.is_pinned = False
        message.pinned_at = None
        message.sticky_until = None
        # Keep pin_amount_paid for record-keeping
        message.save()

        # Update cache
        MessageCache.update_message(message)
        logger.info(f"[ADMIN_UNPIN] Message {message_id} unpinned and cache updated")

        return Response({
            'success': True,
            'message': 'Message unpinned',
            'unpinned_by': request.user.username,
        })


class AdminSiteBanListView(APIView):
    """List all site bans."""
    permission_classes = [IsStaffUser]

    def get(self, request):
        from .models import SiteBan

        bans = SiteBan.objects.all().select_related('banned_user', 'banned_by')

        # Optional filter by active only
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            from django.db.models import Q
            from django.utils import timezone
            bans = bans.filter(
                is_active=True
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )

        ban_list = []
        for ban in bans:
            ban_list.append({
                'id': str(ban.id),
                'banned_user': ban.banned_user.username if ban.banned_user else None,
                'banned_user_id': str(ban.banned_user.id) if ban.banned_user else None,
                'banned_ip_address': ban.banned_ip_address,
                'banned_fingerprint': ban.banned_fingerprint[:8] + '...' if ban.banned_fingerprint else None,
                'banned_fingerprint_full': ban.banned_fingerprint,
                'reason': ban.reason,
                'banned_by': ban.banned_by.username if ban.banned_by else None,
                'created_at': ban.created_at.isoformat(),
                'expires_at': ban.expires_at.isoformat() if ban.expires_at else None,
                'is_active': ban.is_active,
                'is_expired': ban.is_expired(),
            })

        return Response({
            'bans': ban_list,
            'count': len(ban_list),
        })


class AdminSiteBanCreateView(APIView):
    """Create a site-wide ban."""
    permission_classes = [IsStaffUser]

    def post(self, request):
        from .models import SiteBan
        from django.contrib.auth import get_user_model
        import logging
        logger = logging.getLogger(__name__)

        User = get_user_model()

        # Get ban parameters
        user_id = request.data.get('user_id')
        username = request.data.get('username')  # Alternative to user_id
        ip_address = request.data.get('ip_address')
        fingerprint = request.data.get('fingerprint')
        reason = request.data.get('reason', '')
        expires_at = request.data.get('expires_at')  # ISO format or null for permanent

        # At least one identifier required
        if not any([user_id, username, ip_address, fingerprint]):
            return Response({
                'error': 'At least one identifier required (user_id, username, ip_address, or fingerprint)'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not reason:
            return Response({
                'error': 'Reason is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Resolve user if username provided
        banned_user = None
        if user_id:
            banned_user = get_object_or_404(User, id=user_id)
        elif username:
            banned_user = User.objects.filter(username__iexact=username).first()
            # Note: not a 404 since username might be an anonymous user

        # Parse expires_at
        expires_datetime = None
        if expires_at:
            from django.utils.dateparse import parse_datetime
            expires_datetime = parse_datetime(expires_at)

        # Create the ban
        ban = SiteBan.objects.create(
            banned_user=banned_user,
            banned_ip_address=ip_address,
            banned_fingerprint=fingerprint,
            banned_by=request.user,
            reason=reason,
            expires_at=expires_datetime,
        )

        logger.info(f"[ADMIN_BAN] Staff {request.user.username} created site ban {ban.id}")

        # SECURITY: Bump JWT epoch for ALL active chat participations for this user
        # so all outstanding JWT tokens (across every chat) become invalid.
        if banned_user:
            try:
                from .utils.security.auth import ChatSessionValidator
                participations = ChatParticipation.objects.filter(
                    user=banned_user, is_active=True
                ).values_list('chat_room__code', 'username').distinct()
                for chat_code, p_username in participations:
                    ChatSessionValidator.bump_epoch(chat_code, p_username)
            except Exception as e:
                logger.warning(f"[ADMIN_BAN] Failed to bump JWT epochs: {e}")

        # If banning a registered user, kick them from all active WebSocket connections
        if banned_user:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            user_group_name = f'user_{banned_user.id}_notifications'

            async_to_sync(channel_layer.group_send)(
                user_group_name,
                {
                    'type': 'site_banned',
                    'reason': reason,
                    'message': 'You have been banned from this site.',
                }
            )
            logger.info(f"[ADMIN_BAN] Sent site_banned event to user {banned_user.username}")

        # Note: fingerprint/IP bans take effect on reconnect (can't easily find those connections)

        return Response({
            'success': True,
            'ban_id': str(ban.id),
            'message': f'Site ban created',
            'kicked_immediately': banned_user is not None,
        }, status=status.HTTP_201_CREATED)


class AdminSiteBanRevokeView(APIView):
    """Revoke (deactivate) a site ban."""
    permission_classes = [IsStaffUser]

    def post(self, request, ban_id):
        from .models import SiteBan
        import logging
        logger = logging.getLogger(__name__)

        ban = get_object_or_404(SiteBan, id=ban_id)

        if not ban.is_active:
            return Response({
                'success': True,
                'message': 'Ban was already revoked',
            })

        ban.is_active = False
        ban.save()

        logger.info(f"[ADMIN_BAN] Staff {request.user.username} revoked site ban {ban_id}")

        return Response({
            'success': True,
            'message': 'Site ban revoked',
        })


class AdminChatBanCreateView(APIView):
    """
    Create a chat-specific ban (ChatBlock) as admin/staff.
    Same as host blocking but available to all staff.
    """
    permission_classes = [IsStaffUser]

    def post(self, request, room_id):
        from .utils.security.blocking import block_participation
        import logging
        logger = logging.getLogger(__name__)

        chat_room = get_object_or_404(ChatRoom, id=room_id)

        # Get ban parameters
        username = request.data.get('username')
        fingerprint = request.data.get('fingerprint')
        reason = request.data.get('reason', 'Banned by site admin')

        if not username and not fingerprint:
            return Response({
                'error': 'Either username or fingerprint is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        logger.info(f"[ADMIN_CHAT_BAN] Staff {request.user.username} banning from chat {room_id}")

        # Find the participation to block
        participation = None
        if username:
            participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username
            ).first()

        if not participation and fingerprint:
            participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=fingerprint
            ).first()

        if not participation:
            return Response({
                'error': 'User not found in this chat'
            }, status=status.HTTP_404_NOT_FOUND)

        # Create the block using the utility function
        try:
            block, created = block_participation(
                participation=participation,
                blocker=None,  # Admin block, no specific participation
                reason=reason
            )

            if not created:
                return Response({
                    'success': True,
                    'message': 'User was already banned from this chat',
                    'already_banned': True
                })

            logger.info(f"[ADMIN_CHAT_BAN] Created ChatBlock {block.id} for {participation.username}")

            # SECURITY: Revoke all outstanding JWT tokens for this user in this chat
            try:
                from .utils.security.auth import ChatSessionValidator
                ChatSessionValidator.bump_epoch(chat_room.code, participation.username)
            except Exception as e:
                logger.warning(f"[ADMIN_CHAT_BAN] Failed to bump JWT epoch: {e}")

            # Kick user via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            room_group_name = f'chat_{chat_room.code}'

            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'user_kicked',
                    'username': participation.username,
                    'fingerprint': participation.fingerprint,
                    'user_id': str(participation.user.id) if participation.user else None,
                    'message': 'You have been banned from this chat.',
                }
            )

            return Response({
                'success': True,
                'message': f'User {participation.username} banned from this chat',
                'block_id': str(block.id),
                'banned_by': request.user.username,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"[ADMIN_CHAT_BAN] Error creating block: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GiftCatalogView(APIView):
    """Get the gift catalog (cached in Redis)"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, username=None):
        from .utils.performance.cache import GiftCatalogCache

        # Validate session
        session_token = request.query_params.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        ChatSessionValidator.validate_session_token(token=session_token, chat_code=code)

        items = GiftCatalogCache.get_catalog()
        return Response({
            'items': items,
            'bulk_action_threshold': config.GIFT_BULK_ACTION_THRESHOLD,
        })


class SendGiftView(APIView):
    """Send a gift to another user in the chat"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from .utils.performance.cache import GiftCatalogCache, UnacknowledgedGiftCache
        from .models import Gift, GiftCatalogItem, Transaction
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        from rest_framework.renderers import JSONRenderer

        chat_room = get_chat_room_by_url(code, username)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        session_data = ChatSessionValidator.validate_session_token(
            token=session_token, chat_code=code, request=request,
        )
        sender_username = session_data['username']
        sender_user_id = session_data.get('user_id')

        # Validate request data
        serializer = SendGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        gift_id = serializer.validated_data['gift_id']
        recipient_username = serializer.validated_data['recipient_username']

        # Prevent self-gifting
        if sender_username.lower() == recipient_username.lower():
            return Response({'error': 'Cannot send a gift to yourself'}, status=status.HTTP_400_BAD_REQUEST)

        # Look up gift in catalog
        try:
            catalog_item = GiftCatalogItem.objects.get(gift_id=gift_id, is_active=True)
        except GiftCatalogItem.DoesNotExist:
            return Response({'error': 'Gift not found in catalog'}, status=status.HTTP_404_NOT_FOUND)

        # Validate recipient exists in chat
        try:
            recipient_participation = ChatParticipation.objects.get(
                chat_room=chat_room,
                username__iexact=recipient_username,
                is_active=True
            )
        except ChatParticipation.DoesNotExist:
            return Response({'error': 'Recipient not found in this chat'}, status=status.HTTP_404_NOT_FOUND)

        # Get sender user
        sender_user = None
        if sender_user_id:
            try:
                sender_user = User.objects.get(id=sender_user_id)
            except User.DoesNotExist:
                pass

        # Create gift message
        price_display = f"${catalog_item.price_cents / 100:.0f}" if catalog_item.price_cents >= 100 else f"${catalog_item.price_cents / 100:.2f}"
        message_content = f"sent {catalog_item.emoji} {catalog_item.name} ({price_display}) to @{recipient_username}"

        message = Message.objects.create(
            chat_room=chat_room,
            username=sender_username,
            user=sender_user,
            content=message_content,
            message_type=Message.MESSAGE_GIFT,
            is_from_host=bool(sender_user and chat_room.host == sender_user),
            gift_recipient=recipient_username,
        )

        # Create Gift record
        gift = Gift.objects.create(
            chat_room=chat_room,
            gift_catalog_item=catalog_item,
            gift_id=catalog_item.gift_id,
            emoji=catalog_item.emoji,
            name=catalog_item.name,
            price_cents=catalog_item.price_cents,
            sender_username=sender_username,
            sender_user=sender_user,
            recipient_username=recipient_username,
            recipient_user=recipient_participation.user,
            message=message,
        )

        # Create Transaction
        Transaction.objects.create(
            chat_room=chat_room,
            transaction_type=Transaction.TRANSACTION_GIFT,
            amount=Decimal(catalog_item.price_cents) / 100,
            status=Transaction.STATUS_COMPLETED,
            username=sender_username,
            user=sender_user,
            message=message,
        )

        # Dual-write message to Redis cache
        if config.REDIS_CACHE_ENABLED:
            try:
                MessageCache.add_message(message)
            except Exception as e:
                print(f"Redis cache error for gift message {message.id}: {e}")

        # Push to unacked gift queue for recipient
        gift_notification_data = {
            'id': str(gift.id),
            'gift_id': catalog_item.gift_id,
            'emoji': catalog_item.emoji,
            'name': catalog_item.name,
            'price_cents': catalog_item.price_cents,
            'sender_username': sender_username,
            'created_at': gift.created_at.isoformat(),
        }
        UnacknowledgedGiftCache.push_gift(
            room_id=str(chat_room.id),
            username=recipient_username,
            gift_data=gift_notification_data
        )

        # Serialize message for broadcast
        username_is_reserved = MessageCache._compute_username_is_reserved(message)
        message_data = MessageCache._serialize_message(message, username_is_reserved)
        # Convert to JSON-safe (handles UUIDs/Decimals)
        import json
        json_bytes = JSONRenderer().render(message_data)
        json_safe_data = json.loads(json_bytes)

        # WebSocket broadcast
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{chat_room.code}'

        # Broadcast gift chat message to all
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'gift_sent',
                'message_data': json_safe_data,
            }
        )

        # Send gift notification to recipient only
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'gift_received',
                'recipient_username': recipient_username,
                'gift': gift_notification_data,
            }
        )

        # Room notifications for gift
        from .utils.performance.cache import RoomNotificationCache
        actor_participation_id = RoomNotificationCache.resolve_participation_id(
            chat_room, username=sender_username, user_id=sender_user_id
        )
        RoomNotificationCache.mark_new_content(str(chat_room.id), 'gifts', actor_user_id=actor_participation_id)
        RoomNotificationCache.mark_new_content(str(chat_room.id), 'messages', actor_user_id=actor_participation_id)

        return Response({
            'success': True,
            'gift_id': str(gift.id),
            'message_id': str(message.id),
        }, status=status.HTTP_201_CREATED)


class AcknowledgeGiftView(APIView):
    """Acknowledge received gifts"""
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from .utils.performance.cache import UnacknowledgedGiftCache, MessageCache
        from .models import Gift
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        chat_room = get_chat_room_by_url(code, username)

        # Validate session token
        session_token = request.data.get('session_token')
        if not session_token:
            raise PermissionDenied("Session token is required")

        session_data = ChatSessionValidator.validate_session_token(
            token=session_token, chat_code=code, request=request,
        )
        current_username = session_data['username']

        serializer = AcknowledgeGiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        acknowledge_all = serializer.validated_data.get('acknowledge_all', False)
        thank = serializer.validated_data.get('thank', False)
        gift_id = serializer.validated_data.get('gift_id')
        message_id = serializer.validated_data.get('message_id')

        room_id = str(chat_room.id)
        thanked_message_ids = []

        if acknowledge_all:
            count = UnacknowledgedGiftCache.acknowledge_all(room_id, current_username)
            # Get gifts before updating
            gifts = Gift.objects.filter(
                chat_room=chat_room,
                recipient_username=current_username,
                is_acknowledged=False
            ).select_related('message')
            gift_message_ids = [str(g.message.id) for g in gifts if g.message]
            # Batch DB update — mark gifts as acknowledged
            gifts.update(is_acknowledged=True, acknowledged_at=timezone.now())
            # Only mark messages as thanked (🤗 badge) when thank=True
            if thank and gift_message_ids:
                Message.objects.filter(id__in=gift_message_ids).update(is_gift_acknowledged=True)
                thanked_message_ids = gift_message_ids

            remaining = 0
        elif gift_id or message_id:
            # Look up the gift by gift_id or by message_id — enforce recipient ownership
            if message_id:
                gift = Gift.objects.filter(
                    message_id=message_id,
                    recipient_username=current_username
                ).select_related('message').first()
                if not gift:
                    return Response({'error': 'Gift not found or not yours'}, status=status.HTTP_403_FORBIDDEN)
            else:
                gift = Gift.objects.filter(
                    id=gift_id,
                    recipient_username=current_username
                ).select_related('message').first()

            if gift:
                UnacknowledgedGiftCache.acknowledge_one(room_id, current_username, str(gift.id))
                gift.is_acknowledged = True
                gift.acknowledged_at = timezone.now()
                gift.save(update_fields=['is_acknowledged', 'acknowledged_at'])
                # Only mark message as thanked (🤗 badge) when thank=True
                if thank and gift.message:
                    thanked_message_ids = [str(gift.message.id)]
                    gift.message.is_gift_acknowledged = True
                    gift.message.save(update_fields=['is_gift_acknowledged'])
            remaining = len(UnacknowledgedGiftCache.get_unacked(room_id, current_username))
        else:
            return Response({'error': 'Must provide gift_id, message_id, or acknowledge_all'}, status=status.HTTP_400_BAD_REQUEST)

        # Update Redis message cache + broadcast WebSocket for thanked messages
        if thanked_message_ids:
            channel_layer = get_channel_layer()
            room_group_name = f"chat_{chat_room.code}"

            for msg_id in thanked_message_ids:
                try:
                    msg = Message.objects.get(id=msg_id)
                    MessageCache.update_message(msg)
                except Message.DoesNotExist:
                    pass

            # Single broadcast with all thanked message IDs
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'gift_acknowledged',
                    'message_ids': thanked_message_ids,
                }
            )

        return Response({'success': True, 'remaining_count': remaining})
