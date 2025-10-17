import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .utils.security.auth import ChatSessionValidator
from .utils.performance.cache import MessageCache
from .models import ChatRoom, Message, ChatParticipation
from urllib.parse import parse_qs


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_code = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_code}'
        self.username = None
        self.session_token = None
        self.user_id = None
        self.blocked_usernames = set()  # In-memory set for O(1) lookup

        # Extract session token from query string
        query_string = self.scope.get('query_string', b'').decode()
        query_params = parse_qs(query_string)
        session_token = query_params.get('session_token', [None])[0]

        if not session_token:
            # Reject connection without session token
            await self.close(code=4001)
            return

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

        # Check if user is banned from this chat (ChatBlock)
        is_banned = await self.check_if_banned(self.chat_code, self.username, session_data.get('fingerprint'), self.user_id)
        if is_banned:
            # Reject connection - user is banned from this chat
            await self.close(code=4403)  # 4403 = Forbidden (banned from chat)
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

    async def disconnect(self, close_code):
        # Leave room group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_text = data.get('message', '')
        reply_to_id = data.get('reply_to_id')  # Optional message ID to reply to
        voice_url = data.get('voice_url')  # Optional voice message URL
        voice_duration = data.get('voice_duration')  # Optional voice message duration (seconds)
        voice_waveform = data.get('voice_waveform')  # Optional voice waveform data (array of floats 0-1)

        # Validate session token on each message (optional extra security)
        session_token = data.get('session_token', self.session_token)
        try:
            session_data = await self.validate_session(session_token, self.chat_code, self.username)
        except Exception:
            await self.send(text_data=json.dumps({
                'error': 'Invalid session'
            }))
            return

        # Check if user is banned from chat (backup check)
        is_banned = await self.check_if_banned(self.chat_code, self.username, session_data.get('fingerprint'), self.user_id)
        if is_banned:
            await self.send(text_data=json.dumps({
                'error': 'You have been banned from this chat'
            }))
            await self.close(code=4403)  # Close connection
            return

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
                voice_waveform=voice_waveform
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

    @database_sync_to_async
    def validate_session(self, token, chat_code, username=None):
        """Validate JWT session token (async wrapper)"""
        return ChatSessionValidator.validate_session_token(
            token=token,
            chat_code=chat_code,
            username=username
        )

    @database_sync_to_async
    def save_message(self, chat_code, username, user_id, content, reply_to_id=None, voice_url=None, voice_duration=None, voice_waveform=None):
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
            voice_waveform=voice_waveform
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

        return message

    @database_sync_to_async
    def serialize_message_for_broadcast(self, message):
        """
        Serialize message for WebSocket broadcast.

        Includes username_is_reserved flag computed from participation.
        """
        # Compute username_is_reserved
        username_is_reserved = MessageCache._compute_username_is_reserved(message)

        # Include reply_to_message preview if this is a reply
        reply_to_message = None
        if message.reply_to:
            reply_to_message = {
                'id': str(message.reply_to.id),
                'username': message.reply_to.username,
                'content': message.reply_to.content[:100],  # Truncate for preview
                'is_from_host': message.reply_to.user == message.reply_to.chat_room.host if message.reply_to.user else False
            }

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
            'reply_to_id': str(message.reply_to.id) if message.reply_to else None,
            'reply_to_message': reply_to_message,
            'is_pinned': message.is_pinned,
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
    def check_if_banned(self, chat_code, username, fingerprint=None, user_id=None):
        """
        Check if user is banned from this chat (ChatBlock).

        Args:
            chat_code: Chat room code
            username: Username to check
            fingerprint: Browser fingerprint (optional)
            user_id: User ID for registered users (optional)

        Returns:
            bool: True if banned, False otherwise
        """
        from .models import ChatBlock

        # Get chat room
        try:
            chat_room = ChatRoom.objects.get(code=chat_code)
        except ChatRoom.DoesNotExist:
            return False

        # Check for ChatBlock by username (case-insensitive)
        if ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_username__iexact=username
        ).exists():
            return True

        # Check for ChatBlock by fingerprint
        if fingerprint and ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_fingerprint=fingerprint
        ).exists():
            return True

        # Check for ChatBlock by user ID
        if user_id and ChatBlock.objects.filter(
            chat_room=chat_room,
            blocked_user_id=user_id
        ).exists():
            return True

        return False
