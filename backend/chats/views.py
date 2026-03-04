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
from .models import ChatRoom, Message, AnonymousUserFingerprint, ChatParticipation, ChatTheme, MessageReaction
from .serializers import (
    ChatRoomSerializer, ChatRoomCreateSerializer, ChatRoomUpdateSerializer, ChatRoomJoinSerializer,
    MessageSerializer, MessageCreateSerializer, MessagePinSerializer,
    ChatParticipationSerializer, MessageReactionSerializer, MessageReactionCreateSerializer,
    GiftCatalogItemSerializer, SendGiftSerializer, AcknowledgeGiftSerializer
)
from .utils.security.auth import ChatSessionValidator
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
                user=chat_room.host
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

    def post(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)

        # AI-generated rooms (discover) are always joinable - skip host join check
        if chat_room.source != ChatRoom.SOURCE_AI:
            # Check if host has joined
            # Only allow non-host users to join if host has joined first
            host_has_joined = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=chat_room.host
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
        user_id = str(request.user.id) if request.user.is_authenticated else None
        ip_address = get_client_ip(request)

        # SECURITY CHECK 0: Verify username was generated by system OR is user's reserved_username
        # This applies to BOTH anonymous and logged-in users for new participations
        if request.user.is_authenticated:
            # Logged-in user: Check if this is a NEW participation (not rejoining)
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                user=request.user,
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
                    # Not their reserved username - must be a generated username
                    if fingerprint:
                        generated_key = f"username:generated_for_fingerprint:{fingerprint}"
                        generated_usernames = cache.get(generated_key, set())
                        generated_usernames_lower = {u.lower() for u in generated_usernames}

                        if username.lower() not in generated_usernames_lower:
                            raise ValidationError(
                                "Invalid username. Please use your reserved username or the suggest username feature."
                            )
                    else:
                        # No fingerprint and not using reserved username - reject
                        raise ValidationError(
                            "Invalid username. Please use your reserved username or the suggest username feature."
                        )

        elif fingerprint:
            # Anonymous user: Check if this is a NEW participation (not rejoining)
            existing_participation = ChatParticipation.objects.filter(
                chat_room=chat_room,
                fingerprint=fingerprint,
                user__isnull=True,
                is_active=True
            ).first()

            # If NO existing participation, verify username was generated for this fingerprint
            if not existing_participation:
                # Check Redis to verify this username was generated for this fingerprint
                generated_key = f"username:generated_for_fingerprint:{fingerprint}"
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
            fingerprint=fingerprint
        )
        if site_ban:
            raise PermissionDenied("You have been banned from this site.")

        # SECURITY CHECK 1b: Check if user is blocked from this chat
        from .utils.security.blocking import check_if_blocked
        is_blocked, block_message = check_if_blocked(
            chat_room=chat_room,
            username=username,
            fingerprint=fingerprint,
            user=request.user if request.user.is_authenticated else None
        )
        if is_blocked:
            raise PermissionDenied(block_message or "You have been blocked from this chat.")

        # SECURITY CHECK 1: IP-based rate limiting for anonymous users
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

                if anonymous_count >= config.MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT:
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
        # Usernames must be unique per chat room regardless of authentication status
        if request.user.is_authenticated:
            # Registered user: check for ANY other participant (registered or anonymous)
            username_taken = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
            ).exclude(user=request.user).exists()
        else:
            # Anonymous user: check for ANY other participant (registered or anonymous)
            username_taken = ChatParticipation.objects.filter(
                chat_room=chat_room,
                username__iexact=username,
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

            # Generate avatar at join time for logged-in users
            if created:
                self._generate_avatar_for_participation(participation, chat_room, request.user)
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

            # Generate avatar at join time for anonymous users
            if created and not participation.avatar_url:
                self._generate_avatar_for_participation(participation, chat_room)

        # Create JWT session token
        session_token = ChatSessionValidator.create_session_token(
            chat_code=code,
            username=username,
            user_id=user_id,
            fingerprint=fingerprint  # Include fingerprint for ban enforcement
        )

        # Return chat room info, username, and session token
        return Response({
            'chat_room': ChatRoomSerializer(chat_room).data,
            'username': username,
            'session_token': session_token,
            'message': 'Successfully joined chat room'
        })

    def _generate_avatar_for_participation(self, participation, chat_room, user=None):
        """
        Generate and store avatar at join time.

        ALWAYS populates ChatParticipation.avatar_url with the appropriate URL:
        - Registered user using reserved_username: proxy URL (allows avatar changes)
        - Registered user using different username: direct storage URL
        - Anonymous user: direct storage URL
        """
        from chatpop.utils.media import generate_and_store_avatar

        # Get avatar style from theme
        avatar_style = None
        if chat_room.theme and chat_room.theme.avatar_style:
            avatar_style = chat_room.theme.avatar_style

        # If logged-in user using their reserved_username
        if user and user.reserved_username:
            if participation.username.lower() == user.reserved_username.lower():
                # Ensure User.avatar_url exists (the actual avatar file)
                if not user.avatar_url:
                    avatar_url = generate_and_store_avatar(participation.username, style=avatar_style)
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
            avatar_url = generate_and_store_avatar(participation.username, style=avatar_style)
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

        # Extract current user's fingerprint and user_id from session token (for has_reacted)
        current_fingerprint = None
        current_user_id = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                current_fingerprint = session_data.get('fingerprint')
                current_user_id = session_data.get('user_id')
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
            if filter_mode and filter_username:
                if filter_mode == 'focus':
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
                    oldest_cached_timestamp = datetime.fromisoformat(messages[0]['created_at']).timestamp()
                    remaining_limit = limit - len(messages)

                    # Fetch older messages from database
                    older_messages = self._fetch_from_db(
                        chat_room,
                        limit=remaining_limit,
                        before_timestamp=oldest_cached_timestamp,
                        request=request,
                        current_fingerprint=current_fingerprint,
                        current_user_id=current_user_id,
                        filter_mode=filter_mode,
                        filter_username=filter_username
                    )

                    # Backfill cache with the older messages we just fetched
                    # This prevents repeated DB queries for the same messages
                    self._backfill_cache(chat_room, older_messages)

                    # Prepend older messages (they come chronologically before cached ones)
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
                if current_fingerprint or current_user_id:
                    from django.db.models import Q
                    # Build query to match either fingerprint or user_id
                    q_filter = Q()
                    if current_fingerprint:
                        q_filter |= Q(fingerprint=current_fingerprint)
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
            else:
                # Cache miss - fall back to PostgreSQL and backfill cache
                print(f"DEBUG: Cache miss! Calling _fetch_from_db, limit={limit}, before_timestamp={before_timestamp}")
                messages = self._fetch_from_db(chat_room, limit, before_timestamp, request, current_fingerprint, current_user_id, filter_mode, filter_username)
                source = 'postgresql_fallback'
                print(f"DEBUG: _fetch_from_db returned {len(messages)} messages")

                # Backfill cache: Add fetched messages to Redis
                # This ensures subsequent requests hit the cache
                print(f"DEBUG: About to call _backfill_cache with {len(messages)} messages")
                self._backfill_cache(chat_room, messages)
                print(f"DEBUG: _backfill_cache completed")
        else:
            # Cache disabled - always use PostgreSQL
            messages = self._fetch_from_db(chat_room, limit, before_timestamp, request, current_fingerprint, current_user_id, filter_mode, filter_username)

        # Filter blocked users for authenticated users
        if request.user and request.user.is_authenticated:
            from .utils.performance.cache import UserBlockCache

            # Load blocked usernames (uses existing Redis/PostgreSQL cache)
            blocked_usernames = UserBlockCache.get_blocked_usernames(request.user.id)

            # Filter messages in Python
            if blocked_usernames:
                messages = [
                    msg for msg in messages
                    if msg.get('username') not in blocked_usernames
                ]

        # Fetch pinned messages from Redis (pinned messages are ephemeral)
        pinned_messages = MessageCache.get_pinned_messages(chat_room.id)

        return Response({
            'messages': messages,
            'pinned_messages': pinned_messages,
            'source': source,  # Shows where data came from (redis/postgresql/postgresql_fallback)
            'cache_enabled': cache_enabled,
            'count': len(messages),
            'history_limits': {
                'max_days': config.MESSAGE_HISTORY_MAX_DAYS,
                'max_count': config.MESSAGE_HISTORY_MAX_COUNT
            }
        })

    def _fetch_from_db(self, chat_room, limit, before_timestamp=None, request=None, current_fingerprint=None, current_user_id=None, filter_mode=None, filter_username=None):
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
        if filter_mode and filter_username:
            from django.db.models import Q
            if filter_mode == 'focus':
                queryset = queryset.filter(
                    Q(message_type='host') |
                    Q(username__iexact=filter_username) |
                    Q(reply_to__username__iexact=filter_username)
                )
            elif filter_mode == 'gifts':
                queryset = queryset.filter(
                    Q(message_type='gift') & (
                        Q(username__iexact=filter_username) |
                        Q(gift_recipient__iexact=filter_username)
                    )
                )

        # Filter by timestamp if paginating
        if before_timestamp:
            from datetime import datetime
            before_dt = datetime.fromtimestamp(float(before_timestamp))
            queryset = queryset.filter(created_at__lt=before_dt)

        # Order and limit (newest first to get last N messages)
        messages = queryset.order_by('-created_at')[:limit]

        # Force query execution for accurate timing
        message_count = len(messages)

        # Batch fetch reactions from cache for all messages (SOLVES N+1 PROBLEM)
        message_ids = [str(msg.id) for msg in messages]
        reactions_by_message = MessageCache.batch_get_reactions(chat_room.id, message_ids)

        # Get current user's reactions for has_reacted (single query)
        user_reactions = {}  # message_id -> set of emojis
        if current_fingerprint or current_user_id:
            from django.db.models import Q
            # Build query to match either fingerprint or user_id
            q_filter = Q()
            if current_fingerprint:
                q_filter |= Q(fingerprint=current_fingerprint)
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
        avatar_style = None
        if chat_room.theme and chat_room.theme.avatar_style:
            avatar_style = chat_room.theme.avatar_style

        avatar_map = {}
        for p in participations:
            if p.avatar_url:
                avatar_map[p.username.lower()] = p.avatar_url
            # else: not in map, will fallback to DiceBear (orphaned data)

        # Serialize (with username_is_reserved and avatar_url)
        serialized = []
        for msg in messages:
            username_is_reserved = MessageCache._compute_username_is_reserved(msg)
            # Lookup avatar from map, fallback to DiceBear if not found
            avatar_url = avatar_map.get(msg.username.lower()) or get_fallback_dicebear_url(msg.username, style=avatar_style)

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

            # Get cached reactions (or fallback to database if cache miss)
            msg_id_str = str(msg.id)
            cached_reactions = reactions_by_message.get(msg_id_str, [])

            if cached_reactions:
                # Use cached reactions (already top 3 format)
                top_reactions = cached_reactions
            else:
                # Cache miss: fallback to database query (compute reaction summary)
                from collections import defaultdict
                reactions_list = msg.reactions.all()
                emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0})

                for reaction in reactions_list:
                    emoji = reaction.emoji
                    emoji_counts[emoji]['emoji'] = emoji
                    emoji_counts[emoji]['count'] += 1

                top_reactions = sorted(emoji_counts.values(), key=lambda x: x['count'], reverse=True)[:3]

                # Cache the computed reactions for next time
                if top_reactions:
                    MessageCache.set_message_reactions(chat_room.id, msg_id_str, top_reactions)

            # Add has_reacted to each reaction
            user_emojis = user_reactions.get(msg_id_str, set())
            for reaction in top_reactions:
                reaction['has_reacted'] = reaction['emoji'] in user_emojis

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
                'sticky_until': msg.sticky_until.isoformat() if msg.sticky_until else None,
                'pin_amount_paid': str(msg.pin_amount_paid) if msg.pin_amount_paid else "0.00",
                'current_pin_amount': str(msg.current_pin_amount) if msg.current_pin_amount else "0.00",
                'avatar_url': avatar_url,
                'created_at': msg.created_at.isoformat(),
                'is_deleted': msg.is_deleted,
                'reactions': top_reactions,
            })

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
            username=username
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

        message.save(update_fields=['pin_amount_paid', 'current_pin_amount', 'sticky_until'])

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


