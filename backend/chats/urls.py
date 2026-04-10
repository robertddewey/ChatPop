from django.urls import path
from .views import (
    ChatRoomCreateView, ChatRoomDetailView, ChatRoomUpdateView, ChatRoomJoinView, RefreshSessionView, MyChatsView,
    ChatConfigView, NearbyDiscoverableChatsView,
    MessageListView, MessageCreateView, MessagePinView, AddToPinView, MessageBroadcastView, MessageDeleteView, MessageUnpinView, PinTiersView,
    UsernameValidationView, MyParticipationView, UpdateMyThemeView, SuggestUsernameView,
    DismissIntroView,
    VoiceUploadView, VoiceStreamView, PhotoUploadView, VideoUploadView, UserAvatarView,
    MessageReactionToggleView, MessageReactionsListView,
    BlockUserView, UnblockUserView, BlockedUsersListView, MutedUsersInChatView,
    SpotlightListView, SpotlightAddView, SpotlightRemoveView, ParticipantSearchView,
    UserBlockView, UserUnblockView, UserBlockListView,
    PhotoAnalysisView, ChatRoomCreateFromPhotoView, ChatRoomCreateFromLocationView, ChatRoomCreateFromMusicView,
    GiftCatalogView, SendGiftView, AcknowledgeGiftView,
    # Admin/Staff moderation views
    AdminChatDetailView, AdminMessageListView, AdminMessageDeleteView, AdminMessageUnpinView,
    AdminSiteBanListView, AdminSiteBanCreateView, AdminSiteBanRevokeView, AdminChatBanCreateView,
)

app_name = 'chats'

