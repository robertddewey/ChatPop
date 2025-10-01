'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { chatApi, messageApi, authApi, type ChatRoom, type Message } from '@/lib/api';
import Header from '@/components/Header';

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

  // Load chat room details
  useEffect(() => {
    const loadChatRoom = async () => {
      try {
        const room = await chatApi.getChatByCode(code);
        setChatRoom(room);

        // Check if user is already logged in
        const token = localStorage.getItem('auth_token');
        if (token) {
          try {
            const currentUser = await authApi.getCurrentUser();
            const displayUsername = currentUser.display_name || currentUser.email.split('@')[0];
            setUsername(displayUsername);
            localStorage.setItem(`chat_username_${code}`, displayUsername);
            setHasJoined(true);
            await loadMessages();
          } catch (userErr) {
            // If getting user fails, just proceed as guest
            console.error('Failed to load user:', userErr);
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
      localStorage.setItem(`chat_username_${code}`, username.trim());
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
      // Get username from localStorage or use current username
      let messageUsername = localStorage.getItem(`chat_username_${code}`) || username;

      // If logged in and no username saved, use email or display name
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

        // Show my messages
        const myUsername = localStorage.getItem(`chat_username_${code}`);
        if (msg.username === myUsername) return true;

        // Show messages that host replied to
        const hostRepliedToThis = messages.some(
          m => m.is_from_host && m.reply_to === msg.id
        );
        if (hostRepliedToThis) return true;

        return false;
      })
    : messages;

  // Filter messages for sticky section
  const allStickyHostMessages = filteredMessages
    .filter(m => m.is_from_host)
    .slice(-2)  // Get 2 most recent
    .reverse(); // Show newest first

  // Only show in sticky if not visible in scroll area
  const stickyHostMessages = allStickyHostMessages.filter(m => !visibleMessageIds.has(m.id));

  const topPinnedMessage = filteredMessages
    .filter(m => m.is_pinned && !m.is_from_host)
    .sort((a, b) => parseFloat(b.pin_amount_paid) - parseFloat(a.pin_amount_paid))
    [0]; // Get highest paid

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
    if (!container || messages.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        setVisibleMessageIds((prev) => {
          const newVisibleIds = new Set(prev);
          entries.forEach((entry) => {
            const messageId = entry.target.getAttribute('data-message-id');
            if (messageId) {
              if (entry.isIntersecting) {
                newVisibleIds.add(messageId);
              } else {
                newVisibleIds.delete(messageId);
              }
            }
          });
          return newVisibleIds;
        });
      },
      {
        root: container,
        threshold: 0.3, // Message must be 30% visible
        rootMargin: '0px',
      }
    );

    // Observe all sticky host messages and pinned messages in the scroll area
    const stickyHostIds = allStickyHostMessages.map(m => m.id);
    const pinnedId = topPinnedMessage?.id;
    const idsToObserve = [...stickyHostIds];
    if (pinnedId) idsToObserve.push(pinnedId);

    const messageElements = container.querySelectorAll('[data-message-id]');
    messageElements.forEach((el) => {
      const messageId = el.getAttribute('data-message-id');
      if (messageId && idsToObserve.includes(messageId)) {
        observer.observe(el);
      }
    });

    return () => observer.disconnect();
  }, [filteredMessages.length, allStickyHostMessages.length]);

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
      container: "h-screen flex flex-col bg-gradient-to-br from-indigo-50 via-purple-50 to-pink-50 dark:from-gray-900 dark:via-purple-900/20 dark:to-pink-900/20",
      header: "border-b border-purple-200 dark:border-purple-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
      headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
      headerSubtitle: "text-sm text-gray-500 dark:text-gray-400",
      stickySection: "border-b border-purple-200 dark:border-purple-800 bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg px-4 py-2 flex-shrink-0 space-y-2",
      messagesArea: "flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9InBhdHRlcm4iIHBhdHRlcm5Vbml0cz0idXNlclNwYWNlT25Vc2UiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCI+PHBhdGggZD0iTTAgMGg2MHY2MEgweiIgZmlsbD0icmdiYSgyMTYsIDE5MSwgMjE2LCAwLjEpIi8+PHBhdGggZD0iTTMwIDEwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMCAwLTEwek0xMCAzMGE1IDUgMCAxIDAgMCAxMCA1IDUgMCAwIDAtMTB6TTUwIDMwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMC0xMHpNMzAgNTBhNSA1IDAgMSAwIDAgMTAgNSA1IDAgMCAwIDAtMTB6IiBmaWxsPSJyZ2JhKDE5MiwgMTMyLCAyNTIsIDAuMTUpIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI3BhdHRlcm4pIi8+PC9zdmc+')] bg-repeat",
      hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-purple-500 via-pink-500 to-red-500 text-white shadow-lg border-2 border-white/20",
      hostText: "text-white",
      pinnedMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-amber-100 to-yellow-100 dark:from-amber-900/40 dark:to-yellow-900/40 border-2 border-amber-300 dark:border-amber-700 shadow-md",
      pinnedText: "text-amber-900 dark:text-amber-200",
      regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-purple-100 dark:border-purple-800 shadow-sm",
      regularText: "text-gray-700 dark:text-gray-300",
      filterButtonActive: "px-4 py-2 rounded-full text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg border-2 border-white/30 w-[100px]",
      filterButtonInactive: "px-4 py-2 rounded-full text-xs font-bold bg-white/70 dark:bg-gray-700/70 text-purple-700 dark:text-purple-300 backdrop-blur-sm border-2 border-purple-200 dark:border-purple-700 w-[100px]",
    },
    design2: {
      container: "h-screen flex flex-col bg-gradient-to-br from-sky-50 via-blue-50 to-cyan-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-cyan-900/20",
      header: "border-b border-blue-200 dark:border-blue-800 bg-white/80 dark:bg-gray-800/80 backdrop-blur-xl px-4 py-3 flex-shrink-0 shadow-sm",
      headerTitle: "text-lg font-bold text-gray-900 dark:text-white",
      headerSubtitle: "text-sm text-gray-500 dark:text-gray-400",
      stickySection: "border-b border-blue-200 dark:border-blue-800 bg-white/60 dark:bg-gray-800/60 backdrop-blur-lg px-4 py-2 flex-shrink-0 space-y-2",
      messagesArea: "flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjAiIGhlaWdodD0iNjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9InBhdHRlcm4iIHBhdHRlcm5Vbml0cz0idXNlclNwYWNlT25Vc2UiIHdpZHRoPSI2MCIgaGVpZ2h0PSI2MCI+PHBhdGggZD0iTTAgMGg2MHY2MEgweiIgZmlsbD0icmdiYSgyMDAsIDIzMCwgMjUwLCAwLjEpIi8+PHBhdGggZD0iTTMwIDEwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMCAwLTEwek0xMCAzMGE1IDUgMCAxIDAgMCAxMCA1IDUgMCAwIDAtMTB6TTUwIDMwYTUgNSAwIDEgMCAwIDEwIDUgNSAwIDAgMC0xMHpNMzAgNTBhNSA1IDAgMSAwIDAgMTAgNSA1IDAgMCAwIDAtMTB6IiBmaWxsPSJyZ2JhKDU5LCAxMzAsIDI0NiwgMC4xNSkiLz48L3BhdHRlcm4+PC9kZWZzPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9InVybCgjcGF0dGVybikiLz48L3N2Zz4=')] bg-repeat",
      hostMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-blue-500 via-sky-500 to-cyan-500 text-white shadow-lg border-2 border-white/20",
      hostText: "text-white",
      pinnedMessage: "rounded-2xl px-5 py-3 bg-gradient-to-r from-amber-100 to-yellow-100 dark:from-amber-900/40 dark:to-yellow-900/40 border-2 border-amber-300 dark:border-amber-700 shadow-md",
      pinnedText: "text-amber-900 dark:text-amber-200",
      regularMessage: "max-w-[80%] rounded-2xl px-4 py-3 bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border border-blue-100 dark:border-blue-800 shadow-sm",
      regularText: "text-gray-700 dark:text-gray-300",
      filterButtonActive: "px-4 py-2 rounded-full text-xs font-bold bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg border-2 border-white/30 w-[100px]",
      filterButtonInactive: "px-4 py-2 rounded-full text-xs font-bold bg-white/70 dark:bg-gray-700/70 text-blue-700 dark:text-blue-300 backdrop-blur-sm border-2 border-blue-200 dark:border-blue-700 w-[100px]",
    },
    design3: {
      container: "h-screen flex flex-col bg-zinc-950",
      header: "border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0",
      headerTitle: "text-lg font-bold text-zinc-100",
      headerSubtitle: "text-sm text-zinc-400",
      stickySection: "border-b border-zinc-800 bg-zinc-900/80 px-4 py-2 flex-shrink-0 space-y-2",
      messagesArea: "flex-1 overflow-y-auto px-4 py-4 space-y-2",
      hostMessage: "rounded px-3 py-2 bg-cyan-400 font-medium",
      hostText: "text-cyan-950",
      pinnedMessage: "rounded px-3 py-2 bg-yellow-400 font-medium",
      pinnedText: "text-yellow-950",
      regularMessage: "max-w-[85%] rounded px-3 py-2 bg-zinc-800 border-l-2 border-cyan-500/50",
      regularText: "text-zinc-100",
      filterButtonActive: "px-3 py-1.5 rounded text-xs font-bold tracking-wider bg-cyan-400 text-cyan-950 border border-cyan-300 w-[100px]",
      filterButtonInactive: "px-3 py-1.5 rounded text-xs font-bold tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700 w-[100px]",
    },
  };

  const currentDesign = designs[designVariant as keyof typeof designs] || designs.design1;

  // Main chat interface
  return (
    <div className={currentDesign.container}>
      {/* Design Switcher - Only show in dev */}
      {process.env.NODE_ENV === 'development' && (
        <div className="fixed bottom-4 left-4 z-50 flex gap-2 bg-black/80 text-white p-2 rounded-lg text-xs">
          <a href={`?design=design1`} className="px-2 py-1 rounded bg-white/20 hover:bg-white/30">Design 1</a>
          <a href={`?design=design2`} className="px-2 py-1 rounded bg-white/20 hover:bg-white/30">Design 2</a>
          <a href={`?design=design3`} className="px-2 py-1 rounded bg-white/20 hover:bg-white/30">Design 3</a>
        </div>
      )}

      {/* Chat Header */}
      <div className={currentDesign.header}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className={currentDesign.headerTitle}>
              {chatRoom?.name}
            </h1>
            <p className={currentDesign.headerSubtitle}>
              {chatRoom?.message_count} messages
            </p>
          </div>
          {/* Filter Toggle */}
          <button
            onClick={() => setFilterMode(filterMode === 'all' ? 'focus' : 'all')}
            className={`transition-all ${
              filterMode === 'focus'
                ? currentDesign.filterButtonActive
                : currentDesign.filterButtonInactive
            }`}
          >
            {filterMode === 'focus' ? 'Focus On' : 'Focus Off'}
          </button>
        </div>
      </div>

      {/* Sticky Section: Host + Pinned Messages */}
      {(stickyHostMessages.length > 0 || stickyPinnedMessage) && (
        <div className={currentDesign.stickySection}>
          {/* Host Messages */}
          {stickyHostMessages.map((message) => (
            <div
              key={`sticky-${message.id}`}
              className={`${currentDesign.hostMessage} cursor-pointer hover:opacity-90 transition-opacity`}
              onClick={() => scrollToMessage(message.id)}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                  {message.username}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded ${currentDesign.hostText} opacity-70`}>
                  HOST
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
        {filteredMessages.map((message) => (
          <div
            key={message.id}
            data-message-id={message.id}
            className={`flex ${message.is_from_host ? 'flex-col' : 'flex-row'} gap-2`}
          >
            <div
              className={
                message.is_from_host
                  ? currentDesign.hostMessage + ' self-stretch'
                  : message.is_pinned
                  ? currentDesign.pinnedMessage
                  : currentDesign.regularMessage
              }
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-sm font-semibold ${message.is_from_host ? currentDesign.hostText : message.is_pinned ? currentDesign.pinnedText : currentDesign.regularText}`}>
                  {message.username}
                </span>
                {message.is_from_host && (
                  <span className={`text-xs px-2 py-0.5 rounded ${currentDesign.hostText} opacity-70`}>
                    HOST
                  </span>
                )}
                {message.is_pinned && !message.is_from_host && (
                  <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                    📌 Pinned ${message.pin_amount_paid}
                  </span>
                )}
              </div>
              <p className={`text-sm ${message.is_from_host ? currentDesign.hostText : message.is_pinned ? currentDesign.pinnedText : currentDesign.regularText}`}>
                {message.content}
              </p>
              <p className={`text-xs mt-1 ${message.is_from_host ? currentDesign.hostText : message.is_pinned ? currentDesign.pinnedText : currentDesign.regularText} opacity-60`}>
                {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
              </p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="border-t bg-white dark:bg-gray-800 px-4 py-3 flex-shrink-0">
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
