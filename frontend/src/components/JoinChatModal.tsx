'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { BadgeCheck, Ban, ChevronDown, ChevronLeft, ChevronRight, Crown, Dices, RotateCcw, Spotlight, HatGlasses } from 'lucide-react';
import type { ChatRoom, AnonymousParticipationInfo } from '@/lib/api';
import { chatApi, api } from '@/lib/api';
import { validateUsername } from '@/lib/validation';
import { getModalTheme } from '@/lib/modal-theme';
import { verifyHuman } from '@/lib/turnstile';


interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName: string;
  hasJoinedBefore: boolean;
  isBlocked?: boolean;
  isLoggedIn: boolean;
  hasReservedUsername?: boolean;
  themeIsDarkMode?: boolean;
  userAvatarUrl?: string | null;
  anonymousParticipations?: AnonymousParticipationInfo[];
  spotlightUsernames?: Set<string>;
  registeredAvatarUrl?: string | null;
  onAvatarChange?: (avatarUrl: string) => void;
  onIdentityChange?: (identity: { username: string; avatarUrl: string | null; hasReservedUsername: boolean }) => void;
  onJoin: (username: string, accessCode?: string, avatarSeed?: string) => Promise<{ error?: string } | void>;
  onLogin?: () => void;
  onSignup?: () => void;
}

