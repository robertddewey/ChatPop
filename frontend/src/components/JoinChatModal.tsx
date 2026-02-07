'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { BadgeCheck, Dices, RotateCcw } from 'lucide-react';
import type { ChatRoom } from '@/lib/api';
import { chatApi, api } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { getFingerprint } from '@/lib/usernameStorage';
import { isDarkTheme } from '@/lib/themes';

interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName: string;
  hasJoinedBefore: boolean;
  isBlocked?: boolean;
  isLoggedIn: boolean;
  hasReservedUsername?: boolean;
  themeIsDarkMode?: boolean;
  userAvatarUrl?: string | null;
  onJoin: (username: string, accessCode?: string) => void;
}

export default function JoinChatModal({
  chatRoom,
  currentUserDisplayName,
  hasJoinedBefore,
  isLoggedIn,
  hasReservedUsername = false,
  themeIsDarkMode = true,
  userAvatarUrl,
  onJoin,
}: JoinChatModalProps) {
  const router = useRouter();

  // Always force dark mode
  const forceDarkMode = true;

  // Get modal styles based on theme (no system preference detection - force theme mode)
  const modalStyles = forceDarkMode ? {
    overlay: 'bg-transparent',
    container: 'bg-zinc-800 border border-zinc-700',
    title: 'text-zinc-50',
    subtitle: 'text-zinc-300',
    input: 'bg-zinc-700 border border-zinc-600 text-zinc-50 placeholder-zinc-400 focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400',
    primaryButton: 'bg-[#404eed] hover:bg-[#3640d9] text-white',
    secondaryButton: 'bg-zinc-700 hover:bg-zinc-600 text-zinc-100 border border-zinc-600',
    divider: 'border-zinc-600',
    dividerText: 'bg-zinc-800',
    error: 'text-red-400',
  } : {
    overlay: 'bg-transparent',
    container: 'bg-white border border-gray-200',
    title: 'text-gray-900',
    subtitle: 'text-gray-600',
    input: 'bg-white border border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
    primaryButton: 'bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white',
    secondaryButton: 'bg-gray-100 hover:bg-gray-200 text-gray-900 border border-gray-300',
    divider: 'border-gray-200',
    dividerText: 'bg-white',
    error: 'text-red-600',
  };

  // Initialize username with reserved username for logged-in users
  const [username, setUsername] = useState(
    isLoggedIn && hasReservedUsername && currentUserDisplayName ? currentUserDisplayName : ''
  );
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const [isSuggestingUsername, setIsSuggestingUsername] = useState(false);
  const [isValidatingUsername, setIsValidatingUsername] = useState(false);
  const [usernameError, setUsernameError] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState(false);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [rateLimitChecked, setRateLimitChecked] = useState(false);
  const [generationRemaining, setGenerationRemaining] = useState<number | null>(null);
  const [suggestionRemaining, setSuggestionRemaining] = useState<number | null>(null);
  const [usernameSource, setUsernameSource] = useState<'manual' | 'dice'>('manual');
  const [diceUsername, setDiceUsername] = useState<string | null>(null);
  const [isReturningUser, setIsReturningUser] = useState(false);
  const audioContextRef = React.useRef<AudioContext | null>(null);
  const validationTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Import the audio functions lazily
  const [soundModule, setSoundModule] = React.useState<{ initAudioContext: () => void; playJoinSound: () => void } | null>(null);
  React.useEffect(() => {
    if (typeof window !== 'undefined') {
      import('@/lib/sounds').then((mod) => {
        setSoundModule({ initAudioContext: mod.initAudioContext, playJoinSound: mod.playJoinSound });
      });
    }
  }, []);
  const initAudioContext = soundModule?.initAudioContext ?? (() => {});
  const playJoinSound = soundModule?.playJoinSound ?? (() => {});

  // Helper to generate DiceBear avatar URL
  const getDiceBearUrl = (seed: string, size: number = 80): string => {
    return `https://api.dicebear.com/7.x/pixel-art/svg?seed=${encodeURIComponent(seed)}&size=${size}`;
  };

  // Get the current avatar URL based on username
  const getCurrentAvatarUrl = (): string => {
    // If using reserved username and we have a stored avatar, use it
    if (hasReservedUsername && userAvatarUrl && username.toLowerCase() === currentUserDisplayName.toLowerCase()) {
      return userAvatarUrl;
    }
    // Otherwise generate from username seed
    return getDiceBearUrl(username || currentUserDisplayName || 'anonymous');
  };

  // Check if reset button should be enabled (username differs from reserved)
  const isResetEnabled = hasReservedUsername && username.toLowerCase() !== currentUserDisplayName.toLowerCase();

  // Handle reset to reserved username
  const handleResetUsername = () => {
    if (hasReservedUsername && currentUserDisplayName) {
      setUsername(currentUserDisplayName);
      setUsernameSource('manual');
      setDiceUsername(null);
    }
  };

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
        const result = await chatApi.checkRateLimit(chatRoom.code, fingerprint, chatRoom.host.reserved_username || undefined);

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

    // OPTIMIZATION: Skip validation for dice-generated usernames
    // Generated usernames are already validated server-side during generation
    // Applies to BOTH anonymous and logged-in users
    if (usernameSource === 'dice') {
      // Dice-generated username is pre-validated and reserved for 60 minutes
      setUsernameError('');
      setUsernameAvailable(true);
      setIsValidatingUsername(false);
      return;
    }

    // For all other cases (manually typed usernames): show as available
    // Validation will happen at join time
    setUsernameError('');
    setUsernameAvailable(true);
    setIsValidatingUsername(false);
  }, [username, isLoggedIn, hasJoinedBefore, isSuggestingUsername, usernameSource, currentUserDisplayName, hasReservedUsername]);

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Play sound and AWAIT it during user gesture to unlock audio on iOS
    // The await is critical for iOS - it must complete during the gesture
    await playJoinSound();

    // Also initialize AudioContext for future sounds
    await initAudioContext();

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
    } catch (err: unknown) {
      const error = err as Error;
      setError(error.message || 'Failed to join chat');
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
      const result = await chatApi.suggestUsername(chatRoom.code, fingerprint, chatRoom.host.reserved_username || undefined);

      // Backend returns username for both new generation and rotation through previous ones
      if (result.username) {
        setUsername(result.username);
        setDiceUsername(result.username);  // Remember the dice username
        setUsernameSource('dice');  // Mark as dice-generated (skip validation)
        // Update both rate limit counters
        setSuggestionRemaining(result.remaining ?? null);
        setGenerationRemaining(result.generation_remaining ?? null);

        // Check if this is a returning user (locked to their previous username)
        if (result.is_returning) {
          setIsReturningUser(true);
        }
      }
    } catch (err: unknown) {
      const error = err as { response?: { data?: { error?: string; generation_remaining?: number | null }; status?: number }; message?: string };
      const errorMessage = error.response?.data?.error || error.message;
      const statusCode = error.response?.status;

      // Handle rate limit errors specifically
      if (statusCode === 429) {
        const remaining = error.response?.data?.generation_remaining ?? null;
        setError(errorMessage || 'Maximum username generation attempts exceeded. No previously generated usernames are available.');
        setGenerationRemaining(remaining);
      } else {
        setError(errorMessage || 'Failed to generate username');
      }
    } finally {
      setIsSuggestingUsername(false);
    }
  };

  // Auto-fetch username for anonymous users on mount to detect returning users
  useEffect(() => {
    if (!isLoggedIn && !hasJoinedBefore && rateLimitChecked && !isRateLimited) {
      handleSuggestUsername();
    }
  }, [isLoggedIn, hasJoinedBefore, rateLimitChecked, isRateLimited]);

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
            {hasJoinedBefore || isReturningUser ? (
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

        {/* Avatar Preview */}
        {!hasJoinedBefore && !isReturningUser && (
          <div className="flex justify-center mb-6">
            <img
              src={getCurrentAvatarUrl()}
              alt="Your avatar"
              className="w-20 h-20 rounded-full bg-zinc-700"
            />
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleJoin} className="space-y-4">
          {/* Username Display or Input */}
          {hasJoinedBefore ? (
            // Returning user (logged-in or anonymous) - show locked username
            <div className="text-center mb-8">
              <div className="flex items-center justify-center gap-1">
                <p className={`text-sm ${modalStyles.subtitle}`}>You&apos;ll join as: <span className={`font-semibold ${modalStyles.title}`}>{currentUserDisplayName}</span></p>
                {hasReservedUsername && isLoggedIn && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
                )}
              </div>
            </div>
          ) : isLoggedIn ? (
            // Logged-in first-time user - read-only username with dice/reset buttons
            <div>
              <label className={`block text-sm font-medium ${modalStyles.subtitle} mb-2`}>
                Your username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  readOnly
                  tabIndex={-1}
                  placeholder={currentUserDisplayName || "Your username"}
                  className={`w-full px-4 py-3 pr-24 rounded-xl ${modalStyles.input} transition-colors pointer-events-none select-none cursor-default ${
                    usernameError ? 'border-red-500' : ''
                  }`}
                  maxLength={15}
                />
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                  {/* Reset button - always visible for logged-in users with reserved username */}
                  {hasReservedUsername && (
                    <button
                      type="button"
                      onClick={handleResetUsername}
                      disabled={!isResetEnabled || isJoining || isSuggestingUsername}
                      className={`p-2 rounded-lg ${modalStyles.secondaryButton} transition-all active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer`}
                      title="Reset to your username"
                    >
                      <RotateCcw size={20} />
                    </button>
                  )}
                  {/* Dice button */}
                  <button
                    type="button"
                    onClick={handleSuggestUsername}
                    disabled={isJoining || isSuggestingUsername}
                    className={`p-2 rounded-lg ${modalStyles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
                    title="Suggest random username"
                  >
                    <Dices size={20} className={isSuggestingUsername ? 'animate-spin' : ''} />
                  </button>
                </div>
              </div>
              {usernameError && (
                <p className={`text-xs text-red-500 mt-1`}>
                  {usernameError}
                </p>
              )}
            </div>
          ) : isReturningUser ? (
            // Anonymous returning user - show locked username
            <div className="text-center mb-8">
              <p className={`text-sm ${modalStyles.subtitle}`}>
                Rejoining as: <span className={`font-semibold ${modalStyles.title}`}>{username}</span>
              </p>
            </div>
          ) : (
            // Anonymous first-time user - show input with dice
            <div>
              <label className={`block text-sm font-medium ${modalStyles.subtitle} mb-2`}>
                Your username
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  readOnly
                  tabIndex={-1}
                  placeholder={isSuggestingUsername ? "Generating..." : "Click the dice to generate"}
                  className={`w-full px-4 py-3 pr-12 rounded-xl ${modalStyles.input} transition-colors pointer-events-none select-none cursor-default`}
                  maxLength={15}
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  disabled={isJoining || isSuggestingUsername || isRateLimited}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg ${modalStyles.secondaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
                  title="Generate random username"
                >
                  <Dices size={20} className={isSuggestingUsername ? 'animate-spin' : ''} />
                </button>
              </div>
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
            className="w-full px-6 py-4 rounded-xl font-semibold bg-[#404eed] hover:bg-[#3640d9] text-white transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
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
                  className={`w-full px-6 py-3 rounded-xl font-bold ${modalStyles.secondaryButton} transition-all active:scale-95 cursor-pointer`}
                >
                  Log in
                </button>
                <button
                  type="button"
                  onClick={handleSignup}
                  className={`w-full px-6 py-3 rounded-xl font-bold ${modalStyles.secondaryButton} transition-all active:scale-95 cursor-pointer`}
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
