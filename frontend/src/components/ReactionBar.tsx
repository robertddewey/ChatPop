'use client';

import React, { useState } from 'react';
import { ReactionSummary } from '@/lib/api';

interface ReactionHighlightTheme {
  reaction_highlight_bg: string;
  reaction_highlight_border: string;
  reaction_highlight_text: string;
}

interface UiStyles {
  reactionPillBg?: string;
  reactionPillText?: string;
  reactionHighlightBg?: string;
  reactionHighlightBorder?: string;
  reactionHighlightText?: string;
}

interface ReactionBarProps {
  reactions: ReactionSummary[];
  onReactionClick?: (emoji: string) => void;
  highlightTheme?: ReactionHighlightTheme;
  uiStyles?: UiStyles;
  maxVisible?: number;
}

function formatCount(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(count);
}

export default function ReactionBar({ reactions, onReactionClick, highlightTheme, uiStyles, maxVisible = 4 }: ReactionBarProps) {
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

  // Highlight styles: theme JSON > highlightTheme prop > dark-mode fallback
  const highlightBg = uiStyles?.reactionHighlightBg || highlightTheme?.reaction_highlight_bg || 'bg-purple-500/20';
  const highlightBorder = uiStyles?.reactionHighlightBorder || highlightTheme?.reaction_highlight_border || 'border border-purple-500/50';
  const highlightText = uiStyles?.reactionHighlightText || highlightTheme?.reaction_highlight_text || 'text-zinc-200';

  // Non-reacted pill styles
  const pillBg = uiStyles?.reactionPillBg || 'bg-zinc-800 border border-zinc-700';
  const pillText = uiStyles?.reactionPillText || 'text-zinc-400';

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
            className={`flex items-center gap-0.5 px-0.5 flex-shrink-0 ${
              isAnimating ? 'scale-110' : 'scale-100'
            }`}
            style={{
              transition: 'transform 0.15s ease-out, background-color 0.2s, border-color 0.2s',
            }}
          >
            <span className="text-xs">{reaction.emoji}</span>
            <span
              className={`text-[10px] font-medium ${
                hasReacted ? highlightText : pillText
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
