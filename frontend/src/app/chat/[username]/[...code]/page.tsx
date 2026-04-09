'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { flushSync } from 'react-dom';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { api, chatApi, messageApi, authApi, backRoomApi, giftApi, isTokenExpiringSoon, isTokenMissingSessionKey, type ChatRoom, type ChatTheme, type Message, type ReactionSummary, type GiftNotification, type AnonymousParticipationInfo } from '@/lib/api';
import Header from '@/components/Header';
import ChatSettingsSheet from '@/components/ChatSettingsSheet';
import GameRoomTab from '@/components/GameRoomTab';
import FloatingActionButton from '@/components/FloatingActionButton';
import GameRoomView from '@/components/GameRoomView';
import MainChatView from '@/components/MainChatView';
import MessageActionsModal from '@/components/MessageActionsModal';
import JoinChatModal from '@/components/JoinChatModal';
import { GiftReceivedPopup } from '@/components/GiftReceivedPopup';
import FeatureIntroModal from '@/components/FeatureIntroModal';
import LoginModal, { LoginFormContent } from '@/components/LoginModal';
import RegisterModal, { RegisterFormContent } from '@/components/RegisterModal';
import VoiceMessagePlayer from '@/components/VoiceMessagePlayer';
import MessageInput from '@/components/MessageInput';
import { UsernameStorage, getFingerprint } from '@/lib/usernameStorage';
import { fetchGiftCatalog } from '@/lib/gifts';
import { playSendMessageSound, playReceiveMessageSound } from '@/lib/sounds';
import { Settings, BadgeCheck, Crown, Gamepad2, MessageSquare, ArrowLeft, Reply, X, Gift, Eye, Radio, Bell, Star } from 'lucide-react';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { type RecordingMetadata } from '@/lib/waveform';
import { consumeFreshNavigation, markChatVisited, hasChatBeenVisited, clearChatVisited } from '@/lib/modalState';
import { verifyHuman } from '@/lib/turnstile';

// Type for Axios-style errors
interface ApiError {
  response?: {
    data?: { detail?: string; error?: string; non_field_errors?: string[] } | string | string[];
    status?: number;
  };
  message?: string;
}

// Type for window extensions used by global methods
interface ChatPopWindow extends Window {
  __voiceRecorderSendMethod?: () => void;
  __mediaPickerHasMedia?: boolean;
  __mediaPickerSendMethod?: () => void;
}

// Type for camelCase theme (used by components)
interface CamelCaseTheme {
  themeColor: ChatTheme['theme_color'];
  container: string;
  header: string;
  headerTitle: string;
  headerTitleFade: string;
  headerSubtitle: string;
  stickySection: string;
  messagesArea: string;
  messagesAreaContainer: string;
  messagesAreaBg: string;
  hostMessage: string;
  stickyHostMessage: string;
  hostText: string;
  hostMessageFade: string;
  pinnedMessage: string;
  stickyPinnedMessage: string;
  pinnedText: string;
  pinnedMessageFade: string;
  regularMessage: string;
  regularText: string;
  spotlightMessage: string;
  spotlightText: string;
  spotlightIconColor: string;
  myMessage: string;
  myText: string;
  voiceMessageStyles: Record<string, unknown>;
  myVoiceMessageStyles: Record<string, unknown>;
  hostVoiceMessageStyles: Record<string, unknown>;
  pinnedVoiceMessageStyles: Record<string, unknown>;
  filterButtonActive: string;
  filterButtonInactive: string;
  inputArea: string;
  inputField: string;
  pinIconColor: string;
  broadcastIconColor: string;
  crownIconColor: string;
  badgeIconColor: string;
  replyIconColor: string;
  myUsername: string;
  regularUsername: string;
  hostUsername: string;
  myHostUsername: string;
  pinnedUsername: string;
  stickyHostUsername: string;
  stickyPinnedUsername: string;
  myTimestamp: string;
  regularTimestamp: string;
  hostTimestamp: string;
  pinnedTimestamp: string;
  replyPreviewContainer: string;
  replyPreviewIcon: string;
  replyPreviewUsername: string;
  replyPreviewContent: string;
  replyPreviewCloseButton: string;
  replyPreviewCloseIcon: string;
  reactionHighlightBg: string;
  reactionHighlightBorder: string;
  reactionHighlightText: string;
  modalStyles: Record<string, string>;
  emojiPickerStyles: Record<string, string>;
  giftStyles: Record<string, string>;
  inputStyles: Record<string, string>;
  videoPlayerStyles: Record<string, string>;
  uiStyles: Record<string, string>;
  avatarSize: string | null;
  avatarBorder: string | null;
  avatarSpacing: string;
}

// Convert snake_case API theme to camelCase for component compatibility
function convertThemeToCamelCase(theme: ChatTheme): CamelCaseTheme {
  return {
    themeColor: theme.theme_color,
    container: theme.container,
    header: theme.header,
    headerTitle: theme.header_title,
    headerTitleFade: theme.header_title_fade,
    headerSubtitle: theme.header_subtitle,
    stickySection: theme.sticky_section,
    messagesArea: theme.messages_area,
    messagesAreaContainer: theme.messages_area_container,
    messagesAreaBg: theme.messages_area_bg,
    hostMessage: theme.host_message,
    stickyHostMessage: theme.sticky_host_message,
    hostText: theme.host_text,
    hostMessageFade: theme.host_message_fade,
    pinnedMessage: theme.pinned_message,
    stickyPinnedMessage: theme.sticky_pinned_message,
    pinnedText: theme.pinned_text,
    pinnedMessageFade: theme.pinned_message_fade,
    regularMessage: theme.regular_message,
    regularText: theme.regular_text,
    spotlightMessage: theme.spotlight_message,
    spotlightText: theme.spotlight_text,
    spotlightIconColor: theme.spotlight_icon_color,
    myMessage: theme.my_message,
    myText: theme.my_text,
    voiceMessageStyles: theme.voice_message_styles || {},
    myVoiceMessageStyles: theme.my_voice_message_styles || {},
    hostVoiceMessageStyles: theme.host_voice_message_styles || {},
    pinnedVoiceMessageStyles: theme.pinned_voice_message_styles || {},
    filterButtonActive: theme.filter_button_active,
    filterButtonInactive: theme.filter_button_inactive,
    inputArea: theme.input_area,
    inputField: theme.input_field,
    pinIconColor: theme.pin_icon_color,
    broadcastIconColor: theme.broadcast_icon_color,
    crownIconColor: theme.crown_icon_color,
    badgeIconColor: theme.badge_icon_color,
    replyIconColor: theme.reply_icon_color,
    myUsername: theme.my_username,
    regularUsername: theme.regular_username,
    hostUsername: theme.host_username,
    myHostUsername: theme.my_host_username,
    pinnedUsername: theme.pinned_username,
    stickyHostUsername: theme.sticky_host_username,
    stickyPinnedUsername: theme.sticky_pinned_username,
    myTimestamp: theme.my_timestamp,
    regularTimestamp: theme.regular_timestamp,
    hostTimestamp: theme.host_timestamp,
    pinnedTimestamp: theme.pinned_timestamp,
    replyPreviewContainer: theme.reply_preview_container,
    replyPreviewIcon: theme.reply_preview_icon,
    replyPreviewUsername: theme.reply_preview_username,
    replyPreviewContent: theme.reply_preview_content,
    replyPreviewCloseButton: theme.reply_preview_close_button,
    replyPreviewCloseIcon: theme.reply_preview_close_icon,
    reactionHighlightBg: theme.reaction_highlight_bg,
    reactionHighlightBorder: theme.reaction_highlight_border,
    reactionHighlightText: theme.reaction_highlight_text,
    modalStyles: theme.modal_styles || {},
    emojiPickerStyles: theme.emoji_picker_styles || {},
    giftStyles: theme.gift_styles || {},
    inputStyles: theme.input_styles || {},
    videoPlayerStyles: theme.video_player_styles || {},
    uiStyles: theme.ui_styles || {},
    avatarSize: theme.avatar_size,
    avatarBorder: theme.avatar_border,
    avatarSpacing: theme.avatar_spacing,
  };
}

// Fallback theme if chat room has no theme assigned
const defaultTheme: ChatTheme = {
  theme_id: 'dark-mode',
  name: 'Dark Mode',
  is_dark_mode: true,
  theme_color: {
    light: '#18181b',
    dark: '#18181b',
  },
  container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-zinc-950",
  header: "border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
  header_title: "text-lg font-bold text-zinc-100",
  header_title_fade: "bg-gradient-to-l from-zinc-900 to-transparent",
  header_subtitle: "text-sm text-zinc-400",
  sticky_section: "absolute top-0 left-0 right-0 z-20 border-b border-zinc-800 bg-zinc-900/90 px-4 py-2 space-y-2 shadow-lg",
  messages_area: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-2",
  messages_area_bg: "",
  messages_area_container: "bg-zinc-900",
  host_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1 font-medium transition-all duration-300",
  sticky_host_message: "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-zinc-800 font-medium transition-all duration-300",
  host_text: "text-sm text-white",
  host_message_fade: "bg-gradient-to-l from-teal-600 to-transparent",
  pinned_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded-lg px-3 py-2 pb-2 bg-purple-950/50 border border-purple-500/50",
  sticky_pinned_message: "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-purple-900 border border-purple-500/40 shadow-md",
  pinned_text: "text-sm text-white",
  pinned_message_fade: "bg-gradient-to-l from-amber-700 to-transparent",
  regular_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1",
  regular_text: "text-sm text-white",
  my_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1",
  my_text: "text-sm text-white",
  filter_button_active: "px-3 py-1.5 rounded text-xs tracking-wider bg-emerald-500 text-emerald-950 border border-emerald-400",
  filter_button_inactive: "px-3 py-1.5 rounded text-xs tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700",
  input_area: "border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
  input_field: "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500",
  voice_message_styles: {
    containerBg: "bg-white/10",
    playButton: "bg-white hover:bg-white/90",
    playIconColor: "text-zinc-800",
    waveformActive: "bg-white",
    waveformInactive: "bg-white/40",
    durationTextColor: "text-white/80",
  },
  my_voice_message_styles: {
    containerBg: "bg-white/10",
    playButton: "bg-white hover:bg-white/90",
    playIconColor: "text-zinc-800",
    waveformActive: "bg-white",
    waveformInactive: "bg-white/40",
    durationTextColor: "text-white/80",
  },
  host_voice_message_styles: {
    containerBg: "bg-white/10",
    playButton: "bg-white hover:bg-white/90",
    playIconColor: "text-zinc-800",
    waveformActive: "bg-white",
    waveformInactive: "bg-white/40",
    durationTextColor: "text-white/80",
  },
  pinned_voice_message_styles: {
    containerBg: "bg-white/10",
    playButton: "bg-white hover:bg-white/90",
    playIconColor: "text-zinc-800",
    waveformActive: "bg-white",
    waveformInactive: "bg-white/40",
    durationTextColor: "text-white/80",
  },
  pin_icon_color: "text-purple-400",
  broadcast_icon_color: "text-blue-400",
  crown_icon_color: "text-amber-400",
  badge_icon_color: "text-blue-500",
  reply_icon_color: "text-emerald-300",
  reaction_highlight_bg: "bg-purple-500/20",
  reaction_highlight_border: "border border-purple-500/50",
  reaction_highlight_text: "text-zinc-200",
  my_username: "text-sm font-bold text-red-500",
  regular_username: "text-sm font-bold text-white",
  host_username: "text-sm font-bold text-amber-400",
  my_host_username: "text-sm font-semibold text-red-500",
  pinned_username: "text-sm font-bold text-purple-400",
  sticky_host_username: "text-xs font-semibold text-amber-400",
  sticky_pinned_username: "text-xs font-semibold text-purple-400",
  my_timestamp: "text-xs text-white opacity-60",
  regular_timestamp: "text-xs text-white opacity-60",
  host_timestamp: "text-xs opacity-60",
  pinned_timestamp: "text-xs opacity-60",
  reply_preview_container: "flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700",
  reply_preview_icon: "w-4 h-4 flex-shrink-0 text-cyan-400",
  reply_preview_username: "text-xs font-semibold text-zinc-300",
  reply_preview_content: "text-xs text-zinc-400 truncate",
  reply_preview_close_button: "p-1 hover:bg-zinc-700 rounded",
  reply_preview_close_icon: "w-4 h-4 text-zinc-500",
  // Component style overrides
  modal_styles: {
    overlay: "bg-black/60 backdrop-blur-md",
    container: "bg-zinc-900",
    border: "border border-zinc-700",
    dragHandle: "bg-gray-600",
    messagePreview: "bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl",
    actionButton: "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500 text-zinc-50 border border-zinc-500",
    actionIcon: "text-cyan-400",
    divider: "border-zinc-700/50",
    usernameText: "text-gray-300",
    title: "text-zinc-50",
    body: "text-zinc-400",
    primaryButton: "bg-[#404eed] hover:bg-[#3640d9] text-white",
    secondaryButton: "bg-zinc-700 hover:bg-zinc-600 text-zinc-50",
    input: "bg-zinc-800 border border-zinc-600 text-zinc-50 placeholder-zinc-400 focus:ring-2 focus:ring-cyan-400",
    closeButton: "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800",
    error: "bg-red-900/20 border border-red-800 text-red-400",
    messageText: "text-white",
    photoThumbnailBg: "bg-zinc-700",
    voiceText: "text-white/60",
    timestampText: "text-white opacity-60",
    actionLabel: "text-zinc-50",
    subtitle: "text-gray-400",
    inputField: "flex-1 px-4 py-2 border border-zinc-700 rounded-lg bg-zinc-800 text-zinc-100 placeholder-zinc-500",
    inputBorder: "border-zinc-500",
    avatarFallbackBg: "bg-zinc-700",
    badgeIconBg: "#18181b",
    destructiveText: "text-red-400",
    actionBtnBg: "#27272a",
    actionBtnBorder: "#3f3f46",
  },
  emoji_picker_styles: {
    selectedBg: "bg-purple-500/30",
    selectedRing: "ring-2 ring-purple-500/60",
    unselectedBg: "bg-zinc-800 hover:bg-zinc-700",
  },
  gift_styles: {
    cardBgForMe: "bg-purple-950/50 border border-purple-500/50",
    cardBg: "bg-zinc-800/80 border border-zinc-700",
    emojiContainer: "bg-zinc-700/80",
    nameText: "text-white",
    priceBadge: "bg-cyan-900/50 text-cyan-400",
    priceText: "text-cyan-400",
    recipientTextForMe: "text-purple-400",
    recipientText: "text-zinc-300",
    toPrefix: "text-zinc-400",
  },
  input_styles: {
    sendButton: "bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700",
    collapseButton: "bg-zinc-700 text-gray-400 hover:bg-zinc-600",
    disabledBg: "bg-zinc-800/60 border border-zinc-700/50",
    disabledText: "text-zinc-500",
    textFadeGradient: "rgb(39, 39, 42)",
    avatarFallbackBg: "bg-zinc-700",
    youPill: "bg-white/10 text-zinc-400",
  },
  video_player_styles: {
    overlay: "bg-black/30",
    playButtonBg: "bg-white/90",
    playIcon: "text-gray-800",
    spinner: "border-gray-600",
    hoverOverlay: "bg-black/20",
    pauseIcon: "text-white",
    durationBadge: "bg-black/70 text-white",
    progressBg: "bg-black/30",
    progressFill: "bg-white",
  },
  ui_styles: {
    emptyStateText: "text-zinc-600",
    emptyStateSubtext: "text-zinc-500",
    avatarConnector: "bg-zinc-600/30",
    avatarFallbackBg: "bg-zinc-700",
    badgeIconBg: "#18181b",
    loadingBg: "bg-zinc-900",
    loadingCard: "bg-zinc-800 text-zinc-200",
    pinAmountText: "text-zinc-300",
    reactionPillBg: "bg-zinc-800 border border-zinc-700",
    reactionPillText: "text-zinc-400",
    reactionHighlightBg: "bg-purple-500/20",
    reactionHighlightBorder: "border border-purple-500/50",
    reactionHighlightText: "text-zinc-200",
    pinBadgeBg: "bg-white/10",
    loadingIndicatorText: "text-gray-400",
    loadingIndicatorBg: "bg-black/50",
    replyContextOwn: "bg-white/10 border border-white/10 hover:bg-white/15",
    replyContextOther: "bg-white/10 border border-zinc-600 hover:bg-white/15",
    replyIconColor: "text-gray-300",
    replyGiftBadge: "bg-zinc-700/60 border border-zinc-600/50",
    replyGiftText: "text-zinc-300",
    replyPreviewText: "text-gray-300",
    mediaLoadingText: "text-gray-500",
  },
  // Avatar settings
  avatar_size: null,
  avatar_border: null,
  avatar_spacing: "mr-3",
};

