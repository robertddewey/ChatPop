'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { chatApi, messageApi, authApi, backRoomApi, type ChatRoom, type Message, type BackRoom } from '@/lib/api';
import Header from '@/components/Header';
import ChatSettingsSheet from '@/components/ChatSettingsSheet';
import BackRoomTab from '@/components/BackRoomTab';
import BackRoomView from '@/components/BackRoomView';
import MainChatView from '@/components/MainChatView';
import MessageActionsModal from '@/components/MessageActionsModal';
import JoinChatModal from '@/components/JoinChatModal';
import LoginModal from '@/components/LoginModal';
import RegisterModal from '@/components/RegisterModal';
import VoiceRecorder from '@/components/VoiceRecorder';
import VoiceMessagePlayer from '@/components/VoiceMessagePlayer';
import { UsernameStorage, getFingerprint } from '@/lib/usernameStorage';
import { playJoinSound } from '@/lib/sounds';
import { Settings, BadgeCheck, Crown } from 'lucide-react';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { type RecordingMetadata } from '@/lib/waveform';

// Design configuration (dark-mode only)
const design = {
  themeColor: {
    light: '#18181b',
    dark: '#18181b',
  },
  container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-zinc-950",
  header: "border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
  headerTitle: "text-lg font-bold text-zinc-100",
  headerTitleFade: "bg-gradient-to-l from-zinc-900 to-transparent",
  headerSubtitle: "text-sm text-zinc-400",
  stickySection: "absolute top-0 left-0 right-0 z-20 border-b border-zinc-800 bg-zinc-900/90 px-4 py-2 space-y-2 shadow-lg",
  messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-2",
  messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(180deg)_saturate(3)]",
  hostMessage: "max-w-[90%] rounded px-3 py-2 bg-cyan-400 font-medium transition-all duration-300",
  stickyHostMessage: "w-full rounded px-3 py-2 bg-cyan-400 font-medium transition-all duration-300",
  hostText: "text-cyan-950",
  hostMessageFade: "bg-gradient-to-l from-cyan-400 to-transparent",
  pinnedMessage: "max-w-[90%] rounded px-3 py-2 bg-yellow-400 font-medium transition-all duration-300",
  stickyPinnedMessage: "w-full rounded px-3 py-2 bg-yellow-400 font-medium transition-all duration-300",
  pinnedText: "text-yellow-950",
  pinnedMessageFade: "bg-gradient-to-l from-yellow-400 to-transparent",
  regularMessage: "max-w-[90%] rounded px-3 py-2 bg-zinc-800 border-l-2 border-cyan-500/50",
  regularText: "text-zinc-100",
  filterButtonActive: "px-3 py-1.5 rounded text-xs tracking-wider bg-cyan-400 text-cyan-950 border border-cyan-300",
  filterButtonInactive: "px-3 py-1.5 rounded text-xs tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700",
  inputArea: "border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
  inputField: "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-cyan-400 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500",
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

  // Join state for guests
  const [hasJoined, setHasJoined] = useState(false);
  const [hasJoinedBefore, setHasJoinedBefore] = useState(false);
  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [joinError, setJoinError] = useState('');

  // Message input
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [hasVoiceRecording, setHasVoiceRecording] = useState(false);

  // Message filter
  const [filterMode, setFilterMode] = useState<'all' | 'focus'>('all');

  // View state - supports multiple feature views
  type ViewType = 'main' | 'backroom';
  const [activeView, setActiveView] = useState<ViewType>('main');
  const [backRoom, setBackRoom] = useState<BackRoom | null>(null);
  const [isBackRoomMember, setIsBackRoomMember] = useState(false);

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
        let fingerprint: string | undefined;

        console.log('=== Chat Session Debug Info ===');
        console.log('Logged In:', !!token);

        if (token) {
          try {
            const currentUser = await authApi.getCurrentUser();
            setCurrentUserId(currentUser.id);
            setHasReservedUsername(!!currentUser.reserved_username);

            // Get fingerprint for logged-in users too
            try {
              fingerprint = await getFingerprint();
              console.log('Fingerprint:', fingerprint);
            } catch (fpErr) {
              console.error('❌ Error getting fingerprint:', fpErr);
            }

            // Check ChatParticipation to see if they've joined before
            const participation = await chatApi.getMyParticipation(code, fingerprint);

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
            fingerprint = await getFingerprint();
            console.log('Fingerprint:', fingerprint);
            const participation = await chatApi.getMyParticipation(code, fingerprint);

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
          let fingerprint: string | undefined;
          try {
            fingerprint = await getFingerprint();
          } catch (fpErr) {
            console.warn('Failed to get fingerprint:', fpErr);
          }

          // Check if they've already joined this chat
          const participation = await chatApi.getMyParticipation(code, fingerprint);
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

        // Host always has access; for non-hosts, we'll check via BackRoomView's permission handling
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
    } catch (err) {
      console.error('Failed to load messages:', err);
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
        wsSendMessage(newMessage.trim());
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

  // Message action handlers (placeholders for now)
  const handlePinSelf = (messageId: string) => {
    console.log('Pin self message:', messageId);
    // TODO: Implement pin self logic with payment
  };

  const handlePinOther = (messageId: string) => {
    console.log('Pin other message:', messageId);
    // TODO: Implement pin other logic (host only)
  };

  const handleBlockUser = (username: string) => {
    console.log('Block user:', username);
    // TODO: Implement block user logic
  };

  const handleTipUser = (username: string) => {
    console.log('Tip user:', username);
    // TODO: Implement tip user logic with payment
  };

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

  // Only show in sticky if not visible in scroll area
  const stickyHostMessages = allStickyHostMessages.filter(m => !visibleMessageIds.has(m.id));

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
    shouldAutoScrollRef.current = checkIfNearBottom();
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
        setVisibleMessageIds((prev) => {
          const newVisibleIds = new Set<string>();
          let hasChanges = false;

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
    const currentDesign = design;
    return (
      <div className={`${currentDesign.container} flex items-center justify-center`}>
        <div className="text-gray-600 dark:text-gray-400">Loading chat...</div>
      </div>
    );
  }

  if (error) {
    const currentDesign = design;
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

  const currentDesign = design;

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
          design={'dark-mode'}
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
            <ChatSettingsSheet
              key={hasJoined ? 'joined' : 'not-joined'}
              chatRoom={chatRoom}
              currentUserId={currentUserId}
              onUpdate={(updatedRoom) => setChatRoom(updatedRoom)}
              design={'dark-mode'}
            >
              <div className="flex-1 min-w-0 flex items-center gap-2 cursor-pointer hover:opacity-70 transition-opacity">
                <Settings className={`${currentDesign.headerTitle} flex-shrink-0`} size={18} />
                <h1 className={`${currentDesign.headerTitle} truncate`}>
                  {chatRoom.name}
                </h1>
              </div>
            </ChatSettingsSheet>
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
            <Crown size={16} />
            VIP
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
            backRoom={backRoom}
            handleScroll={handleScroll}
            scrollToMessage={scrollToMessage}
            handlePinSelf={handlePinSelf}
            handlePinOther={handlePinOther}
            handleBlockUser={handleBlockUser}
            handleTipUser={handleTipUser}
          />
        )}

        {activeView === 'backroom' && hasJoined && chatRoom?.has_back_room && backRoom && (
          <BackRoomView
            chatRoom={chatRoom}
            backRoom={backRoom}
            username={username}
            currentUserId={currentUserId}
            isMember={isBackRoomMember}
            onBack={() => setActiveView('main')}
            design={'dark-mode'}
          />
        )}
      </div>

      {/* Message Input - Only show in main chat view */}
      {activeView === 'main' && (
        <div className={currentDesign.inputArea}>
          <form onSubmit={handleSendMessage} className="flex gap-2">
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

      {/* Back Room Tab - only show when user has joined */}
      {hasJoined && chatRoom?.has_back_room && backRoom && (
        <BackRoomTab
          isInBackRoom={activeView === 'backroom'}
          hasBackRoom={true}
          onClick={() => {
            console.log('🖱️ BackRoomTab clicked! Toggling from', activeView, 'to', activeView === 'backroom' ? 'main' : 'backroom');
            setActiveView(activeView === 'backroom' ? 'main' : 'backroom');
          }}
          hasNewMessages={false}
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
    </>
  );
}
