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
}

const SAMPLES: GiftMsg[] = [
  { emoji: '🍪', name: 'Cookie', priceCents: 200, sender: 'SharpRaven392', recipient: 'GentleDagger443' },
  { emoji: '💎', name: 'Diamond', priceCents: 10000, sender: 'HappySignal896', recipient: 'IcyBow677' },
  { emoji: '🏎️', name: 'Sports Car', priceCents: 50000, sender: 'IcyBow677', recipient: 'SharpRaven392' },
];

/* ────────────────────────────────────────────────────────────────────
   Shared: fake avatar URL (DiceBear pixel-art)
   ──────────────────────────────────────────────────────────────────── */
function avatarUrl(name: string) {
  return `https://api.dicebear.com/7.x/pixel-art/svg?seed=${encodeURIComponent(name)}&size=80`;
}

/* ────────────────────────────────────────────────────────────────────
   Shared: Message wrapper — avatar + content column (matches real chat)
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
      {/* Avatar column */}
      <div className="w-10 h-10 flex-shrink-0 mr-3">
        <img
          src={avatarUrl(username)}
          alt={username}
          className="w-10 h-10 rounded-full bg-zinc-700"
        />
      </div>
      {/* Content column */}
      <div className="flex-1 min-w-0">
        {/* Username */}
        <div className="mb-1 flex items-center gap-1">
          <span className={`text-sm font-semibold ${
            isHost
              ? (dark ? 'text-red-400' : 'text-red-600')
              : (dark ? 'text-white' : 'text-gray-900')
          }`}>
            {username}
          </span>
          {isHost && <Crown size={16} className={dark ? 'text-teal-400' : 'text-teal-600'} />}
        </div>
        {/* Content (gift card or regular bubble) */}
        {children}
        {/* Timestamp */}
        <div className={`text-[11px] mt-1 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
          {timestamp}
        </div>
      </div>
    </div>
  );
}

/* Regular text bubble */
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
   Style A — "Current" (what's live now)
   Centered card inside the message bubble area
   ──────────────────────────────────────────────────────────────────── */
function StyleA({ g, dark }: { g: GiftMsg; dark: boolean }) {
  const content = `sent ${g.emoji} ${g.name} (${formatGiftPrice(g.priceCents)}) to @${g.recipient}`;
  return (
    <div className={`rounded-xl px-4 py-3 text-center max-w-[85%] ${
      dark ? 'bg-zinc-800/80 border border-zinc-700' : 'bg-gray-50 border border-gray-200'
    }`}>
      <div className="text-3xl mb-1">{g.emoji}</div>
      <div className={`text-sm ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>{content}</div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style B — "Structured Card"
   Clean card with emoji, gift name, price badge, and sender → recipient
   ──────────────────────────────────────────────────────────────────── */
function StyleB({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`rounded-xl px-4 py-3 text-center max-w-[85%] ${
      dark
        ? 'bg-zinc-800/80 border border-zinc-700'
        : 'bg-gray-50 border border-gray-200'
    }`}>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
        {g.name}
      </div>
      <div className={`text-xs mt-0.5 ${dark ? 'text-zinc-400' : 'text-gray-500'}`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style C — "Compact Row"
   Horizontal layout — emoji left, text right, fits in one line
   ──────────────────────────────────────────────────────────────────── */
function StyleC({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`rounded-xl px-3 py-2.5 flex items-center gap-2.5 max-w-[85%] w-fit ${
      dark ? 'bg-zinc-800/80 border border-zinc-700' : 'bg-gray-50 border border-gray-200'
    }`}>
      <div className={`text-2xl flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center ${
        dark ? 'bg-zinc-700/80' : 'bg-gray-100'
      }`}>
        {g.emoji}
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-sm font-semibold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</span>
          <span className={`text-xs font-medium ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>
            {formatGiftPrice(g.priceCents)}
          </span>
        </div>
        <div className={`text-xs ${dark ? 'text-zinc-400' : 'text-gray-500'}`}>
          to <span className="font-medium">@{g.recipient}</span>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style D — "Gradient Card"
   Card with subtle gradient bg, large emoji, structured layout
   ──────────────────────────────────────────────────────────────────── */
function StyleD({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`relative rounded-xl px-4 py-3 text-center max-w-[85%] ${
      dark
        ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border border-zinc-700'
        : 'bg-gradient-to-b from-purple-50/80 to-white border border-purple-200/60'
    }`}>
      <div className={`absolute top-2.5 right-2.5 text-xs font-medium px-2 py-0.5 rounded-full ${
        dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
      }`}>
        {formatGiftPrice(g.priceCents)}
      </div>
      <div className="text-4xl mb-1.5">{g.emoji}</div>
      <div className={`text-sm font-bold ${dark ? 'text-white' : 'text-gray-900'}`}>
        {g.name}
      </div>
      <div className={`text-xs mt-1.5 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-semibold ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style E — "Accent Border"
   Left accent bar with horizontal layout
   ──────────────────────────────────────────────────────────────────── */
function StyleE({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`rounded-lg overflow-hidden flex items-center max-w-[85%] w-fit ${
      dark ? 'bg-zinc-800/60' : 'bg-gray-50'
    }`}>
      <div className={`w-1 self-stretch flex-shrink-0 ${dark ? 'bg-cyan-500' : 'bg-purple-500'}`} />
      <div className="flex items-center gap-2.5 px-3 py-2.5 min-w-0">
        <div className="text-2xl flex-shrink-0">{g.emoji}</div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`text-sm font-semibold ${dark ? 'text-white' : 'text-gray-900'}`}>{g.name}</span>
            <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
              dark ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
            }`}>{formatGiftPrice(g.priceCents)}</span>
          </div>
          <div className={`text-xs ${dark ? 'text-zinc-400' : 'text-gray-500'}`}>
            to <span className="font-medium">@{g.recipient}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style F — "Pill / System Notice"
   Compact centered pill — more like a system event notification
   ──────────────────────────────────────────────────────────────────── */
function StyleF({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`rounded-full px-3.5 py-1.5 flex items-center gap-2 w-fit max-w-[85%] ${
      dark
        ? 'bg-zinc-800/60 border border-zinc-700/50'
        : 'bg-gray-100/80 border border-gray-200/50'
    }`}>
      <span className="text-xl flex-shrink-0">{g.emoji}</span>
      <span className={`text-xs ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>
        sent <span className="font-semibold">{g.name}</span> to <span className="font-semibold">@{g.recipient}</span>
      </span>
      <span className={`text-xs font-semibold flex-shrink-0 ${dark ? 'text-cyan-400' : 'text-purple-600'}`}>
        {formatGiftPrice(g.priceCents)}
      </span>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   Style G — "Bubble Gift"
   Looks like a regular message bubble but with gift content inside
   ──────────────────────────────────────────────────────────────────── */
function StyleG({ g, dark }: { g: GiftMsg; dark: boolean }) {
  return (
    <div className={`rounded-2xl rounded-tl-md px-3.5 py-2.5 max-w-[85%] w-fit ${
      dark ? 'bg-zinc-800 text-zinc-100' : 'bg-gray-100 text-gray-900'
    }`}>
      <div className="flex items-center gap-2">
        <span className="text-2xl">{g.emoji}</span>
        <div className="min-w-0">
          <span className={`text-sm font-semibold ${dark ? 'text-white' : 'text-gray-900'}`}>
            {g.name}
          </span>
          <span className={`text-sm ${dark ? 'text-zinc-400' : 'text-gray-500'}`}>
            {' '}{formatGiftPrice(g.priceCents)}
          </span>
        </div>
      </div>
      <div className={`text-xs mt-1 ${dark ? 'text-zinc-500' : 'text-gray-400'}`}>
        to <span className={`font-medium ${dark ? 'text-zinc-300' : 'text-gray-600'}`}>@{g.recipient}</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────
   DEMO PAGE
   ──────────────────────────────────────────────────────────────────── */

const STYLES = [
  { id: 'A', label: 'Current', desc: 'What\'s live now — centered card with raw content string', Component: StyleA },
  { id: 'B', label: 'Structured Card', desc: 'Clean card — big emoji, name, price, recipient', Component: StyleB },
  { id: 'C', label: 'Compact Row', desc: 'Horizontal — emoji box left, text right', Component: StyleC },
  { id: 'D', label: 'Gradient Card', desc: 'Subtle gradient bg + price badge pill', Component: StyleD },
  { id: 'E', label: 'Accent Border', desc: 'Left color bar with horizontal layout', Component: StyleE },
  { id: 'F', label: 'System Pill', desc: 'Compact rounded pill — system-event style', Component: StyleF },
  { id: 'G', label: 'Bubble Gift', desc: 'Chat-bubble shape with gift inside', Component: StyleG },
];

export default function GiftCardDemo() {
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
              className={`p-1.5 rounded-lg transition-colors ${
                darkMode ? 'hover:bg-zinc-800' : 'hover:bg-gray-200'
              }`}
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-lg font-bold">Gift Card Styles</h1>
              <p className={`text-xs ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>
                7 variants — pick one for the chat timeline
              </p>
            </div>
          </div>
          <button
            onClick={() => setDarkMode(!darkMode)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              darkMode
                ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                : 'bg-gray-200 hover:bg-gray-300 text-gray-700'
            }`}
          >
            {darkMode ? 'Light' : 'Dark'}
          </button>
        </div>
      </div>

      {/* Styles */}
      <div className="max-w-md mx-auto py-6 space-y-10">
        {STYLES.map(({ id, label, desc, Component }) => (
          <section key={id}>
            <div className="mb-2 px-4">
              <h2 className="text-base font-bold">
                {id}. {label}
              </h2>
              <p className={`text-xs ${darkMode ? 'text-zinc-400' : 'text-gray-500'}`}>{desc}</p>
            </div>

            {/* Simulated chat area */}
            <div className={`border-y px-4 py-1 ${
              darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-gray-200'
            }`}>
              {/* Regular message above for context */}
              <ChatMsg username="IcyBow677" dark={darkMode} timestamp="Sun 10:16 PM">
                <TextBubble text="I got here by following the clear and simple directions on Facebook" dark={darkMode} />
              </ChatMsg>

              <ChatMsg username="GentleDagger443" dark={darkMode} timestamp="Sun 10:18 PM">
                <TextBubble text="Same bruh" dark={darkMode} />
              </ChatMsg>

              {/* Gift card — cheap */}
              <ChatMsg username={SAMPLES[0].sender} dark={darkMode} timestamp="Today 11:02 AM">
                <Component g={SAMPLES[0]} dark={darkMode} />
              </ChatMsg>

              {/* Regular message */}
              <ChatMsg username="GentleDagger443" dark={darkMode} timestamp="Today 11:03 AM">
                <TextBubble text="aww thanks! 😊" dark={darkMode} />
              </ChatMsg>

              {/* Gift card — expensive */}
              <ChatMsg username={SAMPLES[1].sender} dark={darkMode} isHost timestamp="Today 11:05 AM">
                <Component g={SAMPLES[1]} dark={darkMode} />
              </ChatMsg>

              {/* Gift card — premium */}
              <ChatMsg username={SAMPLES[2].sender} dark={darkMode} timestamp="Today 11:08 AM">
                <Component g={SAMPLES[2]} dark={darkMode} />
              </ChatMsg>

              <div className="h-2" />
            </div>
          </section>
        ))}

        {/* Spacer */}
        <div className="h-12" />
      </div>
    </div>
  );
}
