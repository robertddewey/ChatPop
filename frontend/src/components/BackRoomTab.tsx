'use client';

import React, { useState, useEffect } from 'react';
import { ChevronLeft, Gamepad2, MessageSquare } from 'lucide-react';

interface BackRoomTabProps {
  isInBackRoom: boolean;
  hasBackRoom: boolean;
  onClick: () => void;
  hasNewMessages?: boolean;
  design?: string;
}

export default function BackRoomTab({
  isInBackRoom,
  hasBackRoom,
  onClick,
  hasNewMessages = false,
  design = 'dark-mode',
}: BackRoomTabProps) {
  const [showInitialBounce, setShowInitialBounce] = useState(false);

  useEffect(() => {
    if (hasBackRoom) {
      // Trigger bounce animation after component mounts
      const timer = setTimeout(() => {
        setShowInitialBounce(true);
        // Remove the animation class after it completes
        const removeTimer = setTimeout(() => setShowInitialBounce(false), 1000);
        return () => clearTimeout(removeTimer);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [hasBackRoom]);

  if (!hasBackRoom) return null;

  // Design-specific styling
  const getDesignStyles = () => {
    switch (design) {
      case 'pink-dream':
        return {
          baseClasses: 'p-3 rounded-2xl',
          backRoomColors: 'bg-gradient-to-br from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white',
          mainChatColors: 'bg-gradient-to-br from-pink-100 to-pink-200 dark:from-indigo-800 dark:to-indigo-900 hover:from-pink-200 hover:to-pink-300 dark:hover:from-indigo-700 dark:hover:to-indigo-800 text-pink-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'ocean-blue':
        return {
          baseClasses: 'p-3 rounded-2xl',
          backRoomColors: 'bg-gradient-to-br from-blue-500 to-cyan-600 hover:from-blue-600 hover:to-cyan-700 text-white',
          mainChatColors: 'bg-gradient-to-br from-blue-100 to-cyan-100 dark:from-gray-700 dark:to-gray-800 hover:from-blue-200 hover:to-cyan-200 dark:hover:from-gray-600 dark:hover:to-gray-700 text-blue-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'dark-mode':
        return {
          baseClasses: 'p-3 rounded-2xl',
          backRoomColors: 'bg-gradient-to-br from-zinc-700 to-zinc-800 hover:from-zinc-600 hover:to-zinc-700 text-white',
          mainChatColors: 'bg-gradient-to-br from-zinc-700 to-zinc-800 hover:from-zinc-600 hover:to-zinc-700 text-white',
          shadow: 'shadow-lg',
        };
      default:
        return {
          baseClasses: 'p-3 rounded-2xl',
          backRoomColors: 'bg-gradient-to-br from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white',
          mainChatColors: 'bg-gradient-to-br from-pink-100 to-pink-200 dark:from-indigo-800 dark:to-indigo-900 hover:from-pink-200 hover:to-pink-300 dark:hover:from-indigo-700 dark:hover:to-indigo-800 text-pink-900 dark:text-white',
          shadow: 'shadow-lg',
        };
    }
  };

  const styles = getDesignStyles();
  const colorClasses = isInBackRoom ? styles.mainChatColors : styles.backRoomColors;

  return (
    <button
      onClick={onClick}
      style={showInitialBounce ? { animation: 'pulsate 1s ease-in-out' } : undefined}
      className={`
        fixed right-[2.5%] top-1/2 -translate-y-1/2 z-50
        transition-all duration-300
        active:scale-90 active:rotate-12
        ${styles.baseClasses}
        ${colorClasses}
        ${styles.shadow}
        ${hasNewMessages && !isInBackRoom ? 'animate-pulse' : ''}
      `}
      aria-label={isInBackRoom ? 'Return to Main Chat' : 'Open Back Room'}
    >
      <style jsx>{`
        @keyframes pulsate {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }
      `}</style>
      {hasNewMessages && !isInBackRoom && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-white shadow-md animate-pulse" />
      )}

      {isInBackRoom ? (
        <MessageSquare className="w-8 h-8 stroke-[1.5]" />
      ) : (
        <Gamepad2 className="w-8 h-8 stroke-[1.5] rotate-90" />
      )}
    </button>
  );
}