export default function JoinChatModal({
  chatRoom,
  currentUserDisplayName,
  hasJoinedBefore,
  isBlocked = false,
  isLoggedIn,
  hasReservedUsername = false,
  themeIsDarkMode = true,
  userAvatarUrl,
  onAvatarChange,
  anonymousParticipations,
  spotlightUsernames,
  registeredAvatarUrl,
  onIdentityChange,
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

  // Restore persisted state from sessionStorage (survives auth modal navigation)
  const storageKey = `joinModal_${chatRoom.code}`;
  const getPersistedState = () => {
    if (typeof window === 'undefined') return null;
    try {
      const stored = sessionStorage.getItem(storageKey);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  };
  const persisted = useRef(getPersistedState());

  // Initialize username with reserved username for logged-in users, or persisted state
  const [username, setUsername] = useState(
    isLoggedIn && hasReservedUsername && currentUserDisplayName
      ? currentUserDisplayName
      : persisted.current?.username || ''
  );
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [isJoining, setIsJoining] = useState(false);



  const [isSuggestingUsername, setIsSuggestingUsername] = useState(false);
  const [isValidatingUsername, setIsValidatingUsername] = useState(false);
  const [usernameError, setUsernameError] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState(false);
  const [generationRemaining, setGenerationRemaining] = useState<number | null>(null);
  const [suggestionRemaining, setSuggestionRemaining] = useState<number | null>(null);
  const [usernameSource, setUsernameSource] = useState<'manual' | 'dice'>(persisted.current?.usernameSource || 'manual');
  const [diceUsername, setDiceUsername] = useState<string | null>(persisted.current?.diceUsername || null);
  const [isReturningUser, setIsReturningUser] = useState(false);
  // Identity chooser state (when logged-in user has prior anonymous participation(s))
  const anonList = anonymousParticipations || [];
  const showIdentityChooser = isLoggedIn && anonList.length > 0 && !hasJoinedBefore;
  // selectedIdentity: 'registered' | `anonymous:${index}`
  const [selectedIdentity, setSelectedIdentity] = useState<string>('registered');
  // Notify parent when identity selection changes (updates MessageInput avatar/badge)
  // Skip the initial render — only fire when user actively toggles identity
  const identityInitialized = useRef(false);
  useEffect(() => {
    if (!showIdentityChooser || !onIdentityChange) {
      identityInitialized.current = false;
      return;
    }
    if (!identityInitialized.current) {
      identityInitialized.current = true;
      return;
    }
    if (selectedIdentity.startsWith('anonymous:')) {
      const idx = parseInt(selectedIdentity.split(':')[1], 10);
      const anon = anonList[idx];
      if (anon) {
        onIdentityChange({
          username: anon.username,
          avatarUrl: anon.avatar_url,
          hasReservedUsername: false,
        });
      }
    } else {
      onIdentityChange({
        username: currentUserDisplayName,
        avatarUrl: registeredAvatarUrl || userAvatarUrl || null,
        hasReservedUsername: hasReservedUsername,
      });
    }
  }, [selectedIdentity, showIdentityChooser, onIdentityChange, anonList, currentUserDisplayName, registeredAvatarUrl, userAvatarUrl, hasReservedUsername]);

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

  // Avatar seed browsing state (restore from persisted if available)
  const [avatarSeeds, setAvatarSeeds] = useState<string[]>(
    persisted.current?.avatarSeeds || [username || currentUserDisplayName || crypto.randomUUID()]
  );
  const [avatarIndex, setAvatarIndex] = useState(persisted.current?.avatarIndex || 0);

  // Whether to show avatar chevrons (only for first-time users, not identity chooser)
  const showAvatarChevrons = !hasJoinedBefore && !isReturningUser && !showIdentityChooser;

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
  }, [avatarSeeds, avatarIndex, showAvatarChevrons, onAvatarChange]);

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

    // Identity chooser: use the selected identity's username
    let finalUsername = username.trim() || currentUserDisplayName || '';
    if (showIdentityChooser && selectedIdentity.startsWith('anonymous:')) {
      const idx = parseInt(selectedIdentity.split(':')[1], 10);
      const anon = anonList[idx];
      if (anon) finalUsername = anon.username;
    }

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

    const result = await onJoin(finalUsername.trim(), accessCode.trim() || undefined, showAvatarChevrons ? avatarSeeds[avatarIndex] : undefined);

    if (!result) {
      // Success — clean up persisted state
      try { sessionStorage.removeItem(storageKey); } catch { /* ignore */ }
      return;
    }

    // General error
    setError(result.error || 'Failed to join chat');
    setIsJoining(false);
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
      const result = await chatApi.suggestUsername(chatRoom.code, chatRoom.host.reserved_username || undefined);

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
  // Waits for Turnstile verification first (suggest-username is a protected endpoint)
  // Skip if we already have a persisted username (returning from auth modal)
  useEffect(() => {
    if (!isLoggedIn && !hasJoinedBefore && !persisted.current?.username) {
      verifyHuman().then((verified) => {
        if (verified) handleSuggestUsername();
      });
    }
  }, [isLoggedIn, hasJoinedBefore]);

  // Persist join modal state to sessionStorage so it survives auth modal navigation
  useEffect(() => {
    if (!username) return;
    try {
      sessionStorage.setItem(storageKey, JSON.stringify({
        username, usernameSource, diceUsername, avatarSeeds, avatarIndex,
      }));
    } catch { /* ignore */ }
  }, [username, usernameSource, diceUsername, avatarSeeds, avatarIndex, storageKey]);

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
  ) : showIdentityChooser ? (
    'Welcome back!'
  ) : isLoggedIn ? (
    <>
      <span>Come join us,</span>
      <span className="inline-flex items-center gap-1 whitespace-nowrap">
        {currentUserDisplayName}
        {hasReservedUsername ? (
          <BadgeCheck className="text-blue-500 flex-shrink-0" size={20} />
        ) : (
          <HatGlasses className="flex-shrink-0" size={20} style={{ color: '#ef4444' }} />
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

      {/* Avatar Preview (hidden when identity chooser is shown — cards have their own avatars) */}
      {!showIdentityChooser && <div className="flex items-center justify-center gap-3 mb-6">
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
      </div>}

      {/* Form */}
      <form data-join-form onSubmit={handleJoin} className="space-y-4">
        {/* Identity Chooser — logged-in user with prior anonymous participation */}
        {showIdentityChooser ? (
          <div className="space-y-3">
            <p className={`text-sm text-center ${modalStyles.subtitle} mb-1`}>
              Choose how to join this chat:
            </p>

            {/* Anonymous identity cards (one per linked anonymous participation) */}
            {anonList.map((anon, idx) => {
              const key = `anonymous:${idx}`;
              const isSelected = selectedIdentity === key;
              return (
                <button
                  key={anon.participation_id || `${anon.username}-${idx}`}
                  type="button"
                  onClick={() => setSelectedIdentity(key)}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer ${
                    isSelected
                      ? 'border-cyan-500 bg-cyan-500/10'
                      : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-500'
                  }`}
                >
                  <div className="relative flex-shrink-0">
                    <img
                      src={anon.avatar_url || ''}
                      alt="Anonymous avatar"
                      className="w-12 h-12 rounded-full bg-zinc-700"
                    />
                    {spotlightUsernames?.has(anon.username) && (
                      <Spotlight
                        size={14}
                        fill="currentColor"
                        className={`absolute -top-1.5 -left-1 ${chatRoom.theme?.spotlight_icon_color || 'text-yellow-400'}`}
                      />
                    )}
                    <HatGlasses size={12} className="absolute -bottom-0.5 -right-0.5" style={{ color: '#ef4444' }} />
                  </div>
                  <div className="text-left min-w-0">
                    <div className="flex items-center gap-1">
                      <p className={`font-semibold ${modalStyles.title} truncate`}>
                        {anon.username}
                      </p>
                      <HatGlasses className="flex-shrink-0" size={14} style={{ color: '#ef4444' }} />
                    </div>
                    <p className={`text-xs ${modalStyles.subtitle}`}>
                      Continue anonymously
                    </p>
                  </div>
                  {isSelected && (
                    <div className="ml-auto flex-shrink-0 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center">
                      <div className="w-2 h-2 rounded-full bg-white" />
                    </div>
                  )}
                </button>
              );
            })}

            {/* Registered identity card */}
            <button
              type="button"
              onClick={() => setSelectedIdentity('registered')}
              className={`w-full flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer ${
                selectedIdentity === 'registered'
                  ? 'border-cyan-500 bg-cyan-500/10'
                  : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-500'
              }`}
            >
              <div className="relative flex-shrink-0">
                <img
                  src={registeredAvatarUrl || userAvatarUrl || ''}
                  alt="Registered avatar"
                  className="w-12 h-12 rounded-full bg-zinc-700"
                />
                {chatRoom.host.reserved_username?.toLowerCase() === currentUserDisplayName.toLowerCase() ? (
                  <Crown size={14} fill="currentColor" className={`absolute -top-1.5 -left-1 ${chatRoom.theme?.crown_icon_color || 'text-amber-400'}`} style={{ transform: 'rotate(-30deg)' }} />
                ) : spotlightUsernames?.has(currentUserDisplayName) && (
                  <Spotlight
                    size={14}
                    fill="currentColor"
                    className={`absolute -top-1.5 -left-1 ${chatRoom.theme?.spotlight_icon_color || 'text-yellow-400'}`}
                  />
                )}
                <BadgeCheck size={12} className="absolute -bottom-0.5 -right-0.5 rounded-full" style={{ color: '#3b82f6', backgroundColor: '#18181b' }} />
              </div>
              <div className="text-left min-w-0">
                <div className="flex items-center gap-1">
                  <p className={`font-semibold ${modalStyles.title} truncate`}>
                    {currentUserDisplayName}
                  </p>
                  {hasReservedUsername ? (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={16} />
                  ) : (
                    <HatGlasses className="flex-shrink-0" size={16} style={{ color: '#ef4444' }} />
                  )}
                </div>
                <p className={`text-xs ${modalStyles.subtitle}`}>
                  Join with your account
                </p>
              </div>
              {selectedIdentity === 'registered' && (
                <div className="ml-auto flex-shrink-0 w-5 h-5 rounded-full bg-cyan-500 flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-white" />
                </div>
              )}
            </button>
          </div>
        ) : hasJoinedBefore ? (
          // Returning user (logged-in or anonymous) - show locked username
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-1">
              <p className={`text-sm ${modalStyles.subtitle}`}>You&apos;ll join as: <span className={`font-semibold ${modalStyles.title}`}>{currentUserDisplayName}</span></p>
              {hasReservedUsername ? (
                <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
              ) : (
                <HatGlasses className="flex-shrink-0" size={18} style={{ color: '#ef4444' }} />
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
              {hasReservedUsername ? (
                <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
              ) : (
                <HatGlasses className="flex-shrink-0" size={18} style={{ color: '#ef4444' }} />
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
                disabled={isJoining || isSuggestingUsername}
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

        {/* Banned message OR Join Button */}
        {isBlocked ? (
          <div className="text-center py-4 space-y-2">
            <div className="flex items-center justify-center gap-2 text-red-400">
              <Ban size={20} />
              <span className="font-semibold">You have been banned from this chat</span>
            </div>
            <p className="text-xs text-zinc-500">
              You can no longer join or send messages in this chat.
            </p>
          </div>
        ) : (
          <button
            type="submit"
            disabled={isJoining || (!isLoggedIn && hasReservedUsername && (hasJoinedBefore || isReturningUser))}
            className={`w-full px-6 py-3 rounded-xl font-semibold ${mt.primaryButton} transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer`}
          >
            {isJoining ? 'Joining...' : 'Join Chat'}
          </button>
        )}

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
          <button
            onClick={() => drawerScrollRef.current?.scrollTo({ top: drawerScrollRef.current.scrollHeight, behavior: 'smooth' })}
            className={`absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full p-2 shadow-lg bg-zinc-800/90 text-zinc-200 border border-zinc-700 transition-opacity duration-300 ${showScrollHint ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
          >
            <ChevronDown size={20} />
          </button>
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