urlpatterns = [
    # Admin/Staff Moderation - MUST come before other patterns
    path('admin/<uuid:room_id>/', AdminChatDetailView.as_view(), name='admin-chat-detail'),
    path('admin/<uuid:room_id>/messages/', AdminMessageListView.as_view(), name='admin-message-list'),
    path('admin/<uuid:room_id>/messages/<uuid:message_id>/delete/', AdminMessageDeleteView.as_view(), name='admin-message-delete'),
    path('admin/<uuid:room_id>/messages/<uuid:message_id>/unpin/', AdminMessageUnpinView.as_view(), name='admin-message-unpin'),
    path('admin/<uuid:room_id>/ban/', AdminChatBanCreateView.as_view(), name='admin-chat-ban'),
    path('admin/site-bans/', AdminSiteBanListView.as_view(), name='admin-site-bans-list'),
    path('admin/site-bans/create/', AdminSiteBanCreateView.as_view(), name='admin-site-ban-create'),
    path('admin/site-bans/<uuid:ban_id>/revoke/', AdminSiteBanRevokeView.as_view(), name='admin-site-ban-revoke'),

    # User Blocking (registered users only, site-wide) - MUST come before other patterns
    path('user-blocks/', UserBlockListView.as_view(), name='user-blocks-list'),
    path('user-blocks/block/', UserBlockView.as_view(), name='user-block'),
    path('user-blocks/unblock/', UserUnblockView.as_view(), name='user-unblock'),

    # Photo/Location/Music Analysis (Chat Generation)
    path('analyze-photo/', PhotoAnalysisView.as_view(), name='analyze-photo'),
    path('create-from-photo/', ChatRoomCreateFromPhotoView.as_view(), name='chat-create-from-photo'),
    path('create-from-location/', ChatRoomCreateFromLocationView.as_view(), name='chat-create-from-location'),
    path('create-from-music/', ChatRoomCreateFromMusicView.as_view(), name='chat-create-from-music'),

    # Chat Management
    path('config/', ChatConfigView.as_view(), name='chat-config'),
    path('nearby/', NearbyDiscoverableChatsView.as_view(), name='nearby-discoverable-chats'),
    path('create/', ChatRoomCreateView.as_view(), name='chat-create'),
    path('my-chats/', MyChatsView.as_view(), name='my-chats'),

    # User Avatar Proxy (must come before generic media path)
    path('media/avatars/user/<uuid:user_id>', UserAvatarView.as_view(), name='user-avatar'),

    # Voice/Media Streaming (global endpoint)
    path('media/<path:storage_path>', VoiceStreamView.as_view(), name='media-stream'),

    # AI-Generated Rooms (globally unique, /discover/{code}/)
    # MUST come before username-based routes to avoid 'discover' being treated as username
    path('discover/<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail-ai'),
    path('discover/<str:code>/update/', ChatRoomUpdateView.as_view(), name='chat-update-ai'),
    path('discover/<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join-ai'),
    path('discover/<str:code>/messages/', MessageListView.as_view(), name='message-list-ai'),
    path('discover/<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create-ai'),
    path('discover/<str:code>/pin-tiers/', PinTiersView.as_view(), name='pin-tiers-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/add-to-pin/', AddToPinView.as_view(), name='add-to-pin-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/broadcast/', MessageBroadcastView.as_view(), name='message-broadcast-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/delete/', MessageDeleteView.as_view(), name='message-delete-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/unpin/', MessageUnpinView.as_view(), name='message-unpin-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/react/', MessageReactionToggleView.as_view(), name='message-react-ai'),
    path('discover/<str:code>/messages/<uuid:message_id>/reactions/', MessageReactionsListView.as_view(), name='message-reactions-list-ai'),

    path('discover/<str:code>/validate-username/', UsernameValidationView.as_view(), name='validate-username-ai'),
    path('discover/<str:code>/suggest-username/', SuggestUsernameView.as_view(), name='suggest-username-ai'),
    path('discover/<str:code>/my-participation/', MyParticipationView.as_view(), name='my-participation-ai'),
    path('discover/<str:code>/update-my-theme/', UpdateMyThemeView.as_view(), name='update-my-theme-ai'),
    path('discover/<str:code>/voice/upload/', VoiceUploadView.as_view(), name='voice-upload-ai'),
    path('discover/<str:code>/photo/upload/', PhotoUploadView.as_view(), name='photo-upload-ai'),
    path('discover/<str:code>/video/upload/', VideoUploadView.as_view(), name='video-upload-ai'),
    path('discover/<str:code>/block-user/', BlockUserView.as_view(), name='block-user-ai'),
    path('discover/<str:code>/unblock/', UnblockUserView.as_view(), name='unblock-user-ai'),
    path('discover/<str:code>/blocked-users/', BlockedUsersListView.as_view(), name='blocked-users-list-ai'),
    path('discover/<str:code>/muted-users/', MutedUsersInChatView.as_view(), name='muted-users-ai'),
    path('discover/<str:code>/spotlight/', SpotlightListView.as_view(), name='spotlight-list-ai'),
    path('discover/<str:code>/spotlight/add/', SpotlightAddView.as_view(), name='spotlight-add-ai'),
    path('discover/<str:code>/spotlight/remove/', SpotlightRemoveView.as_view(), name='spotlight-remove-ai'),
    path('discover/<str:code>/participants/search/', ParticipantSearchView.as_view(), name='participants-search-ai'),
    path('discover/<str:code>/gifts/catalog/', GiftCatalogView.as_view(), name='gift-catalog-ai'),
    path('discover/<str:code>/gifts/send/', SendGiftView.as_view(), name='gift-send-ai'),
    path('discover/<str:code>/gifts/acknowledge/', AcknowledgeGiftView.as_view(), name='gift-acknowledge-ai'),
    path('discover/<str:code>/intros/<str:key>/dismiss/', DismissIntroView.as_view(), name='dismiss-intro-ai'),
    path('discover/<str:code>/refresh-session/', RefreshSessionView.as_view(), name='refresh-session-ai'),

    # Manual Rooms (user-namespaced, /{username}/{code}/)
    path('<str:username>/<str:code>/', ChatRoomDetailView.as_view(), name='chat-detail'),
    path('<str:username>/<str:code>/update/', ChatRoomUpdateView.as_view(), name='chat-update'),
    path('<str:username>/<str:code>/join/', ChatRoomJoinView.as_view(), name='chat-join'),
    path('<str:username>/<str:code>/messages/', MessageListView.as_view(), name='message-list'),
    path('<str:username>/<str:code>/messages/send/', MessageCreateView.as_view(), name='message-create'),
    path('<str:username>/<str:code>/pin-tiers/', PinTiersView.as_view(), name='pin-tiers'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/pin/', MessagePinView.as_view(), name='message-pin'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/add-to-pin/', AddToPinView.as_view(), name='add-to-pin'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/broadcast/', MessageBroadcastView.as_view(), name='message-broadcast'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/delete/', MessageDeleteView.as_view(), name='message-delete'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/unpin/', MessageUnpinView.as_view(), name='message-unpin'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/react/', MessageReactionToggleView.as_view(), name='message-react'),
    path('<str:username>/<str:code>/messages/<uuid:message_id>/reactions/', MessageReactionsListView.as_view(), name='message-reactions-list'),

    path('<str:username>/<str:code>/validate-username/', UsernameValidationView.as_view(), name='validate-username'),
    path('<str:username>/<str:code>/suggest-username/', SuggestUsernameView.as_view(), name='suggest-username'),
    path('<str:username>/<str:code>/my-participation/', MyParticipationView.as_view(), name='my-participation'),
    path('<str:username>/<str:code>/update-my-theme/', UpdateMyThemeView.as_view(), name='update-my-theme'),
    path('<str:username>/<str:code>/voice/upload/', VoiceUploadView.as_view(), name='voice-upload'),
    path('<str:username>/<str:code>/photo/upload/', PhotoUploadView.as_view(), name='photo-upload'),
    path('<str:username>/<str:code>/video/upload/', VideoUploadView.as_view(), name='video-upload'),
    path('<str:username>/<str:code>/block-user/', BlockUserView.as_view(), name='block-user'),
    path('<str:username>/<str:code>/unblock/', UnblockUserView.as_view(), name='unblock-user'),
    path('<str:username>/<str:code>/blocked-users/', BlockedUsersListView.as_view(), name='blocked-users-list'),
    path('<str:username>/<str:code>/muted-users/', MutedUsersInChatView.as_view(), name='muted-users'),
    path('<str:username>/<str:code>/spotlight/', SpotlightListView.as_view(), name='spotlight-list'),
    path('<str:username>/<str:code>/spotlight/add/', SpotlightAddView.as_view(), name='spotlight-add'),
    path('<str:username>/<str:code>/spotlight/remove/', SpotlightRemoveView.as_view(), name='spotlight-remove'),
    path('<str:username>/<str:code>/participants/search/', ParticipantSearchView.as_view(), name='participants-search'),
    path('<str:username>/<str:code>/gifts/catalog/', GiftCatalogView.as_view(), name='gift-catalog'),
    path('<str:username>/<str:code>/gifts/send/', SendGiftView.as_view(), name='gift-send'),
    path('<str:username>/<str:code>/gifts/acknowledge/', AcknowledgeGiftView.as_view(), name='gift-acknowledge'),
    path('<str:username>/<str:code>/intros/<str:key>/dismiss/', DismissIntroView.as_view(), name='dismiss-intro'),
    path('<str:username>/<str:code>/refresh-session/', RefreshSessionView.as_view(), name='refresh-session'),
]
