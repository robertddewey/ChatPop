'use client';

import React from 'react';
import { ReactionSummary } from '@/lib/api';

interface ReactionBarProps {
  reactions: ReactionSummary[];
  onReactionClick?: (emoji: string) => void;
  themeIsDarkMode?: boolean;
}

export default function ReactionBar({ reactions, onReactionClick, themeIsDarkMode = true }: ReactionBarProps) {
  if (!reactions || reactions.length === 0) {
    return null;
  }

  // Show only top 3 reactions
  const topReactions = reactions.slice(0, 3);

  return (
    <div className="flex items-center gap-2 mt-2">
      {topReactions.map((reaction) => (
        <button
          key={reaction.emoji}
          onClick={() => onReactionClick?.(reaction.emoji)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm transition-all active:scale-95 ${
            themeIsDarkMode
              ? 'bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700'
              : 'bg-gray-100/80 hover:bg-gray-200/80 border border-gray-300'
          }`}
        >
          <span className="text-base">{reaction.emoji}</span>
          <span
            className={`font-medium ${
              themeIsDarkMode ? 'text-zinc-300' : 'text-gray-700'
            }`}
          >
            {reaction.count}
          </span>
        </button>
      ))}
    </div>
  );
}
