import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .utils.security.auth import ChatSessionValidator
from .utils.performance.cache import MessageCache, UnacknowledgedGiftCache
from .models import ChatRoom, Message, ChatParticipation
from urllib.parse import parse_qs


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_code = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_code}'
        self.username = None
        self.session_token = None
        self.user_id = None
        self.read_only = False
        self.blocked_usernames = set()  # In-memory set for O(1) lookup

        # Extract session token from query string
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        session_token = query_params.get('session_token', [None])[0]

        if not session_token:
            # No token — allow read-only connection for public chats
            is_public = await self.is_public_chat(self.chat_code)
            if not is_public:
                await self.close(code=4001)
                return

            self.read_only = True
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            return

        # Authenticated connection — full read-write access
        self.read_only = False

        # Validate session token
        try:
            session_data = await self.validate_session(session_token, self.chat_code)
            self.username = session_data['username']
            self.user_id = session_data.get('user_id')
            self.session_token = session_token
        except Exception as e:
            # Invalid session - reject connection
            await self.close(code=4003)
            return

        # Get client IP address for site ban checking
        client_ip = None
        if 'client' in self.scope and self.scope['client']:
            client_ip = self.scope['client'][0]  # (ip, port) tuple

        # Check if user is banned from this chat (ChatBlock) or site-wide (SiteBan)
        is_banned, ban_type = await self.check_if_banned(
            self.chat_code,
            self.username,
            session_data.get('fingerprint'),
            self.user_id,
            client_ip
        )
        if is_banned:
            if ban_type == 'site':
                await self.close(code=4503)  # 4503 = Site-wide ban
            else:
                await self.close(code=4403)  # 4403 = Chat ban
            return

        # Load blocked usernames for registered users
        if self.user_id:
            self.blocked_usernames = await self.load_blocked_usernames(self.user_id)
            # Also join user-specific notification group for block updates
            user_group_name = f'user_{self.user_id}_notifications'
            await self.channel_layer.group_add(
                user_group_name,
                self.channel_name
            )

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Deliver unacknowledged gifts on reconnect
        unacked_gifts = await self.get_unacked_gifts()
        if unacked_gifts:
            await self.send(text_data=json.dumps({
                'type': 'gift_queue',
                'gifts': unacked_gifts,
            }))

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        if self.read_only:
            return  # Read-only connections cannot send messages

        data = json.loads(text_data)
        message_text = data.get('message', '')
        reply_to_id = data.get('reply_to_id')  # Optional message ID to reply to
        voice_url = data.get('voice_url')  # Optional voice message URL
        voice_duration = data.get('voice_duration')  # Optional voice message duration (seconds)
        voice_waveform = data.get('voice_waveform')  # Optional voice waveform data (array of floats 0-1)
        photo_url = data.get('photo_url')  # Optional photo URL
        photo_width = data.get('photo_width')  # Optional photo width
        photo_height = data.get('photo_height')  # Optional photo height
        video_url = data.get('video_url')  # Optional video URL
        video_duration = data.get('video_duration')  # Optional video duration (seconds)
        video_thumbnail_url = data.get('video_thumbnail_url')  # Optional video thumbnail URL
        video_width = data.get('video_width')  # Optional video width
        video_height = data.get('video_height')  # Optional video height

        # Validate session token on each message (optional extra security)
        session_token = data.get('session_token', self.session_token)
        try:
            session_data = await self.validate_session(session_token, self.chat_code, self.username)
        except Exception:
            await self.send(text_data=json.dumps({
                'error': 'Invalid session'
            }))
            return

        # NOTE: Per-message ban check removed for performance.
        # Bans are enforced at connect time and via user_kicked WebSocket event.
        # If user is banned mid-session, they're immediately kicked via WebSocket.

        # Save message to PostgreSQL and Redis (dual-write)
        try:
            message_obj = await self.save_message(
                chat_code=self.chat_code,
                username=session_data['username'],
                user_id=session_data.get('user_id'),
                content=message_text,
                reply_to_id=reply_to_id,
                voice_url=voice_url,
                voice_duration=voice_duration,
                voice_waveform=voice_waveform,
                photo_url=photo_url,
                photo_width=photo_width,
                photo_height=photo_height,
                video_url=video_url,
                video_duration=video_duration,
                video_thumbnail_url=video_thumbnail_url,
                video_width=video_width,
                video_height=video_height
            )

            # Serialize for broadcast (includes username_is_reserved)
            message_data = await self.serialize_message_for_broadcast(message_obj)

            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message_data': message_data,
                }
            )

        except Exception as e:
            error_msg = f"Error saving/broadcasting message: {type(e).__name__}: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                'error': 'Failed to send message'
            }))

    async def chat_message(self, event):
        # Filter messages from blocked users
        message_data = event['message_data']
        sender_username = message_data.get('username')

        # Skip message if sender is blocked by this user
        if sender_username and sender_username in self.blocked_usernames:
            return  # Don't send message to this WebSocket

        # Send message to WebSocket
        await self.send(text_data=json.dumps(message_data))

    async def message_reaction(self, event):
        # Send reaction update to WebSocket
        await self.send(text_data=json.dumps(event['reaction_data']))

    async def message_deleted(self, event):
        # Send message deletion notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id']
        }))

    async def message_pinned(self, event):
        # Send pin update notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_pinned',
            'message': event['message'],
            'is_top_pin': event.get('is_top_pin', False),
        }))

    async def block_update(self, event):
        """Handle block/unblock updates from user_block_views.py"""
        action = event.get('action')  # 'add' or 'remove'
        blocked_username = event.get('blocked_username')

        if action == 'add':
            self.blocked_usernames.add(blocked_username)
        elif action == 'remove':
            self.blocked_usernames.discard(blocked_username)

        # Send update to WebSocket (so frontend can update UI)
        await self.send(text_data=json.dumps({
            'type': 'block_update',
            'action': action,
            'blocked_username': blocked_username
        }))

    async def user_kicked(self, event):
        """Handle user being kicked from chat by host (ChatBlock)"""
        kicked_username = event.get('username')

        # Only send notification if this is the kicked user
        if self.username == kicked_username:
            await self.send(text_data=json.dumps({
                'type': 'kicked',
                'message': event.get('message', 'You have been removed from this chat by the host')
            }))
            # Wait a moment to ensure message is transmitted before closing
            import asyncio
            await asyncio.sleep(0.1)
            # Close the WebSocket connection
            await self.close(code=4403)

    async def site_banned(self, event):
        """Handle user being site-wide banned by staff (SiteBan)"""
        await self.send(text_data=json.dumps({
            'type': 'site_banned',
            'message': event.get('message', 'You have been banned from this site.')
        }))
        # Wait a moment to ensure message is transmitted before closing
        import asyncio
        await asyncio.sleep(0.1)
        # Close the WebSocket connection with site ban code
        await self.close(code=4503)

    async def gift_sent(self, event):
        """Gift chat message - broadcast to all (respects block list)."""
        message_data = event['message_data']
        if message_data.get('username') in self.blocked_usernames:
            return
        await self.send(text_data=json.dumps(message_data))

    async def gift_received(self, event):
        """Gift popup notification - only forwarded to recipient."""
        if self.username == event.get('recipient_username'):
            await self.send(text_data=json.dumps({
                'type': 'gift_received',
                'gift': event['gift'],
            }))

    async def gift_acknowledged(self, event):
        """Gift acknowledged - broadcast message IDs to all clients."""
        await self.send(text_data=json.dumps({
            'type': 'gift_acknowledged',
            'message_ids': event['message_ids'],
        }))

    @database_sync_to_async
    def is_public_chat(self, chat_code):
        """Check if a chat room is public."""
        try:
            room = ChatRoom.objects.get(code=chat_code)
            return room.access_mode == ChatRoom.ACCESS_PUBLIC
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def get_unacked_gifts(self):
        """Get unacknowledged gifts for this user from Redis."""
        try:
            chat_room = ChatRoom.objects.get(code=self.chat_code)
            return UnacknowledgedGiftCache.get_unacked(str(chat_room.id), self.username)
        except ChatRoom.DoesNotExist:
            return []

    @database_sync_to_async
    def validate_session(self, token, chat_code, username=None):
        """Validate JWT session token (async wrapper)"""
        return ChatSessionValidator.validate_session_token(
            token=token,
            chat_code=chat_code,
            username=username
        )

    @database_sync_to_async
    def save_message(self, chat_code, username, user_id, content, reply_to_id=None, voice_url=None, voice_duration=None, voice_waveform=None, photo_url=None, photo_width=None, photo_height=None, video_url=None, video_duration=None, video_thumbnail_url=None, video_width=None, video_height=None):
        """
        Save message to PostgreSQL and Redis (dual-write).

        Returns: Message instance
        """
        # Get chat room
        chat_room = ChatRoom.objects.get(code=chat_code)

        # Get user if user_id provided
        user = None
        if user_id:
            from accounts.models import User
            user = User.objects.get(id=user_id)

        # Get reply_to message if provided
        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id, chat_room=chat_room)
            except Message.DoesNotExist:
                pass

        # Determine message type (host messages should be highlighted)
        message_type = Message.MESSAGE_NORMAL
        if user and chat_room.host == user:
            message_type = Message.MESSAGE_HOST

        # Create message in PostgreSQL
        message = Message.objects.create(
            chat_room=chat_room,
            username=username,
            user=user,
            content=content,
            message_type=message_type,
            reply_to=reply_to,
            voice_url=voice_url,
            voice_duration=voice_duration,
            voice_waveform=voice_waveform,
            photo_url=photo_url,
            photo_width=photo_width,
            photo_height=photo_height,
            video_url=video_url,
            video_duration=video_duration,
            video_thumbnail_url=video_thumbnail_url,
            video_width=video_width,
            video_height=video_height
        )

        # Add to Redis cache (dual-write) - only if enabled
        from constance import config
        if config.REDIS_CACHE_ENABLED:
            try:
                success = MessageCache.add_message(message)
                if not success:
                    print(f"⚠️  Redis cache write failed for message {message.id}")
            except Exception as e:
                print(f"❌ Redis cache error for message {message.id}: {e}")

        # Invalidate message activity cache so discovery modals show fresh data
        try:
            from media_analysis.utils.message_activity import invalidate_message_activity_cache
            invalidate_message_activity_cache(str(chat_room.id))
        except Exception as e:
            print(f"⚠️  Message activity cache invalidation failed: {e}")

        return message

    @database_sync_to_async
    def serialize_message_for_broadcast(self, message):
        """
        Serialize message for WebSocket broadcast.

        Includes username_is_reserved flag computed from participation.
        """
        from chatpop.utils.media import get_fallback_dicebear_url

        # Compute username_is_reserved
        username_is_reserved = MessageCache._compute_username_is_reserved(message)

        # Include reply_to_message preview if this is a reply
        reply_to_message = None
        if message.reply_to:
            reply_username_is_reserved = (
                message.reply_to.user and
                message.reply_to.user.reserved_username and
                message.reply_to.username.lower() == message.reply_to.user.reserved_username.lower()
            )
            reply_to_message = {
                'id': str(message.reply_to.id),
                'username': message.reply_to.username,
                'content': message.reply_to.content[:100],  # Truncate for preview
                'is_from_host': message.reply_to.user == message.reply_to.chat_room.host if message.reply_to.user else False,
                'username_is_reserved': bool(reply_username_is_reserved),
                'is_pinned': message.reply_to.is_pinned,
            }

        # Get avatar_url from ChatParticipation (always populated at join time)
        avatar_url = None
        try:
            participation = ChatParticipation.objects.get(
                chat_room=message.chat_room,
                username__iexact=message.username
            )
            if participation.avatar_url:
                avatar_url = participation.avatar_url
        except ChatParticipation.DoesNotExist:
            pass

        # Fallback to DiceBear for orphaned/legacy data
        if not avatar_url:
            avatar_style = None
            if message.chat_room.theme and message.chat_room.theme.avatar_style:
                avatar_style = message.chat_room.theme.avatar_style
            avatar_url = get_fallback_dicebear_url(message.username, style=avatar_style)

        return {
            'id': str(message.id),
            'chat_code': message.chat_room.code,
            'username': message.username,
            'username_is_reserved': username_is_reserved,
            'user_id': str(message.user.id) if message.user else None,
            'message_type': message.message_type,
            'is_from_host': message.message_type == 'host',  # Add explicit flag for frontend
            'content': message.content,
            'voice_url': message.voice_url,
            'voice_duration': float(message.voice_duration) if message.voice_duration else None,
            'voice_waveform': message.voice_waveform,
            'photo_url': message.photo_url,
            'photo_width': message.photo_width,
            'photo_height': message.photo_height,
            'video_url': message.video_url,
            'video_duration': float(message.video_duration) if message.video_duration else None,
            'video_thumbnail_url': message.video_thumbnail_url,
            'video_width': message.video_width,
            'video_height': message.video_height,
            'reply_to_id': str(message.reply_to.id) if message.reply_to else None,
            'reply_to_message': reply_to_message,
            'is_pinned': message.is_pinned,
            'avatar_url': avatar_url,
            'created_at': message.created_at.isoformat(),
            'is_deleted': message.is_deleted,
        }

    @database_sync_to_async
    def load_blocked_usernames(self, user_id):
        """
        Load blocked usernames for a registered user.

        Uses Redis cache with PostgreSQL fallback for efficiency.
        Returns a set of blocked usernames for O(1) lookup.
        """
        from .utils.performance.cache import UserBlockCache

        # Try Redis cache first
        blocked_usernames = UserBlockCache.get_blocked_usernames(user_id)

        # If cache is empty, sync from database (cache miss)
        if not blocked_usernames:
            UserBlockCache.sync_from_database(user_id)
            blocked_usernames = UserBlockCache.get_blocked_usernames(user_id)

        return blocked_usernames

    @database_sync_to_async
    def check_if_banned(self, chat_code, username, fingerprint=None, user_id=None, ip_address=None):
        """
        Check if user is banned from this chat (ChatBlock) or site-wide (SiteBan).

        Args:
            chat_code: Chat room code
            username: Username to check
            fingerprint: Browser fingerprint (optional)
            user_id: User ID for registered users (optional)
            ip_address: IP address (optional, for site bans)

        Returns:
            tuple: (is_banned: bool, ban_type: str|None)
                   ban_type is 'chat' for ChatBlock, 'site' for SiteBan, None if not banned
        """
        from .models import ChatBlock, SiteBan
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Check for site-wide ban first (applies to all chats)
        user = None
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass

        site_ban = SiteBan.is_banned(
            user=user,
            ip_address=ip_address,
            fingerprint=fingerprint
        )
        if site_ban:
            return True, 'site'

        # Get chat room for ChatBlock check
        try:
            chat_room = ChatRoom.objects.get(code=chat_code)
        except ChatRoom.DoesNotExist:
            return False, None

        # Check for ChatBlock by username (case-insensitive)
        if ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_username__iexact=username
        ).exists():
            return True, 'chat'

        # Check for ChatBlock by fingerprint
        if fingerprint and ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_fingerprint=fingerprint
        ).exists():
            return True, 'chat'

        # Check for ChatBlock by user ID
        if user_id and ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_user_id=user_id
        ).exists():
            return True, 'chat'

        return False, None
