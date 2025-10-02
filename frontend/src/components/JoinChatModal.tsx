'use client';

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import type { ChatRoom } from '@/lib/api';

interface JoinChatModalProps {
  chatRoom: ChatRoom;
  currentUserDisplayName?: string;
  storedUsername?: string;
  isLoggedIn: boolean;
  design?: 'design1' | 'design2' | 'design3';
  onJoin: (username: string, accessCode?: string) => void;
}

// Theme configurations
const modalStyles = {
  design1: {
    overlay: 'bg-black/5',
    container: 'bg-gradient-to-br from-purple-50 to-pink-50 dark:from-gray-900 dark:to-gray-800',
    title: 'text-gray-900 dark:text-gray-100',
    subtitle: 'text-gray-600 dark:text-gray-400',
    input: 'bg-white dark:bg-gray-800 border-2 border-purple-200 dark:border-purple-700 text-gray-900 dark:text-gray-100 focus:border-purple-500 dark:focus:border-purple-400',
    primaryButton: 'bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white',
    secondaryButton: 'bg-white dark:bg-gray-800 border-2 border-purple-200 dark:border-purple-700 text-purple-600 dark:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/20',
    divider: 'border-purple-200 dark:border-purple-700',
    error: 'text-red-600 dark:text-red-400',
  },
  design2: {
    overlay: 'bg-black/5',
    container: 'bg-gradient-to-br from-sky-50 to-cyan-50 dark:from-gray-900 dark:to-gray-800',
    title: 'text-gray-900 dark:text-gray-100',
    subtitle: 'text-gray-600 dark:text-gray-400',
    input: 'bg-white dark:bg-gray-800 border-2 border-blue-200 dark:border-blue-700 text-gray-900 dark:text-gray-100 focus:border-blue-500 dark:focus:border-blue-400',
    primaryButton: 'bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white',
    secondaryButton: 'bg-white dark:bg-gray-800 border-2 border-blue-200 dark:border-blue-700 text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/20',
    divider: 'border-blue-200 dark:border-blue-700',
    error: 'text-red-600 dark:text-red-400',
  },
  design3: {
    overlay: 'bg-black/5',
    container: 'bg-zinc-900',
    title: 'text-zinc-50',
    subtitle: 'text-zinc-400',
    input: 'bg-zinc-800 border border-zinc-600 text-zinc-50 focus:border-cyan-400',
    primaryButton: 'bg-cyan-500 hover:bg-cyan-400 text-zinc-900',
    secondaryButton: 'bg-zinc-700 border border-zinc-600 text-zinc-50 hover:bg-zinc-600',
    divider: 'border-zinc-600',
    error: 'text-red-400',
  },
};

export default function JoinChatModal({
  chatRoom,
  currentUserDisplayName,
  storedUsername,
  isLoggedIn,
  design = 'design1',
  onJoin,
}: JoinChatModalProps) {
  const router = useRouter();
  const styles = modalStyles[design];

  const [username, setUsername] = useState(storedUsername || '');
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

  const displayName = isLoggedIn ? currentUserDisplayName : storedUsername;
  const isReturningUser = !!displayName;

  const handleJoin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Initialize AudioContext during user gesture (button click)
    initAudioContext();

    // Validation
    if (!isLoggedIn && !username.trim()) {
      setError('Please enter a username');
      return;
    }

    if (chatRoom.is_private && !accessCode.trim()) {
      setError('This chat requires an access code');
      return;
    }

    setIsJoining(true);

    try {
      const finalUsername = isLoggedIn ? currentUserDisplayName! : username.trim();
      await onJoin(finalUsername, accessCode.trim() || undefined);
    } catch (err: any) {
      setError(err.message || 'Failed to join chat');
      setIsJoining(false);
    }
  };

  const handleLogin = () => {
    const currentPath = window.location.pathname;
    const searchParams = window.location.search;
    router.push(`/login?redirect=${encodeURIComponent(currentPath + searchParams)}`);
  };

  const handleSignup = () => {
    const currentPath = window.location.pathname;
    const searchParams = window.location.search;
    router.push(`/register?redirect=${encodeURIComponent(currentPath + searchParams)}`);
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
          <h1 className={`text-2xl font-bold ${styles.title} mb-2`}>
            {isReturningUser ? `Welcome back, ${displayName}!` : `Join ${chatRoom.name}`}
          </h1>
          {chatRoom.is_private && (
            <p className={`text-sm ${styles.subtitle}`}>
              This is a private chat
            </p>
          )}
        </div>

        {/* Form */}
        <form onSubmit={handleJoin} className="space-y-4">
          {/* Username Input (only for non-logged-in users) */}
          {!isLoggedIn && !isReturningUser && (
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
