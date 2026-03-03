'use client';

import { useState } from 'react';
import { ArrowLeft, Crown } from 'lucide-react';
import { formatGiftPrice } from '@/lib/gifts';

/* ────────────────────────────────────────────────────────────────────
   Fake data
   ──────────────────────────────────────────────────────────────────── */

interface GiftMsg {
  emoji: string;
  name: string;
  priceCents: number;
  sender: string;
  recipient: string;
  acknowledged: boolean;
}

const MY_USERNAME = 'SharpRaven392';

const MESSAGES: { type: 'text' | 'gift'; username: string; text?: string; gift?: GiftMsg; isHost?: boolean; time: string }[] = [
  { type: 'text', username: 'IcyBow677', text: 'I got here by following the clear and simple directions on Facebook', time: 'Sun 10:16 PM' },
  { type: 'text', username: 'GentleDagger443', text: 'Same bruh', time: 'Sun 10:18 PM' },
  // Gift to someone else
  { type: 'gift', username: 'HappySignal896', gift: { emoji: '☕', name: 'Coffee', priceCents: 100, sender: 'HappySignal896', recipient: 'IcyBow677', acknowledged: true }, time: 'Today 10:55 AM', isHost: true },
  { type: 'text', username: 'IcyBow677', text: 'thanks!! 😊', time: 'Today 10:56 AM' },
  // Gift TO ME
  { type: 'gift', username: 'GentleDagger443', gift: { emoji: '🍪', name: 'Cookie', priceCents: 200, sender: 'GentleDagger443', recipient: MY_USERNAME, acknowledged: true }, time: 'Today 11:02 AM' },
  // Gift TO ME (premium)
  { type: 'gift', username: 'HappySignal896', gift: { emoji: '💎', name: 'Diamond', priceCents: 10000, sender: 'HappySignal896', recipient: MY_USERNAME, acknowledged: false }, isHost: true, time: 'Today 11:05 AM' },
  { type: 'text', username: MY_USERNAME, text: 'omg you guys are too nice', time: 'Today 11:06 AM' },
  // Gift to someone else
  { type: 'gift', username: 'IcyBow677', gift: { emoji: '🌹', name: 'Rose', priceCents: 300, sender: 'IcyBow677', recipient: 'GentleDagger443', acknowledged: false }, time: 'Today 11:08 AM' },
];

/* ────────────────────────────────────────────────────────────────────
   Avatar helper
   ──────────────────────────────────────────────────────────────────── */
function avatarUrl(name: string) {
  return `https://api.dicebear.com/7.x/pixel-art/svg?seed=${encodeURIComponent(name)}&size=80`;
}

/* ────────────────────────────────────────────────────────────────────
   Shared wrapper: avatar + username + content + timestamp
   ──────────────────────────────────────────────────────────────────── */
