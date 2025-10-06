import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .security import ChatSessionValidator
from .redis_cache import MessageCache
from .models import ChatRoom, Message, ChatParticipation
from urllib.parse import parse_qs


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_code = self.scope['url_route']['kwargs']['chat_id']
        self.room_group_name = f'chat_{self.chat_code}'
        self.username = None
        self.session_token = None

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
            self.session_token = session_token
        except Exception as e:
            # Invalid session - reject connection
            await self.close(code=4003)
            return

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
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['message_data']))

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

        # Add to Redis cache (dual-write)
        try:
            success = MessageCache.add_message(message, is_backroom=False)
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

        return {
            'id': str(message.id),
            'chat_code': message.chat_room.code,
            'username': message.username,
            'username_is_reserved': username_is_reserved,
            'user_id': str(message.user.id) if message.user else None,
            'message_type': message.message_type,
            'content': message.content,
            'voice_url': message.voice_url,
            'voice_duration': float(message.voice_duration) if message.voice_duration else None,
            'voice_waveform': message.voice_waveform,
            'reply_to_id': str(message.reply_to.id) if message.reply_to else None,
            'is_pinned': message.is_pinned,
            'created_at': message.created_at.isoformat(),
            'is_deleted': message.is_deleted,
        }
