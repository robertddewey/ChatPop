'use client';

import React, { useState } from 'react';

interface ReactionStyle {
  name: string;
  description: string;
  containerClass: string;
  emojiClass: string;
  countClass: string;
  gapClass: string;
  highlightedContainerClass: string;
}

const reactionStyles: ReactionStyle[] = [
  {
    name: 'Current (ChatPop)',
    description: 'Current implementation - text-base emoji, rounded-full, px-2.5 py-1',
    containerClass: 'px-2.5 py-1 rounded-full bg-zinc-800/50 border border-zinc-700',
    emojiClass: 'text-base',
    countClass: 'text-sm font-medium text-zinc-300',
    gapClass: 'gap-1.5',
    highlightedContainerClass: 'px-2.5 py-1 rounded-full bg-zinc-700 border border-zinc-500',
  },
  {
    name: 'Discord-like',
    description: 'Smaller, tighter padding - text-sm emoji, rounded-md, px-1.5 py-0.5',
    containerClass: 'px-1.5 py-0.5 rounded-md bg-zinc-800/60 border border-zinc-700/50',
    emojiClass: 'text-sm',
    countClass: 'text-xs font-medium text-zinc-400',
    gapClass: 'gap-1',
    highlightedContainerClass: 'px-1.5 py-0.5 rounded-md bg-indigo-500/20 border border-indigo-500/50',
  },
  {
    name: 'Discord-like (variant)',
    description: 'Same size emoji, tighter container - text-base emoji, rounded-md, px-2 py-0.5',
    containerClass: 'px-2 py-0.5 rounded-md bg-zinc-800/60 border border-zinc-700/50',
    emojiClass: 'text-base leading-none',
    countClass: 'text-xs font-medium text-zinc-400',
    gapClass: 'gap-1',
    highlightedContainerClass: 'px-2 py-0.5 rounded-md bg-indigo-500/20 border border-indigo-500/50',
  },
  {
    name: 'Compact',
    description: 'Very compact - smaller everything, minimal padding',
    containerClass: 'px-1.5 py-0.5 rounded bg-zinc-800/40 border border-zinc-700/40',
    emojiClass: 'text-xs',
    countClass: 'text-[10px] font-medium text-zinc-500',
    gapClass: 'gap-0.5',
    highlightedContainerClass: 'px-1.5 py-0.5 rounded bg-blue-500/20 border border-blue-500/40',
  },
  {
    name: 'Pill (smaller)',
    description: 'Smaller pill style - keeps rounded-full but smaller',
    containerClass: 'px-2 py-0.5 rounded-full bg-zinc-800/50 border border-zinc-700/60',
    emojiClass: 'text-sm',
    countClass: 'text-xs font-medium text-zinc-400',
    gapClass: 'gap-1',
    highlightedContainerClass: 'px-2 py-0.5 rounded-full bg-purple-500/20 border border-purple-500/50',
  },
  {
    name: 'Minimal',
    description: 'No border, subtle background only',
    containerClass: 'px-1.5 py-0.5 rounded-md bg-zinc-700/30 hover:bg-zinc-700/50',
    emojiClass: 'text-sm',
    countClass: 'text-xs font-medium text-zinc-500',
    gapClass: 'gap-1',
    highlightedContainerClass: 'px-1.5 py-0.5 rounded-md bg-blue-500/30',
  },
];

const sampleReactions = [
  { emoji: '❤️', count: 1, has_reacted: true },
  { emoji: '😂', count: 3, has_reacted: false },
  { emoji: '👍', count: 2, has_reacted: false },
];

