'use client';

import React, { useState } from 'react';
import { Play, Pause, Crown, Pin, BadgeCheck } from 'lucide-react';

export default function DarkModeDemoPage() {
  const [playingVoice, setPlayingVoice] = useState<string | null>(null);

  // Voice player component with waveform
  const VoicePlayer = ({
    id,
    containerBg,
    buttonBg,
    buttonActiveBg,
    playIconColor
  }: {
    id: string;
    containerBg: string;
    buttonBg: string;
    buttonActiveBg: string;
    playIconColor: string;
  }) => {
    const isPlaying = playingVoice === id;

    return (
      <div className={`flex items-center gap-3 px-3 py-2 rounded-lg ${containerBg}`}>
        <button
          onClick={() => setPlayingVoice(isPlaying ? null : id)}
          className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${isPlaying ? buttonActiveBg : buttonBg}`}
        >
          {isPlaying ? (
            <Pause className={`w-4 h-4 ${playIconColor} fill-current`} />
          ) : (
            <Play className={`w-4 h-4 ${playIconColor} fill-current ml-0.5`} />
          )}
        </button>
        <div className="flex-1 flex items-center gap-2">
          {/* Waveform visualization */}
          <div className="flex-1 h-8 flex items-center gap-0.5">
            {[3, 8, 5, 12, 7, 10, 4, 11, 6, 9, 5, 8, 4, 10, 7, 12, 5, 9, 6, 8].map((height, i) => (
              <div
                key={i}
                className={`flex-1 rounded-full transition-colors ${
                  isPlaying && i < 10 ? 'bg-white/80' : 'bg-white/20'
                }`}
                style={{ height: `${height}px`, minWidth: '2px' }}
              />
            ))}
          </div>
          <span className="text-xs text-white/60 font-mono">0:12</span>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-900">
      {/* Header */}
      <div className="bg-zinc-800 border-b border-zinc-700 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="text-3xl font-bold text-white mb-2">
            Dark Mode Theme Demo
          </h1>
          <p className="text-sm text-gray-400">
            Showcasing audio players, sticky messages, host messages, and pinned messages
          </p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {/* Sticky Messages Section */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Sticky Messages Area</h2>
          <p className="text-sm text-gray-400 mb-4">
            Top section of chat showing pinned messages (emerald green with left border) and host messages (cyan)
          </p>

          {/* Sticky Section Preview */}
          <div className="bg-zinc-900 rounded-lg overflow-hidden border border-zinc-700">
            {/* Sticky area - fixed at top */}
            <div className="border-b border-zinc-600 bg-zinc-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md">

              {/* Host Message in Sticky */}
              <div className="rounded-xl px-4 py-3 bg-cyan-600 text-white shadow-lg">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-sm">ChatHost</span>
                  <Crown className="text-cyan-300 flex-shrink-0" size={16} />
                  <span className="text-xs opacity-60">12:34 PM</span>
                </div>
                <div className="text-sm">Welcome to the chat! This is a sticky host message.</div>
              </div>

              {/* Pinned Message in Sticky */}
              <div className="rounded-xl px-4 py-3 bg-emerald-600 text-white shadow-lg border-l-4 border-emerald-400">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-sm">PinnerUser</span>
                  <Pin className="text-emerald-300 flex-shrink-0" size={16} />
                  <span className="text-xs opacity-70">$5.00</span>
                  <span className="text-xs opacity-60">12:35 PM</span>
                </div>
                <div className="text-sm">This is a pinned message at the top!</div>
              </div>
            </div>

            {/* Messages area placeholder */}
            <div className="px-4 py-8 text-center text-gray-500 text-sm">
              Regular messages would scroll here below the sticky section...
            </div>
          </div>
        </div>

        {/* Host Messages Section */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Host Messages</h2>
          <p className="text-sm text-gray-400 mb-4">
            Messages from the chat creator/host with cyan background
          </p>

          <div className="space-y-4">
            {/* Text Host Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-white">ChatHost</span>
                  <Crown className="text-cyan-400 flex-shrink-0" size={16} />
                  <span className="text-xs text-white opacity-60">12:34 PM</span>
                </div>
                {/* Message bubble */}
                <div className="rounded-xl px-4 py-3 bg-cyan-600 text-white shadow-lg">
                  <div className="text-sm">Thanks for joining everyone! Let&apos;s have a great discussion.</div>
                </div>
              </div>
            </div>

            {/* Voice Host Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-white">ChatHost</span>
                  <Crown className="text-cyan-400 flex-shrink-0" size={16} />
                  <span className="text-xs text-white opacity-60">12:36 PM</span>
                </div>
                {/* Voice message bubble */}
                <div className="rounded-xl px-4 py-3 bg-cyan-600 shadow-lg">
                  <VoicePlayer
                    id="host-voice"
                    containerBg="bg-cyan-800"
                    buttonBg="bg-cyan-800"
                    buttonActiveBg="bg-cyan-400"
                    playIconColor="text-white"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Pinned Messages Section */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Pinned Messages (Outside Sticky Area)</h2>
          <p className="text-sm text-gray-400 mb-4">
            Paid pinned messages in the regular flow with emerald green background and left border accent
          </p>

          <div className="space-y-4">
            {/* Text Pinned Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-gray-400">RegularUser</span>
                  <Pin className="text-emerald-400 flex-shrink-0" size={14} />
                  <span className="text-xs opacity-70 text-emerald-300">$5.00</span>
                  <span className="text-xs text-white opacity-60">12:40 PM</span>
                </div>
                {/* Message bubble */}
                <div className="rounded-xl px-4 py-3 bg-emerald-600 border-l-4 border-emerald-400 text-white shadow-lg">
                  <div className="text-sm">This is my pinned message that I paid to highlight!</div>
                </div>
              </div>
            </div>

            {/* Voice Pinned Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-gray-400">AnotherUser</span>
                  <BadgeCheck className="text-emerald-400 flex-shrink-0" size={14} />
                  <Pin className="text-emerald-400 flex-shrink-0" size={14} />
                  <span className="text-xs opacity-70 text-emerald-300">$10.00</span>
                  <span className="text-xs text-white opacity-60">12:42 PM</span>
                </div>
                {/* Voice message bubble */}
                <div className="rounded-xl px-4 py-3 bg-emerald-600 border-l-4 border-emerald-400 shadow-lg">
                  <VoicePlayer
                    id="pinned-voice"
                    containerBg="bg-emerald-800"
                    buttonBg="bg-emerald-800"
                    buttonActiveBg="bg-emerald-400"
                    playIconColor="text-white"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Regular Messages Section */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Regular Messages</h2>
          <p className="text-sm text-gray-400 mb-4">
            Standard messages from participants with zinc-800 background
          </p>

          <div className="space-y-4">
            {/* Text Regular Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-gray-400">JohnDoe</span>
                  <span className="text-xs text-white opacity-60">12:38 PM</span>
                </div>
                {/* Message bubble */}
                <div className="rounded px-3 py-2 bg-zinc-800 text-white">
                  <div className="text-sm">This is a regular message from a participant.</div>
                </div>
              </div>
            </div>

            {/* Voice Regular Message */}
            <div className="flex justify-start">
              <div className="max-w-[85%]">
                {/* Username header outside bubble */}
                <div className="mb-1 flex items-center gap-1">
                  <span className="text-sm font-semibold text-gray-400">JaneSmith</span>
                  <BadgeCheck className="text-emerald-400 flex-shrink-0" size={14} />
                  <span className="text-xs text-white opacity-60">12:39 PM</span>
                </div>
                {/* Voice message bubble */}
                <div className="rounded px-3 py-2 bg-zinc-800">
                  <VoicePlayer
                    id="regular-voice"
                    containerBg="bg-zinc-700/50"
                    buttonBg="bg-zinc-700/50"
                    buttonActiveBg="bg-zinc-500"
                    playIconColor="text-white"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Voice Player Specifications */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Voice Player Specifications</h2>

          <div className="grid md:grid-cols-2 gap-6 text-sm text-gray-300">
            <div>
              <h3 className="text-emerald-400 font-semibold mb-2">Component Structure:</h3>
              <ul className="space-y-1 list-disc list-inside">
                <li>Outer container: <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">px-3 py-2 rounded-lg</code></li>
                <li>Play button: <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">w-8 h-8 rounded-full</code></li>
                <li>Waveform: 20 bars, <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">gap-0.5</code>, <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">min-width: 2px</code></li>
                <li>Duration: <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">font-mono text-xs</code></li>
              </ul>
            </div>

            <div>
              <h3 className="text-emerald-400 font-semibold mb-2">Color Scheme:</h3>
              <ul className="space-y-1 list-disc list-inside">
                <li>Host: Cyan variants (<code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-cyan-800</code>, <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-cyan-400</code>)</li>
                <li>Pinned: Emerald variants (<code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-emerald-800</code>, <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-emerald-400</code>)</li>
                <li>Regular: Zinc variants (<code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-zinc-700/50</code>, <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-zinc-500</code>)</li>
                <li>Waveform: <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-white/80</code> (played), <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">bg-white/20</code> (unplayed)</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Implementation Notes */}
        <div className="bg-zinc-800 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Key Design Notes</h2>

          <div className="space-y-3 text-sm text-gray-300">
            <div>
              <strong className="text-cyan-400">Sticky Section:</strong> Uses <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">z-20</code> or higher,
              <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs ml-1">backdrop-blur-lg</code>, and
              <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs ml-1">bg-zinc-800/80</code> for glassmorphism effect
            </div>

            <div>
              <strong className="text-emerald-400">Username Placement:</strong>
              <ul className="mt-1 ml-4 space-y-1">
                <li>• Regular messages: Username <strong>outside/above</strong> bubble</li>
                <li>• Host/Pinned in sticky: Username <strong>inside</strong> bubble for compact layout</li>
                <li>• Host/Pinned in flow: Username <strong>outside/above</strong> bubble</li>
              </ul>
            </div>

            <div>
              <strong className="text-amber-400">Left Border Accent:</strong> Pinned messages use
              <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs ml-1">border-l-4 border-emerald-400</code> for visual emphasis
            </div>

            <div>
              <strong className="text-purple-400">Icon Colors:</strong>
              <ul className="mt-1 ml-4 space-y-1">
                <li>• Crown (host): <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">text-cyan-400</code></li>
                <li>• Pin: <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">text-emerald-400</code></li>
                <li>• Badge (verified): <code className="bg-zinc-700 px-2 py-0.5 rounded text-xs">text-emerald-400</code></li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
