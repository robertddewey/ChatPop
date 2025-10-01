'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { chatApi, messageApi, authApi, type ChatRoom, type Message } from '@/lib/api';
import Header from '@/components/Header';

export default function ChatPage() {
  const params = useParams();
  const code = params.code as string;

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

  // Track if user is near bottom
  const shouldAutoScrollRef = useRef(true);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

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

  // Main chat interface
  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      {/* Chat Header */}
      <div className="border-b bg-white dark:bg-gray-800 px-4 py-3 flex-shrink-0">
        <h1 className="text-lg font-bold text-gray-900 dark:text-white">
          {chatRoom?.name}
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {chatRoom?.message_count} messages
        </p>
      </div>

      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4"
      >
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.is_from_host ? 'flex-col' : 'flex-row'} gap-2`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                message.is_from_host
                  ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white self-stretch'
                  : message.is_pinned
                  ? 'bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800'
                  : 'bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-sm font-semibold ${message.is_from_host ? 'text-white' : 'text-gray-900 dark:text-white'}`}>
                  {message.username}
                </span>
                {message.is_from_host && (
                  <span className="text-xs bg-white/20 px-2 py-0.5 rounded">
                    HOST
                  </span>
                )}
                {message.is_pinned && !message.is_from_host && (
                  <span className="text-xs text-yellow-700 dark:text-yellow-400">
                    📌 Pinned
                  </span>
                )}
              </div>
              <p className={`text-sm ${message.is_from_host ? 'text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                {message.content}
              </p>
              <p className={`text-xs mt-1 ${message.is_from_host ? 'text-white/70' : 'text-gray-500 dark:text-gray-500'}`}>
                {new Date(message.created_at).toLocaleTimeString()}
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
