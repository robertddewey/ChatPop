'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { BadgeCheck, ChevronDown, ChevronLeft, ChevronRight, Dices, RotateCcw } from 'lucide-react';
import type { ChatRoom } from '@/lib/api';
import { chatApi, api } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { getFingerprint } from '@/lib/usernameStorage';
import { getModalTheme } from '@/lib/modal-theme';


interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName: string;
  hasJoinedBefore: boolean;
  isBlocked?: boolean;
  isLoggedIn: boolean;
  hasReservedUsername?: boolean;
  themeIsDarkMode?: boolean;
  userAvatarUrl?: string | null;
  onAvatarChange?: (avatarUrl: string) => void;
  onJoin: (username: string, accessCode?: string, avatarSeed?: string) => void;
  onLogin?: () => void;
  onSignup?: () => void;
}

export default function JoinChatModal({
  chatRoom,
  currentUserDisplayName,
  hasJoinedBefore,
  isLoggedIn,
  hasReservedUsername = false,
  themeIsDarkMode = true,
  userAvatarUrl,
  onAvatarChange,
  onJoin,
  onLogin,
  onSignup,
}: JoinChatModalProps) {
  const router = useRouter();

  // Always force dark mode
  const forceDarkMode = true;

  // Get modal styles from centralized theme
  const mt = getModalTheme(forceDarkMode);
  const modalStyles = {
    overlay: mt.backdrop,
    container: `${mt.container} ${mt.border}`,
    title: mt.title,
    subtitle: forceDarkMode ? 'text-zinc-300' : 'text-gray-600',
    input: mt.input,
    primaryButton: mt.primaryButton,
    secondaryButton: `${mt.secondaryButton} ${forceDarkMode ? 'border border-zinc-600' : 'border border-gray-300'}`,
    divider: forceDarkMode ? 'border-zinc-600' : 'border-gray-200',
    dividerText: forceDarkMode ? 'bg-zinc-900' : 'bg-white',
    error: forceDarkMode ? 'text-red-400' : 'text-red-600',
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
  const drawerScrollRef = useRef<HTMLDivElement>(null);
  const [showScrollHint, setShowScrollHint] = useState(false);

  // Check if drawer content is scrollable and update hint visibility
  const checkScrollable = useCallback(() => {
    const el = drawerScrollRef.current;
    if (!el) return;
    const hasMoreBelow = el.scrollHeight - el.scrollTop - el.clientHeight > 8;
    setShowScrollHint(hasMoreBelow);
  }, []);

  useEffect(() => {
    // Check on mount and after a short delay (for content to render)
    const timer = setTimeout(checkScrollable, 100);
    return () => clearTimeout(timer);
  }, [checkScrollable]);
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

  // Avatar seed browsing state
  const [avatarSeeds, setAvatarSeeds] = useState<string[]>([username || currentUserDisplayName || 'anonymous']);
  const [avatarIndex, setAvatarIndex] = useState(0);

  // Whether to show avatar chevrons (only for first-time users)
  const showAvatarChevrons = !hasJoinedBefore && !isReturningUser;

  // Get the current avatar URL
  const getCurrentAvatarUrl = (): string => {
    // Returning users: use stored avatar
    if (userAvatarUrl && !showAvatarChevrons) {
      return userAvatarUrl;
    }
    // First-time users: use the currently selected seed
    return getDiceBearUrl(avatarSeeds[avatarIndex]);
  };

  // Avatar chevron handlers
  const handlePrevAvatar = () => {
    if (avatarIndex > 0) setAvatarIndex(avatarIndex - 1);
  };

  const handleNextAvatar = () => {
    if (avatarIndex < avatarSeeds.length - 1) {
      setAvatarIndex(avatarIndex + 1);
    } else {
      const newSeed = crypto.randomUUID();
      setAvatarSeeds([...avatarSeeds, newSeed]);
      setAvatarIndex(avatarIndex + 1);
    }
  };

  // Notify parent of avatar changes so MessageInput stays in sync
  // Only for first-time users browsing avatars — returning users keep their stored avatar
  useEffect(() => {
    if (showAvatarChevrons) {
      onAvatarChange?.(getDiceBearUrl(avatarSeeds[avatarIndex]));
    }
  }, [avatarSeeds, avatarIndex, showAvatarChevrons]);

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

  // Check rate limit on mount (for anonymous users only)
  useEffect(() => {
    const checkRateLimit = async () => {
      if (isLoggedIn || hasJoinedBefore) {
        // Logged-in users and returning users are exempt
        setIsRateLimited(false);
        setError('');
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
      await onJoin(finalUsername.trim(), accessCode.trim() || undefined, showAvatarChevrons ? avatarSeeds[avatarIndex] : undefined);
    } catch (err: unknown) {
      const error = err as Error;
      setError(error.message || 'Failed to join chat');
      setIsJoining(false);
    }
  };

  const handleLogin = () => {
    if (onLogin) {
      onLogin();
    } else {
      const currentPath = window.location.pathname;
      const currentSearch = window.location.search;
      const params = new URLSearchParams(currentSearch);
      params.set('auth', 'login');
      params.set('redirect', currentPath + currentSearch);
      router.push(`${currentPath}?${params.toString()}`);
    }
  };

  const handleSignup = () => {
    if (onSignup) {
      onSignup();
    } else {
      const currentPath = window.location.pathname;
      const currentSearch = window.location.search;
      const params = new URLSearchParams(currentSearch);
      params.set('auth', 'register');
      params.set('redirect', currentPath + currentSearch);
      router.push(`${currentPath}?${params.toString()}`);
    }
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

  const [isMobile, setIsMobile] = useState(false);

  // Detect mobile viewport
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // Determine the title text
  const titleContent = hasJoinedBefore || isReturningUser ? (
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
  );

  // Shared form content rendered in both mobile and desktop
  const formContent = (
    <>
      {/* Title */}
      <div className="mb-6 text-center">
        <h1 className={`text-xl font-bold ${modalStyles.title} mb-2 flex flex-wrap items-center justify-center gap-2`}>
          {titleContent}
        </h1>
        {chatRoom.is_private && (
          <p className={`text-sm ${modalStyles.subtitle}`}>
            This is a private chat
          </p>
        )}
      </div>

      {/* Avatar Preview */}
      <div className="flex items-center justify-center gap-3 mb-6">
        {showAvatarChevrons && (
          <button
            type="button"
            onClick={handlePrevAvatar}
            disabled={avatarIndex === 0 || isJoining}
            className="p-1.5 rounded-full text-zinc-400 hover:text-white transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
            aria-label="Previous avatar"
          >
            <ChevronLeft size={24} />
          </button>
        )}
        <img
          src={getCurrentAvatarUrl()}
          alt="Your avatar"
          className="w-20 h-20 rounded-full bg-zinc-700"
        />
        {showAvatarChevrons && (
          <button
            type="button"
            onClick={handleNextAvatar}
            disabled={isJoining}
            className="p-1.5 rounded-full text-zinc-400 hover:text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label="Next avatar"
          >
            <ChevronRight size={24} />
          </button>
        )}
      </div>

      {/* Form */}
      <form onSubmit={handleJoin} className="space-y-4">
        {/* Username Display or Input */}
        {hasJoinedBefore ? (
          // Returning user (logged-in or anonymous) - show locked username
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-1">
              <p className={`text-sm ${modalStyles.subtitle}`}>You&apos;ll join as: <span className={`font-semibold ${modalStyles.title}`}>{currentUserDisplayName}</span></p>
              {hasReservedUsername && (
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
            <div className="flex items-center justify-center gap-1">
              <p className={`text-sm ${modalStyles.subtitle}`}>
                Rejoining as: <span className={`font-semibold ${modalStyles.title}`}>{username}</span>
              </p>
              {hasReservedUsername && (
                <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
              )}
            </div>
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

        {/* Reserved username warning for anonymous users */}
        {!isLoggedIn && hasReservedUsername && (hasJoinedBefore || isReturningUser) && (
          <p className={`text-xs text-amber-400 text-center -mt-2`}>
            This username is reserved. Log in to continue as {currentUserDisplayName}.
          </p>
        )}

        {/* Join Button */}
        <button
          type="submit"
          disabled={isJoining || isRateLimited || (!isLoggedIn && hasReservedUsername && (hasJoinedBefore || isReturningUser))}
          className={`w-full px-6 py-3 rounded-xl font-semibold ${mt.primaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
        >
          {isJoining ? 'Joining...' : 'Join Chat'}
        </button>

        {/* Auth links (only for non-logged-in users) */}
        {!isLoggedIn && (
          <p className={`text-sm text-center mt-3 ${modalStyles.subtitle}`}>
            Have an account?{' '}
            <button type="button" onClick={handleLogin} className="font-semibold text-blue-400 hover:text-blue-300 cursor-pointer">
              Log in
            </button>
            {' · '}
            <button type="button" onClick={handleSignup} className="font-semibold text-blue-400 hover:text-blue-300 cursor-pointer">
              Sign up
            </button>
          </p>
        )}
      </form>
    </>
  );

  // Mobile: Bottom-anchored panel within chat container (keeps header accessible)
  if (isMobile) {
    return (
      <div className="absolute inset-0 z-30 flex flex-col pointer-events-none">
        {/* Backdrop - covers messages area but header stays above via z-index */}
        <div className={`absolute inset-0 ${modalStyles.overlay} pointer-events-auto`} />

        {/* Spacer — guaranteed gap between header and drawer top */}
        <div className="shrink-0 h-[108px]" />

        {/* Bottom-anchored panel — fills remaining space, content scrolls if needed */}
        <div className={`relative flex-1 flex flex-col justify-end pointer-events-auto overflow-hidden`}>
          <div
            ref={drawerScrollRef}
            onScroll={checkScrollable}
            className={`${mt.container} border-t border-x border-zinc-700 border-b border-b-zinc-800 rounded-t-2xl p-6 md:p-8 overflow-y-auto overscroll-contain max-h-full`}
          >
            {formContent}
          </div>
          {/* Scroll hint — fades out when user scrolls to bottom */}
          <div
            onClick={() => drawerScrollRef.current?.scrollTo({ top: drawerScrollRef.current.scrollHeight, behavior: 'smooth' })}
            className={`absolute bottom-0 left-0 right-0 flex justify-center py-1.5 bg-black/80 cursor-pointer transition-opacity duration-300 ${showScrollHint ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
          >
            <ChevronDown size={24} strokeWidth={3} className="text-white" />
          </div>
        </div>
      </div>
    );
  }

  // Desktop: Centered modal
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div className={`absolute inset-0 ${modalStyles.overlay}`} />

      <div className={`relative w-full max-w-md max-h-full overflow-y-auto ${modalStyles.container} ${mt.rounded} p-6 md:p-8 ${mt.shadow}`}>
        {formContent}
      </div>
    </div>
  );
}
