'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { chatApi, messageApi, authApi, type ChatRoom, type ChatTheme, type Message } from '@/lib/api';
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
import VoiceRecorder from '@/components/VoiceRecorder';
import VoiceMessagePlayer from '@/components/VoiceMessagePlayer';
import { UsernameStorage, getFingerprint } from '@/lib/usernameStorage';
import { playJoinSound } from '@/lib/sounds';
import { Settings, BadgeCheck, Crown, Gamepad2, MessageSquare, Sparkles, ArrowLeft, Reply, X } from 'lucide-react';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { type RecordingMetadata } from '@/lib/waveform';

// Convert snake_case API theme to camelCase for component compatibility
function convertThemeToCamelCase(theme: ChatTheme): any {
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
    playButton: "bg-zinc-600/40",
    playIconColor: "text-white",
    waveformActive: "bg-white/80",
    waveformInactive: "bg-white/20",
  },
  my_voice_message_styles: {
    playButton: "bg-emerald-800/70",
    playIconColor: "text-white",
    waveformActive: "bg-white/80",
    waveformInactive: "bg-white/20",
  },
  host_voice_message_styles: {
    playButton: "bg-teal-800",
    playIconColor: "text-white",
    waveformActive: "bg-white/80",
    waveformInactive: "bg-white/20",
  },
  pinned_voice_message_styles: {
    playButton: "bg-amber-800",
    playIconColor: "text-white",
    waveformActive: "bg-white/80",
    waveformInactive: "bg-white/20",
  },
  pin_icon_color: "text-amber-400",
  crown_icon_color: "text-teal-400",
  badge_icon_color: "text-emerald-400",
  reply_icon_color: "text-emerald-300",
};

