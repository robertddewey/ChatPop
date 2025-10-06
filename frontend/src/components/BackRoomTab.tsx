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
          baseClasses: 'px-1 py-4 rounded-l-xl',
          backRoomColors: 'bg-gradient-to-br from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 text-white border-l-[3px] border-t-[0.5px] border-b border-cyan-300',
          mainChatColors: 'bg-gradient-to-br from-slate-600 to-slate-800 hover:from-slate-500 hover:to-slate-700 text-white border-l-[3px] border-t-[0.5px] border-b border-slate-500',
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
        flex flex-col items-center justify-center gap-1
        ${styles.baseClasses}
        transition-all duration-300
        ${colorClasses}
        ${hasNewMessages && !isInBackRoom ? 'animate-pulse' : ''}
        ${styles.shadow}
        h-auto min-h-[90px]
      `}
      aria-label={isInBackRoom ? 'Return to Main Chat' : 'Open Back Room'}
    >
      {hasNewMessages && !isInBackRoom && (
        <div className="absolute top-2 right-2 w-3 h-3 bg-red-500 rounded-full border-2 border-white animate-pulse" />
      )}

      {isInBackRoom ? (
        <MessageSquare className="w-6 h-6 stroke-[2.5]" />
      ) : (
        <Gamepad2 className="w-6 h-6 stroke-[2.5] rotate-90" />
      )}

      <div className="w-8 h-[1px] bg-current opacity-30 my-1" />

      <ChevronLeft className={`w-5 h-5 transition-transform ${isInBackRoom ? '' : 'rotate-180'} stroke-[2.5]`} />
    </button>
  );
}
