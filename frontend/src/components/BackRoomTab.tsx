'use client';

import React from 'react';
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
  if (!hasBackRoom) return null;

  // Design-specific styling
  const getDesignStyles = () => {
    switch (design) {
      case 'pink-dream':
        return {
          baseClasses: 'px-2 py-3 rounded-l-lg',
          backRoomColors: 'bg-gradient-to-b from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white',
          mainChatColors: 'bg-gradient-to-b from-pink-100 to-pink-200 dark:from-indigo-800 dark:to-indigo-900 hover:from-pink-200 hover:to-pink-300 dark:hover:from-indigo-700 dark:hover:to-indigo-800 text-pink-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'ocean-blue':
        return {
          baseClasses: 'px-2 py-3 rounded-l-lg',
          backRoomColors: 'bg-gradient-to-b from-blue-500 to-cyan-600 hover:from-blue-600 hover:to-cyan-700 text-white',
          mainChatColors: 'bg-gradient-to-b from-blue-100 to-cyan-100 dark:from-gray-700 dark:to-gray-800 hover:from-blue-200 hover:to-cyan-200 dark:hover:from-gray-600 dark:hover:to-gray-700 text-blue-900 dark:text-white',
          shadow: 'shadow-lg',
        };
      case 'dark-mode':
        return {
          baseClasses: 'p-2 rounded-full',
          backRoomColors: 'text-white hover:text-zinc-200',
          mainChatColors: 'text-white hover:text-zinc-200',
          shadow: '',
        };
      default:
        return {
          baseClasses: 'px-2 py-3 rounded-l-lg',
          backRoomColors: 'bg-gradient-to-b from-pink-500 to-rose-600 hover:from-pink-600 hover:to-rose-700 text-white',
          mainChatColors: 'bg-gradient-to-b from-pink-100 to-pink-200 dark:from-indigo-800 dark:to-indigo-900 hover:from-pink-200 hover:to-pink-300 dark:hover:from-indigo-700 dark:hover:to-indigo-800 text-pink-900 dark:text-white',
          shadow: 'shadow-lg',
        };
    }
  };

  const styles = getDesignStyles();
  const colorClasses = isInBackRoom ? styles.mainChatColors : styles.backRoomColors;

  return (
    <button
      onClick={onClick}
      className={`
        fixed right-0 top-1/2 -translate-y-1/2 z-50
        transition-all duration-300
        ${styles.baseClasses}
        ${colorClasses}
        ${hasNewMessages && !isInBackRoom ? 'animate-pulse' : ''}
      `}
      aria-label={isInBackRoom ? 'Return to Main Chat' : 'Open Back Room'}
    >
      {hasNewMessages && !isInBackRoom && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full border-2 border-zinc-950 animate-pulse" />
      )}

      {isInBackRoom ? (
        <MessageSquare className="w-10 h-10 stroke-[2.5]" />
      ) : (
        <Gamepad2 className="w-10 h-10 stroke-[2.5] rotate-90" />
      )}
    </button>
  );
}
