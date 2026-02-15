'use client';

import { useState } from 'react';
import { ArrowLeft, Reply, Pin, DollarSign, Ban, BadgeCheck, Settings, Crown, Gamepad2, Sparkles, Camera, MessageSquare, Mic, Play, Image, Copy, Forward, Trash2, Flag } from 'lucide-react';

const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '😡'];

type MediaType = 'text' | 'photo' | 'photo-caption' | 'video' | 'voice';

interface FakeMsg {
  id: string;
  username: string;
  content: string;
  isHost: boolean;
  isOwn: boolean;
  isPinned: boolean;
  time: string;
  verified?: boolean;
  isFirstInThread: boolean;
  reactions?: { emoji: string; count: number }[];
  replyTo?: { username: string; content: string };
  mediaType?: MediaType;
  photoUrl?: string;
}

// Different message types to demo
const MSG_VARIANTS: Record<MediaType, FakeMsg> = {
  text: {
    id: 't1', username: 'RetroCrystal831', content: 'Lmfao', isHost: false, isOwn: false,
    isPinned: false, time: '2/5 4:50 PM', isFirstInThread: true, mediaType: 'text',
  },
  photo: {
    id: 'p1', username: 'EchoProton970', content: '', isHost: false, isOwn: false,
    isPinned: false, time: '2/5 5:12 PM', isFirstInThread: true, mediaType: 'photo',
    photoUrl: 'https://picsum.photos/seed/chatpop1/400/300',
  },
  'photo-caption': {
    id: 'pc1', username: 'ThetaPhantom412', content: 'Check out this sunset!', isHost: false, isOwn: false,
    isPinned: false, time: '2/5 5:30 PM', isFirstInThread: true, mediaType: 'photo-caption',
    photoUrl: 'https://picsum.photos/seed/chatpop2/400/300',
  },
  video: {
    id: 'v1', username: 'RetroCrystal831', content: '', isHost: false, isOwn: false,
    isPinned: false, time: '2/5 6:01 PM', isFirstInThread: true, mediaType: 'video',
    photoUrl: 'https://picsum.photos/seed/chatpop3/400/300',
  },
  voice: {
    id: 'vo1', username: 'EchoProton970', content: '', isHost: false, isOwn: false,
    isPinned: false, time: '2/5 6:15 PM', isFirstInThread: true, mediaType: 'voice',
  },
};

const MEDIA_LABELS: Record<MediaType, string> = {
  text: 'Text',
  photo: 'Photo',
  'photo-caption': 'Photo + Caption',
  video: 'Video',
  voice: 'Voice',
};

// Background chat messages (static)
const BG_MESSAGES: FakeMsg[] = [
  { id: 'b1', username: 'RetroCrystal831', content: 'What a great artist!', isHost: false, isOwn: false, isPinned: false, time: '2/3 3:42 PM', isFirstInThread: true },
  { id: 'b2', username: 'ThetaPhantom412', content: "Agreed... listening to Child's Song right now. So sad!", isHost: false, isOwn: false, isPinned: false, time: '2/3 3:55 PM', isFirstInThread: true },
  { id: 'b3', username: 'EchoProton970', content: "Let's test here", isHost: false, isOwn: false, isPinned: false, time: '2/5 9:58 AM', isFirstInThread: true },
  { id: 'b4', username: 'RetroCrystal831', content: 'More than just an artist IMO', isHost: false, isOwn: false, isPinned: false, time: '2/5 4:48 PM', isFirstInThread: true },
];

const ACTIONS = [
  { icon: Reply, label: 'Reply', color: 'text-cyan-400' },
  { icon: Pin, label: 'Pin', color: 'text-cyan-400' },
  { icon: DollarSign, label: 'Tip', color: 'text-cyan-400' },
  { icon: Copy, label: 'Copy', color: 'text-cyan-400' },
  { icon: Forward, label: 'Forward', color: 'text-cyan-400' },
  { icon: Ban, label: 'Mute', color: 'text-red-400' },
  { icon: Flag, label: 'Report', color: 'text-red-400' },
  { icon: Trash2, label: 'Delete', color: 'text-red-400' },
];

