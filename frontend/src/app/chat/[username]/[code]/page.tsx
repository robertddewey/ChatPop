'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { flushSync } from 'react-dom';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { chatApi, messageApi, authApi, backRoomApi, type ChatRoom, type ChatTheme, type Message, type ReactionSummary } from '@/lib/api';
import Header from '@/components/Header';
import ChatSettingsSheet from '@/components/ChatSettingsSheet';
import GameRoomTab from '@/components/GameRoomTab';
import FloatingActionButton from '@/components/FloatingActionButton';
import GameRoomView from '@/components/GameRoomView';
import MainChatView from '@/components/MainChatView';
import MessageActionsModal from '@/components/MessageActionsModal';
import JoinChatModal from '@/components/JoinChatModal';
import LoginModal from '@/components/LoginModal';
import RegisterModal from '@/components/RegisterModal';
import VoiceMessagePlayer from '@/components/VoiceMessagePlayer';
import MessageInput from '@/components/MessageInput';
import { UsernameStorage, getFingerprint } from '@/lib/usernameStorage';
import { playSendMessageSound, playReceiveMessageSound } from '@/lib/sounds';
import { Settings, BadgeCheck, Crown, Gamepad2, MessageSquare, Sparkles, ArrowLeft, Reply, X } from 'lucide-react';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { type RecordingMetadata } from '@/lib/waveform';
import { consumeFreshNavigation, markChatVisited, hasChatBeenVisited, clearChatVisited, hasModalState } from '@/lib/modalState';

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
  messages_area_bg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(120deg)_saturate(3)]",
  host_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-teal-600 font-medium transition-all duration-300",
  sticky_host_message: "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-teal-600 font-medium transition-all duration-300",
  host_text: "text-white",
  host_message_fade: "bg-gradient-to-l from-teal-600 to-transparent",
  pinned_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-amber-700 border-l-4 border-amber-400 font-medium transition-all duration-300",
  sticky_pinned_message: "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-amber-700 border-l-4 border-amber-400 font-medium transition-all duration-300",
  pinned_text: "text-white",
  pinned_message_fade: "bg-gradient-to-l from-amber-700 to-transparent",
  regular_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800 border-l-2 border-emerald-500/50",
  regular_text: "text-zinc-100",
  my_message: "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-emerald-600 shadow-md",
  my_text: "text-white",
  messages_area_container: "bg-zinc-900",
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
  pin_icon_color: "text-amber-400",
  crown_icon_color: "text-teal-400",
  badge_icon_color: "text-emerald-400",
  reply_icon_color: "text-emerald-300",
  my_username: "text-xs font-semibold text-emerald-300",
  regular_username: "text-xs font-semibold text-zinc-300",
  host_username: "text-xs font-semibold text-teal-300",
  my_host_username: "text-xs font-semibold text-emerald-300",
  pinned_username: "text-xs font-semibold text-amber-300",
  sticky_host_username: "text-xs font-semibold text-teal-300",
  sticky_pinned_username: "text-xs font-semibold text-amber-300",
  my_timestamp: "text-xs text-emerald-200",
  regular_timestamp: "text-xs text-zinc-400",
  host_timestamp: "text-xs text-teal-200",
  pinned_timestamp: "text-xs text-amber-200",
  reply_preview_container: "bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2",
  reply_preview_icon: "text-emerald-400",
  reply_preview_username: "text-xs font-semibold text-zinc-300",
  reply_preview_content: "text-xs text-zinc-400 truncate",
  reply_preview_close_button: "p-1 rounded hover:bg-zinc-700",
  reply_preview_close_icon: "text-zinc-400",
  reaction_highlight_bg: "bg-zinc-700",
  reaction_highlight_border: "border border-zinc-500",
  reaction_highlight_text: "text-zinc-200",
  // Avatar settings
  avatar_style: "pixel-art",
  avatar_size: "w-10 h-10",
  avatar_border: null,
  avatar_spacing: "mr-3",
};

