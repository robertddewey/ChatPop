from django.urls import path
from .views import (
    ChatRoomCreateView, ChatRoomDetailView, ChatRoomUpdateView, ChatRoomJoinView, MyChatsView,
    MessageListView, MessageCreateView, MessagePinView,
    FingerprintUsernameView, UsernameValidationView, MyParticipationView, SuggestUsernameView, CheckRateLimitView,
    VoiceUploadView, VoiceStreamView
)

app_name = 'chats'

urlpatterns = [
    # Chat Rooms
    path('create/', ChatRoomCreateView.as_view(), name='chat-create'),
    path('my-chats/', MyChatsView.as_view(), name='my-chats'),
    path('<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail'),
    path('<str:code>/update/', ChatRoomUpdateView.as_view(), name='chat-update'),
    path('<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join'),

    # Messages
    path('<str:code>/messages/', MessageListView.as_view(), name='message-list'),
    path('<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create'),
    path('<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin'),

    # Fingerprint Username
    path('<str:code>/fingerprint-username/', FingerprintUsernameView.as_view(), name='fingerprint-username'),

    # Username Validation
    path('<str:code>/validate-username/', UsernameValidationView.as_view(), name='validate-username'),

    # Username Suggestion
    path('<str:code>/suggest-username/', SuggestUsernameView.as_view(), name='suggest-username'),

    # Chat Participation
    path('<str:code>/my-participation/', MyParticipationView.as_view(), name='my-participation'),

    # Rate Limit Check
    path('<str:code>/check-rate-limit/', CheckRateLimitView.as_view(), name='check-rate-limit'),

    # Voice Messages
    path('<str:code>/voice/upload/', VoiceUploadView.as_view(), name='voice-upload'),
    path('media/<path:storage_path>', VoiceStreamView.as_view(), name='voice-stream'),
]