export default function ChatPage() {
  const params = useParams();
  const code = params.code as string;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [fingerprint, setFingerprint] = useState<string | undefined>(undefined);
  const [participationTheme, setParticipationTheme] = useState<ChatTheme | null>(null);

  // Join state for guests
  const [hasJoined, setHasJoined] = useState(false);
  const [hasJoinedBefore, setHasJoinedBefore] = useState(false);
  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [joinError, setJoinError] = useState('');

  // Message input
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);

  // Infinite scroll state
  const [hasMoreMessages, setHasMoreMessages] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasVoiceRecording, setHasVoiceRecording] = useState(false);
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);

  // Message filter
  const [filterMode, setFilterMode] = useState<'all' | 'focus'>('all');

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
    console.log('[WebSocket] Received message:', JSON.stringify(message, null, 2));
    console.log('[WebSocket] voice_url present?', !!message.voice_url, message.voice_url);
    setMessages((prev) => {
      // Check if message already exists (avoid duplicates)
      if (prev.some((m) => m.id === message.id)) {
        return prev;
      }
      // Add new message and auto-scroll
      shouldAutoScrollRef.current = true;
      return [...prev, message];
    });
  }, []);

  // WebSocket connection
  const { sendMessage: wsSendMessage, sendRawMessage, isConnected } = useChatWebSocket({
    chatCode: code,
    sessionToken,
    onMessage: handleWebSocketMessage,
    enabled: hasJoined && !!sessionToken,
  });

  // Load session token from localStorage on mount and when joining
  useEffect(() => {
    const token = localStorage.getItem(`chat_session_${code}`);
    setSessionToken(token);
  }, [code, hasJoined]);

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

  // Load chat room details
  useEffect(() => {
    const loadChatRoom = async () => {
      try {
        const room = await chatApi.getChatByCode(code);
        setChatRoom(room);

        // Check if user is already logged in
        const token = localStorage.getItem('auth_token');
        let fpValue: string | undefined;

        console.log('=== Chat Session Debug Info ===');
        console.log('Logged In:', !!token);

        if (token) {
          try {
            const currentUser = await authApi.getCurrentUser();
            setCurrentUserId(currentUser.id);
            setHasReservedUsername(!!currentUser.reserved_username);

            // Get fingerprint for logged-in users too
            try {
              fpValue = await getFingerprint();
              setFingerprint(fpValue);
              console.log('Fingerprint:', fpValue);
            } catch (fpErr) {
              console.error('❌ Error getting fingerprint:', fpErr);
            }

            // Check ChatParticipation to see if they've joined before
            const participation = await chatApi.getMyParticipation(code, fpValue);

            // Store participation theme if present
            if (participation.theme) {
              setParticipationTheme(participation.theme);
            }

            if (participation.has_joined && participation.username) {
              // Returning user - use their locked username
              setUsername(participation.username);
              setHasJoinedBefore(true);
              setHasReservedUsername(participation.username_is_reserved || false);
              console.log('Username (from participation):', participation.username);
              console.log('Reserved Username Badge:', participation.username_is_reserved || false);
            } else {
              // First-time user - pre-fill with reserved_username (they can change it)
              setUsername(currentUser.reserved_username || '');
              setHasJoinedBefore(false);
              // Badge shows if they have a reserved username
              setHasReservedUsername(!!currentUser.reserved_username);
              console.log('Username (pre-filled from account):', currentUser.reserved_username || '(none)');
              console.log('Reserved Username Badge:', !!currentUser.reserved_username);
            }
          } catch (userErr) {
            // If getting user fails, just proceed as guest
            console.error('❌ Failed to load user:', userErr);
          }
        } else {
          // Anonymous user - check fingerprint participation
          try {
            fpValue = await getFingerprint();
            setFingerprint(fpValue);
            console.log('Fingerprint:', fpValue);
            const participation = await chatApi.getMyParticipation(code, fpValue);

            // Store participation theme if present
            if (participation.theme) {
              setParticipationTheme(participation.theme);
            }

            if (participation.has_joined && participation.username) {
              // Returning anonymous user
              setUsername(participation.username);
              setHasJoinedBefore(true);
              setHasReservedUsername(participation.username_is_reserved || false);
              console.log('Username (from participation):', participation.username);
              console.log('Reserved Username Badge:', participation.username_is_reserved || false);
            } else {
              // First-time anonymous user
              setHasJoinedBefore(false);
              setHasReservedUsername(false);
              console.log('Username: (not set - first time anonymous user)');
            }
          } catch (err) {
            console.error('❌ Error checking participation:', err);
            setHasJoinedBefore(false);
          }
        }

        console.log('==============================');

        // Always set hasJoined to false initially - user must join through modal
        setHasJoined(false);

        setLoading(false);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load chat room');
        setLoading(false);
      }
    };

    loadChatRoom();
  }, [code]);

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

          // Get fingerprint
          let fpValue: string | undefined;
          try {
            fpValue = await getFingerprint();
            setFingerprint(fpValue);
          } catch (fpErr) {
            console.warn('Failed to get fingerprint:', fpErr);
          }

          // Check if they've already joined this chat
          const participation = await chatApi.getMyParticipation(code, fpValue);

          // Store participation theme if present
          if (participation.theme) {
            setParticipationTheme(participation.theme);
          }

          if (participation.has_joined && participation.username) {
            // They already joined - update username and badge
            setUsername(participation.username);
            setHasJoinedBefore(true);
            setHasReservedUsername(participation.username_is_reserved || false);
          } else {
            // Not joined yet - pre-fill with reserved username
            setUsername(currentUser.reserved_username || '');
            setHasJoinedBefore(false);
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

  // Listen for back button to show join modal when user navigates back
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // If user is currently in chat and presses back, show join modal and reset state
      if (hasJoined) {
        setHasJoined(false);
        setMessages([]); // Clear messages to show fresh state
        setActiveView('main'); // Exit back room view if in there
        // Note: Settings sheet closes automatically via onClose handler
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [hasJoined]);

  // No theme switching - body background set in layout.tsx

  // Load Back Room data if it exists
  useEffect(() => {
    const loadBackRoom = async () => {
      if (!chatRoom?.has_back_room || !hasJoined) return;

      try {
        const backRoomData = await backRoomApi.getBackRoom(code);
        setBackRoom(backRoomData);

        // Host always has access; for non-hosts, we'll check via GameRoomView's permission handling
        const isHost = currentUserId && chatRoom.host.id === currentUserId;
        if (isHost) {
          setIsBackRoomMember(true);
        }
        // For non-hosts, membership will be determined when they try to view messages
      } catch (error) {
        console.error('Failed to load back room:', error);
      }
    };

    loadBackRoom();
  }, [chatRoom, hasJoined, code, currentUserId, username]);

  // Load messages
  const loadMessages = async () => {
    try {
      const msgs = await messageApi.getMessages(code);
      setMessages(msgs);
      setHasMoreMessages(true); // Reset when loading fresh messages

      // Wait for DOM to fully render before scrolling to bottom
      // This prevents race conditions on mobile/small viewports
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          shouldAutoScrollRef.current = true;
          scrollToBottom(); // Explicitly scroll after DOM is ready
        });
      });
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  // Load older messages for infinite scroll
  const loadOlderMessages = async () => {
    if (loadingOlder || !hasMoreMessages || messages.length === 0) return;

    const container = messagesContainerRef.current;
    if (!container) return;

    try {
      setLoadingOlder(true);

      // Save scroll position relative to current scroll height
      const previousScrollHeight = container.scrollHeight;
      const previousScrollTop = container.scrollTop;

      // Get the oldest message timestamp
      const oldestMessage = messages[0];
      const beforeTimestamp = new Date(oldestMessage.created_at).getTime() / 1000;

      // Fetch older messages
      const { messages: olderMessages, hasMore } = await messageApi.getMessagesBefore(code, beforeTimestamp, 50);

      if (olderMessages.length > 0) {
        // Prepend older messages
        setMessages(prev => [...olderMessages, ...prev]);

        // Use requestAnimationFrame to ensure DOM has updated
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            if (container) {
              // Calculate new scroll position to maintain visual position
              const newScrollHeight = container.scrollHeight;
              const heightDifference = newScrollHeight - previousScrollHeight;
              container.scrollTop = previousScrollTop + heightDifference;
            }
          });
        });
      }

      setHasMoreMessages(hasMore);
    } catch (err) {
      console.error('Failed to load older messages:', err);
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

      await chatApi.joinChat(code, username, accessCode, fingerprint);

      // Update session token immediately after joining
      const newSessionToken = localStorage.getItem(`chat_session_${code}`);
      setSessionToken(newSessionToken);

      const token = localStorage.getItem('auth_token');
      const isLoggedIn = !!token;
      await UsernameStorage.saveUsername(code, username, isLoggedIn);
      setUsername(username);
      setHasJoined(true);
      await loadMessages();

      // Add history entry so back button shows join modal again
      window.history.pushState({ joined: true }, '', window.location.href);

      // Play success sound to verify audio works after user gesture
      playJoinSound();
    } catch (err: any) {
      throw new Error(err.response?.data?.detail || 'Invalid access code');
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
      await chatApi.joinChat(code, username.trim(), accessCode || undefined);
      const token = localStorage.getItem('auth_token');
      const isLoggedIn = !!token;
      await UsernameStorage.saveUsername(code, username.trim(), isLoggedIn);
      setHasJoined(true);
      await loadMessages();
    } catch (err: any) {
      setJoinError(err.response?.data?.detail || 'Failed to join chat');
    }
  };

  // Send message
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();

    // If there's a voice recording ready, send it via the global method
    if (hasVoiceRecording && (window as any).__voiceRecorderSendMethod) {
      (window as any).__voiceRecorderSendMethod();
      return;
    }

    if (!newMessage.trim() || sending) return;

    setSending(true);
    try {
      // Send via WebSocket if connected, fallback to REST API
      if (isConnected && wsSendMessage) {
        wsSendMessage(newMessage.trim(), replyingTo?.id);
        setNewMessage('');
        shouldAutoScrollRef.current = true; // Always scroll when sending a message
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

        await messageApi.sendMessage(code, messageUsername, newMessage.trim());
        setNewMessage('');
        shouldAutoScrollRef.current = true;
        await loadMessages();
      }
    } catch (err: any) {
      console.error('Failed to send message:', err);
    } finally {
      setSending(false);
      setReplyingTo(null); // Clear reply state after sending (success or failure)
    }
  };

  // Handle voice message upload
  const handleVoiceRecording = async (audioBlob: Blob, metadata: RecordingMetadata) => {
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
      const { voice_url } = await messageApi.uploadVoiceMessage(code, audioBlob, messageUsername);

      console.log('[Voice Upload] Sending voice message with metadata:', {
        voice_url,
        duration: metadata.duration,
        waveformSamples: metadata.waveformData.length
      });

      // Send the voice message via WebSocket with metadata
      sendRawMessage({
        message: '', // Empty message text for voice-only messages
        voice_url: voice_url,
        voice_duration: metadata.duration,
        voice_waveform: metadata.waveformData,
        reply_to_id: replyingTo?.id, // Include reply context if replying
      });

      // Auto-scroll to show new message
      shouldAutoScrollRef.current = true;
    } catch (err: any) {
      console.error('Failed to upload voice message:', err);
      console.error('Error details:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status,
        stack: err.stack
      });
      const errorMsg = err.response?.data?.error || err.message || 'Unknown error occurred';
      alert(`Failed to send voice message: ${errorMsg}`);
    } finally {
      setSending(false);
      setReplyingTo(null); // Clear reply state after sending (success or failure)
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollToMessage = (messageId: string) => {
    const element = document.querySelector(`[data-message-id="${messageId}"]`);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // Add pulsating animation
      element.classList.add('animate-pulse-scale');
      setTimeout(() => {
        element.classList.remove('animate-pulse-scale');
      }, 2000);
    }
  };

  // Track if user is near bottom
  const shouldAutoScrollRef = useRef(true);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // Track which sticky messages are visible in scroll area
  const [visibleMessageIds, setVisibleMessageIds] = useState<Set<string>>(new Set());
  const [aboveViewportMessageIds, setAboveViewportMessageIds] = useState<Set<string>>(new Set());

  // Message action handlers (wrapped in useCallback to prevent re-renders)
  const handlePinSelf = useCallback((messageId: string) => {
    console.log('Pin self message:', messageId);
    // TODO: Implement pin self logic with payment
  }, []);

  const handlePinOther = useCallback((messageId: string) => {
    console.log('Pin other message:', messageId);
    // TODO: Implement pin other logic (host only)
  }, []);

  const handleReply = useCallback((message: Message) => {
    console.log('Replying to message:', message);
    setReplyingTo(message);
  }, []);

  const handleBlockUser = useCallback((username: string) => {
    console.log('Block user:', username);
    // TODO: Implement block user logic
  }, []);

  const handleTipUser = useCallback((username: string) => {
    console.log('Tip user:', username);
    // TODO: Implement tip user logic with payment
  }, []);

  // Filter messages based on mode
  const filteredMessages = filterMode === 'focus'
    ? messages.filter(msg => {
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
      })
    : messages;

  // Filter messages for sticky section (useMemo to prevent infinite loops)
  const allStickyHostMessages = useMemo(() => {
    return filteredMessages
      .filter(m => m.is_from_host)
      .slice(-1)  // Get 1 most recent
      .reverse(); // Show newest first
  }, [filteredMessages]);

  const topPinnedMessage = useMemo(() => {
    return filteredMessages
      .filter(m => m.is_pinned && !m.is_from_host)
      .sort((a, b) => parseFloat(b.pin_amount_paid) - parseFloat(a.pin_amount_paid))
      [0]; // Get highest paid
  }, [filteredMessages]);

  // Get IDs to observe (useMemo to prevent infinite loops)
  const idsToObserve = useMemo(() => {
    const hostIds = allStickyHostMessages.map(m => m.id);
    const pinnedId = topPinnedMessage?.id;
    const ids = [...hostIds];
    if (pinnedId) ids.push(pinnedId);
    return ids;
  }, [allStickyHostMessages, topPinnedMessage]);

  // Show the most recent host message that is above the viewport (scrolled past)
  const stickyHostMessages = useMemo(() => {
    // Get all host messages from filtered messages
    const hostMessages = filteredMessages.filter(m => m.is_from_host);

    // Find the most recent host message that is above the viewport
    const aboveViewportHosts = hostMessages
      .filter(m => aboveViewportMessageIds.has(m.id))
      .slice(-1); // Get the most recent one

    console.log(`[STICKY SELECTION] Total host messages: ${hostMessages.length}, Above viewport: ${aboveViewportMessageIds.size}, Selected sticky: ${aboveViewportHosts.length > 0 ? aboveViewportHosts[0].id.slice(0, 8) : 'NONE'}`);

    return aboveViewportHosts;
  }, [filteredMessages, aboveViewportMessageIds]);

  // Only show pinned in sticky if not visible in scroll area
  const stickyPinnedMessage = topPinnedMessage && !visibleMessageIds.has(topPinnedMessage.id) ? topPinnedMessage : null;

  // Check if user is scrolled near the bottom
  const checkIfNearBottom = () => {
    const container = messagesContainerRef.current;
    if (!container) return true;

    const threshold = 100; // pixels from bottom
    const position = container.scrollHeight - container.scrollTop - container.clientHeight;
    return position < threshold;
  };

  // Handle scroll events
  const handleScroll = () => {
    const wasAutoScroll = shouldAutoScrollRef.current;
    const nearBottom = checkIfNearBottom();

    // Only update shouldAutoScrollRef if:
    // 1. We're currently NOT auto-scrolling (user is manually scrolling), OR
    // 2. We're checking and we're still near bottom (maintain auto-scroll state)
    // This prevents the ref from being set to false when content is added while auto-scrolling
    if (!wasAutoScroll || nearBottom) {
      shouldAutoScrollRef.current = nearBottom;
    }

    if (wasAutoScroll !== shouldAutoScrollRef.current) {
      console.log(`[AUTO-SCROLL] Changed from ${wasAutoScroll} to ${shouldAutoScrollRef.current}`);
    }

    // Check if scrolled to top for infinite scroll
    // Don't trigger if we're trying to auto-scroll (during initial load) or if no messages loaded yet
    const container = messagesContainerRef.current;
    if (
      container &&
      container.scrollTop < 100 &&
      hasMoreMessages &&
      !loadingOlder &&
      messages.length > 0 &&
      !shouldAutoScrollRef.current
    ) {
      loadOlderMessages();
    }
  };

  // Only auto-scroll if user is near bottom
  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToBottom();
    }
  }, [messages.length]);

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

  // Scroll-based tracking to determine which messages should be in sticky area
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || filteredMessages.length === 0) return;

    let rafId: number | null = null;

    const handleScroll = () => {
      // Cancel any pending frame
      if (rafId) {
        cancelAnimationFrame(rafId);
      }

      // Use requestAnimationFrame for smoother updates
      rafId = requestAnimationFrame(() => {
        // Get the chat header element as our fixed reference point
        const chatHeader = document.querySelector('[data-chat-header]') as HTMLElement;
        let headerBottom = 0;

        if (chatHeader) {
          // Get the bottom edge of the header relative to container
          const headerRect = chatHeader.getBoundingClientRect();
          const containerRect = container.getBoundingClientRect();
          headerBottom = headerRect.bottom - containerRect.top;
        } else {
          // Fallback: estimate based on typical header size
          headerBottom = 60;
        }

        // Hysteresis buffer to prevent flickering at the boundary
        const ENTER_BUFFER = 20; // Message must be 20px past header to leave sticky
        const EXIT_BUFFER = 5;   // Message must be 5px above header to enter sticky

        // Update visible messages
        setVisibleMessageIds((prev) => {
          const newVisibleIds = new Set<string>();
          let hasChanges = false;

          // Check each message that should be observed
          idsToObserve.forEach((messageId) => {
            const messageElement = container.querySelector(`[data-message-id="${messageId}"]`);
            if (messageElement) {
              const rect = messageElement.getBoundingClientRect();
              const containerRect = container.getBoundingClientRect();
              const relativeTop = rect.top - containerRect.top;
              const messageBottom = relativeTop + messageElement.clientHeight;

              const wasVisible = prev.has(messageId);

              if (wasVisible) {
                // Message is currently visible in scroll - keep it visible unless it scrolls well past header
                // Use EXIT_BUFFER to prevent premature exit
                if (messageBottom > headerBottom - EXIT_BUFFER) {
                  newVisibleIds.add(messageId);
                }
              } else {
                // Message is currently in sticky - only make it visible if it scrolls well below header
                // Use ENTER_BUFFER to prevent premature entry
                if (messageBottom > headerBottom + ENTER_BUFFER) {
                  newVisibleIds.add(messageId);
                }
              }
            }
          });

          // Check if there are any changes
          if (newVisibleIds.size !== prev.size) {
            hasChanges = true;
          } else {
            newVisibleIds.forEach(id => {
              if (!prev.has(id)) {
                hasChanges = true;
              }
            });
          }

          return hasChanges ? newVisibleIds : prev;
        });

        // Update above-viewport messages (for host message sticky logic)
        setAboveViewportMessageIds((prev) => {
          const newAboveViewportIds = new Set<string>();
          let hasChanges = false;

          // Hysteresis thresholds for above-viewport detection (prevents jitter)
          const ABOVE_ENTER_THRESHOLD = 50; // Message must be 50px above header to enter set
          const ABOVE_EXIT_THRESHOLD = -20; // Message must be 20px below header to leave set

          // Get all host messages
          const allHostMessages = filteredMessages.filter(m => m.is_from_host);

          // Check each host message
          allHostMessages.forEach((message) => {
            const messageElement = container.querySelector(`[data-message-id="${message.id}"]`);
            if (messageElement) {
              const rect = messageElement.getBoundingClientRect();
              const containerRect = container.getBoundingClientRect();
              const relativeTop = rect.top - containerRect.top;
              const messageBottom = relativeTop + messageElement.clientHeight;

              const wasAboveViewport = prev.has(message.id);

              console.log(`[STICKY] Message ${message.id.slice(0, 8)}: bottom=${messageBottom.toFixed(0)}px, headerBottom=${headerBottom}, wasAbove=${wasAboveViewport}`);

              if (wasAboveViewport) {
                // Keep it in set unless it scrolls well below header
                if (messageBottom < headerBottom + ABOVE_EXIT_THRESHOLD) {
                  newAboveViewportIds.add(message.id);
                  console.log(`  ✓ Keeping in above-viewport set (exit threshold: ${headerBottom + ABOVE_EXIT_THRESHOLD})`);
                } else {
                  console.log(`  ✗ Removing from above-viewport set (past exit threshold)`);
                }
              } else {
                // Add to set only if it's well above header
                if (messageBottom < headerBottom - ABOVE_ENTER_THRESHOLD) {
                  newAboveViewportIds.add(message.id);
                  console.log(`  ✓ Adding to above-viewport set (enter threshold: ${headerBottom - ABOVE_ENTER_THRESHOLD})`);
                } else {
                  console.log(`  ✗ Not above viewport yet (enter threshold: ${headerBottom - ABOVE_ENTER_THRESHOLD})`);
                }
              }
            }
          });

          // Check if there are any changes
          if (newAboveViewportIds.size !== prev.size) {
            hasChanges = true;
          } else {
            newAboveViewportIds.forEach(id => {
              if (!prev.has(id)) {
                hasChanges = true;
              }
            });
          }

          return hasChanges ? newAboveViewportIds : prev;
        });
      });
    };

    // Initial check and add scroll listener
    handleScroll();
    container.addEventListener('scroll', handleScroll, { passive: true });

    return () => {
      if (rafId) {
        cancelAnimationFrame(rafId);
      }
      container.removeEventListener('scroll', handleScroll);
    };
  }, [filteredMessages.length, idsToObserve, activeView]);

  if (loading) {
    const currentDesign = convertThemeToCamelCase(participationTheme || chatRoom?.theme || defaultTheme);
    return (
      <div className={`${currentDesign.container} flex items-center justify-center`}>
        <div className="text-gray-600 dark:text-gray-400">Loading chat...</div>
      </div>
    );
  }

  if (error) {
    const currentDesign = convertThemeToCamelCase(participationTheme || chatRoom?.theme || defaultTheme);
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

  const currentDesign = convertThemeToCamelCase(participationTheme || chatRoom?.theme || defaultTheme);

  // Main chat interface
  return (
    <>
      {/* Join Modal - rendered when user hasn't joined and auth modal is not open */}
      {!hasJoined && chatRoom && !authMode && (
        <JoinChatModal
          chatRoom={chatRoom}
          currentUserDisplayName={username}
          hasJoinedBefore={hasJoinedBefore}
          isLoggedIn={!!currentUserId}
          hasReservedUsername={hasReservedUsername}
          themeIsDarkMode={themeIsDarkMode}
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
                onClick={() => {/* TODO: Add navigation */}}
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
            currentUserId={currentUserId}
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
            handlePinSelf={handlePinSelf}
            handlePinOther={handlePinOther}
            handleBlockUser={handleBlockUser}
            handleTipUser={handleTipUser}
            loadingOlder={loadingOlder}
          />
        )}

        {activeView === 'backroom' && hasJoined && (
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
        <div className={currentDesign.inputArea}>
          {/* Reply Preview Bar */}
          {replyingTo && (
            <div className={currentDesign.replyPreviewContainer}>
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <Reply className={currentDesign.replyPreviewIcon} />
                <div className="flex-1 min-w-0">
                  <div className={currentDesign.replyPreviewUsername}>
                    Replying to {replyingTo.username}
                  </div>
                  <div className={currentDesign.replyPreviewContent}>
                    {replyingTo.content}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setReplyingTo(null)}
                className={currentDesign.replyPreviewCloseButton}
                aria-label="Cancel reply"
              >
                <X className={currentDesign.replyPreviewCloseIcon} />
              </button>
            </div>
          )}
          <form onSubmit={handleSendMessage} className={`flex gap-2 ${replyingTo ? 'mt-2' : ''}`}>
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
            className={currentDesign.inputField}
            disabled={sending}
            style={{
              WebkitUserSelect: 'text',
              userSelect: 'text',
            }}
          />
          {chatRoom?.voice_enabled && (
            <VoiceRecorder
              onRecordingComplete={handleVoiceRecording}
              onRecordingReady={setHasVoiceRecording}
              disabled={sending || !hasJoined}
            />
          )}
          <button
            type="submit"
            disabled={sending || (!newMessage.trim() && !hasVoiceRecording)}
            className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
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
            console.log('🖱️ GameRoomTab clicked! Toggling from', activeView, 'to', activeView === 'backroom' ? 'main' : 'backroom');
            setActiveView(activeView === 'backroom' ? 'main' : 'backroom');
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
          onClick={() => setShowSettingsSheet(true)}
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
          onOpenChange={setShowSettingsSheet}
        >
          {/* Empty trigger - controlled by Settings button */}
          <div />
        </ChatSettingsSheet>
      )}
    </>
  );
}
