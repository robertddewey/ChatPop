'use client';

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { chatApi, messageApi, authApi, backRoomApi, type ChatRoom, type Message, type BackRoom } from '@/lib/api';
import Header from '@/components/Header';
import ChatSettingsSheet from '@/components/ChatSettingsSheet';
import BackRoomTab from '@/components/BackRoomTab';
import BackRoomView from '@/components/BackRoomView';
import MessageActionsModal from '@/components/MessageActionsModal';
import JoinChatModal from '@/components/JoinChatModal';
import LoginModal from '@/components/LoginModal';
import RegisterModal from '@/components/RegisterModal';
import VoiceRecorder from '@/components/VoiceRecorder';
import VoiceMessagePlayer from '@/components/VoiceMessagePlayer';
import { UsernameStorage, getFingerprint } from '@/lib/usernameStorage';
import { playJoinSound } from '@/lib/sounds';
import { Settings, BadgeCheck } from 'lucide-react';
import { useChatWebSocket } from '@/hooks/useChatWebSocket';
import { type RecordingMetadata } from '@/lib/waveform';

// Design configurations
const designs = {
  'pink-dream': {
    themeColor: {
      light: '#fce7f3',
      dark: '#1e1b4b',
    },
    container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-pink-50 dark:bg-indigo-950",
    header: "border-b border-pink-200 dark:border-indigo-800 bg-pink-100/80 dark:bg-indigo-900/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
    headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
    headerTitleFade: "bg-gradient-to-l from-pink-100/80 via-pink-100/60 dark:from-indigo-900/80 dark:via-indigo-900/60 to-pink-100/0 dark:to-indigo-900/0",
    headerSubtitle: "text-sm text-gray-600 dark:text-gray-300",
    stickySection: "absolute top-0 left-0 right-0 z-20 border-b border-pink-200 dark:border-indigo-800 bg-pink-100/80 dark:bg-indigo-900/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
    messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3",
    messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.04] [filter:sepia(1)_hue-rotate(310deg)_saturate(3)]",
    hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-pink-500 via-rose-500 to-red-500 text-white shadow-lg border-2 border-white/20 dark:border-pink-400/20",
    hostText: "text-white",
    hostMessageFade: "bg-gradient-to-l from-red-500 to-transparent",
    pinnedMessage: "rounded-2xl px-5 py-3 bg-pink-200 dark:bg-gradient-to-r dark:from-rose-900/50 dark:to-pink-900/50 border border-pink-500 dark:border-pink-500",
    pinnedText: "text-rose-900 dark:text-rose-200",
    pinnedMessageFade: "bg-gradient-to-l from-pink-200 dark:from-rose-900/50 to-transparent",
    regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-indigo-900/90 backdrop-blur-sm border border-pink-100 dark:border-indigo-700 shadow-sm",
    regularText: "text-gray-700 dark:text-gray-200",
    filterButtonActive: "px-4 py-2 rounded-full text-xs bg-gradient-to-r from-pink-500 to-rose-500 text-white shadow-lg border-2 border-white/30 dark:border-pink-400/30",
    filterButtonInactive: "px-4 py-2 rounded-full text-xs bg-white/70 dark:bg-indigo-800/70 text-black dark:text-white backdrop-blur-sm border-2 border-pink-200 dark:border-indigo-700",
    inputArea: "border-t border-pink-200 dark:border-indigo-800 bg-pink-50 dark:bg-indigo-950 px-4 py-3 flex-shrink-0",
    inputField: "flex-1 px-4 py-2 border border-pink-300 dark:border-indigo-700 rounded-lg focus:ring-2 focus:ring-pink-500 dark:focus:ring-pink-400 focus:border-transparent bg-white dark:bg-indigo-800 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-400",
  },
  'ocean-blue': {
    themeColor: {
      light: '#ffffff',
      dark: '#1f2937',
    },
    container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-gradient-to-br from-sky-50 via-blue-50 to-cyan-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-cyan-900/20",
    header: "border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
    headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
    headerTitleFade: "bg-gradient-to-l from-white/80 via-white/60 dark:from-gray-800/80 dark:via-gray-800/60 to-white/0 dark:to-gray-800/0",
    headerSubtitle: "text-sm text-gray-500 dark:text-gray-400",
    stickySection: "absolute top-0 left-0 right-0 z-20 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
    messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3",
    messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.04] [filter:sepia(1)_hue-rotate(180deg)_saturate(3)]",
    hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500 text-white shadow-lg border-2 border-white/20",
    hostText: "text-white",
    hostMessageFade: "bg-gradient-to-l from-cyan-500 to-transparent",
    pinnedMessage: "rounded-2xl px-5 py-3 bg-cyan-200 dark:bg-gradient-to-r dark:from-cyan-900/50 dark:to-blue-900/50 border border-cyan-500 dark:border-cyan-400",
    pinnedText: "text-cyan-900 dark:text-cyan-200",
    pinnedMessageFade: "bg-gradient-to-l from-cyan-200 dark:from-cyan-900/50 to-transparent",
    regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-blue-100 dark:border-blue-800 shadow-sm",
    regularText: "text-gray-700 dark:text-gray-300",
    filterButtonActive: "px-4 py-2 rounded-full text-xs bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg border-2 border-white/30",
    filterButtonInactive: "px-4 py-2 rounded-full text-xs bg-white/70 dark:bg-gray-700/70 text-black dark:text-white backdrop-blur-sm border-2 border-blue-200 dark:border-blue-700",
    inputArea: "border-t border-gray-200 dark:border-gray-700 bg-sky-50 dark:bg-gray-900 px-4 py-3 flex-shrink-0",
    inputField: "flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-700 text-gray-900 dark:text-white",
  },
  'dark-mode': {
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
    hostMessage: "rounded px-3 py-2 bg-cyan-400 font-medium",
    hostText: "text-cyan-950",
    hostMessageFade: "bg-gradient-to-l from-cyan-400 to-transparent",
    pinnedMessage: "rounded px-3 py-2 bg-yellow-400 font-medium",
    pinnedText: "text-yellow-950",
    pinnedMessageFade: "bg-gradient-to-l from-yellow-400 to-transparent",
    regularMessage: "max-w-[85%] rounded px-3 py-2 bg-zinc-800 border-l-2 border-cyan-500/50",
    regularText: "text-zinc-100",
    filterButtonActive: "px-3 py-1.5 rounded text-xs tracking-wider bg-cyan-400 text-cyan-950 border border-cyan-300",
    filterButtonInactive: "px-3 py-1.5 rounded text-xs tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700",
    inputArea: "border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
    inputField: "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-cyan-400 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500",
  },
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

  // Theme state with hierarchy: URL > localStorage > host default > system default
  // Initialize from URL parameter only (available on both server and client)
  const urlTheme = searchParams.get('design');
  const initialTheme = (urlTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(urlTheme))
    ? (urlTheme as 'pink-dream' | 'ocean-blue' | 'dark-mode')
    : 'pink-dream';

  const [designVariant, setDesignVariant] = useState<'pink-dream' | 'ocean-blue' | 'dark-mode'>(initialTheme);

  // After hydration, check localStorage and update if needed
  useEffect(() => {
    // Only run on client after hydration
    if (!urlTheme) {
      const localTheme = localStorage.getItem(`chatpop_theme_${code}`);
      if (localTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(localTheme)) {
        setDesignVariant(localTheme as 'pink-dream' | 'ocean-blue' | 'dark-mode');
      }
    }
  }, []); // Run once after mount

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

  // Back Room state
  const [isInBackRoom, setIsInBackRoom] = useState(false);
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
  }, [filterMode, isInBackRoom]);

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
        setIsInBackRoom(false); // Exit back room view if in there
        // Note: Settings sheet closes automatically via onClose handler
      }
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [hasJoined]);

  // Determine theme based on hierarchy: URL param > localStorage > host default > system default
  useEffect(() => {
    if (!chatRoom) return;

    const determineTheme = (): 'pink-dream' | 'ocean-blue' | 'dark-mode' => {
      // If theme is locked by host, use host's default theme
      if (chatRoom.theme_locked) {
        return (chatRoom.default_theme as 'pink-dream' | 'ocean-blue' | 'dark-mode') || 'pink-dream';
      }

      // Check URL parameter first (from searchParams hook)
      const urlTheme = searchParams.get('design');
      if (urlTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(urlTheme)) {
        return urlTheme as 'pink-dream' | 'ocean-blue' | 'dark-mode';
      }

      // Check localStorage for user preference
      if (typeof window !== 'undefined') {
        const localTheme = localStorage.getItem(`chatpop_theme_${code}`);
        if (localTheme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(localTheme)) {
          return localTheme as 'pink-dream' | 'ocean-blue' | 'dark-mode';
        }
      }

      // Use host's default theme
      if (chatRoom.default_theme && ['pink-dream', 'ocean-blue', 'dark-mode'].includes(chatRoom.default_theme)) {
        return chatRoom.default_theme as 'pink-dream' | 'ocean-blue' | 'dark-mode';
      }

      // Fall back to system default
      return 'pink-dream';
    };

    const theme = determineTheme();
    setDesignVariant(theme);

    // Save to localStorage if not locked (so it persists for next visit)
    if (!chatRoom.theme_locked && typeof window !== 'undefined') {
      localStorage.setItem(`chatpop_theme_${code}`, theme);
    }
  }, [chatRoom, code, searchParams]);

  // Update body background when theme changes
  // Theme-color meta tags are set in layout.tsx before page loads
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const currentThemeDesign = designs[designVariant as keyof typeof designs];
    if (!currentThemeDesign?.themeColor) return;

    // Detect system dark mode preference
    const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const themeColor = isDarkMode ? currentThemeDesign.themeColor.dark : currentThemeDesign.themeColor.light;

    // Update body background (iOS Safari derives tint from topmost background at scroll edge)
    document.body.style.backgroundColor = themeColor;
  }, [designVariant]);

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

  // IntersectionObserver to track when sticky host messages are visible in scroll
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container || filteredMessages.length === 0) return;

    // Check if we're scrolled to the very top
    const checkScrollPosition = () => {
      if (!container) return;
      const isAtTop = container.scrollTop <= 50; // Within 50px of top

      if (isAtTop && idsToObserve.length > 0) {
        // When at top, mark all messages as visible
        setVisibleMessageIds((prev) => {
          const newSet = new Set(prev);
          let hasChanges = false;
          idsToObserve.forEach(id => {
            if (!newSet.has(id)) {
              newSet.add(id);
              hasChanges = true;
            }
          });
          return hasChanges ? newSet : prev;
        });
      }
    };

    const observer = new IntersectionObserver(
      (entries) => {
        setVisibleMessageIds((prev) => {
          const newVisibleIds = new Set(prev);
          let hasChanges = false;
          entries.forEach((entry) => {
            const messageId = entry.target.getAttribute('data-message-id');
            if (messageId) {
              if (entry.isIntersecting) {
                if (!newVisibleIds.has(messageId)) {
                  newVisibleIds.add(messageId);
                  hasChanges = true;
                }
              } else {
                // Only remove if we're not at the top (prevent overscroll issues)
                if (container.scrollTop > 50 && newVisibleIds.has(messageId)) {
                  newVisibleIds.delete(messageId);
                  hasChanges = true;
                }
              }
            }
          });
          return hasChanges ? newVisibleIds : prev;
        });
      },
      {
        root: container,
        threshold: 0.1, // Message must be 10% visible (more sensitive)
        rootMargin: '0px',
      }
    );

    // Check scroll position initially and on scroll
    checkScrollPosition();
    container.addEventListener('scroll', checkScrollPosition);

    // Observe all sticky host messages and pinned messages in the scroll area
    const messageElements = container.querySelectorAll('[data-message-id]');
    messageElements.forEach((el) => {
      const messageId = el.getAttribute('data-message-id');
      if (messageId && idsToObserve.includes(messageId)) {
        observer.observe(el);
      }
    });

    return () => {
      observer.disconnect();
      container.removeEventListener('scroll', checkScrollPosition);
    };
  }, [filteredMessages.length, idsToObserve]);

  if (loading) {
    const currentDesign = designs[designVariant as keyof typeof designs] || designs['pink-dream'];
    return (
      <div className={`${currentDesign.container} flex items-center justify-center`}>
        <div className="text-gray-600 dark:text-gray-400">Loading chat...</div>
      </div>
    );
  }

  if (error) {
    const currentDesign = designs[designVariant as keyof typeof designs] || designs['pink-dream'];
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

  const currentDesign = designs[designVariant as keyof typeof designs] || designs['pink-dream'];

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
          design={designVariant as 'pink-dream' | 'ocean-blue' | 'dark-mode'}
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
        <div className={currentDesign.header}>
        <div className="flex items-center justify-between gap-3">
          {chatRoom && (
            <ChatSettingsSheet
              key={hasJoined ? 'joined' : 'not-joined'}
              chatRoom={chatRoom}
              currentUserId={currentUserId}
              onUpdate={(updatedRoom) => setChatRoom(updatedRoom)}
              onThemeChange={(theme) => setDesignVariant(theme)}
              design={designVariant as 'pink-dream' | 'ocean-blue' | 'dark-mode'}
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
            className={`transition-all whitespace-nowrap ${
              filterMode === 'focus'
                ? currentDesign.filterButtonActive
                : currentDesign.filterButtonInactive
            }`}
          >
            Focus
          </button>
        </div>
      </div>

      {/* Content Area Wrapper - Contains both Main Chat and Back Room */}
      <div className="flex-1 relative overflow-hidden">
        {!isInBackRoom ? (
          /* Main Chat Content */
          <div className="h-full overflow-hidden relative">
        {/* Sticky Section: Host + Pinned Messages - Absolutely positioned overlay */}
        {hasJoined && (stickyHostMessages.length > 0 || stickyPinnedMessage) && (
          <div className={currentDesign.stickySection}>
            {/* Host Messages */}
            {stickyHostMessages.map((message) => (
              <MessageActionsModal
                key={`sticky-${message.id}`}
                message={message}
                currentUsername={username}
                isHost={chatRoom?.host.id === currentUserId}
                design={designVariant as 'pink-dream' | 'ocean-blue' | 'dark-mode'}
                onPinSelf={handlePinSelf}
                onPinOther={handlePinOther}
                onBlock={handleBlockUser}
                onTip={handleTipUser}
              >
                <div
                  className={`${currentDesign.hostMessage} cursor-pointer hover:opacity-90 transition-opacity`}
                  onClick={() => scrollToMessage(message.id)}
                >
                  <div className="flex items-center gap-1 mb-1">
                    <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                      {message.username}
                    </span>
                    {message.username_is_reserved && (
                      <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                    )}
                    <span className={`text-sm ${currentDesign.hostText} opacity-80`}>
                      👑
                    </span>
                    <span className={`text-xs ${currentDesign.hostText} opacity-60 ml-auto`}>
                      {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className={`text-sm ${currentDesign.hostText} truncate`}>
                    {message.content}
                  </p>
                </div>
              </MessageActionsModal>
            ))}

            {/* Pinned Message */}
            {stickyPinnedMessage && (
              <MessageActionsModal
                message={stickyPinnedMessage}
                currentUsername={username}
                isHost={chatRoom?.host.id === currentUserId}
                design={designVariant as 'pink-dream' | 'ocean-blue' | 'dark-mode'}
                onPinSelf={handlePinSelf}
                onPinOther={handlePinOther}
                onBlock={handleBlockUser}
                onTip={handleTipUser}
              >
                <div
                  className={`${currentDesign.pinnedMessage} cursor-pointer hover:opacity-90 transition-opacity`}
                  onClick={() => scrollToMessage(stickyPinnedMessage.id)}
                >
                  <div className="flex items-center gap-1 mb-1">
                    <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                      {stickyPinnedMessage.username}
                    </span>
                    {stickyPinnedMessage.username_is_reserved && (
                      <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                    )}
                    <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                      📌 ${stickyPinnedMessage.pin_amount_paid}
                    </span>
                    <span className={`text-xs ${currentDesign.pinnedText} opacity-60 ml-auto`}>
                      {new Date(stickyPinnedMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className={`text-sm ${currentDesign.pinnedText} truncate`}>
                    {stickyPinnedMessage.content}
                  </p>
                </div>
              </MessageActionsModal>
            )}
          </div>
        )}

      {/* Background Pattern Layer - Fixed behind everything */}
      <div className={`absolute inset-0 pointer-events-none ${currentDesign.messagesAreaBg}`} />

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className={`${currentDesign.messagesArea} ${chatRoom?.has_back_room && backRoom ? 'pr-12' : ''}`}
      >
        {/* Add padding-top when sticky messages are present to avoid overlap */}
        <div className={`space-y-3 relative z-10 ${(stickyHostMessages.length > 0 || stickyPinnedMessage) ? 'pt-4' : ''}`}>
        {hasJoined && filteredMessages.map((message, index) => {
          const prevMessage = index > 0 ? filteredMessages[index - 1] : null;

          // Time-based threading: break thread if >5 minutes gap
          // TODO: Make this dynamic based on chat velocity when WebSockets are implemented
          const THREAD_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
          const timeDiff = prevMessage ?
            new Date(message.created_at).getTime() - new Date(prevMessage.created_at).getTime() :
            Infinity;

          const isFirstInThread = !prevMessage ||
            prevMessage.username !== message.username ||
            prevMessage.is_from_host ||
            message.is_from_host ||
            message.is_pinned ||
            timeDiff > THREAD_WINDOW_MS;

          const nextMessage = index < filteredMessages.length - 1 ? filteredMessages[index + 1] : null;
          const nextTimeDiff = nextMessage ?
            new Date(nextMessage.created_at).getTime() - new Date(message.created_at).getTime() :
            Infinity;

          const isLastInThread = !nextMessage ||
            nextMessage.username !== message.username ||
            nextMessage.is_from_host ||
            message.is_from_host ||
            message.is_pinned ||
            nextTimeDiff > THREAD_WINDOW_MS;

          // Find the last message in this thread to get its timestamp
          let lastMessageInThread = message;
          if (isFirstInThread && !isLastInThread && !message.is_from_host && !message.is_pinned) {
            for (let i = index + 1; i < filteredMessages.length; i++) {
              const futureMsg = filteredMessages[i];
              const futureMsgTimeDiff = new Date(futureMsg.created_at).getTime() - new Date(lastMessageInThread.created_at).getTime();

              if (futureMsg.username === message.username &&
                  !futureMsg.is_from_host &&
                  !futureMsg.is_pinned &&
                  futureMsgTimeDiff <= THREAD_WINDOW_MS) {
                lastMessageInThread = futureMsg;
              } else {
                break;
              }
            }
          }

          return (
            <div key={message.id} data-message-id={message.id}>
              {/* Show username header for first message in thread */}
              {isFirstInThread && !message.is_from_host && !message.is_pinned && (
                <div className={`text-xs mb-1 flex items-center gap-1 ${designVariant === 'dark-mode' ? 'text-red-500' : 'text-gray-700 dark:text-zinc-100'}`}>
                  <span className="font-semibold">
                    {message.username}
                  </span>
                  {message.username_is_reserved && (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                  )}
                  <span className="opacity-80">
                    {new Date(lastMessageInThread.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>
              )}

              {/* Message with threading line */}
              <div className="flex gap-0">
                {/* Vertical thread line for consecutive messages */}
                {!isFirstInThread && !message.is_from_host && !message.is_pinned && (
                  <div className="w-0.5 mr-2 bg-gray-400 dark:bg-gray-600 opacity-30"></div>
                )}

                {/* Message bubble with action modal */}
                <MessageActionsModal
                  message={message}
                  currentUsername={username}
                  isHost={chatRoom?.host.id === currentUserId}
                  design={designVariant as 'pink-dream' | 'ocean-blue' | 'dark-mode'}
                  onPinSelf={handlePinSelf}
                  onPinOther={handlePinOther}
                  onBlock={handleBlockUser}
                  onTip={handleTipUser}
                >
                  <div
                    className={
                      message.is_from_host
                        ? currentDesign.hostMessage + ' flex-1'
                        : message.is_pinned
                        ? currentDesign.pinnedMessage
                        : currentDesign.regularMessage
                    }
                  >
                    {/* Host message header */}
                    {message.is_from_host && (
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1">
                          <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                            {message.username}
                          </span>
                          {message.username_is_reserved && (
                            <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                          )}
                          <span className={`text-sm ${currentDesign.hostText} opacity-80`}>
                            👑
                          </span>
                        </div>
                        <span className={`text-xs ${currentDesign.hostText} opacity-60`}>
                          {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </div>
                    )}

                    {/* Pinned message header */}
                    {message.is_pinned && !message.is_from_host && (
                      <div className="flex items-center justify-between mb-1 gap-3">
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                            {message.username}
                          </span>
                          {message.username_is_reserved && (
                            <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                          )}
                          <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                            📌 ${message.pin_amount_paid}
                          </span>
                        </div>
                        <span className={`text-xs ${currentDesign.pinnedText} opacity-60 ml-auto`}>
                          {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </div>
                    )}

                    {/* Message content */}
                    {message.voice_url ? (
                      <div className="-mt-px">
                        <VoiceMessagePlayer
                          voiceUrl={`${message.voice_url}${message.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                          duration={message.voice_duration || 0}
                          waveformData={message.voice_waveform || []}
                        />
                      </div>
                    ) : message.content ? (
                      <p className={`text-sm ${message.is_from_host ? currentDesign.hostText : message.is_pinned ? currentDesign.pinnedText : currentDesign.regularText}`}>
                        {message.content}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-500 italic">
                        [Voice message - loading...]
                        <br />
                        <small>Debug: voice_url={JSON.stringify(message.voice_url)}, id={message.id}</small>
                      </p>
                    )}
                  </div>
                </MessageActionsModal>
              </div>

            </div>
          );
        })}
        <div ref={messagesEndRef} />
        </div>
      </div>
      </div>
        ) : hasJoined && chatRoom?.has_back_room && backRoom ? (
          /* Back Room View - only when joined */
          <BackRoomView
            chatRoom={chatRoom}
            backRoom={backRoom}
            username={username}
            currentUserId={currentUserId}
            isMember={isBackRoomMember}
            onBack={() => setIsInBackRoom(false)}
            design={designVariant}
          />
        ) : null}
      </div>

      {/* Message Input */}
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

      {/* Back Room Tab - only show when user has joined */}
      {hasJoined && chatRoom?.has_back_room && backRoom && (
        <BackRoomTab
          isInBackRoom={isInBackRoom}
          hasBackRoom={true}
          onClick={() => {
            console.log('🖱️ BackRoomTab clicked! Toggling from', isInBackRoom, 'to', !isInBackRoom);
            setIsInBackRoom(!isInBackRoom);
          }}
          hasNewMessages={false}
          design={designVariant}
        />
      )}
      </div>

      {/* Auth Modals */}
      {authMode === 'login' && (
        <LoginModal
          onClose={closeModal}
          theme="chat"
          chatTheme={designVariant}
        />
      )}
      {authMode === 'register' && (
        <RegisterModal
          onClose={closeModal}
          theme="chat"
          chatTheme={designVariant}
        />
      )}
    </>
  );
}
