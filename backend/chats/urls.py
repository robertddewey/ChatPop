from django.urls import path
from .views import (
    ChatRoomCreateView, ChatRoomDetailView, ChatRoomJoinView, MyChatsView,
    MessageListView, MessageCreateView, MessagePinView,
    BackRoomDetailView, BackRoomJoinView
)

app_name = 'chats'

urlpatterns = [
    # Chat Rooms
    path('create/', ChatRoomCreateView.as_view(), name='chat-create'),
    path('my-chats/', MyChatsView.as_view(), name='my-chats'),
    path('<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail'),
    path('<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join'),

    # Messages
    path('<str:code>/messages/', MessageListView.as_view(), name='message-list'),
    path('<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create'),
    path('<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin'),

    # Back Room
    path('<str:code>/backroom/', BackRoomDetailView.as_view(), name='backroom-detail'),
    path('<str:code>/backroom/join/', BackRoomJoinView.as_view(), name='backroom-join'),
]