const THEME = {
  regular: { message: 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1', text: 'text-sm text-white', username: 'text-sm font-bold text-white', timestamp: 'text-xs text-white opacity-60' },
  pinned: { message: 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1', text: 'text-sm text-white', username: 'text-sm font-bold text-purple-400', timestamp: 'text-xs opacity-60' },
  host: { message: 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1 font-medium', text: 'text-sm text-white', username: 'text-sm font-bold text-amber-400', timestamp: 'text-xs opacity-60' },
  own: { message: 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1', text: 'text-sm text-white', username: 'text-sm font-bold text-red-500', timestamp: 'text-xs text-white opacity-60' },
};

function getStyle(msg: FakeMsg) {
  if (msg.isPinned) return THEME.pinned;
  if (msg.isHost) return THEME.host;
  if (msg.isOwn) return THEME.own;
  return THEME.regular;
}

function AvatarImg({ username }: { username: string }) {
  return (
    <img
      src={`https://api.dicebear.com/7.x/pixel-art/svg?seed=${username}&size=80`}
      alt={username}
      className="w-10 h-10 rounded-full bg-zinc-700"
    />
  );
}

// Voice message waveform (fake)
function VoiceWaveform() {
  return (
    <div className="flex items-center gap-2 bg-white/10 rounded-lg px-3 py-2 mt-1">
      <button className="w-8 h-8 rounded-full bg-white hover:bg-white/90 flex items-center justify-center flex-shrink-0">
        <Play className="w-4 h-4 text-zinc-800 ml-0.5" />
      </button>
      <div className="flex items-end gap-[2px] flex-1 h-6">
        {[3,5,8,12,6,10,14,8,5,11,7,13,9,4,8,12,6,10,5,3,7,11,8,5,9,6,4].map((h, i) => (
          <div key={i} className={`w-[3px] rounded-full ${i < 12 ? 'bg-white' : 'bg-white/40'}`} style={{ height: `${h * 1.5}px` }} />
        ))}
      </div>
      <span className="text-white/80 text-xs ml-1">0:14</span>
    </div>
  );
}

// Photo/video thumbnail
function MediaThumbnail({ url, isVideo = false, compact = false }: { url: string; isVideo?: boolean; compact?: boolean }) {
  return (
    <div className={`relative ${compact ? 'w-16 h-16' : 'w-full max-w-[240px]'} rounded-lg overflow-hidden bg-zinc-700 mt-1`}>
      <img
        src={url}
        alt="Media"
        className={`w-full ${compact ? 'h-16 object-cover' : 'h-auto'} rounded-lg`}
      />
      {isVideo && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-10 h-10 rounded-full bg-black/60 flex items-center justify-center">
            <Play className="w-5 h-5 text-white ml-0.5" />
          </div>
        </div>
      )}
    </div>
  );
}

// Render media content for a message
function MessageMedia({ msg, compact = false }: { msg: FakeMsg; compact?: boolean }) {
  const s = getStyle(msg);
  switch (msg.mediaType) {
    case 'photo':
      return <MediaThumbnail url={msg.photoUrl!} compact={compact} />;
    case 'photo-caption':
      return (
        <div>
          {msg.content && <p className={`${s.text} mb-1`}>{msg.content}</p>}
          <MediaThumbnail url={msg.photoUrl!} compact={compact} />
        </div>
      );
    case 'video':
      return <MediaThumbnail url={msg.photoUrl!} isVideo compact={compact} />;
    case 'voice':
      return <VoiceWaveform />;
    default:
      return msg.content ? <p className={s.text}>{msg.content}</p> : null;
  }
}

// Message row for the chat background
function BgMessageRow({ msg }: { msg: FakeMsg }) {
  const s = getStyle(msg);
  return (
    <div className="flex">
      <div className="w-10 flex-shrink-0 mr-3"><AvatarImg username={msg.username} /></div>
      <div className="flex-1 min-w-0">
        <div className="mb-1">
          <span className={s.username}>{msg.username}</span>
          <span className={`${s.timestamp} -mt-0.5 block`}>{msg.time}</span>
        </div>
        <div className={s.message}><p className={s.text}>{msg.content}</p></div>
      </div>
    </div>
  );
}

// Floating message with media support
function FloatingMessage({ msg }: { msg: FakeMsg }) {
  const s = getStyle(msg);
  return (
    <div className="flex">
      <div className="w-10 flex-shrink-0 mr-3"><AvatarImg username={msg.username} /></div>
      <div className="flex-1 min-w-0">
        <div className="mb-1">
          <span className={s.username}>{msg.username}</span>
          <span className={`${s.timestamp} -mt-0.5 block`}>{msg.time}</span>
        </div>
        <div className={s.message}>
          <MessageMedia msg={msg} />
        </div>
      </div>
    </div>
  );
}

// Quote strip with media support (for E3)
function QuoteStrip({ msg }: { msg: FakeMsg }) {
  const s = getStyle(msg);
  const hasPhoto = msg.mediaType === 'photo' || msg.mediaType === 'photo-caption' || msg.mediaType === 'video';
  const isVoice = msg.mediaType === 'voice';

  return (
    <div className="flex items-center gap-3 px-3 py-2.5 bg-zinc-800 rounded-xl" style={{ borderLeftWidth: '3px', borderLeftColor: '#a855f7', borderLeftStyle: 'solid' }}>
      <img src={`https://api.dicebear.com/7.x/pixel-art/svg?seed=${msg.username}&size=64`} alt="" className="w-8 h-8 rounded-full bg-zinc-700 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <span className={s.username}>{msg.username}</span>
        {msg.content ? (
          <p className="text-sm text-zinc-200 truncate">{msg.content}</p>
        ) : isVoice ? (
          <div className="flex items-center gap-1 mt-0.5">
            <Mic className="w-3 h-3 text-zinc-400" />
            <span className="text-sm text-zinc-400">Voice message</span>
          </div>
        ) : hasPhoto ? (
          <div className="flex items-center gap-1 mt-0.5">
            <Image className="w-3 h-3 text-zinc-400" />
            <span className="text-sm text-zinc-400">{msg.mediaType === 'video' ? 'Video' : 'Photo'}</span>
          </div>
        ) : null}
      </div>
      {hasPhoto && (
        <div className="w-10 h-10 rounded-lg overflow-hidden flex-shrink-0 bg-zinc-700">
          <img src={msg.photoUrl!} alt="" className="w-full h-full object-cover" />
          {msg.mediaType === 'video' && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Play className="w-4 h-4 text-white" />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ChatBackground({ blurred = false }: { blurred?: boolean }) {
  return (
    <div className={`absolute inset-0 bg-zinc-950 flex flex-col ${blurred ? 'blur-[2px]' : ''}`}>
      <div className="border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <ArrowLeft size={18} className="text-zinc-100 flex-shrink-0" />
            <h1 className="text-lg font-bold text-zinc-100 truncate">Tom Rush</h1>
          </div>
          <button className="px-3 py-1.5 rounded text-xs tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700 flex items-center gap-1.5 whitespace-nowrap">
            <Sparkles size={16} />
            Focus
          </button>
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden bg-zinc-900">
        <div className="absolute inset-0 overflow-y-auto px-4 py-4">
          <div className="space-y-2">
            {BG_MESSAGES.map((msg) => <BgMessageRow key={msg.id} msg={msg} />)}
          </div>
        </div>
      </div>
      <div className="border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 min-w-0">
            <div className="flex items-center gap-2 w-full px-4 py-[7px] border border-zinc-700 rounded-lg bg-zinc-800 text-zinc-500 text-sm">
              <MessageSquare className="w-4 h-4 flex-shrink-0" /><span>Aa</span>
            </div>
          </div>
          <button className="w-9 h-9 flex items-center justify-center rounded-lg bg-blue-600 text-white flex-shrink-0"><Camera className="w-5 h-5" /></button>
          <button className="h-9 px-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-semibold rounded-lg flex-shrink-0">Send</button>
        </div>
      </div>
      <div className="absolute right-2 bottom-20 flex flex-col gap-2">
        <div className="w-10 h-10 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center"><Crown className="w-5 h-5 text-zinc-400" strokeWidth={1.5} /></div>
        <div className="w-10 h-10 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center"><Gamepad2 className="w-5 h-5 text-zinc-400" strokeWidth={1.5} /></div>
        <div className="w-10 h-10 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center"><Settings className="w-5 h-5 text-zinc-400" strokeWidth={1.5} /></div>
      </div>
    </div>
  );
}

function EmojiRow() {
  return (
    <div className="flex items-center justify-between">
      {REACTION_EMOJIS.map((emoji) => (
        <button key={emoji} className="flex items-center justify-center rounded-full bg-zinc-800 hover:bg-zinc-700 transition-all active:scale-110 cursor-pointer" style={{ width: '52px', height: '52px' }}>
          <span className="text-2xl">{emoji}</span>
        </button>
      ))}
    </div>
  );
}

function ActionRow() {
  return (
    <div className="relative">
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {ACTIONS.map((action) => (
          <button key={action.label} className="flex flex-col items-center gap-2 py-3 px-4 rounded-2xl bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 transition-all active:scale-95 cursor-pointer flex-shrink-0 min-w-[72px]">
            <action.icon className={`w-6 h-6 ${action.color}`} />
            <span className="text-xs font-medium text-zinc-300">{action.label}</span>
          </button>
        ))}
      </div>
      {/* Right fade gradient to hint scrollability */}
      <div className="absolute top-0 right-0 bottom-1 w-10 bg-gradient-to-l from-zinc-900 to-transparent pointer-events-none" />
    </div>
  );
}

// Media type selector pills
function MediaSelector({ selected, onChange }: { selected: MediaType; onChange: (t: MediaType) => void }) {
  const types: MediaType[] = ['text', 'photo', 'photo-caption', 'video', 'voice'];
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 px-1 -mx-1">
      {types.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={`px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
            selected === t
              ? 'bg-purple-600 text-white'
              : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
          }`}
        >
          {MEDIA_LABELS[t]}
        </button>
      ))}
    </div>
  );
}

// ============================================================
// E1: Message stays in-place in backdrop, sheet slides up independently
// ============================================================
function VariantE1({ msg, onClose }: { msg: FakeMsg; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      <ChatBackground blurred />
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      {/* Message floats in the middle area — visually "still in the chat" */}
      <div className="absolute left-0 right-0 z-10 px-4" style={{ bottom: '55%' }} onClick={(e) => e.stopPropagation()}>
        <FloatingMessage msg={msg} />
      </div>
      {/* Sheet slides up from bottom, separate from message */}
      <div className="absolute bottom-0 left-0 right-0 z-10 w-full max-w-lg mx-auto animate-slide-up">
        <div className="w-full bg-zinc-900 rounded-t-3xl" onClick={(e) => e.stopPropagation()}>
          <div className="pt-3 pb-2 flex justify-center"><div className="w-12 h-1.5 bg-gray-600 rounded-full" /></div>
          <div className="px-5 pb-4"><EmojiRow /></div>
          <div className="mx-5 border-t border-zinc-700/50" />
          <div className="px-5 pt-3 pb-8"><ActionRow /></div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// E2: Message + emoji bar floating in backdrop, minimal sheet
// ============================================================
function VariantE2({ msg, onClose }: { msg: FakeMsg; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      <ChatBackground blurred />
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 flex-1 flex flex-col justify-end px-4 pb-4" onClick={onClose}>
        <div className="mb-3" onClick={(e) => e.stopPropagation()}><FloatingMessage msg={msg} /></div>
        <div className="flex items-center gap-1.5 justify-start pl-[52px]" onClick={(e) => e.stopPropagation()}>
          {REACTION_EMOJIS.map((emoji) => (
            <button key={emoji} className="flex items-center justify-center w-12 h-12 rounded-full bg-zinc-800/90 hover:bg-zinc-700 backdrop-blur-md transition-all active:scale-110 cursor-pointer shadow-lg border border-zinc-700/50">
              <span className="text-xl">{emoji}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="relative z-10 w-full max-w-lg mx-auto animate-slide-up">
        <div className="w-full bg-zinc-900 rounded-t-3xl" onClick={(e) => e.stopPropagation()}>
          <div className="pt-3 pb-2 flex justify-center"><div className="w-12 h-1.5 bg-gray-600 rounded-full" /></div>
          <div className="px-5 pb-8"><ActionRow /></div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// E3: All-in-sheet with quote strip + avatar
// ============================================================
function VariantE3({ msg, onClose }: { msg: FakeMsg; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <ChatBackground blurred />
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg z-10 animate-slide-up">
        <div className="w-full bg-zinc-900 rounded-t-3xl" onClick={(e) => e.stopPropagation()}>
          <div className="pt-3 pb-2 flex justify-center"><div className="w-12 h-1.5 bg-gray-600 rounded-full" /></div>
          <div className="px-5 pb-3"><QuoteStrip msg={msg} /></div>
          <div className="px-5 pb-4"><EmojiRow /></div>
          <div className="mx-5 border-t border-zinc-700/50" />
          <div className="px-5 pt-3 pb-8"><ActionRow /></div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// E4: Bubble floating just above sheet edge
// ============================================================
function VariantE4({ msg, onClose }: { msg: FakeMsg; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <ChatBackground blurred />
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg z-10 animate-slide-up">
        <div className="px-4 pb-3" onClick={(e) => e.stopPropagation()}><FloatingMessage msg={msg} /></div>
        <div className="w-full bg-zinc-900 rounded-t-3xl" onClick={(e) => e.stopPropagation()}>
          <div className="pt-3 pb-2 flex justify-center"><div className="w-12 h-1.5 bg-gray-600 rounded-full" /></div>
          <div className="px-5 pb-4"><EmojiRow /></div>
          <div className="mx-5 border-t border-zinc-700/50" />
          <div className="px-5 pt-3 pb-8"><ActionRow /></div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// E5: iMessage hybrid — emojis above message, minimal sheet
// ============================================================
function VariantE5({ msg, onClose }: { msg: FakeMsg; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col">
      <ChatBackground blurred />
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 flex-1 flex flex-col justify-end px-4 pb-4" onClick={onClose}>
        <div className="flex items-center gap-1.5 justify-start mb-2 pl-[52px]" onClick={(e) => e.stopPropagation()}>
          {REACTION_EMOJIS.map((emoji) => (
            <button key={emoji} className="flex items-center justify-center w-11 h-11 rounded-full bg-zinc-800/90 hover:bg-zinc-700 backdrop-blur-md transition-all active:scale-110 cursor-pointer shadow-lg border border-zinc-700/50">
              <span className="text-lg">{emoji}</span>
            </button>
          ))}
        </div>
        <div onClick={(e) => e.stopPropagation()}><FloatingMessage msg={msg} /></div>
      </div>
      <div className="relative z-10 w-full max-w-lg mx-auto animate-slide-up">
        <div className="w-full bg-zinc-900 rounded-t-3xl" onClick={(e) => e.stopPropagation()}>
          <div className="pt-3 pb-2 flex justify-center"><div className="w-12 h-1.5 bg-gray-600 rounded-full" /></div>
          <div className="px-5 pb-8"><ActionRow /></div>
        </div>
      </div>
    </div>
  );
}

// Variant renderer
const VARIANTS: Record<string, React.FC<{ msg: FakeMsg; onClose: () => void }>> = {
  E1: VariantE1, E2: VariantE2, E3: VariantE3, E4: VariantE4, E5: VariantE5,
};

// ============================================================
// Main
// ============================================================
export default function MessageActionsDemo() {
  const [activeVariant, setActiveVariant] = useState<string | null>(null);
  const [mediaType, setMediaType] = useState<MediaType>('text');

  const variants = [
    { id: 'E1', label: 'E1: Lifted Message', desc: 'Message floats at bottom of backdrop, sheet has emojis + action grid' },
    { id: 'E2', label: 'E2: Message + Floating Emojis', desc: 'Message and emojis both float in backdrop, sheet is just the action grid' },
    { id: 'E3', label: 'E3: All-in-Sheet', desc: 'Quote strip with avatar + emojis + grid, all inside the bottom sheet' },
    { id: 'E4', label: 'E4: Message Above Sheet', desc: 'Full message rendered just above the sheet, emojis + grid inside' },
    { id: 'E5', label: 'E5: iMessage Hybrid', desc: 'Emojis float above message in backdrop, sheet is just the compact grid' },
  ];

  const ActiveVariant = activeVariant ? VARIANTS[activeVariant] : null;
  const currentMsg = MSG_VARIANTS[mediaType];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="border-b border-zinc-800 bg-zinc-900 px-6 py-4">
        <h1 className="text-xl font-bold">Message Actions — All Variants</h1>
        <p className="text-sm text-zinc-400 mt-1">Pick a message type, then tap a layout to preview.</p>
      </div>

      {/* Media type selector */}
      <div className="px-6 pt-4 pb-2">
        <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">Message Type</p>
        <MediaSelector selected={mediaType} onChange={setMediaType} />
      </div>

      {/* Layout variants */}
      <div className="p-6 pt-3 space-y-3">
        {variants.map((v) => (
          <button
            key={v.id}
            onClick={() => setActiveVariant(v.id)}
            className="w-full text-left p-4 rounded-2xl bg-zinc-900 border border-zinc-700 hover:border-zinc-500 transition-all cursor-pointer active:scale-[0.98]"
          >
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-zinc-100">{v.label}</h2>
                <p className="text-sm text-zinc-400 mt-1">{v.desc}</p>
              </div>
              <div className="text-zinc-500 text-xl">&rarr;</div>
            </div>
          </button>
        ))}
      </div>

      {/* Active modal */}
      {ActiveVariant && <ActiveVariant msg={currentMsg} onClose={() => setActiveVariant(null)} />}

      <style jsx>{`
        @keyframes slide-up {
          from { transform: translateY(100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .animate-slide-up {
          animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
      <style jsx global>{`
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
      `}</style>
    </div>
  );
}
