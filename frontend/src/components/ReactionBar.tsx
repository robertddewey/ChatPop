'use client';

import React from 'react';
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
  // Filter out reactions with no count (e.g., after removal via WebSocket re-fetch)
  const validReactions = reactions?.filter(r => r.count > 0) || [];

  // Show user's reactions first (by popularity), then top others, capped at maxVisible
  const sorted = [...validReactions].sort((a, b) => b.count - a.count);
  const userReactions = sorted.filter(r => r.has_reacted);
  const otherReactions = sorted.filter(r => !r.has_reacted);
  const topReactions = [...userReactions, ...otherReactions].slice(0, Math.max(maxVisible, userReactions.length));

  // Highlight styles: theme JSON > highlightTheme prop > dark-mode fallback
  const highlightBg = uiStyles?.reactionHighlightBg || highlightTheme?.reaction_highlight_bg || 'bg-purple-500/20';
  const highlightBorder = uiStyles?.reactionHighlightBorder || highlightTheme?.reaction_highlight_border || 'border border-purple-500/50';
  const highlightText = uiStyles?.reactionHighlightText || highlightTheme?.reaction_highlight_text || 'text-zinc-200';

  // Non-reacted pill styles
  const pillBg = uiStyles?.reactionPillBg || 'bg-zinc-800 border border-zinc-700';
  const pillText = uiStyles?.reactionPillText || 'text-zinc-400';

  // Resolve highlight text color to a hex value for inline style (Safari !important workaround)
  const highlightTextColor = (() => {
    const cls = highlightText.replace(/^!/, '');
    const colorMap: Record<string, string> = {
      'text-purple-300': '#d8b4fe',
      'text-purple-400': '#c084fc',
      'text-zinc-200': '#e4e4e7',
      'text-white': '#ffffff',
    };
    return colorMap[cls] || undefined;
  })();

  const pillTextColor = (() => {
    const cls = pillText.replace(/^!/, '');
    const colorMap: Record<string, string> = {
      'text-zinc-400': '#a1a1aa',
      'text-zinc-500': '#71717a',
      'text-zinc-600': '#52525b',
    };
    return colorMap[cls] || undefined;
  })();

  // Always render the container to prevent browser paint artifacts
  // when reaction buttons with shadow-lg are removed from DOM
  return (
    <div
      className="flex-1 flex items-center gap-1 overflow-x-auto scrollbar-hide min-w-0 touch-pan-x"
    >
      {topReactions.map((reaction) => {
        const hasReacted = reaction.has_reacted;

        return (
          <button
            key={reaction.emoji}
            onClick={() => onReactionClick?.(reaction.emoji)}
            className={`flex items-center gap-0.5 px-1 py-0.5 rounded-full flex-shrink-0 ${
              hasReacted ? `${highlightBg} ${highlightBorder}` : pillBg
            }`}
          >
            <span className="text-[10px] leading-none">{reaction.emoji}</span>
            <span
              className="text-[10px] font-medium"
              style={{ color: hasReacted ? highlightTextColor : pillTextColor }}
            >
              {formatCount(reaction.count)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