class FingerprintUsernameView(APIView):
    """Get or set username by fingerprint for anonymous users"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, username=None):
        """Get username for a fingerprint if it exists"""
        # Check if fingerprinting is enabled
        if not settings.ANONYMOUS_USER_FINGERPRINT:
            return Response(
                {'detail': 'Fingerprinting is disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        chat_room = get_chat_room_by_url(code, username)
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

    def post(self, request, code, username=None):
        """Set username for a fingerprint"""
        # Check if fingerprinting is enabled
        if not settings.ANONYMOUS_USER_FINGERPRINT:
            return Response(
                {'detail': 'Fingerprinting is disabled'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        chat_room = get_chat_room_by_url(code, username)
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

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
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

            # Check if user is blocked
            from .utils.security.blocking import check_if_blocked
            is_blocked, _ = check_if_blocked(
                chat_room=chat_room,
                username=participation.username,
                fingerprint=fingerprint,
                user=request.user if request.user.is_authenticated else None
            )

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
                'theme': theme_data,
                'is_blocked': is_blocked
            })

        # No participation found - check if first-time visitor is blocked
        # This allows frontend to show "You are blocked" message immediately
        from .utils.security.blocking import check_if_blocked
        is_blocked, _ = check_if_blocked(
            chat_room=chat_room,
            username=None,  # No username yet (they haven't joined)
            fingerprint=fingerprint,
            user=request.user if request.user.is_authenticated else None
        )

        return Response({
            'has_joined': False,
            'is_blocked': is_blocked
        })


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

    def get(self, request, code, username=None):
        chat_room = get_chat_room_by_url(code, username)
        fingerprint = request.query_params.get('fingerprint')

        # Logged-in users are always allowed
        if request.user.is_authenticated:
            return Response({
                'can_join': True,
                'is_rate_limited': False
            })

        # Anonymous users: check rate limit
        ip_address = get_client_ip(request)

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

        is_rate_limited = anonymous_count >= config.MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT

        return Response({
            'can_join': not is_rate_limited,
            'is_rate_limited': is_rate_limited,
            'anonymous_count': anonymous_count,
            'max_allowed': config.MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT
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
    Rate limited to 20 requests per fingerprint/IP per chat per hour.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, code, username=None):
        from .utils.username.generator import generate_username
        import logging
        logger = logging.getLogger(__name__)

        # Get chat room
        chat_room = get_chat_room_by_url(code, username)

        # Get fingerprint or IP for rate limiting
        fingerprint = request.data.get('fingerprint')
        if not fingerprint:
            # Fallback to IP-based rate limiting
            fingerprint = get_client_ip(request)

        # Check if this fingerprint already has a participation in this room
        # If so, return their existing username immediately (they're a returning user)
        existing_participation = ChatParticipation.objects.filter(
            chat_room=chat_room,
            fingerprint=fingerprint,
            is_active=True
        ).first()

        if existing_participation:
            logger.info(f"[USERNAME_SUGGEST] Returning user detected - fingerprint={fingerprint}, existing_username={existing_participation.username}")
            return Response({
                'username': existing_participation.username,
                'is_returning': True,
                'remaining': 0,
                'generation_remaining': 0
            })

        # Rate limiting key (per chat, per fingerprint/IP)
        rate_limit_key = f"username_suggest_limit:{code}:{fingerprint}"
        current_count = cache.get(rate_limit_key, 0)

        logger.info(f"[USERNAME_SUGGEST] Starting - fingerprint={fingerprint}, chat_code={code}, current_count={current_count}")

        # Check chat-specific generation rate limit FIRST (before generating!)
        # NOTE: Rotation does NOT count against this limit (handled below)
        max_generations_per_chat = config.MAX_USERNAME_GENERATION_ATTEMPTS_PER_CHAT
        if current_count >= max_generations_per_chat:
            # Per-chat rate limit hit - offer rotation through previously generated usernames
            logger.info(f"[USERNAME_PER_CHAT_LIMIT] Per-chat limit hit: current_count={current_count}, max={max_generations_per_chat}")

            # Get all usernames generated for this fingerprint IN THIS CHAT
            generated_per_chat_key = f"username:generated_for_chat:{code}:{fingerprint}"
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

                # Get rotation index for this fingerprint IN THIS CHAT
                rotation_key = f"username:rotation_index:{code}:{fingerprint}"
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
                attempts_key = f"username:generation_attempts:{fingerprint}"
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
                attempts_key = f"username:generation_attempts:{fingerprint}"
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

        # Generate username with new signature (requires fingerprint)
        username, generation_remaining = generate_username(fingerprint, code)

        logger.info(f"[USERNAME_SUGGEST] After generate_username - username={username}, generation_remaining={generation_remaining}")

        if not username:
            # If rate limited (0 attempts left), rotate through previous usernames they can reuse
            if generation_remaining == 0:
                # Get all usernames generated for this fingerprint IN THIS CHAT
                generated_per_chat_key = f"username:generated_for_chat:{code}:{fingerprint}"
                generated_usernames = cache.get(generated_per_chat_key, set())
                logger.info(f"[USERNAME_ROTATION] Fingerprint: {fingerprint}")
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

                    # Get rotation index for this fingerprint IN THIS CHAT
                    rotation_key = f"username:rotation_index:{code}:{fingerprint}"
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
                username=username
            )
        except Exception as e:
            raise

        # Validate emoji
        serializer = MessageReactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        emoji = serializer.validated_data['emoji']

        # Determine user identity
        user = request.user if request.user.is_authenticated else None
        fingerprint_value = fingerprint if not user else None

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
                fingerprint=fingerprint_value,
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
                fingerprint=fingerprint_value,
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


class MessageReactionsListView(APIView):
    """Get all reactions for a specific message"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, code, message_id, username=None):
        chat_room = get_chat_room_by_url(code, username)
        message = get_object_or_404(Message, id=message_id, chat_room=chat_room, is_deleted=False)

        # Get current user's fingerprint and user_id for has_reacted
        session_token = request.query_params.get('session_token')
        current_fingerprint = None
        current_user_id = None
        if session_token:
            try:
                session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
                current_fingerprint = session_data.get('fingerprint')
                current_user_id = session_data.get('user_id')
            except Exception:
                pass

        reactions = MessageReaction.objects.filter(message=message).order_by('-created_at')
        serializer = MessageReactionSerializer(reactions, many=True)

        # Group reactions by emoji with counts
        from collections import defaultdict
        emoji_counts = defaultdict(lambda: {'emoji': '', 'count': 0})
        user_emojis = set()  # Track current user's emojis

        for reaction in reactions:
            emoji = reaction.emoji
            emoji_counts[emoji]['emoji'] = emoji
            emoji_counts[emoji]['count'] += 1
            # Check if this is the current user's reaction (by fingerprint or user_id)
            is_user_reaction = (
                (current_fingerprint and reaction.fingerprint == current_fingerprint) or
                (current_user_id and reaction.user_id and str(reaction.user_id) == current_user_id)
            )
            if is_user_reaction:
                user_emojis.add(emoji)

        # Sort by count (descending) and take top 3
        top_reactions = sorted(emoji_counts.values(), key=lambda x: x['count'], reverse=True)[:3]

        # Add has_reacted to each summary item
        for reaction in top_reactions:
            reaction['has_reacted'] = reaction['emoji'] in user_emojis

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
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
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

        # Validate file size (max 10MB before compression)
        if photo_file.size > 10 * 1024 * 1024:
            return Response({
                'error': 'Photo too large (max 10MB)'
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

            # Resize if larger than 1920px on longest side
            max_dimension = 1920
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
            session_data = ChatSessionValidator.validate_session_token(session_token, chat_code=code)
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
            logger.info(f"[BLOCK] Calling block_participation with chat_room={chat_room.id}, participation={participation.id}, blocked_by={host_participation.id}, ip_address={ip_address}")
            block_created = block_participation(
                chat_room=chat_room,
                participation=participation,
                blocked_by=host_participation,
                ip_address=ip_address
            )
            logger.info(f"[BLOCK] block_participation succeeded, created consolidated block with ID: {block_created.id}")

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

            # Send eviction event to the chat room
            async_to_sync(channel_layer.group_send)(
                room_group_name,
                {
                    'type': 'user_kicked',
                    'username': participation.username,
                    'message': 'You have been removed from this chat by the host.',
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
                chat_code=code
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

        # Broadcast deletion event via WebSocket
        channel_layer = get_channel_layer()
        room_group_name = f'chat_{code}'
        async_to_sync(channel_layer.group_send)(
            room_group_name,
            {
                'type': 'message_deleted',
                'message_id': str(message_id)
            }
        )
        logger.info(f"[MESSAGE_DELETE] Deletion event broadcast via WebSocket")

        return Response({
            'success': True,
            'message': 'Message deleted successfully',
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
            token=session_token, chat_code=code
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
            token=session_token, chat_code=code
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