export default function ChatPage() {
  const params = useParams();
  const codeSegments = params.code as string[];
  const code = codeSegments[0];
  const authSegment = codeSegments[1] as 'login' | 'signup' | undefined;
  const roomUsername = params.username as string;
  const searchParams = useSearchParams();
  const router = useRouter();

  // Auth mode: URL path segment (mobile: /login, /signup) or query param (desktop: ?auth=login)
  const [authModeState, setAuthModeState] = useState<string | null>(
    authSegment === 'login' ? 'login'
    : authSegment === 'signup' ? 'register'
    : null
  );
  const authMode = authModeState || searchParams.get('auth');

  // Base chat URL without auth segments
  const baseChatUrl = `/chat/${roomUsername}/${code}`;

  const openAuth = (mode: 'login' | 'signup') => {
    setAuthModeState(mode === 'signup' ? 'register' : 'login');
    window.history.pushState(null, '', `${baseChatUrl}/${mode}`);
  };

  const switchAuth = (mode: 'login' | 'signup') => {
    setAuthModeState(mode === 'signup' ? 'register' : 'login');
    window.history.replaceState(null, '', `${baseChatUrl}/${mode}`);
  };

  const closeModal = () => {
    setAuthModeState(null);
    window.history.pushState(null, '', baseChatUrl);
  };

  // No theme switching - always use dark-mode

  // Verify human on page load (session-based, runs once)
  useEffect(() => { verifyHuman(); }, []);

  // Detect mobile viewport for inline auth rendering
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);


  const [chatRoom, setChatRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | undefined>(undefined);
  const [hasReservedUsername, setHasReservedUsername] = useState(false);
  const [userAvatarUrl, setUserAvatarUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fingerprint, setFingerprint] = useState<string | undefined>(undefined);
  const [participationTheme, setParticipationTheme] = useState<ChatTheme | null>(null);
  const initialScrollDoneRef = useRef(false); // Track if initial scroll to bottom is complete

  // Join state for guests
  const [hasJoined, setHasJoined] = useState(false);
  const [hasJoinedBefore, setHasJoinedBefore] = useState(false);
  const [joinModalKey, setJoinModalKey] = useState(0); // Force remount on back navigation
  const [isBlocked, setIsBlocked] = useState(false);
  const [anonymousParticipations, setAnonymousParticipations] = useState<AnonymousParticipationInfo[]>([]);
  const [registeredDisplayName, setRegisteredDisplayName] = useState(''); // Stable registered username for identity chooser
  const [registeredAvatarUrl, setRegisteredAvatarUrl] = useState<string | null>(null); // Stable registered avatar for identity chooser
  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [joinError, setJoinError] = useState('');

  // Preview state for identity chooser — keeps source-of-truth untouched
  const [previewUsername, setPreviewUsername] = useState<string | null>(null);
  const [previewAvatarUrl, setPreviewAvatarUrl] = useState<string | null | undefined>(undefined);
  const [previewHasReservedUsername, setPreviewHasReservedUsername] = useState<boolean | null>(null);
  const [previewIsHost, setPreviewIsHost] = useState<boolean | null>(null);

  // Scroll-to-bottom indicator
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [expandStickySignal, setExpandStickySignal] = useState(0);
  const headerTouchStartYRef = useRef<number | null>(null);

  // Message input state (message text is managed locally in MessageInput component)
  const [sending, setSending] = useState(false);
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);

  // Infinite scroll state
  const [hasMoreMessages, setHasMoreMessages] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);

  // Room navigation — unified state for all views
  type Room = 'main' | 'focus' | 'gifts' | 'broadcast' | 'backroom';
  const [currentRoom, setCurrentRoom] = useState<Room>('main');
  const [previousRoom, setPreviousRoom] = useState<Room>('main');
  const [roomLoading, setRoomLoading] = useState(false);

  // Feature intro tracking
  const [seenIntros, setSeenIntros] = useState<Record<string, boolean>>({});
  const [showFeatureIntro, setShowFeatureIntro] = useState<string | null>(null);

  // Sticky height from MainChatView (for FAB strip positioning)
  // Debounce drops to 0 — room switches briefly clear sticky content but it reappears.
  // Genuine removals (pin expiry) stay at 0 permanently, so a longer delay is fine.
  const [stickyHeight, setStickyHeight] = useState(0);
  const [stickyIsHidden, setStickyIsHidden] = useState(false);
  const expandedStickyHeightRef = useRef(0);
  // Remember the last expanded height so we can use it instantly on expand
  // (before ResizeObserver reports the new full height)
  useEffect(() => {
    if (!stickyIsHidden && stickyHeight > 40) {
      expandedStickyHeightRef.current = stickyHeight;
    }
  }, [stickyHeight, stickyIsHidden]);
  // FAB strip positioning — Android perf:
  // Instead of animating the `top` CSS property (which triggers layout on every frame
  // and was laggy on Android Chrome), we keep `top` anchored at the EXPANDED position
  // and apply a GPU-composited transform: translateY(-offset) when the sticky is
  // collapsed. Transform animations are the only reliable fast path on Blink.
  // `top` still updates when sticky content changes size (new pin etc.) but those
  // transitions aren't animated — content-change jumps are rare and acceptable.
  const COLLAPSED_STICKY_HEIGHT = 31;
  const fabTopExpanded = stickyHeight > 0
    ? (stickyHeight > 40 ? stickyHeight + 8 : (expandedStickyHeightRef.current || stickyHeight) + 8)
    : 8;
  const fabCollapseOffset = stickyHeight > 0
    ? Math.max(0, fabTopExpanded - (COLLAPSED_STICKY_HEIGHT + 8))
    : 0;
  const stickyZeroTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleStickyHeightChange = useCallback((height: number) => {
    if (stickyZeroTimerRef.current) {
      clearTimeout(stickyZeroTimerRef.current);
      stickyZeroTimerRef.current = null;
    }
    if (height > 0) {
      setStickyHeight(height);
    } else {
      stickyZeroTimerRef.current = setTimeout(() => setStickyHeight(0), 1500);
    }
  }, []);

  // FAB scroll strip fade indicators
  const fabStripRef = useRef<HTMLDivElement>(null);
  const [fabCanScrollUp, setFabCanScrollUp] = useState(false);
  const [fabCanScrollDown, setFabCanScrollDown] = useState(false);
  const updateFabScrollFades = useCallback(() => {
    const el = fabStripRef.current;
    if (!el) return;
    setFabCanScrollUp(el.scrollTop > 4);
    setFabCanScrollDown(el.scrollTop + el.clientHeight < el.scrollHeight - 4);
  }, []);

  // Initialize and update fade indicators when strip size changes
  useEffect(() => {
    const el = fabStripRef.current;
    if (!el) return;
    updateFabScrollFades();
    const observer = new ResizeObserver(() => updateFabScrollFades());
    observer.observe(el);
    return () => observer.disconnect();
  }, [updateFabScrollFades, hasJoined, stickyHeight]);

  // Helper: get filter param for API calls (only chat filter rooms have a filter)
  const getRoomFilter = useCallback((room: Room): string | undefined => {
    if (room === 'focus' || room === 'gifts' || room === 'broadcast') return room;
    return undefined;
  }, []);

  // Helper: is this a separate full-screen view (not a filtered chat)?
  const isSeparateViewRoom = useCallback((room: Room): boolean => {
    return room === 'backroom';
  }, []);

  // Helper: loading text per room
  const getRoomLoadingText = useCallback((target: Room, prev: Room): string => {
    if (target === 'focus') return 'Focusing...';
    if (target === 'gifts') return 'Gifting...';
    if (target === 'broadcast') return 'Broadcasting...';
    if (target === 'backroom') return 'Gaming...';
    if (prev === 'focus') return 'Unfocusing...';
    if (prev === 'gifts') return 'Ungifting...';
    if (prev === 'broadcast') return 'Unbroadcasting...';
    if (prev === 'backroom') return 'Ungaming...';
    return 'Loading...';
  }, []);

  // Emoji reactions state
  const [messageReactions, setMessageReactions] = useState<Record<string, ReactionSummary[]>>({});

  // Independent sticky state — survives room switches, only updated from authoritative sources
  const [stickyHostMessage, setStickyHostMessage] = useState<Message | null>(null);
  const [stickyPinnedMsg, setStickyPinnedMsg] = useState<Message | null>(null);

  // Mute state — declared here because the sticky/filtered memos below depend on it.
  const [mutedUsernames, setMutedUsernames] = useState<Set<string>>(new Set());

  // Spotlight state — host-curated featured users (visible to all)
  const [spotlightUsernames, setSpotlightUsernames] = useState<Set<string>>(new Set());

  // Shared mute-filter helper matching the rules in filteredMessages.applyMute.
  // Returns the message if it should render, or null if it should be hidden.
  const applyMuteToSticky = useCallback((msg: Message | null): Message | null => {
    if (!msg) return null;
    const author = msg.username || '';
    if (mutedUsernames.has(author)) {
      if (msg.is_broadcast) return msg;
      if (
        msg.message_type === 'gift' &&
        msg.gift_recipient &&
        msg.gift_recipient.toLowerCase() === (username || '').toLowerCase()
      ) {
        return msg;
      }
      return null;
    }
    if (msg.message_type === 'gift' && msg.gift_recipient) {
      if (
        mutedUsernames.has(msg.gift_recipient) &&
        author.toLowerCase() !== (username || '').toLowerCase()
      ) {
        return null;
      }
    }
    return msg;
  }, [mutedUsernames, username]);

  // Stable array reference for StickySection memo — avoids re-render on every parent render.
  // Applies mute rules: muted users don't appear in host sticky even if they're the host.
  const stickyHostMessages = useMemo(() => {
    const filtered = applyMuteToSticky(stickyHostMessage);
    return filtered ? [filtered] : [];
  }, [stickyHostMessage, applyMuteToSticky]);

  // Apply mute rules to the sticky pinned message.
  const stickyPinnedMsgFiltered = useMemo(
    () => applyMuteToSticky(stickyPinnedMsg),
    [stickyPinnedMsg, applyMuteToSticky]
  );

  // Settings sheet state
  const [showSettingsSheet, setShowSettingsSheet] = useState(false);

  // Gift notification state
  const [giftQueue, setGiftQueue] = useState<GiftNotification[]>([]);

  // WebSocket state
  const [sessionToken, setSessionToken] = useState<string | null>(null);

  // Extract sticky-worthy messages and update state (never clears — only updates)
  const updateStickyFromMessages = useCallback((msgs: Message[]) => {
    const latestHost = msgs.filter(m => m.is_from_host).slice(-1)[0];
    if (latestHost) setStickyHostMessage(latestHost);

    const now = new Date();
    const topPinned = msgs
      .filter(m => m.is_pinned && !m.is_from_host && (!m.sticky_until || new Date(m.sticky_until) > now))
      .sort((a, b) => parseFloat(b.current_pin_amount) - parseFloat(a.current_pin_amount))[0];
    if (topPinned) setStickyPinnedMsg(topPinned);
  }, []);

  // Switch room — unified handler for all room transitions (lateral navigation)
  const switchRoom = useCallback(async (target: Room) => {
    if (target === currentRoom) return;

    // For separate-view rooms (backroom): set room state with loading delay
    if (isSeparateViewRoom(target)) {
      setPreviousRoom(currentRoom);
      setRoomLoading(true);
      setCurrentRoom(target);
      setReplyingTo(null);
      window.history.replaceState({ room: target }, '', window.location.href);
      await new Promise(resolve => setTimeout(resolve, 500));
      setRoomLoading(false);
      return;
    }

    // For chat rooms (main/focus/gifts): clear messages, fetch fresh, use replaceState
    setPreviousRoom(currentRoom);
    setRoomLoading(true);
    setCurrentRoom(target);
    setHasMoreMessages(true);
    setReplyingTo(null);
    window.history.replaceState({ room: target }, '', window.location.href);

    const filterParam = getRoomFilter(target);
    const filterUser = filterParam && filterParam !== 'broadcast' ? username : undefined;

    if (target === 'main') {
      // Main room: fetch fresh (no firehose caching)
      try {
        const { messages: msgs, pinnedMessages } = await messageApi.getMessages(code, roomUsername, sessionToken || undefined, undefined, undefined);
        const pinnedMap = new Map(pinnedMessages.map(pm => [pm.id, pm]));
        const updatedMessages = msgs.map(msg => {
          const pinnedVersion = pinnedMap.get(msg.id);
          if (pinnedVersion) {
            return { ...msg, is_pinned: pinnedVersion.is_pinned, pinned_at: pinnedVersion.pinned_at, sticky_until: pinnedVersion.sticky_until, pin_amount_paid: pinnedVersion.pin_amount_paid, current_pin_amount: pinnedVersion.current_pin_amount };
          }
          return msg;
        });
        const messageIds = new Set(msgs.map(m => m.id));
        const uniquePinnedMessages = pinnedMessages.filter(pm => !messageIds.has(pm.id));
        const allMessages = [...updatedMessages, ...uniquePinnedMessages].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        setMessages(allMessages);
        updateStickyFromMessages(allMessages);
        // Extract reactions
        const reactions: Record<string, ReactionSummary[]> = {};
        allMessages.forEach((msg) => {
          if (msg.reactions && msg.reactions.length > 0) {
            reactions[msg.id] = msg.reactions;
          }
        });
        setMessageReactions(reactions);
      } catch (err) {
        console.error('Failed to load messages:', err);
      } finally {
        setRoomLoading(false);
      }
    } else {
      // Filter rooms (focus/gifts): fetch with filter + minimum loading delay
      const minDelay = new Promise(resolve => setTimeout(resolve, 500));
      try {
        const [, { messages: filtered, pinnedMessages }] = await Promise.all([
          minDelay,
          messageApi.getMessages(code, roomUsername, sessionToken || undefined, filterParam, filterUser)
        ]);
        const pinnedMap = new Map(pinnedMessages.map(pm => [pm.id, pm]));
        const updatedMessages = filtered.map(msg => {
          const pinnedVersion = pinnedMap.get(msg.id);
          if (pinnedVersion) {
            return { ...msg, is_pinned: pinnedVersion.is_pinned, pinned_at: pinnedVersion.pinned_at, sticky_until: pinnedVersion.sticky_until, pin_amount_paid: pinnedVersion.pin_amount_paid, current_pin_amount: pinnedVersion.current_pin_amount };
          }
          return msg;
        });
        const messageIds = new Set(filtered.map(m => m.id));
        const uniquePinnedMessages = pinnedMessages.filter(pm => !messageIds.has(pm.id));
        const allMessages = [...updatedMessages, ...uniquePinnedMessages].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        setMessages(allMessages);
        updateStickyFromMessages(allMessages);
      } catch (err) {
        console.error('Failed to load filtered messages:', err);
      } finally {
        setRoomLoading(false);
      }
    }

    // Show feature intro if user hasn't seen it for this room type
    const introRooms: Room[] = ['focus'];
    if (introRooms.includes(target) && !seenIntros[target]) {
      setShowFeatureIntro(target);
    }

    shouldAutoScrollRef.current = true;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
      });
    });
  }, [currentRoom, code, roomUsername, sessionToken, username, getRoomFilter, isSeparateViewRoom, seenIntros, updateStickyFromMessages]);

  // Dismiss a feature intro
  const handleDismissIntro = useCallback((key: string) => {
    setShowFeatureIntro(null);
    setSeenIntros(prev => ({ ...prev, [key]: true }));
    // Inline API call to avoid webpack chunk caching issues with chatApi.dismissIntro
    const username = roomUsername || 'discover';
    api.post(`/api/chats/${username}/${code}/intros/${key}/dismiss/`, { fingerprint })
      .catch(err => console.error('[FeatureIntro] Dismiss failed:', err));
  }, [code, fingerprint, roomUsername]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = useCallback((message: Message) => {
    setMessages((prev) => {
      // Check if message already exists (avoid duplicates)
      if (prev.some((m) => m.id === message.id)) {
        return prev;
      }
      // Add new message - don't force auto-scroll here
      // Let handleScroll manage shouldAutoScrollRef based on user's position
      return [...prev, message];
    });
    // Update sticky if this is a host message
    if (message.is_from_host) {
      setStickyHostMessage(message);
    }
    // Play receive sound only when someone replies to YOUR message (not their own)
    if (message.reply_to_message?.username === username && message.username !== username) {
      playReceiveMessageSound();
    }
  }, [username]);

  // Handle user blocked event (eviction)
  const handleUserBlocked = useCallback((message: string) => {
    // Clear local state
    localStorage.removeItem(`chat_session_${code}`);
    setSessionToken(null);
    setHasJoined(false);
    setMessages([]);
    setStickyHostMessage(null);
    setStickyPinnedMsg(null);

    // Show alert and redirect to home page
    alert(message || 'You have been removed from this chat.');
    window.location.href = '/';
  }, [code]);

  // Handle user kicked event (host removed user from chat)
  const handleUserKicked = useCallback((message: string) => {
    // Keep session token so getMyParticipation returns is_blocked=true with original username
    // Don't redirect — stay on the chat page and show blocked state
    setHasJoined(false);
    setIsBlocked(true);
    setMessages([]);
    setStickyHostMessage(null);
    setStickyPinnedMsg(null);
  }, []);

  // Handle ban status change (update is_banned on all messages from that user)
  const handleBanStatusChanged = useCallback((bannedUsername: string, isBanned: boolean) => {
    setMessages(prev => prev.map(msg =>
      msg.username.toLowerCase() === bannedUsername.toLowerCase()
        ? { ...msg, is_banned: isBanned }
        : msg
    ));
  }, []);

  // Handle reaction WebSocket events
  const handleReactionEvent = useCallback(async (data: { message_id: string; action: string; emoji: string }) => {
    const { message_id } = data;

    // Fetch fresh reaction summary for this message (with sessionToken for has_reacted)
    try {
      const { summary } = await messageApi.getReactions(code, message_id, roomUsername, sessionToken || undefined);
      setMessageReactions(prev => ({
        ...prev,
        [message_id]: summary
      }));
    } catch (error) {
      console.error('Failed to fetch reactions:', error);
    }
  }, [code, sessionToken]);

  // Handle message deletion WebSocket events
  const handleMessageDeleted = useCallback((messageId: string) => {
    // Remove message from local state
    setMessages(prev => prev.filter(msg => msg.id !== messageId));

    // Remove reactions for this message
    setMessageReactions(prev => {
      const updated = { ...prev };
      delete updated[messageId];
      return updated;
    });
  }, []);

  // Handle message pinned WebSocket events
  const handleMessagePinned = useCallback((message: Message, isTopPin: boolean) => {
    // Update the message in local state with new pin data
    setMessages(prev => prev.map(msg =>
      msg.id === message.id
        ? { ...msg, is_pinned: message.is_pinned, pin_amount_paid: message.pin_amount_paid, current_pin_amount: message.current_pin_amount, pinned_at: message.pinned_at, sticky_until: message.sticky_until }
        : msg
    ));
    // Update sticky pinned if this is the top pin
    if (isTopPin && !message.is_from_host) {
      setStickyPinnedMsg(message);
    }
  }, []);

  const handleMessageBroadcast = useCallback((message: Message, isBroadcast: boolean) => {
    setMessages(prev => prev.map(msg =>
      msg.id === message.id
        ? { ...msg, is_broadcast: isBroadcast }
        : msg
    ));
  }, []);

  // Handle visibility changes (mobile app switching)
  // Refetch messages to catch any missed while page was hidden
  const loadMessagesRef = useRef<() => void>(null);
  const handleVisibilityChange = useCallback((isVisible: boolean) => {
    if (isVisible && loadMessagesRef.current) {
      loadMessagesRef.current();
    }
  }, []);

  // WebSocket connection
  const { sendMessage: wsSendMessage, sendRawMessage, isConnected } = useChatWebSocket({
    chatCode: code,
    sessionToken,
    onMessage: handleWebSocketMessage,
    onUserBlocked: handleUserBlocked,
    onUserKicked: handleUserKicked,
    onBanStatusChanged: handleBanStatusChanged,
    onReaction: handleReactionEvent,
    onMessageDeleted: handleMessageDeleted,
    onMessagePinned: handleMessagePinned,
    onMessageBroadcast: handleMessageBroadcast,
    onGiftReceived: useCallback((gift: GiftNotification) => {
      setGiftQueue(prev => [...prev, gift]);
    }, []),
    onGiftQueue: useCallback((gifts: GiftNotification[]) => {
      setGiftQueue(gifts);
    }, []),
    onGiftAcknowledged: useCallback((messageIds: string[]) => {
      setMessages(prev => prev.map(msg =>
        messageIds.includes(msg.id) ? { ...msg, is_gift_acknowledged: true } : msg
      ));
    }, []),
    onBlockUpdate: useCallback((action: 'add' | 'remove', blockedUsername: string) => {
      setMutedUsernames(prev => {
        const next = new Set(prev);
        if (action === 'add') next.add(blockedUsername);
        else next.delete(blockedUsername);
        return next;
      });
    }, []),
    onSpotlightUpdate: useCallback((action: 'add' | 'remove', spotlightUsername: string) => {
      setSpotlightUsernames(prev => {
        const next = new Set(prev);
        if (action === 'add') next.add(spotlightUsername);
        else next.delete(spotlightUsername);
        return next;
      });
    }, []),
    onVisibilityChange: handleVisibilityChange,
    enabled: hasJoined || (!!chatRoom && chatRoom.access_mode === 'public'),
  });

  // Fetch muted users in this chat for authenticated users
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!chatRoom) return;
    const authToken = localStorage.getItem('auth_token');
    if (!authToken) return;
    messageApi
      .getMutedUsersInChat(code, roomUsername)
      .then((data) => {
        setMutedUsernames(new Set(data.muted_users.map((u) => u.username)));
      })
      .catch(() => {
        // Silent fail
      });
  }, [chatRoom, code, roomUsername]);

  // Fetch spotlight users (public — anyone who can view the chat can see)
  useEffect(() => {
    if (!chatRoom) return;
    messageApi
      .getSpotlightUsers(code, roomUsername)
      .then((data) => {
        setSpotlightUsernames(new Set(data.spotlight_users.map((u) => u.username)));
      })
      .catch((err) => {
        console.error('Failed to load spotlight users', err);
      });
  }, [chatRoom, code, roomUsername]);

  // Spotlight handlers (host only)
  const handleSpotlightAdd = useCallback(async (targetUsername: string) => {
    try {
      await messageApi.spotlightAdd(code, targetUsername, roomUsername);
      setSpotlightUsernames((prev) => {
        const next = new Set(prev);
        next.add(targetUsername);
        return next;
      });
    } catch (err) {
      console.error('Failed to spotlight user', err);
    }
  }, [code, roomUsername]);

  // Show intro overlay when current user gets spotlighted (first time only)
  useEffect(() => {
    if (!username) return;
    if (!hasJoined) return;
    if (!spotlightUsernames.has(username)) return;
    if (seenIntros.spotlight_first_time) return;
    setShowFeatureIntro('spotlight_first_time');
  }, [spotlightUsernames, username, hasJoined, seenIntros]);

  const handleSpotlightRemove = useCallback(async (targetUsername: string) => {
    try {
      await messageApi.spotlightRemove(code, targetUsername, roomUsername);
      setSpotlightUsernames((prev) => {
        const next = new Set(prev);
        next.delete(targetUsername);
        return next;
      });
    } catch (err) {
      console.error('Failed to unspotlight user', err);
    }
  }, [code, roomUsername]);

  // Detect forward navigation and redirect back to home
  // This prevents users from using browser forward to return to chat join modal
  useEffect(() => {
    const isFreshNavigation = consumeFreshNavigation();

    if (isFreshNavigation) {
      // Valid navigation from modal - allow (don't mark visited yet, that happens on leave)
      return;
    }

    // Not a fresh navigation - check if this is forward navigation
    const existingSession = localStorage.getItem(`chat_session_${code}`);

    if (!existingSession && hasChatBeenVisited(code)) {
      // User visited before but has no session — clear marker so they can rejoin.
      // Previously this redirected to home, but that blocks legitimate direct URL access.
      clearChatVisited(code);
    }

    // First-time visit via direct URL or existing session - allow
  }, [code, router]);

  // Add chat-layout class to body (position:fixed, overflow:hidden, etc.)
  // Remove during mobile inline auth so the page scrolls naturally with the keyboard
  const inlineAuthActive = !!(authMode && isMobile);

  // When closing inline auth, the chat JSX remounts with a fresh DOM — scrollTop is lost.
  // Restore by snapping to bottom (messages/state are preserved in React).
  const prevInlineAuthActiveRef = useRef(inlineAuthActive);
  useEffect(() => {
    if (prevInlineAuthActiveRef.current && !inlineAuthActive) {
      // Transitioned from auth → chat; scroll to bottom after remount
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (container) {
          container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
          shouldAutoScrollRef.current = true;
        }
      });
    }
    prevInlineAuthActiveRef.current = inlineAuthActive;
  }, [inlineAuthActive]);

  useEffect(() => {
    document.body.classList.add('chat-layout');
    return () => {
      document.body.classList.remove('chat-layout');
    };
  }, []);

  // Track visual viewport for auth container — height shrinks when keyboard opens,
  // Track visual viewport to size auth container when keyboard opens
  // Login: pin at top:0 (short form, no scroll needed)
  // Signup: track offsetTop (tall form, iOS scrolls visual viewport)
  const [authStyle, setAuthStyle] = useState<React.CSSProperties>({ height: '100dvh' });
  useEffect(() => {
    if (!inlineAuthActive) return;
    const vv = window.visualViewport;
    if (!vv) return;
    const isLogin = authMode === 'login';
    let lastHeight = 0;
    let lastOffset = 0;
    const update = () => {
      const h = Math.round(vv.height);
      const t = isLogin ? 0 : Math.round(vv.offsetTop);
      if (h === lastHeight && t === lastOffset) return;
      lastHeight = h;
      lastOffset = t;
      setAuthStyle({
        position: 'fixed',
        top: `${t}px`,
        left: 0,
        right: 0,
        height: `${h}px`,
        ...(isLogin ? { overflow: 'hidden' } : {}),
      });
    };
    update();
    vv.addEventListener('resize', update);
    if (!isLogin) vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      if (!isLogin) vv.removeEventListener('scroll', update);
    };
  }, [inlineAuthActive, authMode]);

  // Load session token from localStorage on mount and when joining
  useEffect(() => {
    const token = localStorage.getItem(`chat_session_${code}`);
    setSessionToken(token);
  }, [code, hasJoined]);

  // Load messages when user auto-joins (has session token on page load)
  useEffect(() => {
    if (hasJoined && sessionToken && messages.length === 0) {
      loadMessages();
    }
  }, [hasJoined, sessionToken]);

  // One-time upgrade for old JWTs missing session_key — force rejoin to get a proper token
  useEffect(() => {
    if (!hasJoined || !sessionToken) return;
    if (!isTokenMissingSessionKey(code)) return;

    // Old token without session_key can't be safely refreshed — clear it to trigger rejoin
    localStorage.removeItem(`chat_session_${code}`);
    setSessionToken(null);
    setHasJoined(false);
  }, [hasJoined, sessionToken, code]);

  // Proactive JWT refresh — check every 5 minutes, refresh if within 1 hour of expiry
  useEffect(() => {
    if (!hasJoined || !sessionToken) return;

    const checkInterval = setInterval(async () => {
      if (!isTokenExpiringSoon(code)) return;

      const authToken = localStorage.getItem('auth_token');
      const currentToken = localStorage.getItem(`chat_session_${code}`);
      if (!currentToken) return;

      if (authToken) {
        // Logged-in user: silent refresh
        try {
          await chatApi.refreshSession(code, currentToken, roomUsername);
          setSessionToken(localStorage.getItem(`chat_session_${code}`));
        } catch {
          // Refresh failed — will fall through to join modal on next API error
        }
      }
      // Anonymous users: can't refresh silently (need PIN)
      // They'll be dumped to join modal when token expires
    }, 5 * 60 * 1000);

    return () => clearInterval(checkInterval);
  }, [hasJoined, sessionToken, code, roomUsername]);

  // Load preview messages for public chats (shown blurred behind join modal)
  // Double rAF ensures messages are rendered before scrolling to bottom
  useEffect(() => {
    if (hasJoined || !chatRoom || chatRoom.access_mode === 'private') return;
    loadMessages().then(() => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const container = messagesContainerRef.current;
          if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
        });
      });
    });
  }, [chatRoom, hasJoined]);

  // Scroll to bottom when switching rooms
  // Double rAF ensures sticky section padding is applied before scrolling
  useEffect(() => {
    shouldAutoScrollRef.current = true;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (container) container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
      });
    });
  }, [currentRoom]);

  // Load chat room details - run independent API calls in parallel for faster load
  useEffect(() => {
    const loadChatRoom = async () => {
      try {
        const token = localStorage.getItem('auth_token');

        // Run independent operations in parallel
        const [room, fpValue, currentUser] = await Promise.all([
          chatApi.getChatByCode(code, roomUsername),
          getFingerprint().catch(() => undefined),
          token ? authApi.getCurrentUser().catch(() => null) : Promise.resolve(null),
        ]);

        setChatRoom(room);
        if (fpValue) setFingerprint(fpValue);

        // Now fetch participation (depends on fingerprint)
        const participation = await chatApi.getMyParticipation(code, fpValue, roomUsername);

        if (participation.theme) {
          setParticipationTheme(participation.theme);
        }
        if (participation.seen_intros) {
          console.log('[FeatureIntro] Loaded seen_intros from API:', participation.seen_intros);
          setSeenIntros(participation.seen_intros);
        }

        if (currentUser) {
          // Logged-in user
          setCurrentUserId(currentUser.id);
          setRegisteredDisplayName(currentUser.reserved_username || '');
          setRegisteredAvatarUrl(`/api/chats/media/avatars/user/${currentUser.id}`);

          // Track anonymous participations for identity chooser
          const anonsList = participation.anonymous_participations || (participation.anonymous_participation ? [participation.anonymous_participation] : []);
          setAnonymousParticipations(anonsList);

          if (participation.has_joined && participation.username && !participation.is_anonymous_identity && anonsList.length === 0) {
            // Returning user with registered identity only (no anonymous alt) - use their locked username
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
            // Use participation avatar (same source as message avatars)
            setUserAvatarUrl(participation.avatar_url || currentUser.avatar_url || null);
          } else if (anonsList.length > 0 || participation.is_anonymous_identity) {
            // Has anonymous participation(s) (with or without registered) — show identity chooser
            setAnonymousParticipations(anonsList);
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(!!currentUser.reserved_username);
            // Use proxy avatar URL for consistency with other pages
            setUserAvatarUrl(`/api/chats/media/avatars/user/${currentUser.id}`);
          } else {
            // First-time user - pre-fill with reserved_username
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(false);
            setHasReservedUsername(!!currentUser.reserved_username);
            // Use proxy avatar URL for consistency with other pages
            setUserAvatarUrl(`/api/chats/media/avatars/user/${currentUser.id}`);
          }
        } else {
          // Anonymous user
          if (participation.has_joined && participation.username) {
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
            setUserAvatarUrl(participation.avatar_url || null);
          } else {
            setHasJoinedBefore(false);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(false);
          }
        }

        // Load session token if it exists
        const existingSessionToken = localStorage.getItem(`chat_session_${code}`);
        setSessionToken(existingSessionToken);

        setLoading(false);
      } catch (err: unknown) {
        const error = err as ApiError;
        if (error.response?.status === 404) {
          window.location.href = '/';
          return;
        }

        const errorData = error.response?.data;
        const errorMessage = typeof errorData === 'object' && errorData && 'detail' in errorData
          ? errorData.detail
          : 'Failed to load chat room';
        setError(errorMessage || 'Failed to load chat room');
        setLoading(false);
      }
    };

    loadChatRoom();
  }, [code, router]);

  // Listen for auth changes (login/register/logout)
  useEffect(() => {
    const handleAuthChange = async () => {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        // User just logged out — clear any identity state tied to the previous user
        // so the JoinChatModal doesn't render with their reserved_username pre-filled.
        setCurrentUserId(undefined);
        setRegisteredDisplayName('');
        setRegisteredAvatarUrl(null);
        setHasReservedUsername(false);
        setUserAvatarUrl(null);
        setUsername('');
        setHasJoined(false);
        setHasJoinedBefore(false);
        setAnonymousParticipations([]);
        setIsBlocked(false);
        setJoinModalKey((prev) => prev + 1);
        // Django's logout() flushed the session, wiping turnstile_verified server-side.
        // Re-run the human verification flow so the fresh session gets re-flagged
        // before the user touches any @require_turnstile endpoint (suggest-username, join, etc.).
        verifyHuman().catch(() => { /* fail-open handled inside */ });
        return;
      }
      // User just logged in or registered - refresh user state
      if (token) {
        try {
          const currentUser = await authApi.getCurrentUser();
          setCurrentUserId(currentUser.id);
          setRegisteredDisplayName(currentUser.reserved_username || '');
          setRegisteredAvatarUrl(`/api/chats/media/avatars/user/${currentUser.id}`);
          setHasReservedUsername(!!currentUser.reserved_username);
          // Use proxy avatar URL for consistency with other pages
          setUserAvatarUrl(`/api/chats/media/avatars/user/${currentUser.id}`);

          // Get fingerprint
          let fpValue: string | undefined;
          try {
            fpValue = await getFingerprint();
            setFingerprint(fpValue);
          } catch (fpErr) {
            console.warn('Failed to get fingerprint:', fpErr);
          }

          // Check if they've already joined this chat
          const participation = await chatApi.getMyParticipation(code, fpValue, roomUsername);

          // Store participation theme if present
          if (participation.theme) {
            setParticipationTheme(participation.theme);
          }

          // Phase 1 fix: clear stale identity state so chat re-runs join flow with fresh user
          setHasJoined(false);
          setUsername('');
          setAnonymousParticipations([]);
          setJoinModalKey(prev => prev + 1);

          // Track anonymous participations for identity chooser
          const anonsList = participation.anonymous_participations || (participation.anonymous_participation ? [participation.anonymous_participation] : []);
          setAnonymousParticipations(anonsList);

          if (participation.has_joined && participation.username && !participation.is_anonymous_identity && anonsList.length === 0) {
            // They already joined with registered identity only (no anonymous alt)
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
          } else if (anonsList.length > 0 || participation.is_anonymous_identity) {
            // Has anonymous participation(s) (with or without registered) — show identity chooser
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(!!currentUser.reserved_username);
          } else {
            // Not joined yet - pre-fill with reserved username
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(false);
            setHasReservedUsername(!!currentUser.reserved_username);
          }

          // Close the auth modal
          closeModal();
        } catch (err) {
          console.error('Failed to refresh user after auth:', err);
        }
      }
    };

    window.addEventListener('auth-change', handleAuthChange);
    return () => window.removeEventListener('auth-change', handleAuthChange);
  }, [code]);

  // Blocked users stay on the page — JoinChatModal shows a "banned" message

  // Listen for back button to handle auth, settings overlay, and chat exit
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      const path = window.location.pathname;

      // Auth navigation: going back/forward between /login, /signup, and base chat URL
      if (path.endsWith('/login')) {
        setAuthModeState('login');
        return;
      } else if (path.endsWith('/signup')) {
        setAuthModeState('register');
        return;
      } else if (authModeState) {
        // Was in auth mode, now back to chat page — just close auth
        setAuthModeState(null);
        return;
      }

      // If settings sheet is open, close it (settings uses pushState)
      if (showSettingsSheet) {
        setShowSettingsSheet(false);
        return;
      }

      // Back button exits chat entirely (rooms use replaceState, no unwinding needed)
      // Reset to main room as part of exit
      if (currentRoom !== 'main') {
        setCurrentRoom('main');
      }

      if (hasJoined) {
        setHasJoined(false);
        // If user has both identities, show identity chooser again (not "Welcome back")
        setHasJoinedBefore(anonymousParticipations.length > 0 ? false : true);
        setMessages([]);
        setStickyHostMessage(null);
        setStickyPinnedMsg(null);
        setJoinModalKey(prev => prev + 1);
        // Reset preview state so source-of-truth values are used
        setPreviewUsername(null);
        setPreviewAvatarUrl(undefined);
        setPreviewHasReservedUsername(null);
        setPreviewIsHost(null);
        window.history.pushState({ modal: true }, '', window.location.href);
      } else {
        markChatVisited(code);
        router.push('/');
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [hasJoined, showSettingsSheet, currentRoom, router, code, authModeState, anonymousParticipations]);

  // No theme switching - body background set in layout.tsx

  // TODO: Back Room feature - uncomment when backend is ready
  // Load Back Room data if it exists
  // useEffect(() => {
  //   const loadBackRoom = async () => {
  //     if (!chatRoom?.has_back_room || !hasJoined) return;
  //
  //     try {
  //       const backRoomData = await backRoomApi.getBackRoom(code);
  //       setBackRoom(backRoomData);
  //
  //       // Host always has access; for non-hosts, we'll check via GameRoomView's permission handling
  //       const isHost = currentUserId && chatRoom.host.id === currentUserId;
  //       if (isHost) {
  //         setIsBackRoomMember(true);
  //       }
  //       // For non-hosts, membership will be determined when they try to view messages
  //     } catch (error) {
  //       console.error('Failed to load back room:', error);
  //     }
  //   };
  //
  //   loadBackRoom();
  // }, [chatRoom, hasJoined, code, currentUserId, username]);

  // Load messages
  const loadMessages = async () => {
    if (isLoadingMessagesRef.current) return;
    isLoadingMessagesRef.current = true;

    try {
      // Read sessionToken directly from localStorage to avoid stale closure
      const currentSessionToken = localStorage.getItem(`chat_session_${code}`) || undefined;
      // Pass filter params when in focus/gifts room
      const filterParam = getRoomFilter(currentRoom);
      const filterUser = filterParam && filterParam !== 'broadcast' ? username : undefined;
      const { messages: msgs, pinnedMessages } = await messageApi.getMessages(code, roomUsername, currentSessionToken, filterParam, filterUser);

      // Create a map of pinned messages for quick lookup
      const pinnedMap = new Map(pinnedMessages.map(pm => [pm.id, pm]));

      // Update messages with pinned data, or add if not present
      const updatedMessages = msgs.map(msg => {
        const pinnedVersion = pinnedMap.get(msg.id);
        if (pinnedVersion) {
          // Merge pinned fields into the message
          return {
            ...msg,
            is_pinned: pinnedVersion.is_pinned,
            pinned_at: pinnedVersion.pinned_at,
            sticky_until: pinnedVersion.sticky_until,
            pin_amount_paid: pinnedVersion.pin_amount_paid,
            current_pin_amount: pinnedVersion.current_pin_amount,
          };
        }
        return msg;
      });

      // Add any pinned messages not already in main array
      const messageIds = new Set(msgs.map(m => m.id));
      const uniquePinnedMessages = pinnedMessages.filter(pm => !messageIds.has(pm.id));
      const allMessages = [...updatedMessages, ...uniquePinnedMessages].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      );

      setMessages(allMessages);
      updateStickyFromMessages(allMessages);
      setHasMoreMessages(true);

      // Extract reactions from messages
      const reactions: Record<string, ReactionSummary[]> = {};
      allMessages.forEach((msg) => {
        if (msg.reactions && msg.reactions.length > 0) {
          reactions[msg.id] = msg.reactions;
        }
      });
      setMessageReactions(reactions);

      // Scroll to bottom after React renders
      shouldAutoScrollRef.current = true;
      initialScrollDoneRef.current = false; // Reset before scroll
      requestAnimationFrame(() => {
        const container = messagesContainerRef.current;
        if (container) {
          container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
        }
        initialScrollDoneRef.current = true; // Mark scroll complete
      });
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      isLoadingMessagesRef.current = false;
    }
  };
  loadMessagesRef.current = loadMessages;

  // Load older messages for infinite scroll
  const loadOlderMessages = async () => {
    if (loadingOlder || !hasMoreMessages || messages.length === 0) {
      return;
    }

    const container = messagesContainerRef.current;
    if (!container) {
      return;
    }

    try {
      setLoadingOlder(true);

      // Get the oldest message timestamp
      const oldestMessage = messages[0];
      const beforeTimestamp = new Date(oldestMessage.created_at).getTime() / 1000;

      // Fetch older messages (async - user may scroll during this)
      const filterParam = getRoomFilter(currentRoom);
      const filterUser = filterParam && filterParam !== 'broadcast' ? username : undefined;
      const { messages: olderMessages, hasMore } = await messageApi.getMessagesBefore(code, beforeTimestamp, 50, roomUsername, filterParam, filterUser);

      if (olderMessages.length > 0) {
        // Capture scroll position RIGHT BEFORE the DOM update
        const previousScrollHeight = container.scrollHeight;
        const previousScrollTop = container.scrollTop;

        // Use flushSync to force synchronous state update and DOM mutation
        // Filter duplicates in case preload already loaded some of these
        flushSync(() => {
          setMessages(prev => {
            const existingIds = new Set(prev.map(m => m.id));
            const uniqueOlderMessages = olderMessages.filter(m => !existingIds.has(m.id));
            return [...uniqueOlderMessages, ...prev];
          });
        });

        // IMMEDIATELY adjust scroll after flushSync (no RAF delay)
        // This prevents the user from seeing even 1 frame of wrong position
        const newScrollHeight = container.scrollHeight;
        const heightDifference = newScrollHeight - previousScrollHeight;
        const targetScrollTop = previousScrollTop + heightDifference;
        container.scrollTo({ top: targetScrollTop, behavior: 'instant' });
      }

      setHasMoreMessages(hasMore);
    } catch (err) {
      console.error('Failed to load older messages:', err);
    } finally {
      setLoadingOlder(false);
    }
  };

  // Join handler for modal
  const handleJoinChat = async (username: string, accessCode?: string, avatarSeed?: string): Promise<{ error?: string } | void> => {
    try {
      // Get fingerprint
      let fingerprint: string | undefined;
      try {
        fingerprint = await getFingerprint();
      } catch (fpErr) {
        console.warn('Failed to get fingerprint:', fpErr);
      }

      // Wrap in inner try/catch to prevent AxiosError from triggering Next.js error overlay
      let joinError: ApiError | null = null;
      try {
        await chatApi.joinChat(code, username, accessCode, fingerprint, roomUsername, avatarSeed);
      } catch (e) {
        joinError = e as ApiError;
      }

      if (joinError) {
        // Throw to outer catch for standard error handling
        throw joinError;
      }

      // Update session token immediately after joining
      const newSessionToken = localStorage.getItem(`chat_session_${code}`);
      setSessionToken(newSessionToken);

      const token = localStorage.getItem('auth_token');
      const isLoggedIn = !!token;
      await UsernameStorage.saveUsername(code, username, isLoggedIn);
      setUsername(username);
      setHasJoined(true);
      clearChatVisited(code); // Clear visit tracking since user joined
      fetchGiftCatalog(code, roomUsername); // Preload catalog + settings (fire-and-forget)
      await loadMessages();

      // Add history entry so back button shows join modal again
      window.history.pushState({ joined: true }, '', window.location.href);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      console.error('[Join Error] Full error:', err);

      // Extract error message from various DRF error formats
      let errorMessage = 'Failed to join chat';

      if (apiErr.response?.data) {
        const data = apiErr.response.data;

        if (Array.isArray(data) && data.length > 0) {
          errorMessage = String(data[0]);
        } else if (typeof data === 'object' && data !== null && 'detail' in data && data.detail) {
          errorMessage = String(data.detail);
        } else if (typeof data === 'object' && data !== null && 'non_field_errors' in data && Array.isArray(data.non_field_errors)) {
          errorMessage = String(data.non_field_errors[0]);
        } else if (typeof data === 'string') {
          errorMessage = data;
        } else if (typeof data === 'object' && data !== null) {
          const dataObj = data as Record<string, unknown>;
          const firstField = Object.keys(dataObj)[0];
          if (firstField && Array.isArray(dataObj[firstField])) {
            errorMessage = String((dataObj[firstField] as unknown[])[0]);
          }
        }
      }

      // Check if user is blocked - trigger redirect
      if (errorMessage.includes('blocked from this chat')) {
        setIsBlocked(true);
        return;
      }

      // Username persistence error
      const usernameMatch = errorMessage.match(/already joined this chat as '([^']+)'/);
      if (usernameMatch && chatRoom) {
        const existingUsername = usernameMatch[1];
        localStorage.setItem(`chat_${chatRoom.code}_suggested_username`, existingUsername);
        errorMessage = `You previously joined as "${existingUsername}". Please use that username to rejoin.`;
      }

      return { error: errorMessage };
    }
  };

  // Join as guest (old handler - kept for backward compatibility but not used in UI)
  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setJoinError('');

    if (!username.trim()) {
      setJoinError('Please enter a username');
      return;
    }

    try {
      await chatApi.joinChat(code, username.trim(), accessCode || undefined, undefined, roomUsername);
      const token = localStorage.getItem('auth_token');
      const isLoggedIn = !!token;
      await UsernameStorage.saveUsername(code, username.trim(), isLoggedIn);
      setHasJoined(true);
      clearChatVisited(code); // Clear visit tracking since user joined
      fetchGiftCatalog(code, roomUsername); // Preload catalog + settings (fire-and-forget)
      await loadMessages();
    } catch (err: unknown) {
      const error = err as ApiError;
      const errorData = error.response?.data;
      const errorMessage = typeof errorData === 'object' && errorData && 'detail' in errorData
        ? String(errorData.detail)
        : 'Failed to join chat';
      setJoinError(errorMessage);
    }
  };

  // Send text message - receives message text from MessageInput component
  const handleSubmitText = useCallback(async (messageText: string) => {
    if (!messageText.trim() || sending) return;

    setSending(true);
    try {
      // Send via WebSocket if connected, fallback to REST API
      if (isConnected && wsSendMessage) {
        wsSendMessage(messageText, replyingTo?.id);
        shouldAutoScrollRef.current = true; // Always scroll when sending a message
        playSendMessageSound(); // Play send sound
      } else {
        // Fallback to REST API (for backwards compatibility or if WebSocket fails)
        let messageUsername = username;

        if (!messageUsername) {
          const token = localStorage.getItem('auth_token');
          const isLoggedIn = !!token;
          messageUsername = (await UsernameStorage.getUsername(code)) || '';
        }

        if (!messageUsername && chatRoom) {
          const token = localStorage.getItem('auth_token');
          if (token) {
            messageUsername = chatRoom.host.reserved_username || chatRoom.host.email.split('@')[0];
          }
        }

        if (!messageUsername) {
          console.error('No username available');
          return;
        }

        await messageApi.sendMessage(code, messageUsername, messageText, roomUsername);
        shouldAutoScrollRef.current = true;
        await loadMessages();
      }
    } catch (err: unknown) {
      console.error('Failed to send message:', err);
    } finally {
      setSending(false);
      setReplyingTo(null); // Clear reply state after sending (success or failure)
    }
  }, [sending, isConnected, wsSendMessage, replyingTo?.id, username, code, chatRoom, roomUsername, loadMessages]);

  // Handle voice message upload
  const handleVoiceRecording = useCallback(async (audioBlob: Blob, metadata: RecordingMetadata, caption: string) => {
    if (sending) return;

    setSending(true);
    try {
      let messageUsername = username;

      if (!messageUsername) {
        const token = localStorage.getItem('auth_token');
        const isLoggedIn = !!token;
        messageUsername = (await UsernameStorage.getUsername(code)) || '';
      }

      if (!messageUsername && chatRoom) {
        const token = localStorage.getItem('auth_token');
        if (token) {
          messageUsername = chatRoom.host.reserved_username || chatRoom.host.email.split('@')[0];
        }
      }

      if (!messageUsername) {
        console.error('No username available');
        alert('Please join the chat first');
        return;
      }

      // Upload voice message file and get the URL
      const { voice_url } = await messageApi.uploadVoiceMessage(code, audioBlob, messageUsername, roomUsername);

      // Send the voice message via WebSocket with metadata
      sendRawMessage({
        message: caption, // Caption text for voice messages
        voice_url: voice_url,
        voice_duration: metadata.duration,
        voice_waveform: metadata.waveformData,
        reply_to_id: replyingTo?.id, // Include reply context if replying
      });

      // Auto-scroll to show new message
      shouldAutoScrollRef.current = true;
    } catch (err: unknown) {
      const error = err as ApiError & { stack?: string };
      console.error('Failed to upload voice message:', err);
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        stack: error.stack
      });
      const errorData = error.response?.data;
      const errorMsg = (typeof errorData === 'object' && errorData && 'error' in errorData ? String(errorData.error) : null)
        || error.message || 'Unknown error occurred';
      alert(`Failed to send voice message: ${errorMsg}`);
    } finally {
      setSending(false);
      setReplyingTo(null); // Clear reply state after sending (success or failure)
    }
  }, [sending, username, code, chatRoom, roomUsername, replyingTo?.id, sendRawMessage]);

  // Handle photo message upload
  const handlePhotoSelected = useCallback(async (file: File, width: number, height: number, caption: string) => {
    if (sending) return;

    setSending(true);
    try {
      let messageUsername = username;

      if (!messageUsername) {
        const token = localStorage.getItem('auth_token');
        const isLoggedIn = !!token;
        messageUsername = (await UsernameStorage.getUsername(code)) || '';
      }

      if (!messageUsername && chatRoom) {
        const token = localStorage.getItem('auth_token');
        if (token) {
          messageUsername = chatRoom.host.reserved_username || chatRoom.host.email.split('@')[0];
        }
      }

      if (!messageUsername) {
        console.error('No username available');
        alert('Please join the chat first');
        return;
      }

      // Upload photo and get the URL
      const { photo_url, width: uploadedWidth, height: uploadedHeight } = await messageApi.uploadPhoto(code, file, roomUsername);

      // Send the photo message via WebSocket
      sendRawMessage({
        message: caption, // Caption text for photo messages
        photo_url: photo_url,
        photo_width: uploadedWidth,
        photo_height: uploadedHeight,
        reply_to_id: replyingTo?.id,
      });

      // Auto-scroll to show new message
      shouldAutoScrollRef.current = true;
    } catch (err: unknown) {
      const error = err as ApiError;
      console.error('Failed to upload photo:', err);
      const errorData = error.response?.data;
      const errorMsg = (typeof errorData === 'object' && errorData && 'error' in errorData ? String(errorData.error) : null)
        || error.message || 'Unknown error occurred';
      alert(`Failed to send photo: ${errorMsg}`);
    } finally {
      setSending(false);
      setReplyingTo(null);
    }
  }, [sending, username, code, chatRoom, roomUsername, replyingTo?.id, sendRawMessage]);

  // Handle video message upload
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleVideoSelected = useCallback(async (file: File, duration: number, thumbnail: Blob | null, caption: string) => {
    if (sending) return;

    setSending(true);
    try {
      let messageUsername = username;

      if (!messageUsername) {
        const token = localStorage.getItem('auth_token');
        const isLoggedIn = !!token;
        messageUsername = (await UsernameStorage.getUsername(code)) || '';
      }

      if (!messageUsername && chatRoom) {
        const token = localStorage.getItem('auth_token');
        if (token) {
          messageUsername = chatRoom.host.reserved_username || chatRoom.host.email.split('@')[0];
        }
      }

      if (!messageUsername) {
        console.error('No username available');
        alert('Please join the chat first');
        return;
      }

      // Upload video and get URLs
      const { video_url, duration: uploadedDuration, thumbnail_url, width, height } = await messageApi.uploadVideo(code, file, roomUsername);

      // Send the video message via WebSocket
      sendRawMessage({
        message: caption, // Caption text for video messages
        video_url: video_url,
        video_duration: uploadedDuration,
        video_thumbnail_url: thumbnail_url,
        video_width: width,
        video_height: height,
        reply_to_id: replyingTo?.id,
      });

      // Auto-scroll to show new message
      shouldAutoScrollRef.current = true;
    } catch (err: unknown) {
      const error = err as ApiError;
      console.error('Failed to upload video:', err);
      const errorData = error.response?.data;
      const errorMsg = (typeof errorData === 'object' && errorData && 'error' in errorData ? String(errorData.error) : null)
        || error.message || 'Unknown error occurred';
      alert(`Failed to send video: ${errorMsg}`);
    } finally {
      setSending(false);
      setReplyingTo(null);
    }
  }, [sending, username, code, chatRoom, roomUsername, replyingTo?.id, sendRawMessage]);

  const scrollToBottom = () => {
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
    }
  };

  const handleScrollToBottom = useCallback(() => {
    shouldAutoScrollRef.current = true;
    setShowScrollToBottom(false);
    const container = messagesContainerRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
    }
  }, []);

  const highlightMessage = useCallback((messageId: string) => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`);
    if (element) {
      element.classList.remove('animate-pulse-scale');
      void (element as HTMLElement).offsetWidth; // force reflow to restart animation
      element.classList.add('animate-pulse-scale');
      setTimeout(() => {
        element.classList.remove('animate-pulse-scale');
      }, 2000);
    }
  }, []);

  // Track rAF-based scroll animation so it can be cancelled (e.g. by sticky toggle)
  const scrollAnimationRef = useRef<number | null>(null);
  const cancelScrollAnimation = useCallback(() => {
    if (scrollAnimationRef.current !== null) {
      cancelAnimationFrame(scrollAnimationRef.current);
      scrollAnimationRef.current = null;
    }
  }, []);

  const scrollToMessage = useCallback((messageId: string) => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`);
    const container = messagesContainerRef.current;
    if (element && container) {
      cancelScrollAnimation();
      const containerRect = container.getBoundingClientRect();
      const elementRect = element.getBoundingClientRect();
      const elementCenter = elementRect.top + elementRect.height / 2;
      const containerCenter = containerRect.top + containerRect.height / 2;
      const scrollOffset = elementCenter - containerCenter;
      const targetScrollTop = container.scrollTop + scrollOffset;
      // Manual smooth scroll via rAF — avoids browser native smooth scroll
      // state that corrupts subsequent scrollTop assignments (toggle bug)
      const startScrollTop = container.scrollTop;
      const distance = targetScrollTop - startScrollTop;
      const duration = 300;
      const startTime = performance.now();
      const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        container.scrollTop = startScrollTop + distance * eased;
        if (progress < 1) {
          scrollAnimationRef.current = requestAnimationFrame(animate);
        } else {
          scrollAnimationRef.current = null;
        }
      };
      scrollAnimationRef.current = requestAnimationFrame(animate);
      highlightMessage(messageId);
    }
  }, [highlightMessage, cancelScrollAnimation]);

  // Track if user is near bottom
  const shouldAutoScrollRef = useRef(true);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Track last message ID to detect NEW messages vs prepended old ones
  const lastMessageIdRef = useRef<string | null>(null);

  // Prevent double loadMessages calls
  const isLoadingMessagesRef = useRef(false);

  // Debounce timer for infinite scroll trigger (prevents momentum scroll interruption)
  const loadOlderDebounceRef = useRef<NodeJS.Timeout | null>(null);

  // RAF throttling for scroll handler (prevents 60+ calls/sec)
  const scrollRAFRef = useRef<number | null>(null);

  // Refs to track state values in scroll handler (avoids recreating callback on state change)
  const hasMoreMessagesRef = useRef(hasMoreMessages);
  const loadingOlderRef = useRef(loadingOlder);
  const messagesLengthRef = useRef(messages.length);

  // Keep refs in sync with state
  useEffect(() => {
    hasMoreMessagesRef.current = hasMoreMessages;
    loadingOlderRef.current = loadingOlder;
    messagesLengthRef.current = messages.length;
  }, [hasMoreMessages, loadingOlder, messages.length]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (loadOlderDebounceRef.current) {
        clearTimeout(loadOlderDebounceRef.current);
      }
      if (scrollRAFRef.current) {
        cancelAnimationFrame(scrollRAFRef.current);
      }
    };
  }, []);



  // Note: We previously tracked scroll-based visibility for sticky host messages,
  // but now always show the latest host message for simplicity and to prevent flickering

  // Message action handlers (wrapped in useCallback to prevent re-renders)

  // Get pin requirements for a message (current pin value, minimum required, tiers, etc.)
  const getPinRequirements = useCallback(async (messageId: string): Promise<{
    current_pin_cents: number;
    minimum_cents?: number;
    required_cents?: number;
    minimum_required_cents?: number;
    duration_minutes: number;
    tiers?: { amount_cents: number; duration_minutes: number }[];
    is_pinned?: boolean;
    is_expired?: boolean;
    time_remaining_seconds?: number;
  }> => {
    return await messageApi.getPinRequirements(code, messageId, roomUsername);
  }, [code, roomUsername]);

  // Pin a message (or outbid existing pin)
  const handlePin = useCallback(async (messageId: string, amountCents: number): Promise<boolean> => {
    try {
      await messageApi.pinMessage(code, messageId, amountCents, roomUsername);
      return true;
    } catch (err: unknown) {
      const error = err as ApiError;
      console.error('Pin failed:', error);
      const errorData = error.response?.data;
      const errorMsg = (typeof errorData === 'object' && errorData && 'error' in errorData ? String(errorData.error) : null)
        || (typeof errorData === 'object' && errorData && 'detail' in errorData ? String(errorData.detail) : null)
        || 'Failed to pin message';
      alert(errorMsg);
      return false;
    }
  }, [code, roomUsername]);

  // Add to an existing pin (increase value without resetting timer)
  const handleAddToPin = useCallback(async (messageId: string, amountCents: number): Promise<boolean> => {
    try {
      await messageApi.addToPin(code, messageId, amountCents, roomUsername);
      return true;
    } catch (err: unknown) {
      const error = err as ApiError;
      console.error('Add to pin failed:', error);
      const errorData = error.response?.data;
      const errorMsg = (typeof errorData === 'object' && errorData && 'error' in errorData ? String(errorData.error) : null)
        || (typeof errorData === 'object' && errorData && 'detail' in errorData ? String(errorData.detail) : null)
        || 'Failed to add to pin';
      alert(errorMsg);
      return false;
    }
  }, [code, roomUsername]);

  const handleReply = useCallback((message: Message) => {
        setReplyingTo(message);
  }, []);

  const handleCancelReply = useCallback(() => {
    setReplyingTo(null);
  }, []);

  const handleBlockUser = useCallback(async (username: string) => {
    // Check if user is authenticated (has auth token)
    const authToken = localStorage.getItem('auth_token');

    if (!authToken) {
      console.error('Must be logged in to block users');
      alert('You must be logged in to block users. Please log in or register.');
      return;
    }

    try {
      // Check if current user is the host
      const userIsHost = !!(currentUserId && chatRoom && chatRoom.host.id === currentUserId);

      if (userIsHost) {
        // Host can ban users from the chat (ChatBlock)
        await messageApi.blockUser(code, { blocked_username: username }, roomUsername);
      } else {
        // Non-hosts can only mute users site-wide (UserBlock)
        await messageApi.blockUserSiteWide(username);
        setMutedUsernames(prev => {
          const next = new Set(prev);
          next.add(username);
          return next;
        });
      }
    } catch (err: unknown) {
      console.error('Failed to block user:', err);
    }
  }, [currentUserId, chatRoom, code, roomUsername]);

  const handleUnmuteUser = useCallback(async (username: string) => {
    try {
      await messageApi.unblockUserSiteWide(username);
      setMutedUsernames(prev => {
        const next = new Set(prev);
        next.delete(username);
        return next;
      });
    } catch (err: unknown) {
      console.error('Failed to unmute user:', err);
    }
  }, []);

  const handleUnblockUser = useCallback(async (username: string) => {
    try {
      await messageApi.unblockUser(code, username, roomUsername);
    } catch (err: unknown) {
      console.error('Failed to unban user:', err);
    }
  }, [code, roomUsername]);

  const handleTipUser = useCallback((username: string) => {
        // TODO: Implement tip user logic with payment
  }, []);

  const handleSendGift = useCallback(async (giftId: string, recipientUsername: string): Promise<boolean> => {
    try {
      await giftApi.sendGift(code, giftId, recipientUsername, roomUsername);
      return true;
    } catch (error: unknown) {
      const err = error as ApiError;
      console.error('[Gift] Send failed:', err.response?.data || error);
      return false;
    }
  }, [code, roomUsername]);

  const handleDismissGift = useCallback(async (giftId: string) => {
    try {
      await giftApi.acknowledgeGift(code, giftId, false, roomUsername);
      setGiftQueue(prev => prev.filter(g => g.id !== giftId));
    } catch (error) {
      console.error('[Gift] Dismiss failed:', error);
      setGiftQueue(prev => prev.filter(g => g.id !== giftId));
    }
  }, [code, roomUsername]);

  const handleThankGiftPopup = useCallback(async (giftId: string) => {
    try {
      await giftApi.acknowledgeGift(code, giftId, true, roomUsername);
      setGiftQueue(prev => prev.filter(g => g.id !== giftId));
    } catch (error) {
      console.error('[Gift] Thank failed:', error);
      setGiftQueue(prev => prev.filter(g => g.id !== giftId));
    }
  }, [code, roomUsername]);

  const handleDismissAllGifts = useCallback(async () => {
    try {
      await giftApi.acknowledgeAllGifts(code, false, roomUsername);
      setGiftQueue([]);
    } catch (error) {
      console.error('[Gift] Dismiss all failed:', error);
      setGiftQueue([]);
    }
  }, [code, roomUsername]);

  const handleThankAllGifts = useCallback(async () => {
    try {
      await giftApi.acknowledgeAllGifts(code, true, roomUsername);
      setGiftQueue([]);
    } catch (error) {
      console.error('[Gift] Thank all failed:', error);
      setGiftQueue([]);
    }
  }, [code, roomUsername]);

  const handleThankGift = useCallback(async (messageId: string): Promise<boolean> => {
    try {
      await giftApi.acknowledgeGiftByMessage(code, messageId, roomUsername);
      return true;
    } catch (error) {
      console.error('[Gift] Thank failed:', error);
      return false;
    }
  }, [code, roomUsername]);

  const handleBroadcastMessage = useCallback(async (messageId: string): Promise<boolean> => {
    try {
      await messageApi.broadcastMessage(code, messageId, roomUsername);
      return true;
    } catch (error) {
      console.error('[Broadcast] Toggle failed:', error);
      return false;
    }
  }, [code, roomUsername]);

  const handleDeleteMessage = useCallback(async (messageId: string) => {
    // Only hosts can delete messages
    if (!chatRoom || !currentUserId || chatRoom.host.id !== currentUserId) {
      console.error('Only the host can delete messages');
      return;
    }

    try {
      await messageApi.deleteMessage(code, messageId, roomUsername);
            // The WebSocket will handle real-time removal for all users
    } catch (error) {
      console.error('Failed to delete message:', error);
      alert('Failed to delete message. Please try again.');
    }
  }, [code, chatRoom, currentUserId]);

  const handleReactionToggle = useCallback(async (messageId: string, emoji: string) => {
    if (!username) {
      console.warn('[Reactions] No username available');
      return;
    }

    try {
      const result = await messageApi.toggleReaction(
        code,
        messageId,
        emoji,
        username,
        roomUsername
      );

      
      // Optimistically update local state
      if (result.action === 'removed') {
        setMessageReactions(prev => {
          const updated = { ...prev };
          const reactions = updated[messageId] || [];
          // Find the reaction and decrement count, or remove if count becomes 0
          updated[messageId] = reactions
            .map(r => r.emoji === emoji ? { ...r, count: r.count - 1, has_reacted: false } : r)
            .filter(r => r.count > 0);
          return updated;
        });
      } else if (result.action === 'added') {
        // Optimistically add the reaction with has_reacted: true
        setMessageReactions(prev => {
          const updated = { ...prev };
          const reactions = [...(updated[messageId] || [])];
          const existingIndex = reactions.findIndex(r => r.emoji === emoji);
          if (existingIndex >= 0) {
            reactions[existingIndex] = { ...reactions[existingIndex], count: reactions[existingIndex].count + 1, has_reacted: true };
          } else {
            reactions.push({ emoji, count: 1, has_reacted: true });
          }
          updated[messageId] = reactions;
          return updated;
        });
      }
      // WebSocket will also broadcast the update for consistency across clients
    } catch (error) {
      console.error('Failed to toggle reaction:', error);
    }
  }, [code, username]);

  // Filter messages based on room (memoized to prevent recalculation on unrelated state changes)
  const filteredMessages = useMemo(() => {
    // While room is loading, return empty to prevent stale content flash
    if (roomLoading) return [];

    // Client-side mute filter (mirrors backend rules):
    // - Hide messages from muted users
    // - Exception: host broadcasts always shown
    // - Exception: gifts TO me from muted user still shown
    // - Also hide gifts TO muted users (unless I'm the sender)
    const applyMute = (msg: Message): boolean => {
      const author = msg.username || '';
      const authorMuted = mutedUsernames.has(author);
      if (authorMuted) {
        if (msg.is_broadcast) return true;
        if (
          msg.message_type === 'gift' &&
          msg.gift_recipient &&
          msg.gift_recipient.toLowerCase() === (username || '').toLowerCase()
        ) {
          return true;
        }
        return false;
      }
      if (msg.message_type === 'gift' && msg.gift_recipient) {
        if (
          mutedUsernames.has(msg.gift_recipient) &&
          author.toLowerCase() !== (username || '').toLowerCase()
        ) {
          return false;
        }
      }
      return true;
    };

    // Server already returns filtered results, but real-time WS messages
    // arrive unfiltered — apply client-side filter for those
    if (currentRoom === 'gifts') {
      return messages.filter(msg => {
        if (msg.message_type !== 'gift') return false;
        if (msg.username === username) return true;
        if (msg.gift_recipient && msg.gift_recipient.toLowerCase() === username?.toLowerCase()) return true;
        return false;
      }).filter(applyMute);
    }

    if (currentRoom === 'focus') {
      return messages.filter(msg => {
        if (msg.is_from_host) return true;
        if (msg.username === username) return true;
        if (msg.reply_to_message?.username?.toLowerCase() === username?.toLowerCase()) return true;
        if (spotlightUsernames.has(msg.username)) return true;
        return false;
      }).filter(applyMute);
    }

    if (currentRoom === 'broadcast') {
      return messages.filter(msg => msg.is_broadcast).filter(applyMute);
    }

    return messages.filter(applyMute);
  }, [messages, currentRoom, roomLoading, username, mutedUsernames, spotlightUsernames]);

  // Check if current user is the host
  const isHost = useMemo(() => {
    return !!(currentUserId && chatRoom && chatRoom.host.id === currentUserId);
  }, [currentUserId, chatRoom]);

  // Auto-remove expired pins from sticky section
  useEffect(() => {
    if (!stickyPinnedMsg?.sticky_until) return;

    const expiryTime = new Date(stickyPinnedMsg.sticky_until).getTime();
    const now = Date.now();
    const timeRemaining = expiryTime - now;

    // If already expired, clear immediately
    if (timeRemaining <= 0) {
      setStickyPinnedMsg(null);
      return;
    }

    // Set timer to clear sticky pinned when pin expires
    const timer = setTimeout(() => {
      setStickyPinnedMsg(null);
    }, timeRemaining);

    return () => clearTimeout(timer);
  }, [stickyPinnedMsg?.id, stickyPinnedMsg?.sticky_until]);

  // Check if user is scrolled near the bottom
  const checkIfNearBottom = () => {
    const container = messagesContainerRef.current;
    if (!container) return true;

    const threshold = 100; // pixels from bottom
    const position = container.scrollHeight - container.scrollTop - container.clientHeight;
    return position < threshold;
  };

  // Scroll handler implementation (stored in ref so handleScroll has stable reference)
  const handleScrollImpl = () => {
    // Throttle to once per animation frame (~60fps max)
    if (scrollRAFRef.current !== null) return;

    scrollRAFRef.current = requestAnimationFrame(() => {
      scrollRAFRef.current = null;

      const container = messagesContainerRef.current;
      if (!container) return;

      const wasAutoScroll = shouldAutoScrollRef.current;
      const nearBottom = checkIfNearBottom();
      const scrolledFarFromBottom = container.scrollTop < container.scrollHeight - container.clientHeight - 200;

      // Update shouldAutoScrollRef based on scroll position
      if (nearBottom) {
        // Always enable auto-scroll when near bottom
        shouldAutoScrollRef.current = true;
        setShowScrollToBottom(false);

        // Mark initial scroll as complete once we reach bottom for the first time
        if (!initialScrollDoneRef.current) {
          initialScrollDoneRef.current = true;
        }
      } else if (scrolledFarFromBottom && wasAutoScroll) {
        // User manually scrolled up significantly while auto-scroll was on
        // Disable auto-scroll
        shouldAutoScrollRef.current = false;
        setShowScrollToBottom(true);
      }
      // If we're just temporarily not at bottom (e.g., content added), keep auto-scroll enabled

      // Infinite scroll - load older messages when near top
      // Use debouncing to avoid interrupting momentum scroll
      // Only trigger after 150ms of scroll inactivity in the trigger zone
      if (
        initialScrollDoneRef.current &&
        container.scrollTop < 3000 &&
        hasMoreMessagesRef.current &&
        !loadingOlderRef.current &&
        messagesLengthRef.current > 0
      ) {
        // Clear any existing debounce timer
        if (loadOlderDebounceRef.current) {
          clearTimeout(loadOlderDebounceRef.current);
        }

        // Set new debounce timer - wait for scroll to settle before loading
        loadOlderDebounceRef.current = setTimeout(() => {
          // Re-check conditions after debounce (user may have scrolled away)
          const currentContainer = messagesContainerRef.current;
          if (
            currentContainer &&
            currentContainer.scrollTop < 3000 &&
            hasMoreMessagesRef.current &&
            !loadingOlderRef.current
          ) {
            loadOlderMessages();
          }
        }, 150);
      } else {
        // User scrolled out of trigger zone - cancel pending load
        if (loadOlderDebounceRef.current) {
          clearTimeout(loadOlderDebounceRef.current);
          loadOlderDebounceRef.current = null;
        }
      }
    });
  };

  // Stable reference wrapper for scroll handler (prevents MainChatView re-renders)
  const handleScrollImplRef = useRef(handleScrollImpl);
  handleScrollImplRef.current = handleScrollImpl;

  const handleScroll = useCallback(() => {
    handleScrollImplRef.current();
  }, []);

  // Only auto-scroll if user is near bottom AND a NEW message arrived (at the end)
  // Initial scroll is handled directly in loadMessages with instant scroll
  // Prepending old messages (preload/infinite scroll) should NOT trigger auto-scroll
  useEffect(() => {
    const currentLastId = messages.length > 0 ? messages[messages.length - 1]?.id : null;
    const previousLastId = lastMessageIdRef.current;

    lastMessageIdRef.current = currentLastId;

    // Skip during initial load - loadMessages handles that with instant scroll
    if (!initialScrollDoneRef.current) return;

    // Only scroll if the LAST message changed (new message arrived)
    if (currentLastId === previousLastId) return;

    if (shouldAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [messages.length, messageReactions]);

  // Auto-refresh messages every 3 seconds (fallback polling when WebSocket is not connected)
  useEffect(() => {
    if (!hasJoined || isConnected) return; // Don't poll if WebSocket is connected

    const interval = setInterval(() => {
      loadMessages();
    }, 3000);

    return () => clearInterval(interval);
  }, [hasJoined, code, isConnected]);

  // Calculate theme dark mode setting (used by modals)
  const activeTheme = participationTheme || chatRoom?.theme;
  const themeIsDarkMode = activeTheme?.is_dark_mode ?? true; // Default to dark if no theme

  // Memoize currentDesign to prevent expensive recalculation on every render
  const currentDesign = useMemo(() => {
    return convertThemeToCamelCase(participationTheme || chatRoom?.theme || defaultTheme);
  }, [participationTheme, chatRoom?.theme]);

  // Memoized design prop for MessageInput to prevent re-renders
  const messageInputDesign = useMemo(() => ({
    inputArea: currentDesign.inputArea as string,
    inputField: currentDesign.inputField as string,
    replyPreviewContainer: currentDesign.replyPreviewContainer as string,
    replyPreviewIcon: currentDesign.replyPreviewIcon as string,
    replyPreviewUsername: currentDesign.replyPreviewUsername as string,
    replyPreviewContent: currentDesign.replyPreviewContent as string,
    replyPreviewCloseButton: currentDesign.replyPreviewCloseButton as string,
    replyPreviewCloseIcon: currentDesign.replyPreviewCloseIcon as string,
    inputStyles: {
      ...(currentDesign.inputStyles as Record<string, string> | undefined),
      crownIconColor: ({ 'text-teal-400': '#2dd4bf', 'text-amber-400': '#fbbf24', 'text-cyan-400': '#22d3ee', 'text-emerald-400': '#34d399', 'text-purple-400': '#c084fc', 'text-yellow-400': '#facc15' } as Record<string, string>)[(currentDesign.crownIconColor as string)?.trim()] || '#2dd4bf',
    },
  }), [currentDesign]);

  // Update theme-color meta tags when theme changes
  useEffect(() => {
    // Use participation theme if available, otherwise fall back to chat room theme
    if (!activeTheme) return;

    const themeColor = activeTheme.theme_color;

    // Store theme colors in localStorage for layout.tsx to use on next load
    localStorage.setItem('chat_theme_color', JSON.stringify(themeColor));

    // Detect system color scheme preference
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const currentColor = prefersDark ? themeColor.dark : themeColor.light;

    // Update default meta tag
    let defaultMeta = document.querySelector('meta[name="theme-color"]:not([media])');
    if (defaultMeta) {
      defaultMeta.setAttribute('content', currentColor);
    } else {
      defaultMeta = document.createElement('meta');
      defaultMeta.setAttribute('name', 'theme-color');
      defaultMeta.setAttribute('content', currentColor);
      document.head.appendChild(defaultMeta);
    }

    // Update light mode meta tag
    let lightMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: light)"]');
    if (lightMeta) {
      lightMeta.setAttribute('content', themeColor.light);
    } else {
      lightMeta = document.createElement('meta');
      lightMeta.setAttribute('name', 'theme-color');
      lightMeta.setAttribute('media', '(prefers-color-scheme: light)');
      lightMeta.setAttribute('content', themeColor.light);
      document.head.appendChild(lightMeta);
    }

    // Update dark mode meta tag
    let darkMeta = document.querySelector('meta[name="theme-color"][media="(prefers-color-scheme: dark)"]');
    if (darkMeta) {
      darkMeta.setAttribute('content', themeColor.dark);
    } else {
      darkMeta = document.createElement('meta');
      darkMeta.setAttribute('name', 'theme-color');
      darkMeta.setAttribute('media', '(prefers-color-scheme: dark)');
      darkMeta.setAttribute('content', themeColor.dark);
      document.head.appendChild(darkMeta);
    }

    // Also update body background to match theme
    document.body.style.backgroundColor = currentColor;
  }, [participationTheme, chatRoom?.theme]);

  // Note: Scroll-based visibility tracking for sticky host messages was removed.
  // We now always show the latest host message in the sticky area, which is simpler
  // and eliminates the flickering that occurred when multiple messages crossed
  // the visibility threshold (especially problematic in Focus mode where all
  // messages are from the host).

  if (loading) {
    return (
      <div className={`${currentDesign.container} flex items-center justify-center`}>
        <div className="text-gray-600 dark:text-gray-400">Loading chat...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={currentDesign.container}>
        <Header />
        <div className="container mx-auto px-4 py-12 max-w-2xl">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-red-600 dark:text-red-400">
            {error}
          </div>
        </div>
      </div>
    );
  }

  if (authMode && isMobile) {
    return (
      <div className="overflow-y-auto bg-zinc-900" style={authStyle}>
        <div className={`${currentDesign.header} sticky top-0 z-50 bg-zinc-900`}>
          <div className="flex items-center justify-between gap-3">
            <h1 className={`${currentDesign.headerTitle} text-lg font-semibold`}>
              {authMode === 'login' ? 'Log in' : 'Sign up'}
            </h1>
            <button
              onClick={closeModal}
              className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle}`}
              aria-label="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>
        <div className="p-6">
          {authMode === 'login' && <LoginFormContent onClose={closeModal} onSwitchToRegister={() => switchAuth('signup')} hideTitle />}
          {authMode === 'register' && <RegisterFormContent onClose={closeModal} onSwitchToLogin={() => switchAuth('login')} hideTitle />}
        </div>
      </div>
    );
  }

  // Main chat interface
  return (
    <>
      {/* Main Chat Interface */}
      <div
        className={`${currentDesign.container}`}
        style={{
          WebkitUserSelect: 'none',
          userSelect: 'none',
          WebkitTouchCallout: 'none',
        }}
      >
        {/* Chat Header */}
        <div
          data-chat-header
          className={currentDesign.header}
          onTouchStart={(e) => {
            headerTouchStartYRef.current = e.touches[0].clientY;
          }}
          onTouchEnd={(e) => {
            if (headerTouchStartYRef.current !== null) {
              const deltaY = e.changedTouches[0].clientY - headerTouchStartYRef.current;
              if (deltaY > 30) {
                setExpandStickySignal(s => s + 1);
              }
              headerTouchStartYRef.current = null;
            }
          }}
        >
          <div className="flex items-center justify-between gap-3">
            {chatRoom && (
              <>
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  <button
                    onClick={() => {
                      if (currentRoom !== 'main') {
                        switchRoom('main');  // Return to main chat
                      } else if (hasJoined) {
                        router.back();
                      } else {
                        router.push('/');
                      }
                    }}
                    className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle}`}
                    aria-label="Back"
                  >
                    <ArrowLeft size={18} />
                  </button>
                  <h1 className={`${currentDesign.headerTitle} truncate text-base`}>
                    <span className="text-sm opacity-50 relative -top-px">@{roomUsername}&apos;s</span> #{chatRoom.name.replace(/\s+/g, '')}
                  </h1>
                </div>
                <button
                  className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle}`}
                  aria-label="Notifications"
                >
                  <Bell size={18} />
                </button>
              </>
            )}
          </div>
        </div>

      {/* Content Area Wrapper - View Router for Main Chat, Back Room, and future features */}
      <div className={`flex-1 relative overflow-hidden ${!hasJoined ? 'pointer-events-none' : ''}`}>
        {/* Page-level loading overlay for room transitions */}
        {roomLoading && isSeparateViewRoom(currentRoom) && (
          <div className={`absolute inset-0 z-40 flex items-center justify-center ${
            currentDesign.uiStyles?.loadingBg || 'bg-zinc-900'
          }`}>
            <div className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl ${
              currentDesign.uiStyles?.loadingCard || 'bg-zinc-800 text-zinc-200'
            }`}>
              <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              <span className="text-sm font-medium">
                {getRoomLoadingText(currentRoom, previousRoom)}
              </span>
            </div>
          </div>
        )}
              <MainChatView
                hiddenMode={isSeparateViewRoom(currentRoom)}
                chatRoom={chatRoom}
                currentUserId={currentUserId ?? null}
                username={username}
                hasJoined={hasJoined}
                sessionToken={sessionToken}
                filteredMessages={filteredMessages}
                stickyHostMessages={stickyHostMessages}
                stickyPinnedMessage={stickyPinnedMsgFiltered}
                messagesContainerRef={messagesContainerRef}
                messagesEndRef={messagesEndRef}
                currentDesign={currentDesign}
                themeIsDarkMode={themeIsDarkMode}
                handleScroll={handleScroll}
                scrollToMessage={scrollToMessage}
                cancelScrollAnimation={cancelScrollAnimation}
                highlightMessage={highlightMessage}
                handleReply={handleReply}
                disableReply={currentRoom === 'gifts' || currentRoom === 'broadcast'}
                filterLoading={roomLoading}
                filterMode={currentRoom === 'main' ? 'all' : currentRoom as 'focus' | 'gifts' | 'broadcast'}
                filterLoadingText={getRoomLoadingText(currentRoom, previousRoom)}
                handlePin={handlePin}
                handleAddToPin={handleAddToPin}
                getPinRequirements={getPinRequirements}
                handleBlockUser={handleBlockUser}
                handleUnblockUser={handleUnblockUser}
                handleUnmuteUser={handleUnmuteUser}
                mutedUsernames={mutedUsernames}
                spotlightUsernames={spotlightUsernames}
                onSpotlightAdd={handleSpotlightAdd}
                onSpotlightRemove={handleSpotlightRemove}
                onRequestSignup={() => openAuth('signup')}
                handleTipUser={handleTipUser}
                handleSendGift={handleSendGift}
                handleThankGift={handleThankGift}
                handleBroadcastMessage={handleBroadcastMessage}
                handleDeleteMessage={handleDeleteMessage}
                handleReactionToggle={handleReactionToggle}
                messageReactions={messageReactions}
                loadingOlder={loadingOlder}
                onStickyHeightChange={handleStickyHeightChange}
                onStickyHiddenChange={setStickyIsHidden}
                showScrollToBottom={showScrollToBottom}
                onScrollToBottom={handleScrollToBottom}
                expandStickySignal={expandStickySignal}
              />

            {/* Join Modal - inline overlay within messages area */}
            {!hasJoined && chatRoom && (
              <div className="pointer-events-auto">
                <JoinChatModal
                  key={joinModalKey}
                  chatRoom={chatRoom}
                  currentUserDisplayName={registeredDisplayName || username}
                  hasJoinedBefore={hasJoinedBefore}
                  isBlocked={isBlocked}
                  isLoggedIn={!!currentUserId}
                  hasReservedUsername={hasReservedUsername}
                  themeIsDarkMode={themeIsDarkMode}
                  userAvatarUrl={userAvatarUrl}
                  anonymousParticipations={anonymousParticipations}
                  registeredAvatarUrl={registeredAvatarUrl}
                  onAvatarChange={setUserAvatarUrl}
                  onIdentityChange={(identity) => {
                    setPreviewUsername(identity.username);
                    setPreviewAvatarUrl(identity.avatarUrl);
                    setPreviewHasReservedUsername(identity.hasReservedUsername);
                    setPreviewIsHost(identity.hasReservedUsername ? isHost : false);
                  }}
                  onJoin={handleJoinChat}
                  onLogin={() => openAuth('login')}
                  onSignup={() => openAuth('signup')}
                />
              </div>
            )}

        {currentRoom === 'backroom' && hasJoined && chatRoom && (
          <GameRoomView
            chatRoom={chatRoom}
            username={username}
            currentUserId={currentUserId}
            onBack={() => switchRoom('main')}
            design={'dark-mode'}
          />
        )}

        {/* FAB Scroll Strip - positioned inside content area, adjusts to sticky section */}
        {hasJoined && (
          <div
            className="absolute right-0 z-50"
            onTouchStart={() => { (document.activeElement as HTMLElement)?.blur(); }}
            style={{
              top: `${fabTopExpanded}px`,
              bottom: '8px',
              // translate3d forces GPU layer pre-allocation on Android Chrome so the
              // transition starts instantly instead of waiting for layer promotion.
              transform: stickyIsHidden
                ? `translate3d(0, -${fabCollapseOffset}px, 0)`
                : 'translate3d(0, 0, 0)',
              transition: 'transform 200ms ease-out',
              willChange: 'transform',
            }}
          >
            {/* Top fade — matches page background, icons dissolve into it */}
            <div className={`absolute top-0 left-0 right-0 h-10 z-10 pointer-events-none transition-opacity duration-200 ${fabCanScrollUp ? 'opacity-100' : 'opacity-0'}`}
              style={{ background: 'linear-gradient(to bottom, #18181b 0%, #18181b 30%, transparent 100%)' }}
            />

            {/* Scrollable icon strip */}
            <div
              ref={fabStripRef}
              onScroll={updateFabScrollFades}
              className="h-full flex flex-col items-center gap-2 overflow-y-auto no-scrollbar px-1 py-1"
            >
              {/* Broadcast Room */}
              <FloatingActionButton
                inline
                icon={Radio}
                toggledIcon={MessageSquare}
                onClick={() => switchRoom(currentRoom === 'broadcast' ? 'main' : 'broadcast')}
                isToggled={currentRoom === 'broadcast'}
                ariaLabel="Broadcasts"
                toggledAriaLabel="Show All Messages"
                design={'dark-mode'}
              />
              {/* Focus Filter */}
              <FloatingActionButton
                inline
                icon={Eye}
                toggledIcon={MessageSquare}
                onClick={() => switchRoom(currentRoom === 'focus' ? 'main' : 'focus')}
                isToggled={currentRoom === 'focus'}
                ariaLabel="Focus Mode"
                toggledAriaLabel="Show All Messages"
                design={'dark-mode'}
              />
              {/* Gift Filter */}
              <FloatingActionButton
                inline
                icon={Gift}
                toggledIcon={MessageSquare}
                onClick={() => switchRoom(currentRoom === 'gifts' ? 'main' : 'gifts')}
                isToggled={currentRoom === 'gifts'}
                ariaLabel="Filter Gifts"
                toggledAriaLabel="Show All Messages"
                design={'dark-mode'}
              />
              {/* Game Room Tab */}
              <FloatingActionButton
                inline
                icon={Gamepad2}
                toggledIcon={MessageSquare}
                onClick={() => switchRoom(currentRoom === 'backroom' ? 'main' : 'backroom')}
                isToggled={currentRoom === 'backroom'}
                hasNotification={false}
                ariaLabel="Open Game Room"
                toggledAriaLabel="Return to Main Chat"
                design={'dark-mode'}
              />
              {/* Settings Button */}
              <FloatingActionButton
                inline
                icon={Settings}
                onClick={() => {
                  window.history.pushState({ view: 'settings' }, '', window.location.href);
                  setShowSettingsSheet(true);
                }}
                ariaLabel="Open Settings"
                design={'dark-mode'}
              />
            </div>

            {/* Bottom fade — matches page background, icons dissolve into it */}
            <div className={`absolute bottom-0 left-0 right-0 h-10 z-10 pointer-events-none transition-opacity duration-200 ${fabCanScrollDown ? 'opacity-100' : 'opacity-0'}`}
              style={{ background: 'linear-gradient(to top, #18181b 0%, #18181b 30%, transparent 100%)' }}
            />
          </div>
        )}
      </div>

      {/* Message Input - Only show in chat rooms (not separate views like backroom, not read-only rooms) */}
      {!isSeparateViewRoom(currentRoom) && currentRoom !== 'broadcast' && (
        <div className="relative">
          <MessageInput
            chatRoom={chatRoom}
            isHost={previewIsHost ?? isHost}
            hasJoined={hasJoined}
            sending={sending}
            username={previewUsername ?? username}
            avatarUrl={previewAvatarUrl !== undefined ? previewAvatarUrl : userAvatarUrl}
            hasReservedUsername={previewHasReservedUsername ?? hasReservedUsername}
            replyingTo={replyingTo}
            onCancelReply={handleCancelReply}
            onSubmitText={handleSubmitText}
            onVoiceRecording={handleVoiceRecording}
            onPhotoSelected={handlePhotoSelected}
            onVideoSelected={handleVideoSelected}
            disabled={currentRoom === 'gifts'}
            disabledMessage="Viewing gift history"
            design={messageInputDesign}
          />
          {!hasJoined && (
            <div className="absolute inset-0 bg-black/40 pointer-events-auto" />
          )}
        </div>
      )}
      </div>

      {/* Auth Modals (desktop only — mobile renders inline in content area) */}
      {!isMobile && authMode === 'login' && (
        <LoginModal
          onClose={closeModal}
          theme="chat"
          chatTheme={'dark-mode'}
        />
      )}
      {!isMobile && authMode === 'register' && (
        <RegisterModal
          onClose={closeModal}
          theme="chat"
          chatTheme={'dark-mode'}
        />
      )}

      {/* Chat Settings Sheet - opened by floating Settings button */}
      {chatRoom && (
        <ChatSettingsSheet
          key={hasJoined ? 'joined' : 'not-joined'}
          chatRoom={chatRoom}
          currentUserId={currentUserId}
          activeThemeId={(participationTheme || chatRoom.theme)?.theme_id}
          onUpdate={(updatedRoom) => setChatRoom(updatedRoom)}
          themeIsDarkMode={themeIsDarkMode}
          spotlightUsernames={spotlightUsernames}
          onSpotlightAdd={handleSpotlightAdd}
          onSpotlightRemove={handleSpotlightRemove}
          open={showSettingsSheet}
          onOpenChange={(open) => {
            if (!open && showSettingsSheet) {
              // Closing - use history.back() to properly handle browser history
              window.history.back();
            } else {
              setShowSettingsSheet(open);
            }
          }}
        >
          {/* Empty trigger - controlled by Settings button */}
          <div />
        </ChatSettingsSheet>
      )}

      {/* Gift Received Popup */}
      <GiftReceivedPopup
        gifts={giftQueue}
        themeIsDarkMode={themeIsDarkMode}
        onSkipOne={handleDismissGift}
        onThankOne={handleThankGiftPopup}
        onSkipAll={handleDismissAllGifts}
        onThankAll={handleThankAllGifts}
        onClose={() => setGiftQueue([])}
      />

      {/* Feature Intro Modals */}
      {showFeatureIntro === 'focus' && (
        <FeatureIntroModal
          title="Focus Mode"
          description="Focus shows messages most relevant to you — your messages, replies to you, and host messages in your threads. Everything else is filtered out."
          icon={Eye}
          themeIsDarkMode={themeIsDarkMode}
          onDismiss={() => handleDismissIntro('focus')}
        />
      )}
      {showFeatureIntro === 'spotlight_first_time' && (
        <FeatureIntroModal
          title="You're in the spotlight!"
          description="The host has featured you in this chat. Your messages will appear in the Focus room and carry a star for all members to see."
          icon={Star}
          themeIsDarkMode={themeIsDarkMode}
          onDismiss={() => handleDismissIntro('spotlight_first_time')}
        />
      )}
    </>
  );
}
