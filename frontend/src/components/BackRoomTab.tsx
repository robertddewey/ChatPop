'use client';

import React from 'react';
import { ChevronLeft } from 'lucide-react';

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
  design = 'pink-dream',
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
          baseClasses: 'px-2 py-3 rounded-l-md border-l-4',
          backRoomColors: 'bg-cyan-400 hover:bg-cyan-500 text-cyan-950 border-cyan-300',
          mainChatColors: 'bg-zinc-800 hover:bg-zinc-700 text-zinc-100 border-zinc-700',
          shadow: 'shadow-md',
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
        fixed right-0 top-1/2 -translate-y-1/2 z-40
        flex items-center justify-center
        ${styles.baseClasses}
        transition-all duration-300
        ${colorClasses}
        ${hasNewMessages && !isInBackRoom ? 'animate-pulse' : ''}
        ${styles.shadow}
      `}
      aria-label={isInBackRoom ? 'Return to Main Chat' : 'Open Back Room'}
    >
      <div className="flex flex-col items-center justify-center gap-1 h-24">
        {hasNewMessages && !isInBackRoom && (
          <div className="absolute top-2 right-2 w-3 h-3 bg-red-500 rounded-full border-2 border-white" />
        )}
        <ChevronLeft className={`w-4 h-4 transition-transform ${isInBackRoom ? '' : 'rotate-180'}`} />
        <span className="text-xs font-semibold whitespace-nowrap" style={{ writingMode: 'vertical-rl' }}>
          {isInBackRoom ? 'Main Chat' : 'Back Room'}
        </span>
      </div>
    </button>
  );
}