export default function ReactionsDemo() {
  const [selectedStyle, setSelectedStyle] = useState<number>(0);

  return (
    <div className="min-h-screen bg-zinc-900 text-white p-8">
      <h1 className="text-2xl font-bold mb-2">Reaction Styles Demo</h1>
      <p className="text-zinc-400 mb-8">Compare different reaction styling approaches. The first reaction (heart) shows the &quot;highlighted&quot; state (user has reacted).</p>

      {/* Message context preview */}
      <div className="mb-12 p-6 bg-zinc-800/50 rounded-lg max-w-md">
        <h2 className="text-lg font-semibold mb-4">In Message Context</h2>
        <div className="space-y-4">
          {/* Sample message */}
          <div>
            <div className="flex items-center gap-1 mb-1">
              <span className="text-sm font-bold text-white">FairWind251</span>
              <span className="text-xs text-zinc-500">2/5 4:48 PM</span>
            </div>
            <p className="text-sm text-white mb-2">That&apos;s so cool!</p>

            {/* Current selected style */}
            <div className={`flex items-center gap-2`}>
              {sampleReactions.map((reaction) => (
                <button
                  key={reaction.emoji}
                  className={`flex items-center ${reactionStyles[selectedStyle].gapClass} ${
                    reaction.has_reacted
                      ? reactionStyles[selectedStyle].highlightedContainerClass
                      : reactionStyles[selectedStyle].containerClass
                  } transition-all hover:scale-105`}
                >
                  <span className={reactionStyles[selectedStyle].emojiClass}>{reaction.emoji}</span>
                  <span className={`${reactionStyles[selectedStyle].countClass} ${reaction.has_reacted ? 'text-zinc-200' : ''}`}>
                    {reaction.count}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Style selector */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold mb-3">Select Style:</h2>
        <div className="flex flex-wrap gap-2">
          {reactionStyles.map((style, index) => (
            <button
              key={style.name}
              onClick={() => setSelectedStyle(index)}
              className={`px-3 py-1.5 rounded-md text-sm transition-all ${
                selectedStyle === index
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
              }`}
            >
              {style.name}
            </button>
          ))}
        </div>
        <p className="mt-2 text-sm text-zinc-500">{reactionStyles[selectedStyle].description}</p>
      </div>

      {/* All styles comparison */}
      <h2 className="text-lg font-semibold mb-4">All Styles Comparison</h2>
      <div className="grid gap-6">
        {reactionStyles.map((style, index) => (
          <div
            key={style.name}
            className={`p-4 rounded-lg border transition-all ${
              selectedStyle === index
                ? 'bg-zinc-800/80 border-blue-500/50'
                : 'bg-zinc-800/30 border-zinc-700/50'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium">{style.name}</h3>
              <span className="text-xs text-zinc-500">{style.description}</span>
            </div>

            {/* Normal state */}
            <div className="flex items-center gap-4 mb-3">
              <span className="text-xs text-zinc-500 w-20">Normal:</span>
              <div className={`flex items-center gap-2`}>
                {sampleReactions.filter(r => !r.has_reacted).map((reaction) => (
                  <div
                    key={reaction.emoji}
                    className={`flex items-center ${style.gapClass} ${style.containerClass}`}
                  >
                    <span className={style.emojiClass}>{reaction.emoji}</span>
                    <span className={style.countClass}>{reaction.count}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Highlighted state */}
            <div className="flex items-center gap-4">
              <span className="text-xs text-zinc-500 w-20">Highlighted:</span>
              <div className={`flex items-center gap-2`}>
                {sampleReactions.filter(r => r.has_reacted).map((reaction) => (
                  <div
                    key={reaction.emoji}
                    className={`flex items-center ${style.gapClass} ${style.highlightedContainerClass}`}
                  >
                    <span className={style.emojiClass}>{reaction.emoji}</span>
                    <span className={`${style.countClass} text-zinc-200`}>{reaction.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Technical details */}
      <div className="mt-12 p-4 bg-zinc-800/30 rounded-lg">
        <h2 className="text-lg font-semibold mb-3">Current Selection - CSS Classes</h2>
        <div className="space-y-2 text-sm font-mono">
          <div><span className="text-zinc-500">Container:</span> <span className="text-green-400">{reactionStyles[selectedStyle].containerClass}</span></div>
          <div><span className="text-zinc-500">Emoji:</span> <span className="text-green-400">{reactionStyles[selectedStyle].emojiClass}</span></div>
          <div><span className="text-zinc-500">Count:</span> <span className="text-green-400">{reactionStyles[selectedStyle].countClass}</span></div>
          <div><span className="text-zinc-500">Gap:</span> <span className="text-green-400">{reactionStyles[selectedStyle].gapClass}</span></div>
          <div><span className="text-zinc-500">Highlighted:</span> <span className="text-green-400">{reactionStyles[selectedStyle].highlightedContainerClass}</span></div>
        </div>
      </div>
    </div>
  );
}
