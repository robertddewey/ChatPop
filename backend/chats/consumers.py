import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .security import ChatSessionValidator
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
        message = data.get('message', '')

        # Validate session token on each message (optional extra security)
        session_token = data.get('session_token', self.session_token)
        try:
            await self.validate_session(session_token, self.chat_code, self.username)
        except Exception:
            await self.send(text_data=json.dumps({
                'error': 'Invalid session'
            }))
            return

        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': self.username,
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username'],
        }))

    @database_sync_to_async
    def validate_session(self, token, chat_code, username=None):
        """Validate JWT session token (async wrapper)"""
        return ChatSessionValidator.validate_session_token(
            token=token,
            chat_code=chat_code,
            username=username
        )
