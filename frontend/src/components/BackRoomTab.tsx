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
  design = 'purple-dream',
}: BackRoomTabProps) {
  if (!hasBackRoom) return null;

  // Design-specific styling
  const getDesignStyles = () => {
    switch (design) {
      case 'design2':
        return {
          baseClasses: 'px-3 py-4 rounded-l-xl',
          backRoomColors: 'bg-gradient-to-b from-purple-600 to-purple-800 hover:from-purple-700 hover:to-purple-900 text-white',
          mainChatColors: 'bg-gradient-to-b from-gray-700 to-gray-900 hover:from-gray-600 hover:to-gray-800 text-white',
          shadow: 'shadow-2xl',
        };
      case 'design3':
        return {
          baseClasses: 'px-2 py-3 rounded-l-md border-l-4',
          backRoomColors: 'bg-purple-50 hover:bg-purple-100 text-purple-900 border-purple-600',
          mainChatColors: 'bg-gray-50 hover:bg-gray-100 text-gray-900 border-gray-600',
          shadow: 'shadow-md',
        };
      default: // design1
        return {
          baseClasses: 'px-2 py-3 rounded-l-lg',
          backRoomColors: 'bg-purple-600 hover:bg-purple-700 text-white',
          mainChatColors: 'bg-gray-800 hover:bg-gray-700 text-white',
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
