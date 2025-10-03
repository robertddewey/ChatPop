'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { BadgeCheck } from 'lucide-react';
import type { ChatRoom } from '@/lib/api';

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
      ? 'bg-zinc-700 border border-zinc-600 text-zinc-50 hover:bg-zinc-600'
      : 'bg-white border-2 border-gray-300 text-gray-700 hover:bg-gray-50',
    divider: isDark ? 'border-zinc-600' : 'border-gray-300',
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

  const [username, setUsername] = useState(currentUserDisplayName || '');
  const [accessCode, setAccessCode] = useState('');
  const [error, setError] = useState('');
  const [isJoining, setIsJoining] = useState(false);
  const audioContextRef = React.useRef<AudioContext>();

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

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Initialize AudioContext during user gesture (button click)
    initAudioContext();

    // Validation
    if (!username.trim()) {
      setError('Please enter a username');
      return;
    }

    if (chatRoom.is_private && !accessCode.trim()) {
      setError('This chat requires an access code');
      return;
    }

    setIsJoining(true);

    try {
      await onJoin(username.trim(), accessCode.trim() || undefined);
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
    router.push(`${currentPath}?${params.toString()}`);
  };

  const handleSignup = () => {
    const currentPath = window.location.pathname;
    const currentSearch = window.location.search;
    const params = new URLSearchParams(currentSearch);
    params.set('auth', 'register');
    params.set('redirect', currentPath + currentSearch);
    router.push(`${currentPath}?${params.toString()}`);
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
          <h1 className={`text-2xl font-bold ${styles.title} mb-2 flex items-center justify-center gap-2`}>
            {hasJoinedBefore ? (
              <>
                Welcome back, {currentUserDisplayName}!
                {hasReservedUsername && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={20} />
                )}
              </>
            ) : isLoggedIn ? (
              <>
                Come join us, {currentUserDisplayName}
                {hasReservedUsername && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={20} />
                )}
              </>
            ) : (
              `Join ${chatRoom.name}`
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
          {isLoggedIn && hasJoinedBefore ? (
            // Logged-in returning user - show locked username
            <div className="text-center">
              <p className={`text-sm ${styles.subtitle} mb-2`}>You'll join as:</p>
              <div className="flex items-center justify-center gap-2">
                <p className={`text-lg font-semibold ${styles.title}`}>{currentUserDisplayName}</p>
                {hasReservedUsername && (
                  <BadgeCheck className="text-blue-500 flex-shrink-0" size={18} />
                )}
              </div>
            </div>
          ) : isLoggedIn ? (
            // Logged-in first-time user - editable username pre-filled with reserved_username
            <div>
              <label className={`block text-sm font-medium ${styles.subtitle} mb-2`}>
                Username for this chat
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className={`w-full px-4 py-3 rounded-xl ${styles.input} transition-colors focus:outline-none`}
                maxLength={30}
                disabled={isJoining}
              />
            </div>
          ) : (
            // Anonymous user - always show input
            <div>
              <label className={`block text-sm font-medium ${styles.subtitle} mb-2`}>
                Choose a username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                className={`w-full px-4 py-3 rounded-xl ${styles.input} transition-colors focus:outline-none`}
                maxLength={30}
                disabled={isJoining}
              />
            </div>
          )}

          {/* Access Code Input (only for private chats) */}
          {chatRoom.is_private && (
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
            <p className={`text-sm ${styles.error} text-center`}>
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
              <div className="relative my-6">
                <div className={`absolute inset-0 flex items-center`}>
                  <div className={`w-full border-t ${styles.divider}`} />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className={`px-4 ${styles.container} ${styles.subtitle}`}>
                    or
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <button
                  type="button"
                  onClick={handleLogin}
                  className={`w-full px-6 py-3 rounded-xl font-medium ${styles.secondaryButton} transition-all active:scale-95`}
                >
                  Log in
                </button>
                <button
                  type="button"
                  onClick={handleSignup}
                  className={`w-full px-6 py-3 rounded-xl font-medium ${styles.secondaryButton} transition-all active:scale-95`}
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
