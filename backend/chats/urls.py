from django.urls import path
from .views import (
    ChatRoomCreateView, ChatRoomDetailView, ChatRoomUpdateView, ChatRoomJoinView, MyChatsView,
    ChatConfigView, NearbyDiscoverableChatsView,
    MessageListView, MessageCreateView, MessagePinView, AddToPinView, MessageDeleteView,
    FingerprintUsernameView, UsernameValidationView, MyParticipationView, UpdateMyThemeView, SuggestUsernameView, CheckRateLimitView,
    VoiceUploadView, VoiceStreamView,
    MessageReactionToggleView, MessageReactionsListView,
    BlockUserView, UnblockUserView, BlockedUsersListView,
    UserBlockView, UserUnblockView, UserBlockListView,
    PhotoAnalysisView, ChatRoomCreateFromPhotoView
)

app_name = 'chats'

urlpatterns = [
    # User Blocking (registered users only, site-wide) - MUST come before other patterns
    path('user-blocks/', UserBlockListView.as_view(), name='user-blocks-list'),
    path('user-blocks/block/', UserBlockView.as_view(), name='user-block'),
    path('user-blocks/unblock/', UserUnblockView.as_view(), name='user-unblock'),

    # Photo Analysis (Chat Generation)
    path('analyze-photo/', PhotoAnalysisView.as_view(), name='analyze-photo'),
    path('create-from-photo/', ChatRoomCreateFromPhotoView.as_view(), name='chat-create-from-photo'),

    # Chat Management
    path('config/', ChatConfigView.as_view(), name='chat-config'),
    path('nearby/', NearbyDiscoverableChatsView.as_view(), name='nearby-discoverable-chats'),
    path('create/', ChatRoomCreateView.as_view(), name='chat-create'),
    path('my-chats/', MyChatsView.as_view(), name='my-chats'),

    # Voice Streaming (global endpoint)
    path('media/<path:storage_path>', VoiceStreamView.as_view(), name='voice-stream'),

    # AI-Generated Rooms (globally unique, /discover/{code}/)
    # MUST come before username-based routes to avoid 'discover' being treated as username
    path('discover/<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail-ai'),
    path('discover/<str:code>/update/', ChatRoomUpdateView.as_view(), name='chat-update-ai'),
    path('discover/<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join-ai'),
    path('discover/<str:code>/messages/', MessageListView.as_view(), name='message-list-ai'),
    path('discover/<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/add-to-pin/', AddToPinView.as_view(), name='add-to-pin-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/delete/', MessageDeleteView.as_view(), name='message-delete-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/react/', MessageReactionToggleView.as_view(), name='message-react-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/reactions/', MessageReactionsListView.as_view(), name='message-reactions-list-ai'),
    path('discover/<str:code>/fingerprint-username/', FingerprintUsernameView.as_view(), name='fingerprint-username-ai'),
    path('discover/<str:code>/validate-username/', UsernameValidationView.as_view(), name='validate-username-ai'),
    path('discover/<str:code>/suggest-username/', SuggestUsernameView.as_view(), name='suggest-username-ai'),
    path('discover/<str:code>/my-participation/', MyParticipationView.as_view(), name='my-participation-ai'),
    path('discover/<str:code>/update-my-theme/', UpdateMyThemeView.as_view(), name='update-my-theme-ai'),
    path('discover/<str:code>/check-rate-limit/', CheckRateLimitView.as_view(), name='check-rate-limit-ai'),
    path('discover/<str:code>/voice/upload/', VoiceUploadView.as_view(), name='voice-upload-ai'),
    path('discover/<str:code>/block-user/', BlockUserView.as_view(), name='block-user-ai'),
    path('discover/<str:code>/unblock/', UnblockUserView.as_view(), name='unblock-user-ai'),
    path('discover/<str:code>/blocked-users/', BlockedUsersListView.as_view(), name='blocked-users-list-ai'),

    # Manual Rooms (user-namespaced, /{username}/{code}/)
    path('<str:username>/<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail'),
    path('<str:username>/<str:code>/update/', ChatRoomUpdateView.as_view(), name='chat-update'),
    path('<str:username>/<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join'),
    path('<str:username>/<str:code>/messages/', MessageListView.as_view(), name='message-list'),
    path('<str:username>/<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/add-to-pin/', AddToPinView.as_view(), name='add-to-pin'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/delete/', MessageDeleteView.as_view(), name='message-delete'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/react/', MessageReactionToggleView.as_view(), name='message-react'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/reactions/', MessageReactionsListView.as_view(), name='message-reactions-list'),
    path('<str:username>/<str:code>/fingerprint-username/', FingerprintUsernameView.as_view(), name='fingerprint-username'),
    path('<str:username>/<str:code>/validate-username/', UsernameValidationView.as_view(), name='validate-username'),
    path('<str:username>/<str:code>/suggest-username/', SuggestUsernameView.as_view(), name='suggest-username'),
    path('<str:username>/<str:code>/my-participation/', MyParticipationView.as_view(), name='my-participation'),
    path('<str:username>/<str:code>/update-my-theme/', UpdateMyThemeView.as_view(), name='update-my-theme'),
    path('<str:username>/<str:code>/check-rate-limit/', CheckRateLimitView.as_view(), name='check-rate-limit'),
    path('<str:username>/<str:code>/voice/upload/', VoiceUploadView.as_view(), name='voice-upload'),
    path('<str:username>/<str:code>/block-user/', BlockUserView.as_view(), name='block-user'),
    path('<str:username>/<str:code>/unblock/', UnblockUserView.as_view(), name='unblock-user'),
    path('<str:username>/<str:code>/blocked-users/', BlockedUsersListView.as_view(), name='blocked-users-list'),
]
