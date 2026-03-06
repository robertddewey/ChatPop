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
  fullWidth?: boolean;
  maxVisible?: number;
}

function formatCount(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(count);
}

export default function ReactionBar({ reactions, onReactionClick, themeIsDarkMode = true, highlightTheme, fullWidth, maxVisible = 4 }: ReactionBarProps) {
  const [animatingEmoji, setAnimatingEmoji] = useState<string | null>(null);

  // Filter out reactions with no count (e.g., after removal via WebSocket re-fetch)
  const validReactions = reactions?.filter(r => r.count > 0) || [];

  // Show top N by popularity + user's own reactions (deduped), sorted by count
  const sorted = [...validReactions].sort((a, b) => b.count - a.count);
  const topN = sorted.slice(0, maxVisible);
  const topNEmojis = new Set(topN.map(r => r.emoji));
  const userExtras = sorted.filter(r => r.has_reacted && !topNEmojis.has(r.emoji));
  const topReactions = [...topN, ...userExtras].sort((a, b) => b.count - a.count);

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

  // Always render the container to prevent browser paint artifacts
  // when reaction buttons with shadow-lg are removed from DOM
  return (
    <div
      className="flex-1 flex items-center gap-1 overflow-x-auto scrollbar-hide min-w-0 touch-pan-x"
    >
      {topReactions.map((reaction) => {
        const isAnimating = animatingEmoji === reaction.emoji;
        const hasReacted = reaction.has_reacted;

        return (
          <button
            key={reaction.emoji}
            onClick={() => handleClick(reaction.emoji)}
            className={`flex items-center gap-0.5 rounded-full px-1.5 py-0.5 shadow-lg flex-shrink-0 ${
              isAnimating ? 'scale-110' : 'scale-100'
            } ${
              hasReacted
                ? `${highlightBg} ${highlightBorder}`
                : themeIsDarkMode
                  ? 'bg-zinc-800 border border-zinc-700'
                  : 'bg-white border border-gray-200'
            }`}
            style={{
              transition: 'transform 0.15s ease-out, background-color 0.2s, border-color 0.2s',
            }}
          >
            <span className="text-xs">{reaction.emoji}</span>
            <span
              className={`text-[10px] font-medium ${
                hasReacted
                  ? highlightText
                  : themeIsDarkMode ? 'text-zinc-400' : 'text-gray-600'
              }`}
            >
              {formatCount(reaction.count)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