function ChatMsg({
  username,
  dark,
  isHost,
  children,
  timestamp,
}: {
  username: string;
  dark: boolean;
  isHost?: boolean;
  children: React.ReactNode;
  timestamp: string;
}) {
  return (
    <div className="flex mt-3">
      <div className="w-10 h-10 flex-shrink-0 mr-3">
        <img src={avatarUrl(username)} alt={username} className="w-10 h-10 rounded-full bg-zinc-700" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="mb-1 flex items-center gap-1">
          <span className={`text-sm font-semibold ${
            isHost ? (dark ? 'text-red-400' : 'text-red-600') : (dark ? 'text-white' : 'text-gray-900')
          }`}>
            {username}
          </span>
          {isHost && <Crown size={16} className={dark ? 'text-teal-400' : 'text-teal-600'} />}
        </div>
        {children}
        <div className={`text-[11px] mt-1 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>{timestamp}</div>
      </div>
    </div>
  );
}

function TextBubble({ text, dark, isOwn }: { text: string; dark: boolean; isOwn?: boolean }) {
  return (
    <div className={`rounded-2xl rounded-tl-md px-3.5 py-2 w-fit max-w-[85%] ${
      isOwn
        ? (dark ? 'bg-cyan-700 text-white' : 'bg-purple-600 text-white')
        : (dark ? 'bg-zinc-800 text-zinc-100' : 'bg-gray-100 text-gray-900')
    }`}>
      <div className="text-sm">{text}</div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   BASE gift card (not for me) — same as current production style
   ──────────────────────────────────────────────────────────────────── */
function BaseGiftCard({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] ${
      dark
        ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border border-zinc-700'
        : 'bg-gradient-to-b from-purple-50/80 to-white border border-purple-200/60'
    }`}>
      {g.acknowledged && (
        <div className="absolute top-2 left-2.5 text-lg" title="Thanked">🤗</div>
      )}
      {g.priceCents > 0 && (
        <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
          dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
        }`}>
          {formatGiftPrice(g.priceCents)}
        </div>
      )}
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   HIGHLIGHT STYLES — "for me" variants
   ──────────────────────────────────────────────────────────────────── */

/* Style 1: Accent Border — colored border replaces neutral one */
function HighlightAccentBorder({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] ${
      dark
        ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border-2 border-cyan-500/60'
        : 'bg-gradient-to-b from-purple-50/80 to-white border-2 border-purple-400/60'
    }`}>
      {g.acknowledged && (
        <div className="absolute top-2 left-2.5 text-lg" title="Thanked">🤗</div>
      )}
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* Style 2: Background Tint — subtle colored gradient */
function HighlightBgTint({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] border ${
      dark
        ? 'bg-gradient-to-b from-cyan-950/50 to-zinc-800/60 border-cyan-800/40'
        : 'bg-gradient-to-b from-purple-100/80 to-purple-50/40 border-purple-300/50'
    }`}>
      {g.acknowledged && (
        <div className="absolute top-2 left-2.5 text-lg" title="Thanked">🤗</div>
      )}
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* Style 3: Glow Shadow — colored shadow behind the card */
function HighlightGlow({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div
      className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] border ${
        dark
          ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border-zinc-700'
          : 'bg-gradient-to-b from-purple-50/80 to-white border-purple-200/60'
      }`}
      style={{
        boxShadow: dark
          ? '0 0 12px 2px rgba(6, 182, 212, 0.25)'
          : '0 0 12px 2px rgba(147, 51, 234, 0.2)',
      }}
    >
      {g.acknowledged && (
        <div className="absolute top-2 left-2.5 text-lg" title="Thanked">🤗</div>
      )}
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* Style 4: Left Accent Bar — colored bar on the left edge */
function HighlightLeftBar({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl overflow-hidden px-4 py-3 text-center max-w-[65%] border ${
      dark
        ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border-zinc-700'
        : 'bg-gradient-to-b from-purple-50/80 to-white border-purple-200/60'
    }`}>
      <div className={`absolute top-0 left-0 bottom-0 w-1 ${dark ? 'bg-cyan-500' : 'bg-purple-500'}`} />
      {g.acknowledged && (
        <div className="absolute top-2 left-3.5 text-lg" title="Thanked">🤗</div>
      )}
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* Style 5: "For You" Tag — small badge top-left instead of (or alongside) 🤗 */
function HighlightForYouTag({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] border ${
      dark
        ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border-zinc-700'
        : 'bg-gradient-to-b from-purple-50/80 to-white border-purple-200/60'
    }`}>
      <div className={`absolute top-2 left-2 text-[10px] font-bold px-1.5 py-0.5 rounded-full ${
        dark ? 'bg-cyan-600 text-white' : 'bg-purple-600 text-white'
      }`}>
        {g.acknowledged ? '🤗 For you' : 'For you'}
      </div>
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* Style 6: Combined — Accent border + background tint + glow */
function HighlightCombined({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div
      className={`relative rounded-xl px-4 py-3 text-center max-w-[65%] border-2 ${
        dark
          ? 'bg-gradient-to-b from-cyan-950/40 to-zinc-800/60 border-cyan-500/50'
          : 'bg-gradient-to-b from-purple-100/60 to-white border-purple-400/50'
      }`}
      style={{
        boxShadow: dark
          ? '0 0 8px 1px rgba(6, 182, 212, 0.15)'
          : '0 0 8px 1px rgba(147, 51, 234, 0.12)',
      }}
    >
      {g.acknowledged && (
        <div className="absolute top-2 left-2.5 text-lg" title="Thanked">🤗</div>
      )}
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   DEMO PAGE
   ──────────────────────────────────────────────────────────────────── */

const HIGHLIGHT_STYLES = [
  { id: '1', label: 'Accent Border', desc: 'Colored border replaces the neutral one', HighlightComponent: HighlightAccentBorder },
  { id: '2', label: 'Background Tint', desc: 'Subtle colored gradient background', HighlightComponent: HighlightBgTint },
  { id: '3', label: 'Glow Shadow', desc: 'Colored glow/shadow behind the card', HighlightComponent: HighlightGlow },
  { id: '4', label: 'Left Accent Bar', desc: 'Colored bar on the left edge', HighlightComponent: HighlightLeftBar },
  { id: '5', label: '"For You" Tag', desc: 'Small badge in the top-left corner', HighlightComponent: HighlightForYouTag },
  { id: '6', label: 'Combined', desc: 'Accent border + bg tint + subtle glow', HighlightComponent: HighlightCombined },
];

function renderMessage(
  msg: typeof MESSAGES[0],
  dark: boolean,
  HighlightComponent: typeof HighlightAccentBorder,
) {
  if (msg.type === 'text') {
    return (
      <ChatMsg key={msg.time + msg.username} username={msg.username} dark={dark} isHost={msg.isHost} timestamp={msg.time}>
        <TextBubble text={msg.text!} dark={dark} isOwn={msg.username === MY_USERNAME} />
      </ChatMsg>
    );
  }

  const g = msg.gift!;
  const isForMe = g.recipient === MY_USERNAME;

  return (
    <ChatMsg key={msg.time + msg.username} username={msg.username} dark={dark} isHost={msg.isHost} timestamp={msg.time}>
      {isForMe ? <HighlightComponent g={g} dark={dark} /> : <BaseGiftCard g={g} dark={dark} />}
    </ChatMsg>
  );
}

export default function GiftHighlightDemo() {
  const [darkMode, setDarkMode] = useState(true);

  return (
    <div className={`min-h-screen transition-colors ${darkMode ? 'bg-zinc-950 text-white' : 'bg-gray-50 text-gray-900'}`}>
      {/* Header */}
      <div className={`sticky top-0 z-10 backdrop-blur-lg border-b px-4 py-3 ${
        darkMode ? 'bg-zinc-950/80 border-zinc-800' : 'bg-white/80 border-gray-200'
      }`}>
        <div className="max-w-md mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.history.back()}
              className={`p-1.5 rounded-lg transition-colors ${darkMode ? 'hover:bg-zinc-800' : 'hover:bg-gray-200'}`}
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-lg font-bold">Gift Highlight Styles</h1>
              <p className={`text-xs ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>
                You are <span className="font-semibold">@{MY_USERNAME}</span> — gifts to you are highlighted
              </p>
            </div>
          </div>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              darkMode ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200' : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
            }`}
          >
            {darkMode ? 'Light' : 'Dark'}
          </button>
        </div>
      </div>

      {/* Styles */}
      <div className="max-w-md mx-auto py-6 space-y-10">
        {HIGHLIGHT_STYLES.map(({ id, label, desc, HighlightComponent }) => (
          <section key={id}>
            <div className="mb-2 px-4">
              <h2 className="text-base font-bold">{id}. {label}</h2>
              <p className={`text-xs ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>{desc}</p>
            </div>

            <div className={`border-y px-4 py-1 ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-gray-200'}`}>
              {MESSAGES.map((msg) => renderMessage(msg, darkMode, HighlightComponent))}
              <div className="h-2" />
            </div>
          </section>
        ))}

        <div className="h-12" />
      </div>
    </div>
  );
}
