'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { BadgeCheck, Dices } from 'lucide-react';
import type { ChatRoom } from '@/lib/api';
import { chatApi, api } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { getFingerprint } from '@/lib/usernameStorage';
import { isDarkTheme } from '@/lib/themes';

interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName: string;
  hasJoinedBefore: boolean;
  isLoggedIn: boolean;
  hasReservedUsername?: boolean;
  design?: 'purple-dream' | 'ocean-blue' | 'dark-mode';
  onJoin: (username: string, accessCode?: string) => void;
}

// Get theme-aware modal styles
const getModalStyles = (design: 'purple-dream' | 'ocean-blue' | 'dark-mode') => {
  const useDarkMode = isDarkTheme(design);

  if (useDarkMode) {
    // Always use dark mode for dark-type themes
    return {
      overlay: 'bg-transparent',
      container: 'bg-zinc-900 border border-zinc-800',
      title: 'text-zinc-50',
      subtitle: 'text-zinc-400',
      input: 'bg-zinc-800 border border-zinc-700 text-zinc-50 placeholder-zinc-500 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400',
      primaryButton: 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
      secondaryButton: 'bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border border-zinc-700',
      divider: 'border-zinc-700',
      dividerText: 'bg-zinc-900',
      error: 'text-red-400',
    };
  } else {
    // Use system preference for light-type themes
    return {
      overlay: 'bg-transparent',
      container: 'bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800',
      title: 'text-gray-900 dark:text-zinc-50',
      subtitle: 'text-gray-600 dark:text-zinc-400',
      input: 'bg-white dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 text-gray-900 dark:text-zinc-50 placeholder-gray-400 dark:placeholder-zinc-500 focus:ring-2 focus:ring-purple-500 dark:focus:ring-cyan-400 focus:border-purple-500 dark:focus:border-cyan-400',
      primaryButton: 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
      secondaryButton: 'bg-gray-50 dark:bg-zinc-800 hover:bg-gray-100 dark:hover:bg-zinc-700 text-gray-700 dark:text-zinc-100 border border-gray-200 dark:border-zinc-700',
      divider: 'border-gray-200 dark:border-zinc-700',
      dividerText: 'bg-white dark:bg-zinc-900',
      error: 'text-red-600 dark:text-red-400',
    };
  }
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
  const modalStyles = getModalStyles(design);

  const [username, setUsername] = useState('');
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [isSuggestingUsername, setIsSuggestingUsername] = useState(false);
  const [isValidatingUsername, setIsValidatingUsername] = useState(false);
  const [usernameError, setUsernameError] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState(false);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [rateLimitChecked, setRateLimitChecked] = useState(false);
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

  // Check rate limit on mount (for anonymous users only)
  useEffect(() => {
    const checkRateLimit = async () => {
      if (isLoggedIn || hasJoinedBefore) {
        // Logged-in users and returning users are exempt
        setRateLimitChecked(true);
        return;
      }

      try {
        const fingerprint = await getFingerprint();
        const result = await chatApi.checkRateLimit(chatRoom.code, fingerprint);

        if (result.is_rate_limited) {
          setIsRateLimited(true);
          setError('Max anonymous usernames. Log in to continue.');
        }
      } catch (err) {
        console.error('Failed to check rate limit:', err);
        // Don't block if check fails
      } finally {
        setRateLimitChecked(true);
      }
    };

    checkRateLimit();
  }, [isLoggedIn, hasJoinedBefore, chatRoom.code]);

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
      <div className={`absolute inset-0 ${modalStyles.overlay}`} />

      {/* Modal */}
      <div className={`relative w-full max-w-md ${modalStyles.container} rounded-3xl p-8 shadow-2xl`}>
        {/* Title */}
        <div className="mb-6 text-center">
          <h1 className={`text-2xl font-bold ${modalStyles.title} mb-2 flex flex-wrap items-center justify-center gap-2`}>
            {hasJoinedBefore ? (
              'Welcome back!'
            ) : isLoggedIn ? (
              <>
                <span>Come join us,</span>
                <span className="inline-flex items-center gap-1 whitespace-nowrap">
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
            <p className={`text-sm ${modalStyles.subtitle}`}>
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
              <div className="flex items-center justify-center gap-1">
                <p className={`text-sm ${modalStyles.subtitle}`}>You'll join as: <span className={`font-semibold ${modalStyles.title}`}>{currentUserDisplayName}</span></p>
                {hasReservedUsername && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
                )}
              </div>
            </div>
          ) : isLoggedIn ? (
            // Logged-in first-time user - editable username pre-filled with reserved_username
            <div>
              <label className={`block text-sm font-medium ${modalStyles.subtitle} mb-2`}>
                Pick a username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={currentUserDisplayName || "Enter username"}
                  className={`w-full px-4 py-3 pr-12 rounded-xl ${modalStyles.input} transition-colors focus:outline-none ${
                    usernameError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''
                  }`}
                  maxLength={15}
                  disabled={isJoining || isSuggestingUsername}
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  disabled={isJoining || isSuggestingUsername}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${modalStyles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
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
              <label className={`block text-sm font-medium ${modalStyles.subtitle} mb-2`}>
                Pick a username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className={`w-full px-4 py-3 pr-12 rounded-xl ${modalStyles.input} transition-colors focus:outline-none ${
                    usernameError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''
                  }`}
                  maxLength={15}
                  disabled={isJoining || isSuggestingUsername || isRateLimited}
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  disabled={isJoining || isSuggestingUsername || isRateLimited}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${modalStyles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
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
              <label className={`block text-sm font-medium ${modalStyles.subtitle} mb-2`}>
                Access Code
              </label>
              <input
                type="password"
                value={accessCode}
                onChange={(e) => setAccessCode(e.target.value)}
                placeholder="Enter access code"
                className={`w-full px-4 py-3 rounded-xl ${modalStyles.input} transition-colors focus:outline-none`}
                disabled={isJoining}
              />
            </div>
          )}

          {/* Error Message */}
          {error && (
            <p className={`text-xs ${modalStyles.error} text-left -mt-3`}>
              {error}
            </p>
          )}

          {/* Join Button */}
          <button
            type="submit"
            disabled={isJoining || isRateLimited}
            className={`w-full px-6 py-4 rounded-xl font-semibold ${modalStyles.primaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isJoining ? 'Joining...' : 'Join Chat'}
          </button>

          {/* Divider and Auth Buttons (only for non-logged-in users) */}
          {!isLoggedIn && (
            <>
              <div className="relative my-3">
                <div className={`absolute inset-0 flex items-center`}>
                  <div className={`w-full border-t ${modalStyles.divider}`} />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className={`px-4 ${modalStyles.dividerText} ${modalStyles.subtitle}`}>
                    or
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <button
                  type="button"
                  onClick={handleLogin}
                  className={`w-full px-6 py-3 rounded-xl font-bold ${modalStyles.secondaryButton} transition-all active:scale-95`}
                >
                  Log in
                </button>
                <button
                  type="button"
                  onClick={handleSignup}
                  className={`w-full px-6 py-3 rounded-xl font-bold ${modalStyles.secondaryButton} transition-all active:scale-95`}
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