export default function ChatPage() {
  const params = useParams();
  const code = params.code as string;
  const roomUsername = params.username as string; // Extract username from URL for manual rooms
  const searchParams = useSearchParams();
  const router = useRouter();

  const authMode = searchParams.get('auth');

  const closeModal = () => {
    const newParams = new URLSearchParams(searchParams);
    newParams.delete('auth');
    newParams.delete('redirect');
    router.replace(`${window.location.pathname}?${newParams.toString()}`);
  };

  // No theme switching - always use dark-mode

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
  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [joinError, setJoinError] = useState('');

  // Message input state (message text is managed locally in MessageInput component)
  const [sending, setSending] = useState(false);
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);

  // Infinite scroll state
  const [hasMoreMessages, setHasMoreMessages] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);

  // Message filter
  const [filterMode, setFilterMode] = useState<'all' | 'focus'>('all');

  // Emoji reactions state
  const [messageReactions, setMessageReactions] = useState<Record<string, ReactionSummary[]>>({});

  // Pin expiry trigger - incrementing this forces re-computation of topPinnedMessage
  const [pinExpiryTick, setPinExpiryTick] = useState(0);

  // View state - supports multiple feature views
  type ViewType = 'main' | 'backroom';
  const [activeView, setActiveView] = useState<ViewType>('main');

  // Settings sheet state
  const [showSettingsSheet, setShowSettingsSheet] = useState(false);

  // WebSocket state
  const [sessionToken, setSessionToken] = useState<string | null>(null);

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

    // Show alert and redirect to home page
    alert(message || 'You have been removed from this chat.');
    window.location.href = '/';
  }, [code]);

  // Handle user kicked event (host removed user from chat)
  const handleUserKicked = useCallback((message: string) => {
    // Clear local state
    localStorage.removeItem(`chat_session_${code}`);
    setSessionToken(null);
    setHasJoined(false);
    setMessages([]);

    // Show alert and redirect to home page
    alert(message || 'You have been removed from this chat by the host.');
    window.location.href = '/';
  }, [code]);

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
  }, []);

  // Handle visibility changes (mobile app switching)
  // WebSocket handles real-time messages, no need to refetch on tab return
  const handleVisibilityChange = useCallback((_isVisible: boolean) => {
    // No action needed - WebSocket delivers messages in real-time
  }, []);

  // WebSocket connection
  const { sendMessage: wsSendMessage, sendRawMessage, isConnected } = useChatWebSocket({
    chatCode: code,
    sessionToken,
    onMessage: handleWebSocketMessage,
    onUserBlocked: handleUserBlocked,
    onUserKicked: handleUserKicked,
    onReaction: handleReactionEvent,
    onMessageDeleted: handleMessageDeleted,
    onMessagePinned: handleMessagePinned,
    onVisibilityChange: handleVisibilityChange,
    enabled: hasJoined && !!sessionToken,
  });

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
      // User has visited this chat page before in this session,
      // has no existing session, and didn't come from modal
      // This is forward navigation - redirect to home
      console.log('[ChatPage] Forward navigation detected, redirecting to home');
      router.replace('/');
      return;
    }

    // First-time visit via direct URL or existing session - allow
  }, [code, router]);

  // Add chat-layout class to body on mount, remove on unmount
  // This enables the chat-specific CSS (position: fixed, overflow: hidden, etc.)
  useEffect(() => {
    document.body.classList.add('chat-layout');
    return () => {
      document.body.classList.remove('chat-layout');
    };
  }, []);

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

  // Scroll to bottom when filter mode changes, or when switching between Main Chat and Back Room
  useEffect(() => {
    // Mark that we should auto-scroll
    shouldAutoScrollRef.current = true;
    // Use requestAnimationFrame to ensure DOM has updated with filtered messages
    requestAnimationFrame(() => {
      const container = messagesContainerRef.current;
      if (container) {
        // Instant scroll to bottom (no animation)
        container.scrollTop = container.scrollHeight;
      }
    });
  }, [filterMode, activeView]);

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

        if (currentUser) {
          // Logged-in user
          setCurrentUserId(currentUser.id);
          setUserAvatarUrl(currentUser.avatar_url || null);

          if (participation.has_joined && participation.username) {
            // Returning user - use their locked username
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
          } else {
            // First-time user - pre-fill with reserved_username
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(false);
            setHasReservedUsername(!!currentUser.reserved_username);
          }
        } else {
          // Anonymous user
          if (participation.has_joined && participation.username) {
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
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

  // Listen for auth changes (login/register)
  useEffect(() => {
    const handleAuthChange = async () => {
      // User just logged in or registered - refresh user state
      const token = localStorage.getItem('auth_token');
      if (token) {
        try {
          const currentUser = await authApi.getCurrentUser();
          setCurrentUserId(currentUser.id);
          setHasReservedUsername(!!currentUser.reserved_username);
          setUserAvatarUrl(currentUser.avatar_url || null);

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

          if (participation.has_joined && participation.username) {
            // They already joined - update username and badge
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setIsBlocked(participation.is_blocked || false);
            setHasReservedUsername(participation.username_is_reserved || false);
          } else {
            // Not joined yet - pre-fill with reserved username
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
            setIsBlocked(false);
            // Badge shows if they have a reserved username
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

  // Redirect blocked users to home page immediately
  useEffect(() => {
    if (isBlocked) {
            router.replace('/'); // Use replace to avoid adding to browser history
    }
  }, [isBlocked, router]);

  // Listen for back button to handle view navigation and join modal
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // If settings sheet is open, close it first
      if (showSettingsSheet) {
        setShowSettingsSheet(false);
        return;
      }

      // If in a secondary view (backroom), return to main chat first
      if (activeView !== 'main') {
        setActiveView('main');
        return;
      }

      // If user is in main chat and presses back, show join modal and reset state
      if (hasJoined) {
        setHasJoined(false);
        setHasJoinedBefore(true); // They've joined, so mark as returning user
        setMessages([]); // Clear messages to show fresh state
        setJoinModalKey(prev => prev + 1); // Force modal remount
        // Push new state to clear forward history - prevents forward button from being available
        window.history.pushState({ modal: true }, '', window.location.href);
      } else {
        // User is on join modal and leaving - mark as visited for forward navigation detection
        markChatVisited(code);

        // Check if they came from suggestions modal
        if (hasModalState()) {
          // User came from suggestions - go back to restore modal
          router.back();
        } else {
          // User came from direct URL - go to homepage
          router.replace('/');
        }
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [hasJoined, activeView, showSettingsSheet, router, code]);

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
      const { messages: msgs, pinnedMessages } = await messageApi.getMessages(code, roomUsername, sessionToken || undefined);

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
          container.scrollTop = container.scrollHeight;
        }
        initialScrollDoneRef.current = true; // Mark scroll complete
      });
    } catch (err) {
      console.error('Failed to load messages:', err);
    } finally {
      isLoadingMessagesRef.current = false;
    }
  };

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
      const { messages: olderMessages, hasMore } = await messageApi.getMessagesBefore(code, beforeTimestamp, 50, roomUsername);

      if (olderMessages.length > 0) {
        // Freeze sticky state during insert
        isInsertingRef.current = true;

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
        container.scrollTop = targetScrollTop;

        // Unfreeze sticky after scroll adjustment settles
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            isInsertingRef.current = false;
          });
        });
      }

      setHasMoreMessages(hasMore);
    } catch (err) {
      console.error('Failed to load older messages:', err);
      isInsertingRef.current = false; // Ensure we unfreeze on error
    } finally {
      setLoadingOlder(false);
    }
  };

  // Join handler for modal
  const handleJoinChat = async (username: string, accessCode?: string) => {
    try {
      // Get fingerprint
      let fingerprint: string | undefined;
      try {
        fingerprint = await getFingerprint();
      } catch (fpErr) {
        console.warn('Failed to get fingerprint:', fpErr);
      }

      await chatApi.joinChat(code, username, accessCode, fingerprint, roomUsername);

      // Update session token immediately after joining
      const newSessionToken = localStorage.getItem(`chat_session_${code}`);
      setSessionToken(newSessionToken);

      const token = localStorage.getItem('auth_token');
      const isLoggedIn = !!token;
      await UsernameStorage.saveUsername(code, username, isLoggedIn);
      setUsername(username);
      setHasJoined(true);
      clearChatVisited(code); // Clear visit tracking since user joined
      await loadMessages();

      // Add history entry so back button shows join modal again
      window.history.pushState({ joined: true }, '', window.location.href);
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      // Log the full error structure for debugging
      console.error('[Join Error] Full error:', err);
      console.error('[Join Error] Response data:', apiErr.response?.data);
      console.error('[Join Error] Status:', apiErr.response?.status);

      // Extract error message from various DRF error formats
      let errorMessage = 'Failed to join chat';

      if (apiErr.response?.data) {
        const data = apiErr.response.data;

        // Direct array response: ["error message"]
        if (Array.isArray(data) && data.length > 0) {
          errorMessage = String(data[0]);
        }
        // PermissionDenied: { detail: "message" }
        else if (typeof data === 'object' && data !== null && 'detail' in data && data.detail) {
          errorMessage = String(data.detail);
        }
        // ValidationError: { non_field_errors: ["message"] }
        else if (typeof data === 'object' && data !== null && 'non_field_errors' in data && Array.isArray(data.non_field_errors)) {
          errorMessage = String(data.non_field_errors[0]);
        }
        // ValidationError: direct string message
        else if (typeof data === 'string') {
          errorMessage = data;
        }
        // Check for field-specific errors (e.g., { username: ["error"] })
        else if (typeof data === 'object' && data !== null) {
          // Get first error from any field
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
        // Don't throw error - the redirect will happen via useEffect
        return;
      }

      // If this is a username persistence error, extract the username and store it for pre-population
      const usernameMatch = errorMessage.match(/already joined this chat as '([^']+)'/);
      if (usernameMatch && chatRoom) {
        const existingUsername = usernameMatch[1];
        // Store the suggested username in localStorage so the modal can pick it up
        localStorage.setItem(`chat_${chatRoom.code}_suggested_username`, existingUsername);
        errorMessage = `You previously joined as "${existingUsername}". Please use that username to rejoin.`;
      }

      throw new Error(errorMessage);
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
          messageUsername = (await UsernameStorage.getUsername(code, isLoggedIn)) || '';
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
        messageUsername = (await UsernameStorage.getUsername(code, isLoggedIn)) || '';
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
        messageUsername = (await UsernameStorage.getUsername(code, isLoggedIn)) || '';
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
        messageUsername = (await UsernameStorage.getUsername(code, isLoggedIn)) || '';
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
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
  };

  const scrollToMessage = useCallback((messageId: string) => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Add pulsating animation
      element.classList.add('animate-pulse-scale');
      setTimeout(() => {
        element.classList.remove('animate-pulse-scale');
      }, 2000);
    }
  }, []);

  // Track if user is near bottom
  const shouldAutoScrollRef = useRef(true);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Track if we're inserting older messages (to freeze sticky during insert)
  const isInsertingRef = useRef(false);

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

  // Anchor scroll position when content height changes above viewport
  // (e.g., reaction bars appearing/disappearing on messages the user has scrolled past).
  // Uses ResizeObserver on the content wrapper so it's decoupled from React rendering.
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || !hasJoined) return;

    const content = container.firstElementChild;
    if (!content) return;

    let prevScrollHeight = container.scrollHeight;

    const observer = new ResizeObserver(() => {
      const newScrollHeight = container.scrollHeight;
      const heightDiff = newScrollHeight - prevScrollHeight;

      // Only adjust if:
      // - Height actually changed
      // - User is scrolled up (not auto-scrolling at bottom)
      // - Not during infinite scroll prepend (that handles its own adjustment)
      if (heightDiff !== 0 && !shouldAutoScrollRef.current && !isInsertingRef.current) {
        container.scrollTop += heightDiff;
      }

      prevScrollHeight = newScrollHeight;
    });

    observer.observe(content);
    return () => observer.disconnect();
  }, [hasJoined]);


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
            // Reload messages to get updated pin status
      await loadMessages();
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
            // Reload messages to get updated pin amount
      await loadMessages();
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
                alert(`Banned ${username} from this chat. They will no longer be able to join or send messages.`);
      } else {
        // Non-hosts can only mute users site-wide (UserBlock)
        await messageApi.blockUserSiteWide(username);
                alert(`Blocked ${username}. You will no longer see their messages anywhere on ChatPop.`);
      }
      // TODO: Update local state to filter out blocked user's messages
    } catch (err: unknown) {
      const error = err as ApiError & { response?: { data?: { username?: string[]; message?: string } } };
      console.error('Failed to block user:', error);
      const errorData = error.response?.data;
      const errorMsg = errorData?.username?.[0] || errorData?.message || 'Failed to block user. Please try again.';
      alert(errorMsg);
    }
  }, [currentUserId, chatRoom, code]);

  const handleTipUser = useCallback((username: string) => {
        // TODO: Implement tip user logic with payment
  }, []);

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
        fingerprint,
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
  }, [code, username, fingerprint]);

  // Filter messages based on mode (memoized to prevent recalculation on unrelated state changes)
  const filteredMessages = useMemo(() => {
    if (filterMode !== 'focus') return messages;

    return messages.filter(msg => {
      // Show host messages
      if (msg.is_from_host) return true;

      // Show my messages (use username from state)
      if (msg.username === username) return true;

      // Show messages that host replied to
      const hostRepliedToThis = messages.some(
        m => m.is_from_host && m.reply_to === msg.id
      );
      if (hostRepliedToThis) return true;

      return false;
    });
  }, [messages, filterMode, username]);

  // Filter messages for sticky section (useMemo to prevent infinite loops)
  const allStickyHostMessages = useMemo(() => {
    return filteredMessages
      .filter(m => m.is_from_host)
      .slice(-1)  // Get 1 most recent
      .reverse(); // Show newest first
  }, [filteredMessages]);

  // Use full messages list (not filtered) so sticky pin is always the true winner
  const topPinnedMessage = useMemo(() => {
    const now = new Date();
    return messages
      .filter(m => m.is_pinned && !m.is_from_host && (!m.sticky_until || new Date(m.sticky_until) > now))
      .sort((a, b) => parseFloat(b.current_pin_amount) - parseFloat(a.current_pin_amount))
      [0]; // Get highest paid, non-expired
  }, [messages, pinExpiryTick]);

  // Check if current user is the host
  const isHost = useMemo(() => {
    return !!(currentUserId && chatRoom && chatRoom.host.id === currentUserId);
  }, [currentUserId, chatRoom]);

  // Refs to store previous sticky values (for freezing during insert)
  const prevStickyHostRef = useRef<Message[]>([]);
  const prevStickyPinnedRef = useRef<Message | null>(null);

  // Always show the most recent host message in sticky area
  // This is simpler than scroll-based tracking and eliminates flickering
  const stickyHostMessages = useMemo(() => {
    // If inserting older messages, return frozen value to prevent flash
    if (isInsertingRef.current) {
            return prevStickyHostRef.current;
    }

    // Save for future freeze
    prevStickyHostRef.current = allStickyHostMessages;

    return allStickyHostMessages;
  }, [allStickyHostMessages]);

  // Always show pinned message in sticky area (user paid for visibility)
  const computedStickyPinnedMessage = topPinnedMessage || null;

  // Freeze pinned message during insert too
  const stickyPinnedMessage = useMemo(() => {
    if (isInsertingRef.current) {
      return prevStickyPinnedRef.current;
    }
    prevStickyPinnedRef.current = computedStickyPinnedMessage;
    return computedStickyPinnedMessage;
  }, [computedStickyPinnedMessage]);

  // Auto-remove expired pins from sticky section
  useEffect(() => {
    if (!stickyPinnedMessage?.sticky_until) return;

    const expiryTime = new Date(stickyPinnedMessage.sticky_until).getTime();
    const now = Date.now();
    const timeRemaining = expiryTime - now;

    // If already expired, trigger immediate re-computation
    if (timeRemaining <= 0) {
      setPinExpiryTick(t => t + 1);
      return;
    }

    // Set timer to trigger re-computation when pin expires
    const timer = setTimeout(() => {
            setPinExpiryTick(t => t + 1);
    }, timeRemaining);

    return () => clearTimeout(timer);
  }, [stickyPinnedMessage?.id, stickyPinnedMessage?.sticky_until]);

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

        // Mark initial scroll as complete once we reach bottom for the first time
        if (!initialScrollDoneRef.current) {
          initialScrollDoneRef.current = true;
        }
      } else if (scrolledFarFromBottom && wasAutoScroll) {
        // User manually scrolled up significantly while auto-scroll was on
        // Disable auto-scroll
        shouldAutoScrollRef.current = false;
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

  // Main chat interface
  return (
    <>
      {/* Floating Back Button - ONLY this is clickable above the modal */}
      {chatRoom && !hasJoined && (
        <button
          onClick={() => {
            if (hasModalState()) {
              router.back();
            } else {
              router.replace('/');
            }
          }}
          className={`fixed top-3 left-4 z-[10000] p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle}`}
          aria-label="Back"
        >
          <ArrowLeft size={18} />
        </button>
      )}

      {/* Join Modal - rendered when user hasn't joined and auth modal is not open */}
      {!hasJoined && chatRoom && !authMode && (
        <JoinChatModal
          key={joinModalKey}
          chatRoom={chatRoom}
          currentUserDisplayName={username}
          hasJoinedBefore={hasJoinedBefore}
          isBlocked={isBlocked}
          isLoggedIn={!!currentUserId}
          hasReservedUsername={hasReservedUsername}
          themeIsDarkMode={themeIsDarkMode}
          userAvatarUrl={userAvatarUrl}
          onJoin={handleJoinChat}
        />
      )}

      {/* Main Chat Interface - blurred when not joined */}
      <div
        className={`${currentDesign.container} ${!hasJoined ? 'pointer-events-none' : ''}`}
        style={{
          WebkitUserSelect: 'none',
          userSelect: 'none',
          WebkitTouchCallout: 'none',
        }}
      >
        {/* Chat Header */}
        <div data-chat-header className={currentDesign.header}>
          <div className="flex items-center justify-between gap-3">
            {chatRoom && (
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <button
                  onClick={() => {
                    if (activeView !== 'main') {
                      setActiveView('main');  // Return to main chat
                    } else if (hasJoined) {
                      // In chat - use browser back to return to previous page
                      // This allows returning to modal with suggestions if user came from there
                      router.back();
                    } else {
                      // On join modal - check if user came from suggestions modal
                      if (hasModalState()) {
                        // User came from suggestions - go back to restore modal
                        router.back();
                      } else {
                        // User came from direct URL - go to homepage
                        router.replace('/');
                      }
                    }
                  }}
                  className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle}`}
                  aria-label="Back"
                >
                  <ArrowLeft size={18} />
                </button>
                <h1 className={`${currentDesign.headerTitle} truncate text-base`}>
                  {chatRoom.name}
                </h1>
              </div>
            )}
            {/* Filter Toggle */}
            <button
              onClick={() => {
                const newMode = filterMode === 'all' ? 'focus' : 'all';
                setFilterMode(newMode);

                // Reset scroll to top when changing filter to prevent weird jumps
                setTimeout(() => {
                  if (messagesContainerRef.current) {
                    messagesContainerRef.current.scrollTop = 0;
                  }
                }, 0);
              }}
              className={`transition-all whitespace-nowrap flex items-center gap-1.5 ${
                filterMode === 'focus'
                  ? currentDesign.filterButtonActive
                  : currentDesign.filterButtonInactive
              }`}
            >
              <Sparkles size={16} />
              Focus
            </button>
          </div>
        </div>

      {/* Content Area Wrapper - View Router for Main Chat, Back Room, and future features */}
      <div className="flex-1 relative overflow-hidden">
        {activeView === 'main' && (
          <MainChatView
            chatRoom={chatRoom}
            currentUserId={currentUserId ?? null}
            username={username}
            hasJoined={hasJoined}
            sessionToken={sessionToken}
            filteredMessages={filteredMessages}
            stickyHostMessages={stickyHostMessages}
            stickyPinnedMessage={stickyPinnedMessage}
            messagesContainerRef={messagesContainerRef}
            messagesEndRef={messagesEndRef}
            currentDesign={currentDesign}
            themeIsDarkMode={themeIsDarkMode}
            handleScroll={handleScroll}
            scrollToMessage={scrollToMessage}
            handleReply={handleReply}
            handlePin={handlePin}
            handleAddToPin={handleAddToPin}
            getPinRequirements={getPinRequirements}
            handleBlockUser={handleBlockUser}
            handleTipUser={handleTipUser}
            handleDeleteMessage={handleDeleteMessage}
            handleReactionToggle={handleReactionToggle}
            messageReactions={messageReactions}
            loadingOlder={loadingOlder}
          />
        )}

        {activeView === 'backroom' && hasJoined && chatRoom && (
          <GameRoomView
            chatRoom={chatRoom}
            username={username}
            currentUserId={currentUserId}
            onBack={() => setActiveView('main')}
            design={'dark-mode'}
          />
        )}
      </div>

      {/* Message Input - Only show in main chat view */}
      {activeView === 'main' && (
        <MessageInput
          chatRoom={chatRoom}
          isHost={isHost}
          hasJoined={hasJoined}
          sending={sending}
          replyingTo={replyingTo}
          onCancelReply={handleCancelReply}
          onSubmitText={handleSubmitText}
          onVoiceRecording={handleVoiceRecording}
          onPhotoSelected={handlePhotoSelected}
          onVideoSelected={handleVideoSelected}
          design={messageInputDesign}
        />
      )}

      {/* Crown Button - Grid centered at 50%, first icon at top of grid */}
      {hasJoined && (
        <FloatingActionButton
          icon={Crown}
          onClick={() => {}}
          position="right"
          customPosition="right-[2.5%] top-[calc(50%-92px)]"
          ariaLabel="Host Actions"
          design={'dark-mode'}
        />
      )}

      {/* Game Room Tab - Center icon of 3-icon grid */}
      {hasJoined && (
        <FloatingActionButton
          icon={Gamepad2}
          toggledIcon={MessageSquare}
          onClick={() => {
            if (activeView === 'backroom') {
              // Going back to main - use history.back() to properly handle browser history
              window.history.back();
            } else {
              // Entering backroom - push history state so back button returns to main
              window.history.pushState({ view: 'backroom' }, '', window.location.href);
              setActiveView('backroom');
            }
          }}
          isToggled={activeView === 'backroom'}
          hasNotification={false}
          position="right"
          customPosition="right-[2.5%] top-[calc(50%-28px)]"
          ariaLabel="Open Game Room"
          toggledAriaLabel="Return to Main Chat"
          design={'dark-mode'}
          initialBounce={false}
        />
      )}

      {/* Settings Button - Bottom icon of grid */}
      {hasJoined && (
        <FloatingActionButton
          icon={Settings}
          onClick={() => {
            window.history.pushState({ view: 'settings' }, '', window.location.href);
            setShowSettingsSheet(true);
          }}
          position="right"
          customPosition="right-[2.5%] top-[calc(50%+36px)]"
          ariaLabel="Open Settings"
          design={'dark-mode'}
        />
      )}
      </div>

      {/* Auth Modals */}
      {authMode === 'login' && (
        <LoginModal
          onClose={closeModal}
          theme="chat"
          chatTheme={'dark-mode'}
        />
      )}
      {authMode === 'register' && (
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
          fingerprint={fingerprint}
          activeThemeId={(participationTheme || chatRoom.theme)?.theme_id}
          onUpdate={(updatedRoom) => setChatRoom(updatedRoom)}
          themeIsDarkMode={themeIsDarkMode}
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
    </>
  );
}
