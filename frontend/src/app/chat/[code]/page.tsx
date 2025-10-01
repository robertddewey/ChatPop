'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { chatApi, messageApi, authApi, type ChatRoom, type Message } from '@/lib/api';
import Header from '@/components/Header';
import { UsernameStorage } from '@/lib/usernameStorage';

export default function ChatPage() {
  const params = useParams();
  const code = params.code as string;

  // Get design variant from URL query params
  const [searchParams] = useState(() => {
    if (typeof window !== 'undefined') {
      return new URLSearchParams(window.location.search);
    }
    return new URLSearchParams();
  });
  const designVariant = searchParams.get('design') || 'design1';

  const [chatRoom, setChatRoom] = useState<ChatRoom | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Join state for guests
  const [hasJoined, setHasJoined] = useState(false);
  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [joinError, setJoinError] = useState('');

  // Message input
  const [newMessage, setNewMessage] = useState('');
  const [sending, setSending] = useState(false);

  // Message filter
  const [filterMode, setFilterMode] = useState<'all' | 'focus'>('all');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom when filter mode changes
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
  }, [filterMode]);

  // Load chat room details
  useEffect(() => {
    const loadChatRoom = async () => {
      try {
        const room = await chatApi.getChatByCode(code);
        setChatRoom(room);

        // Check if user is already logged in
        const token = localStorage.getItem('auth_token');
        let isLoggedIn = false;

        if (token) {
          try {
            const currentUser = await authApi.getCurrentUser();
            isLoggedIn = true;
            const displayUsername = currentUser.display_name || currentUser.email.split('@')[0];
            setUsername(displayUsername);
            await UsernameStorage.saveUsername(code, displayUsername, true); // Skip fingerprinting for logged-in users
            setHasJoined(true);
            await loadMessages();
          } catch (userErr) {
            // If getting user fails, just proceed as guest
            console.error('Failed to load user:', userErr);
          }
        }

        // If not logged in, try to get username from storage (including fingerprint)
        if (!isLoggedIn) {
          const storedUsername = await UsernameStorage.getUsername(code, false);
          if (storedUsername) {
            setUsername(storedUsername);
            setHasJoined(true);
            await loadMessages();
          }
        }

        setLoading(false);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load chat room');
        setLoading(false);
      }
    };

    loadChatRoom();
  }, [code]);

  // Load messages
  const loadMessages = async () => {
    try {
      const msgs = await messageApi.getMessages(code);
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load messages:', err);
    }
  };

  // Join as guest
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
    if (!newMessage.trim() || sending) return;

    setSending(true);
    try {
      // Use current username from state (already loaded via UsernameStorage)
      let messageUsername = username;

      // If no username, try to get from storage
      if (!messageUsername) {
        const token = localStorage.getItem('auth_token');
        const isLoggedIn = !!token;
        messageUsername = (await UsernameStorage.getUsername(code, isLoggedIn)) || '';
      }

      // If still no username and logged in, use email or display name
      if (!messageUsername && chatRoom) {
        const token = localStorage.getItem('auth_token');
        if (token) {
          messageUsername = chatRoom.host.display_name || chatRoom.host.email.split('@')[0];
        }
      }

      if (!messageUsername) {
        console.error('No username available');
        return;
      }

      await messageApi.sendMessage(code, messageUsername, newMessage.trim());
      setNewMessage('');
      shouldAutoScrollRef.current = true; // Always scroll when sending a message
      await loadMessages();
    } catch (err: any) {
      console.error('Failed to send message:', err);
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
  const allStickyHostMessages = React.useMemo(() => {
    return filteredMessages
      .filter(m => m.is_from_host)
      .slice(-1)  // Get 1 most recent
      .reverse(); // Show newest first
  }, [filteredMessages]);

  const topPinnedMessage = React.useMemo(() => {
    return filteredMessages
      .filter(m => m.is_pinned && !m.is_from_host)
      .sort((a, b) => parseFloat(b.pin_amount_paid) - parseFloat(a.pin_amount_paid))
      [0]; // Get highest paid
  }, [filteredMessages]);

  // Get IDs to observe (useMemo to prevent infinite loops)
  const idsToObserve = React.useMemo(() => {
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

  // Auto-refresh messages every 3 seconds (simple polling for now)
  useEffect(() => {
    if (!hasJoined) return;

    const interval = setInterval(() => {
      loadMessages();
    }, 3000);

    return () => clearInterval(interval);
  }, [hasJoined, code]);

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
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center">
        <div className="text-gray-600 dark:text-gray-400">Loading chat...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800">
        <Header />
        <div className="container mx-auto px-4 py-12 max-w-2xl">
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-red-600 dark:text-red-400">
            {error}
          </div>
        </div>
      </div>
    );
  }

  // Join screen for guests
  if (!hasJoined && chatRoom) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 dark:from-gray-900 dark:to-gray-800">
        <Header />
        <div className="container mx-auto px-4 py-12 max-w-md">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl p-8">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              {chatRoom.name}
            </h1>
            {chatRoom.description && (
              <p className="text-gray-600 dark:text-gray-400 mb-6">
                {chatRoom.description}
              </p>
            )}

            <p className="text-sm text-gray-500 dark:text-gray-500 mb-6">
              Hosted by {chatRoom.host.display_name || chatRoom.host.email}
            </p>

            {joinError && (
              <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-600 dark:text-red-400">
                {joinError}
              </div>
            )}

            <form onSubmit={handleJoin} className="space-y-4">
              <div>
                <label htmlFor="username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Choose a username
                </label>
                <input
                  type="text"
                  id="username"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                  placeholder="Your name"
                />
              </div>

              {chatRoom.access_mode === 'private' && (
                <div>
                  <label htmlFor="access_code" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Access Code
                  </label>
                  <input
                    type="text"
                    id="access_code"
                    required
                    value={accessCode}
                    onChange={(e) => setAccessCode(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
                    placeholder="Enter access code"
                  />
                </div>
              )}

              <button
                type="submit"
                className="w-full px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all"
              >
                Join Chat
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // Design configurations
  const designs = {
    design1: {
      container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-pink-900/20",
      header: "border-b border-purple-200 dark:border-purple-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
      headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
      headerSubtitle: "text-sm text-gray-500 dark:text-gray-400",
      stickySection: "absolute top-0 left-0 right-0 z-10 border-b border-purple-200 dark:border-purple-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
      messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9InBhdHRlcm4iIHBhdHRlcm5Vbml0cz0idXNlclNwYWNlT25Vc2UiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCI+PHBhdGggZD0iTTAgMGg2MHY2MEgweiIgZmlsbD0icmdiYSgyMTYsIDE5MSwgMjE2LCAwLjEpIi8+PHBhdGggZD0iTTMwIDEwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMCAwLTEwek0xMCAzMGE1IDUgMCAxIDAgMCAxMCA1IDUgMCAwIDAtMTB6TTUwIDMwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMC0xMHpNMzAgNTBhNSA1IDAgMSAwIDAgMTAgNSA1IDAgMCAwIDAtMTB6IiBmaWxsPSJyZ2JhKDE5MiwgMTMyLCAyNTIsIDAuMTUpIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI3BhdHRlcm4pIi8+PC9zdmc+')] bg-repeat",
      hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-purple-500 via-pink-500 to-red-500 text-white shadow-lg border-2 border-white/20",
      hostText: "text-white",
      pinnedMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-amber-100 to-yellow-100 dark:from-amber-900/40 dark:to-yellow-900/40 border-2 border-amber-300 dark:border-amber-700 shadow-md",
      pinnedText: "text-amber-900 dark:text-amber-200",
      regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-purple-100 dark:border-purple-800 shadow-sm",
      regularText: "text-gray-700 dark:text-gray-300",
      filterButtonActive: "px-4 py-2 rounded-full text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg border-2 border-white/30",
      filterButtonInactive: "px-4 py-2 rounded-full text-xs font-bold bg-white/70 dark:bg-gray-700/70 text-purple-700 dark:text-purple-300 backdrop-blur-sm border-2 border-purple-200 dark:border-purple-700",
      inputArea: "border-t border-gray-300 bg-white dark:bg-gray-800 px-4 py-3 flex-shrink-0",
    },
    design2: {
      container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-gradient-to-br from-sky-50 via-blue-50 to-cyan-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-cyan-900/20",
      header: "border-b border-blue-200 dark:border-blue-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
      headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
      headerSubtitle: "text-sm text-gray-500 dark:text-gray-400",
      stickySection: "absolute top-0 left-0 right-0 z-10 border-b border-blue-200 dark:border-blue-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
      messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9InBhdHRlcm4iIHBhdHRlcm5Vbml0cz0idXNlclNwYWNlT25Vc2UiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCI+PHBhdGggZD0iTTAgMGg2MHY2MEgweiIgZmlsbD0icmdiYSgyMDAsIDIzMCwgMjUwLCAwLjEpIi8+PHBhdGggZD0iTTMwIDEwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMCAwLTEwek0xMCAzMGE1IDUgMCAxIDAgMCAxMCA1IDUgMCAwIDAtMTB6TTUwIDMwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMC0xMHpNMzAgNTBhNSA1IDAgMSAwIDAgMTAgNSA1IDAgMCAwIDAtMTB6IiBmaWxsPSJyZ2JhKDU5LCAxMzAsIDI0NiwgMC4xNSkiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjcGF0dGVybikiLz48L3N2Zz4=')] bg-repeat",
      hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500 text-white shadow-lg border-2 border-white/20",
      hostText: "text-white",
      pinnedMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-amber-100 to-yellow-100 dark:from-amber-900/40 dark:to-yellow-900/40 border-2 border-amber-300 dark:border-amber-700 shadow-md",
      pinnedText: "text-amber-900 dark:text-amber-200",
      regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-blue-100 dark:border-blue-800 shadow-sm",
      regularText: "text-gray-700 dark:text-gray-300",
      filterButtonActive: "px-4 py-2 rounded-full text-xs font-bold bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg border-2 border-white/30",
      filterButtonInactive: "px-4 py-2 rounded-full text-xs font-bold bg-white/70 dark:bg-gray-700/70 text-blue-700 dark:text-blue-300 backdrop-blur-sm border-2 border-blue-200 dark:border-blue-700",
      inputArea: "border-t border-gray-300 bg-white dark:bg-gray-800 px-4 py-3 flex-shrink-0",
    },
    design3: {
      container: "h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-zinc-950",
      header: "border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
      headerTitle: "text-lg font-bold text-zinc-100",
      headerSubtitle: "text-sm text-zinc-400",
      stickySection: "absolute top-0 left-0 right-0 z-10 border-b border-zinc-800 bg-zinc-900/90 px-4 py-2 space-y-2 shadow-lg",
      messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-2",
      hostMessage: "rounded px-3 py-2 bg-cyan-400 font-medium",
      hostText: "text-cyan-950",
      pinnedMessage: "rounded px-3 py-2 bg-yellow-400 font-medium",
      pinnedText: "text-yellow-950",
      regularMessage: "max-w-[85%] rounded px-3 py-2 bg-zinc-800 border-l-2 border-cyan-500/50",
      regularText: "text-zinc-100",
      filterButtonActive: "px-3 py-1.5 rounded text-xs font-bold tracking-wider bg-cyan-400 text-cyan-950 border border-cyan-300",
      filterButtonInactive: "px-3 py-1.5 rounded text-xs font-bold tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700",
      inputArea: "border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
    },
  };

  const currentDesign = designs[designVariant as keyof typeof designs] || designs.design1;

  // Main chat interface
  return (
    <div className={currentDesign.container}>
      {/* Chat Header */}
      <div className={currentDesign.header}>
        <div className="flex items-center justify-between">
          <h1 className={currentDesign.headerTitle}>
            {chatRoom?.name}
          </h1>
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
            Host Focus: {filterMode === 'focus' ? 'On' : 'Off'}
          </button>
        </div>
      </div>

      {/* Content Area - Relative positioned to contain absolute sticky section */}
      <div className="flex-1 relative overflow-hidden">
        {/* Sticky Section: Host + Pinned Messages - Absolutely positioned overlay */}
        {(stickyHostMessages.length > 0 || stickyPinnedMessage) && (
          <div className={currentDesign.stickySection}>
            {/* Host Messages */}
            {stickyHostMessages.map((message) => (
              <div
                key={`sticky-${message.id}`}
                className={`${currentDesign.hostMessage} cursor-pointer hover:opacity-90 transition-opacity`}
                onClick={() => scrollToMessage(message.id)}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                    {message.username}
                  </span>
                  <span className={`text-sm ${currentDesign.hostText} opacity-80`}>
                    👑
                  </span>
                  <span className={`text-xs ${currentDesign.hostText} opacity-60 ml-auto`}>
                    {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <p className={`text-sm ${currentDesign.hostText}`}>
                  {message.content}
                </p>
              </div>
            ))}

            {/* Pinned Message */}
            {stickyPinnedMessage && (
              <div
                className={`${currentDesign.pinnedMessage} cursor-pointer hover:opacity-90 transition-opacity`}
                onClick={() => scrollToMessage(stickyPinnedMessage.id)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                    {stickyPinnedMessage.username}
                  </span>
                  <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                    📌 Pinned ${stickyPinnedMessage.pin_amount_paid}
                  </span>
                  <span className={`text-xs ${currentDesign.pinnedText} opacity-60 ml-auto`}>
                    {new Date(stickyPinnedMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <p className={`text-sm ${currentDesign.pinnedText}`}>
                  {stickyPinnedMessage.content}
                </p>
              </div>
            )}
          </div>
        )}

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className={currentDesign.messagesArea}
      >
        {/* Add padding-top when sticky messages are present to avoid overlap */}
        <div className={`space-y-3 ${(stickyHostMessages.length > 0 || stickyPinnedMessage) ? 'pt-4' : ''}`}>
        {filteredMessages.map((message, index) => {
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
                <div className="text-xs mb-1 flex items-center gap-2 text-gray-700 dark:text-gray-300">
                  <span className="font-semibold">
                    {message.username}
                  </span>
                  <span className="opacity-60">
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

                {/* Message bubble */}
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
                      <div className="flex items-center gap-1.5">
                        <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                          {message.username}
                        </span>
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
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                          {message.username}
                        </span>
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
                  <p className={`text-sm ${message.is_from_host ? currentDesign.hostText : message.is_pinned ? currentDesign.pinnedText : currentDesign.regularText}`}>
                    {message.content}
                  </p>
                </div>
              </div>

            </div>
          );
        })}
        <div ref={messagesEndRef} />
        </div>
      </div>
      </div>

      {/* Message Input */}
      <div className={currentDesign.inputArea}>
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
            disabled={sending}
          />
          <button
            type="submit"
            disabled={sending || !newMessage.trim()}
            className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
