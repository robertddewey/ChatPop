'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { BadgeCheck, Dices } from 'lucide-react';
import type { ChatRoom } from '@/lib/api';
import { chatApi, api } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { getFingerprint } from '@/lib/usernameStorage';

interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName: string;
  hasJoinedBefore: boolean;
  isLoggedIn: boolean;
  hasReservedUsername?: boolean;
  design?: 'purple-dream' | 'ocean-blue' | 'dark-mode';
  onJoin: (username: string, accessCode?: string) => void;
}

// Theme configurations - simplified to light/dark
const getModalStyles = (design: 'purple-dream' | 'ocean-blue' | 'dark-mode') => {
  const isDark = design === 'dark-mode';

  return {
    overlay: 'bg-transparent',
    container: isDark ? 'bg-zinc-900 border border-zinc-800' : 'bg-white border border-gray-200',
    title: isDark ? 'text-zinc-50' : 'text-gray-900',
    subtitle: isDark ? 'text-zinc-400' : 'text-gray-600',
    input: isDark
      ? 'bg-zinc-800 border border-zinc-700 text-zinc-50 placeholder-zinc-500 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400'
      : 'bg-white border border-gray-300 text-gray-900 focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
    primaryButton: isDark
      ? 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950'
      : 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
    secondaryButton: isDark
      ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700'
      : 'bg-gray-50 hover:bg-gray-100 text-gray-700 border border-gray-200',
    divider: isDark ? 'border-zinc-700' : 'border-gray-200',
    dividerText: isDark ? 'bg-zinc-900' : 'bg-white',
    error: isDark ? 'text-red-400' : 'text-red-600',
  };
};

