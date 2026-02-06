'use client';

import React, { useState } from 'react';
import { ReactionSummary } from '@/lib/api';

interface ReactionHighlightTheme {
  reaction_highlight_bg: string;
  reaction_highlight_border: string;
  reaction_highlight_text: string;
}

interface ReactionBarProps {
  reactions: ReactionSummary[];
  onReactionClick?: (emoji: string) => void;
  themeIsDarkMode?: boolean;
  highlightTheme?: ReactionHighlightTheme;
}

export default function ReactionBar({ reactions, onReactionClick, themeIsDarkMode = true, highlightTheme }: ReactionBarProps) {
  const [animatingEmoji, setAnimatingEmoji] = useState<string | null>(null);

  if (!reactions || reactions.length === 0) {
    return null;
  }

  // Show only top 3 reactions
  const topReactions = reactions.slice(0, 3);

  const handleClick = (emoji: string) => {
    // Trigger animation
    setAnimatingEmoji(emoji);
    setTimeout(() => setAnimatingEmoji(null), 200);

    // Call the click handler
    onReactionClick?.(emoji);
  };

  // Default highlight styles (fallback if no theme provided)
  const defaultHighlightBg = themeIsDarkMode ? 'bg-purple-500/20' : 'bg-purple-100';
  const defaultHighlightBorder = themeIsDarkMode ? 'border border-purple-500/50' : 'border border-purple-500';
  const defaultHighlightText = themeIsDarkMode ? 'text-zinc-200' : 'text-purple-700';

  // Use theme values if provided, otherwise fallback to defaults
  const highlightBg = highlightTheme?.reaction_highlight_bg || defaultHighlightBg;
  const highlightBorder = highlightTheme?.reaction_highlight_border || defaultHighlightBorder;
  const highlightText = highlightTheme?.reaction_highlight_text || defaultHighlightText;

  return (
    <div className="flex items-center gap-1.5 mt-1.5">
      {topReactions.map((reaction) => {
        const isAnimating = animatingEmoji === reaction.emoji;
        const hasReacted = reaction.has_reacted;

        return (
          <button
            key={reaction.emoji}
            onClick={() => handleClick(reaction.emoji)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded-full transition-all ${
              isAnimating ? 'scale-110' : 'scale-100'
            } ${
              hasReacted
                ? `${highlightBg} ${highlightBorder}`
                : themeIsDarkMode
                  ? 'bg-zinc-800/50 hover:bg-zinc-700/50 border border-zinc-700/60'
                  : 'bg-gray-100/80 hover:bg-gray-200/80 border border-gray-300/60'
            }`}
            style={{
              transition: 'transform 0.15s ease-out, background-color 0.2s, border-color 0.2s',
            }}
          >
            <span className="text-sm">{reaction.emoji}</span>
            <span
              className={`text-xs font-medium ${
                hasReacted
                  ? highlightText
                  : themeIsDarkMode ? 'text-zinc-400' : 'text-gray-600'
              }`}
            >
              {reaction.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