export default function JoinChatModal({
  chatRoom,
  currentUserDisplayName,
  hasJoinedBefore,
  isLoggedIn,
  hasReservedUsername = false,
  design = 'purple-dream',
  onJoin,
}: JoinChatModalProps) {
  const router = useRouter();
  const styles = getModalStyles(design);

  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [isSuggestingUsername, setIsSuggestingUsername] = useState(false);
  const [isValidatingUsername, setIsValidatingUsername] = useState(false);
  const [usernameError, setUsernameError] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState(false);
  const audioContextRef = React.useRef<AudioContext>();
  const validationTimeoutRef = React.useRef<NodeJS.Timeout>();

  // Import the audio initialization function
  const { initAudioContext } = React.useMemo(() => {
    return typeof window !== 'undefined'
      ? require('@/lib/sounds')
      : { initAudioContext: () => {} };
  }, []);

  // Prevent body scrolling when modal is open (only on non-chat routes)
  // Chat routes already have body scroll locked via chat-layout.css
  useEffect(() => {
    const isChatRoute = window.location.pathname.startsWith('/chat/');
    if (!isChatRoute) {
      document.body.style.overflow = 'hidden';
    }
    return () => {
      if (!isChatRoute) {
        document.body.style.overflow = 'unset';
      }
    };
  }, []);

  // Real-time username validation with debouncing
  useEffect(() => {
    // Clear any existing timeout
    if (validationTimeoutRef.current) {
      clearTimeout(validationTimeoutRef.current);
    }

    // Don't validate if:
    // - Username is empty
    // - User is logged in and has joined before (locked username)
    // - Currently suggesting a username
    if (!username.trim() || (isLoggedIn && hasJoinedBefore) || isSuggestingUsername) {
      setUsernameError('');
      setUsernameAvailable(false);
      setIsValidatingUsername(false);
      return;
    }

    // Start validation after debounce delay
    validationTimeoutRef.current = setTimeout(async () => {
      // First check format validation (client-side)
      const validation = validateUsername(username.trim());
      if (!validation.isValid) {
        // Show specific format validation error
        setUsernameError(validation.error || 'Invalid username');
        setUsernameAvailable(false);
        setIsValidatingUsername(false);
        return;
      }

      // Then check availability (server-side)
      setIsValidatingUsername(true);
      setUsernameError('');
      setUsernameAvailable(false);

      try {
        const fingerprint = await getFingerprint();
        const response = await api.post(
          `/api/chats/${chatRoom.code}/validate-username/`,
          {
            username: username.trim(),
            fingerprint: fingerprint,
          }
        );

        const data = response.data;

        if (!data.available) {
          // Username validation succeeded but username is not available
          setUsernameError('Unavailable');
          setUsernameAvailable(false);
        } else {
          // Username is available!
          setUsernameError('');
          setUsernameAvailable(true);
        }
      } catch (err) {
        // Error from server (400, 500, etc.) or network error
        setUsernameError('Unavailable');
        setUsernameAvailable(false);
      } finally {
        setIsValidatingUsername(false);
      }
    }, 500); // 500ms debounce

    return () => {
      if (validationTimeoutRef.current) {
        clearTimeout(validationTimeoutRef.current);
      }
    };
  }, [username, isLoggedIn, hasJoinedBefore, isSuggestingUsername, chatRoom.code]);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Initialize AudioContext during user gesture (button click)
    initAudioContext();

    // Use placeholder (reserved username) if no username entered
    const finalUsername = username.trim() || currentUserDisplayName || '';

    // Validate username format
    const validation = validateUsername(finalUsername);
    if (!validation.isValid) {
      setError(validation.error || 'Invalid username');
      return;
    }

    if (chatRoom.access_mode === 'private' && !accessCode.trim()) {
      setError('This chat requires an access code');
      return;
    }

    setIsJoining(true);

    try {
      await onJoin(finalUsername.trim(), accessCode.trim() || undefined);
    } catch (err: any) {
      setError(err.message || 'Failed to join chat');
      setIsJoining(false);
    }
  };

  const handleLogin = () => {
    const currentPath = window.location.pathname;
    const currentSearch = window.location.search;
    const params = new URLSearchParams(currentSearch);
    params.set('auth', 'login');
    params.set('redirect', currentPath + currentSearch);
    router.replace(`${currentPath}?${params.toString()}`);
  };

  const handleSignup = () => {
    const currentPath = window.location.pathname;
    const currentSearch = window.location.search;
    const params = new URLSearchParams(currentSearch);
    params.set('auth', 'register');
    params.set('redirect', currentPath + currentSearch);
    router.replace(`${currentPath}?${params.toString()}`);
  };

  const handleSuggestUsername = async () => {
    setError('');
    setIsSuggestingUsername(true);

    try {
      const fingerprint = await getFingerprint();
      const result = await chatApi.suggestUsername(chatRoom.code, fingerprint);
      setUsername(result.username);
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage || 'Failed to generate username');
    } finally {
      setIsSuggestingUsername(false);
    }
  };

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div className={`fixed inset-0 z-[9999] flex items-center justify-center p-4`}>
      {/* Backdrop */}
      <div className={`absolute inset-0 ${styles.overlay}`} />

      {/* Modal */}
      <div className={`relative w-full max-w-md ${styles.container} rounded-3xl p-8 shadow-2xl`}>
        {/* Title */}
        <div className="mb-6 text-center">
          <h1 className={`text-2xl font-bold ${styles.title} mb-2 flex flex-wrap items-center justify-center gap-2`}>
            {hasJoinedBefore ? (
              'Welcome back!'
            ) : isLoggedIn ? (
              <>
                <span>Come join us,</span>
                <span className="inline-flex items-center gap-2 whitespace-nowrap">
                  {currentUserDisplayName}
                  {hasReservedUsername && (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={20} />
                  )}
                </span>
              </>
            ) : (
              'Start chatting'
            )}
          </h1>
          {chatRoom.is_private && (
            <p className={`text-sm ${styles.subtitle}`}>
              This is a private chat
            </p>
          )}
        </div>

        {/* Form */}
        <form onSubmit={handleJoin} className="space-y-4">
          {/* Username Display or Input */}
          {hasJoinedBefore ? (
            // Returning user (logged-in or anonymous) - show locked username
            <div className="text-center mb-8">
              <div className="flex items-center justify-center gap-2">
                <p className={`text-sm ${styles.subtitle}`}>You'll join as: <span className={`font-semibold ${styles.title}`}>{currentUserDisplayName}</span></p>
                {hasReservedUsername && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
                )}
              </div>
            </div>
          ) : isLoggedIn ? (
            // Logged-in first-time user - editable username pre-filled with reserved_username
            <div>
              <label className={`block text-sm font-medium ${styles.subtitle} mb-2`}>
                Pick a username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={currentUserDisplayName || "Enter username"}
                  className={`w-full px-4 py-3 pr-12 rounded-xl ${styles.input} transition-colors focus:outline-none ${
                    usernameError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''
                  }`}
                  maxLength={15}
                  disabled={isJoining || isSuggestingUsername}
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  disabled={isJoining || isSuggestingUsername}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${styles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
                  title="Suggest random username"
                >
                  <Dices size={20} className={isSuggestingUsername ? 'animate-spin' : ''} />
                </button>
              </div>
              {usernameError && (
                <p className={`text-xs text-red-500 mt-1`}>
                  {usernameError}
                </p>
              )}
              {usernameAvailable && !usernameError && (
                <p className={`text-xs text-green-500 mt-1`}>
                  Username is available
                </p>
              )}
            </div>
          ) : (
            // Anonymous first-time user - show input
            <div>
              <label className={`block text-sm font-medium ${styles.subtitle} mb-2`}>
                Pick a username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className={`w-full px-4 py-3 pr-12 rounded-xl ${styles.input} transition-colors focus:outline-none ${
                    usernameError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''
                  }`}
                  maxLength={15}
                  disabled={isJoining || isSuggestingUsername}
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  disabled={isJoining || isSuggestingUsername}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${styles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
                  title="Suggest random username"
                >
                  <Dices size={20} className={isSuggestingUsername ? 'animate-spin' : ''} />
                </button>
              </div>
              {usernameError && (
                <p className={`text-xs text-red-500 mt-1`}>
                  {usernameError}
                </p>
              )}
              {usernameAvailable && !usernameError && (
                <p className={`text-xs text-green-500 mt-1`}>
                  Username is available
                </p>
              )}
            </div>
          )}

          {/* Access Code Input (only for private chats) */}
          {chatRoom.access_mode === 'private' && (
            <div>
              <label className={`block text-sm font-medium ${styles.subtitle} mb-2`}>
                Access Code
              </label>
              <input
                type="password"
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                placeholder="Enter access code"
                className={`w-full px-4 py-3 rounded-xl ${styles.input} transition-colors focus:outline-none`}
                disabled={isJoining}
              />
            </div>
          )}

          {/* Error Message */}
          {error && (
            <p className={`text-xs ${styles.error} text-left -mt-3`}>
              {error}
            </p>
          )}

          {/* Join Button */}
          <button
            type="submit"
            disabled={isJoining}
            className={`w-full px-6 py-4 rounded-xl font-semibold ${styles.primaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isJoining ? 'Joining...' : 'Join Chat'}
          </button>

          {/* Divider and Auth Buttons (only for non-logged-in users) */}
          {!isLoggedIn && (
            <>
              <div className="relative my-3">
                <div className={`absolute inset-0 flex items-center`}>
                  <div className={`w-full border-t ${styles.divider}`} />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className={`px-4 ${styles.dividerText} ${styles.subtitle}`}>
                    or
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <button
                  type="button"
                  onClick={handleLogin}
                  className={`w-full px-6 py-3 rounded-xl font-bold ${styles.secondaryButton} transition-all active:scale-95`}
                >
                  Log in
                </button>
                <button
                  type="button"
                  onClick={handleSignup}
                  className={`w-full px-6 py-3 rounded-xl font-bold ${styles.secondaryButton} transition-all active:scale-95`}
                >
                  Sign up
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>,
    document.body
  );
}
