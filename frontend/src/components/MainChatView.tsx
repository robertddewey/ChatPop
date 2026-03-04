'use client';

import React, { useMemo, useRef, useState, useLayoutEffect, useEffect, memo } from 'react';
import { BadgeCheck, Reply, Crown, Pin, Mic, ImageIcon, Video } from 'lucide-react';
import MessageActionsModal from './MessageActionsModal';
import VoiceMessagePlayer from './VoiceMessagePlayer';
import PhotoMessage from './PhotoMessage';
import VideoMessage from './VideoMessage';
import ReactionBar from './ReactionBar';
import { ChatRoom, Message, ReactionSummary } from '@/lib/api';

// Extract inline styles from Tailwind classes (opacity and filter)
function extractInlineStyles(classString: string): { classes: string; style: React.CSSProperties } {
  const classes: string[] = [];
  const style: React.CSSProperties = {};

  // Split by spaces and process each class
  classString.split(' ').forEach(cls => {
    // Match opacity-[value] or opacity-{number}
    const opacityMatch = cls.match(/^opacity-(?:\[([0-9.]+)\]|(\d+))$/);
    if (opacityMatch) {
      const value = opacityMatch[1] || (parseInt(opacityMatch[2]) / 100);
      style.opacity = typeof value === 'string' ? parseFloat(value) : value;
      return;
    }

    // Match [filter:...] arbitrary value
    const filterMatch = cls.match(/^\[filter:(.+)\]$/);
    if (filterMatch) {
      // Convert underscore-separated filters to space-separated CSS
      const filterValue = filterMatch[1].replace(/_/g, ' ');
      style.filter = filterValue;
      return;
    }

    // Match [mix-blend-mode:...] arbitrary value
    const blendModeMatch = cls.match(/^\[mix-blend-mode:(.+)\]$/);
    if (blendModeMatch) {
      style.mixBlendMode = blendModeMatch[1] as React.CSSProperties['mixBlendMode'];
      return;
    }

    // Keep all other classes
    classes.push(cls);
  });

  return { classes: classes.join(' '), style };
}

// Format timestamp with date (M/D) and time
function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });

  // Get date-only values for comparison (strip time)
  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const todayOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayOnly = new Date(todayOnly);
  yesterdayOnly.setDate(yesterdayOnly.getDate() - 1);

  // Calculate days difference
  const daysDiff = Math.floor((todayOnly.getTime() - dateOnly.getTime()) / (1000 * 60 * 60 * 24));

  if (dateOnly.getTime() === todayOnly.getTime()) {
    // Today - show "Today" prefix
    return `Today ${time}`;
  } else if (dateOnly.getTime() === yesterdayOnly.getTime()) {
    // Yesterday
    return `Yesterday ${time}`;
  } else if (daysDiff < 7 && daysDiff > 0) {
    // Within last week - show abbreviated day name
    const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
    return `${dayName} ${time}`;
  } else {
    // Older - show month/day
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day} ${time}`;
  }
}

// Tailwind color lookup table for icon colors
const tailwindColors: Record<string, string> = {
  'text-amber-400': '#fbbf24',
  'text-teal-400': '#2dd4bf',
  'text-emerald-400': '#34d399',
  'text-emerald-300': '#6ee7b7',
  'text-cyan-400': '#22d3ee',
  'text-blue-500': '#3b82f6',
  'text-yellow-400': '#facc15',
  'text-white': '#ffffff',
  'text-gray-400': '#9ca3af',
  'text-red-500': '#ef4444',
  'text-purple-400': '#c084fc',
};

// Convert Tailwind color class to inline color style
function getIconColor(tailwindClass: string | undefined): string | undefined {
  if (!tailwindClass) {
    return undefined;
  }
  const color = tailwindColors[tailwindClass.trim()];
  return color;
}

// Tailwind color values map (comprehensive)
const tailwindColorValues: Record<string, Record<number, string>> = {
  'red': { 50: '#fef2f2', 100: '#fee2e2', 200: '#fecaca', 300: '#fca5a5', 400: '#f87171', 500: '#ef4444', 600: '#dc2626', 700: '#b91c1c', 800: '#991b1b', 900: '#7f1d1d' },
  'blue': { 50: '#eff6ff', 100: '#dbeafe', 200: '#bfdbfe', 300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8', 800: '#1e40af', 900: '#1e3a8a' },
  'green': { 50: '#f0fdf4', 100: '#dcfce7', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80', 500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d' },
  'yellow': { 50: '#fefce8', 100: '#fef9c3', 200: '#fef08a', 300: '#fde047', 400: '#facc15', 500: '#eab308', 600: '#ca8a04', 700: '#a16207', 800: '#854d0e', 900: '#713f12' },
  'purple': { 50: '#faf5ff', 100: '#f3e8ff', 200: '#e9d5ff', 300: '#d8b4fe', 400: '#c084fc', 500: '#a855f7', 600: '#9333ea', 700: '#7e22ce', 800: '#6b21a8', 900: '#581c87' },
  'pink': { 50: '#fdf2f8', 100: '#fce7f3', 200: '#fbcfe8', 300: '#f9a8d4', 400: '#f472b6', 500: '#ec4899', 600: '#db2777', 700: '#be185d', 800: '#9d174d', 900: '#831843' },
  'gray': { 50: '#f9fafb', 100: '#f3f4f6', 200: '#e5e7eb', 300: '#d1d5db', 400: '#9ca3af', 500: '#6b7280', 600: '#4b5563', 700: '#374151', 800: '#1f2937', 900: '#111827' },
  'zinc': { 50: '#fafafa', 100: '#f4f4f5', 200: '#e4e4e7', 300: '#d4d4d8', 400: '#a1a1aa', 500: '#71717a', 600: '#52525b', 700: '#3f3f46', 800: '#27272a', 900: '#18181b' },
  'cyan': { 50: '#ecfeff', 100: '#cffafe', 200: '#a5f3fc', 300: '#67e8f9', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2', 700: '#0e7490', 800: '#155e75', 900: '#164e63' },
  'teal': { 50: '#f0fdfa', 100: '#ccfbf1', 200: '#99f6e4', 300: '#5eead4', 400: '#2dd4bf', 500: '#14b8a6', 600: '#0d9488', 700: '#0f766e', 800: '#115e59', 900: '#134e4a' },
  'emerald': { 50: '#ecfdf5', 100: '#d1fae5', 200: '#a7f3d0', 300: '#6ee7b7', 400: '#34d399', 500: '#10b981', 600: '#059669', 700: '#047857', 800: '#065f46', 900: '#064e3b' },
  'amber': { 50: '#fffbeb', 100: '#fef3c7', 200: '#fde68a', 300: '#fcd34d', 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706', 700: '#b45309', 800: '#92400e', 900: '#78350f' },
  'white': { 500: '#ffffff' },
};

// Extract text color from Tailwind classes and convert to inline style
// Handles classes like "text-xs font-semibold text-white" or "text-xs !text-white opacity-60"
function getTextColor(classString: string | undefined): string | undefined {
  if (!classString) return undefined;

  // Look for text-{color} classes (including !text-{color})
  const classes = classString.split(' ');
  for (const cls of classes) {
    // Remove ! prefix if present
    const cleanClass = cls.replace(/^!/, '').replace(/\\/g, '');

    // First check the legacy lookup table
    if (tailwindColors[cleanClass]) {
      return tailwindColors[cleanClass];
    }

    // Parse text-{color}-{shade} pattern (e.g., text-red-500)
    const match = cleanClass.match(/^text-([a-z]+)-(\d+)$/);
    if (match) {
      const [, colorName, shade] = match;
      const shadeNum = parseInt(shade);
      if (tailwindColorValues[colorName] && tailwindColorValues[colorName][shadeNum]) {
        return tailwindColorValues[colorName][shadeNum];
      }
    }

    // Handle text-white (no shade)
    if (cleanClass === 'text-white') {
      return '#ffffff';
    }

    // Handle text-black (no shade)
    if (cleanClass === 'text-black') {
      return '#000000';
    }
  }

  return undefined;
}

// "you" pill shown next to the current user's username
function YouPill({ dark = true }: { dark?: boolean }) {
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none ${
      dark ? 'bg-white/10 text-zinc-400' : 'bg-black/10 text-gray-500'
    }`}>you</span>
  );
}

// Generate DiceBear avatar URL
function getDiceBearUrl(style: string, seed: string, size: number = 80): string {
  return `https://api.dicebear.com/7.x/${style}/svg?seed=${encodeURIComponent(seed)}&size=${size}`;
}

interface MainChatViewProps {
  chatRoom: ChatRoom | null;
  currentUserId: string | null;
  username: string;
  hasJoined: boolean;
  sessionToken: string | null;
  filteredMessages: Message[];
  stickyHostMessages: Message[];
  stickyPinnedMessage: Message | null;
  messagesContainerRef: React.RefObject<HTMLDivElement | null>;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  currentDesign: Record<string, any>;
  themeIsDarkMode?: boolean;
  handleScroll: () => void;
  scrollToMessage: (messageId: string) => void;
  highlightMessage?: (messageId: string) => void;
  handleReply: (message: Message) => void;
  disableReply?: boolean;
  handlePin: (messageId: string, amountCents: number) => Promise<boolean>;
  handleAddToPin: (messageId: string, amountCents: number) => Promise<boolean>;
  getPinRequirements: (messageId: string) => Promise<{
    current_pin_cents: number;
    minimum_cents?: number;
    required_cents?: number;
    minimum_required_cents?: number;
    duration_minutes: number;
    tiers?: { amount_cents: number; duration_minutes: number }[];
    is_pinned?: boolean;
    is_expired?: boolean;
    time_remaining_seconds?: number;
  }>;
  // Legacy (deprecated)
  handlePinSelf?: (messageId: string) => void;
  handlePinOther?: (messageId: string) => void;
  handleBlockUser: (username: string) => void;
  handleTipUser: (username: string) => void;
  handleSendGift: (giftId: string, recipientUsername: string) => Promise<boolean>;
  handleThankGift: (messageId: string) => Promise<boolean>;
  handleDeleteMessage: (messageId: string) => void;
  handleReactionToggle: (messageId: string, emoji: string) => void;
  messageReactions: Record<string, ReactionSummary[]>;
  loadingOlder?: boolean;
}

function MainChatView({
  chatRoom,
  currentUserId,
  username,
  hasJoined,
  sessionToken,
  filteredMessages,
  stickyHostMessages,
  stickyPinnedMessage,
  messagesContainerRef,
  messagesEndRef,
  currentDesign,
  themeIsDarkMode = true,
  handleScroll,
  scrollToMessage,
  highlightMessage,
  handleReply,
  disableReply = false,
  handlePin,
  handleAddToPin,
  getPinRequirements,
  handlePinSelf,
  handlePinOther,
  handleBlockUser,
  handleTipUser,
  handleSendGift,
  handleThankGift,
  handleDeleteMessage,
  handleReactionToggle,
  messageReactions,
  loadingOlder = false,
}: MainChatViewProps) {
  // Ref for measuring sticky section height
  const stickySectionRef = useRef<HTMLDivElement>(null);
  const [stickyHeight, setStickyHeight] = useState(0);

  // Compute theme colors for modal badges/icons (memoized)
  const modalThemeColors = useMemo(() => ({
    badgeIcon: getIconColor(currentDesign.badgeIconColor) || '#34d399',
    crownIcon: getIconColor(currentDesign.crownIconColor) || '#2dd4bf',
    pinIcon: getIconColor(currentDesign.pinIconColor) || '#fbbf24',
    hostUsername: getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff',
    pinnedUsername: getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff',
    myUsername: getTextColor(currentDesign.myUsername) || '#ef4444',
    regularUsername: getTextColor(currentDesign.regularUsername) || '#ffffff',
  }), [currentDesign]);

  // Track if initial render is complete - skip all animations until then
  const initialRenderDoneRef = useRef(false);
  // State version for sticky section animations (refs don't trigger re-renders)
  const [allowAnimations, setAllowAnimations] = useState(false);

  // Track message IDs we've already seen to only animate new messages
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  // Measure sticky section height dynamically
  useLayoutEffect(() => {
    const stickyEl = stickySectionRef.current;
    const hasSticky = stickyHostMessages.length > 0 || stickyPinnedMessage;

    if (!stickyEl || !hasSticky) {
      setStickyHeight(0);
      return;
    }

    // Initial measurement
    const height = stickyEl.offsetHeight;
    setStickyHeight(height);

    // Watch for size changes
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.borderBoxSize?.[0]?.blockSize ?? (entry.target as HTMLElement).offsetHeight;
        setStickyHeight(height);
      }
    });

    resizeObserver.observe(stickyEl);
    return () => resizeObserver.disconnect();
  }, [stickyHostMessages.length, stickyPinnedMessage]);

  // Extract inline styles from messagesAreaBg for dynamic opacity/filter support
  const backgroundStyles = useMemo(() => {
    if (!currentDesign?.messagesAreaBg) return { classes: '', style: {} };
    const result = extractInlineStyles(currentDesign.messagesAreaBg as string);
    return result;
  }, [currentDesign?.messagesAreaBg]);

  // Track new message IDs for animation (computed during render)
  // Skip ALL animations during initial render to prevent page bouncing
  // Skip animations when loading older messages (infinite scroll) to prevent jump
  const newMessageIds = useMemo(() => {
    // Don't animate anything until initial render is complete
    if (!initialRenderDoneRef.current) {
      return new Set<string>();
    }
    // Don't animate prepended older messages from infinite scroll
    if (loadingOlder) {
      return new Set<string>();
    }
    const newIds = new Set<string>();
    for (const message of filteredMessages) {
      if (!seenMessageIdsRef.current.has(message.id)) {
        newIds.add(message.id);
      }
    }
    return newIds;
  }, [filteredMessages, loadingOlder]);

  // After render, mark all current messages as "seen" so they won't animate again
  // Also mark initial render as complete after first effect run
  useEffect(() => {
    for (const message of filteredMessages) {
      seenMessageIdsRef.current.add(message.id);
    }
    // Mark initial render as done after first batch of messages is seen
    if (!initialRenderDoneRef.current && filteredMessages.length > 0) {
      // Use a small delay to ensure DOM has settled before allowing animations
      setTimeout(() => {
        initialRenderDoneRef.current = true;
        setAllowAnimations(true);
      }, 100);
    }
  }, [filteredMessages]);

  return (
    <div className={`h-full overflow-hidden relative ${currentDesign.messagesAreaContainer || 'bg-white'}`}>
      {/* Sticky Section: Host + Pinned Messages - Absolutely positioned overlay */}
      {hasJoined && (stickyHostMessages.length > 0 || stickyPinnedMessage) && (
        <div ref={stickySectionRef} data-sticky-section className={currentDesign.stickySection}>
          {/* Host Messages */}
          {stickyHostMessages.map((message) => (
            <MessageActionsModal
              key={`sticky-${message.id}`}
              message={message}
              currentUsername={username}
              isHost={chatRoom?.host.id === currentUserId}
              themeIsDarkMode={themeIsDarkMode}
              sessionToken={sessionToken}
              themeColors={modalThemeColors}
              onReply={disableReply ? undefined : handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onSendGift={handleSendGift}
              onThankGift={handleThankGift}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
              onHighlight={highlightMessage}
              reactions={messageReactions[message.id] || message.reactions || []}
            >
              <div
                className={`${currentDesign.stickyHostMessage} w-full relative cursor-pointer hover:opacity-90 transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
                onClick={() => scrollToMessage(message.id)}
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <img
                    src={message.avatar_url || getDiceBearUrl(currentDesign.avatarStyle || 'pixel-art', message.username, 80)}
                    alt={message.username}
                    className={`${currentDesign.avatarSize || 'w-10 h-10'} rounded-full bg-zinc-700 flex-shrink-0 ${currentDesign.avatarBorder || ''}`}
                  />
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-1">
                      <span
                        className={currentDesign.stickyHostUsername || 'text-sm font-semibold'}
                        style={{ color: getTextColor(currentDesign.stickyHostUsername || currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                      >
                        {message.username}
                      </span>
                      {message.username_is_reserved && (
                        <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                      )}
                      {message.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                      <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                    </div>
                <span
                  className="absolute top-3 right-3 text-xs opacity-60"
                  style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                >
                  {formatTimestamp(message.created_at)}
                </span>
                {message.voice_url ? (
                  <div className="flex items-center gap-2">
                    <Mic size={16} className={currentDesign.hostText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.hostText} opacity-70 truncate`}>
                      Voice{message.content ? `: ${message.content}` : message.voice_duration ? ` (${Math.floor(message.voice_duration / 60)}:${String(Math.floor(message.voice_duration % 60)).padStart(2, '0')})` : ''}
                    </span>
                  </div>
                ) : message.photo_url ? (
                  <div className="flex items-center gap-2">
                    <ImageIcon size={16} className={currentDesign.hostText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.hostText} opacity-70 truncate`}>
                      Photo{message.content ? `: ${message.content}` : ''}
                    </span>
                  </div>
                ) : message.video_url ? (
                  <div className="flex items-center gap-2">
                    <Video size={16} className={currentDesign.hostText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.hostText} opacity-70 truncate`}>
                      Video{message.content ? `: ${message.content}` : message.video_duration ? ` (${Math.floor(message.video_duration / 60)}:${String(Math.floor(message.video_duration % 60)).padStart(2, '0')})` : ''}
                    </span>
                  </div>
                ) : (
                  <p className={`text-sm ${currentDesign.hostText} truncate`}>
                    {message.content}
                  </p>
                )}
                  </div>
                </div>
              </div>
            </MessageActionsModal>
          ))}

          {/* Pinned Message */}
          {stickyPinnedMessage && (
            <MessageActionsModal
              message={stickyPinnedMessage}
              currentUsername={username}
              isHost={chatRoom?.host.id === currentUserId}
              themeIsDarkMode={themeIsDarkMode}
              sessionToken={sessionToken}
              themeColors={modalThemeColors}
              onReply={disableReply ? undefined : handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onSendGift={handleSendGift}
              onThankGift={handleThankGift}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
              onHighlight={highlightMessage}
              reactions={messageReactions[stickyPinnedMessage.id] || stickyPinnedMessage.reactions || []}
            >
              <div
                className={`${currentDesign.stickyPinnedMessage} w-full relative cursor-pointer hover:opacity-90 transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
                onClick={() => scrollToMessage(stickyPinnedMessage.id)}
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <img
                    src={stickyPinnedMessage.avatar_url || getDiceBearUrl(currentDesign.avatarStyle || 'pixel-art', stickyPinnedMessage.username, 80)}
                    alt={stickyPinnedMessage.username}
                    className={`${currentDesign.avatarSize || 'w-10 h-10'} rounded-full bg-zinc-700 flex-shrink-0 ${currentDesign.avatarBorder || ''}`}
                  />
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-1">
                      <span
                        className={currentDesign.stickyPinnedUsername || 'text-sm font-semibold'}
                        style={{ color: getTextColor(currentDesign.stickyPinnedUsername || currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                      >
                        {stickyPinnedMessage.username}
                      </span>
                  {stickyPinnedMessage.username_is_reserved && (
                    <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                  )}
                  {stickyPinnedMessage.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                  <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full ${
                    themeIsDarkMode ? 'bg-white/10' : 'bg-black/10'
                  }`}>
                    <Pin size={12} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                    <span className={`text-xs font-medium ${currentDesign.pinnedText}`}>
                      ${stickyPinnedMessage.current_pin_amount}
                    </span>
                  </div>
                </div>
                <span
                  className="absolute top-3 right-3 text-xs opacity-60"
                  style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                >
                  {formatTimestamp(stickyPinnedMessage.created_at)}
                </span>
                {stickyPinnedMessage.voice_url ? (
                  <div className="flex items-center gap-2">
                    <Mic size={16} className={currentDesign.pinnedText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.pinnedText} opacity-70 truncate`}>
                      Voice{stickyPinnedMessage.content ? `: ${stickyPinnedMessage.content}` : stickyPinnedMessage.voice_duration ? ` (${Math.floor(stickyPinnedMessage.voice_duration / 60)}:${String(Math.floor(stickyPinnedMessage.voice_duration % 60)).padStart(2, '0')})` : ''}
                    </span>
                  </div>
                ) : stickyPinnedMessage.photo_url ? (
                  <div className="flex items-center gap-2">
                    <ImageIcon size={16} className={currentDesign.pinnedText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.pinnedText} opacity-70 truncate`}>
                      Photo{stickyPinnedMessage.content ? `: ${stickyPinnedMessage.content}` : ''}
                    </span>
                  </div>
                ) : stickyPinnedMessage.video_url ? (
                  <div className="flex items-center gap-2">
                    <Video size={16} className={currentDesign.pinnedText} style={{ opacity: 0.7 }} />
                    <span className={`text-sm ${currentDesign.pinnedText} opacity-70 truncate`}>
                      Video{stickyPinnedMessage.content ? `: ${stickyPinnedMessage.content}` : stickyPinnedMessage.video_duration ? ` (${Math.floor(stickyPinnedMessage.video_duration / 60)}:${String(Math.floor(stickyPinnedMessage.video_duration % 60)).padStart(2, '0')})` : ''}
                    </span>
                  </div>
                ) : stickyPinnedMessage.message_type === 'gift' ? (() => {
                  const m = stickyPinnedMessage.content.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
                  const emoji = m ? m[1] : '🎁';
                  const name = m ? m[2] : '';
                  const price = m ? m[3] : '';
                  const recipient = m ? m[4] : '';
                  return (
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className="flex-shrink-0">{emoji}</span>
                      <span className={`${currentDesign.pinnedText} truncate`}>
                        sent <span className="font-semibold">{name}</span> to <span className="font-semibold">@{recipient}</span>
                        {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill dark={themeIsDarkMode} /></span>}
                      </span>
                      <span className="font-semibold text-cyan-400 flex-shrink-0">{price}</span>
                    </div>
                  );
                })() : (
                  <p className={`text-sm ${currentDesign.pinnedText} truncate`}>
                    {stickyPinnedMessage.content}
                  </p>
                )}
                  </div>
                </div>
              </div>
            </MessageActionsModal>
          )}
        </div>
      )}

      {/* Background Pattern Layer - Fixed behind everything */}
      <div
        className={`absolute inset-0 pointer-events-none ${backgroundStyles.classes}`}
        style={backgroundStyles.style}
      />

      {/* Messages Area */}
      {/* no-scroll-anchor class disables browser scroll anchoring on container AND all descendants */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className={`${currentDesign.messagesArea} no-scroll-anchor`}
      >
        {/* Dynamic padding-top to avoid overlap with sticky section */}
        <div
          className="relative z-10"
          style={{ paddingTop: stickyHeight > 0 ? `${stickyHeight + 8}px` : undefined }}
        >
        {/* Loading indicator for infinite scroll - positioned absolutely to avoid layout shift */}
        {loadingOlder && (
          <div className="absolute top-0 left-0 right-0 flex justify-center py-2 pointer-events-none z-30">
            <div className="animate-pulse text-gray-400 text-sm bg-black/50 px-3 py-1 rounded-full">Loading...</div>
          </div>
        )}
        {hasJoined && (() => {
          // Pre-compute thread groups for continuous thread lines
          const THREAD_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
          type ThreadGroup = { messages: { message: Message; index: number }[] };
          const threadGroups: ThreadGroup[] = [];
          let currentGroup: ThreadGroup | null = null;

          filteredMessages.forEach((message, index) => {
            const prevMessage = index > 0 ? filteredMessages[index - 1] : null;
            const timeDiff = prevMessage ?
              new Date(message.created_at).getTime() - new Date(prevMessage.created_at).getTime() :
              Infinity;

            const isFirstInThread = !prevMessage ||
              prevMessage.username !== message.username ||
              prevMessage.is_from_host ||
              message.is_from_host ||
              message.is_pinned ||
              timeDiff > THREAD_WINDOW_MS;

            if (isFirstInThread) {
              currentGroup = { messages: [{ message, index }] };
              threadGroups.push(currentGroup);
            } else {
              currentGroup!.messages.push({ message, index });
            }
          });

          return threadGroups.map((group) => {
            const isMultiMessage = group.messages.length > 1;
            const firstMsg = group.messages[0].message;

            // Get avatar settings from theme
            const avatarStyle = currentDesign.avatarStyle || 'pixel-art';
            const avatarSize = currentDesign.avatarSize || 'w-10 h-10';
            const avatarSpacing = currentDesign.avatarSpacing || 'mr-3';
            const avatarBorder = currentDesign.avatarBorder || '';

            // Avatar width for thread line positioning
            const avatarWidthMatch = avatarSize.match(/w-(\d+)/);
            const avatarWidthRem = avatarWidthMatch ? parseInt(avatarWidthMatch[1]) * 0.25 : 2.5;

            // Find the last message in this thread to get its timestamp
            const lastMessageInThread = group.messages[group.messages.length - 1].message;

            return (
              <div key={firstMsg.id} className="relative mt-3">
                {/* Single continuous thread line for multi-message groups */}
                {isMultiMessage && (
                  <div
                    className="absolute w-0.5 bg-zinc-600/30 pointer-events-none"
                    style={{
                      left: `${avatarWidthRem / 2}rem`,
                      transform: 'translateX(-50%)',
                      top: `${avatarWidthRem}rem`,
                      bottom: 0,
                    }}
                  />
                )}

                {group.messages.map(({ message, index: msgIndex }, groupIndex) => {
                  const isFirstInGroup = groupIndex === 0;
                  const isRegularMessage = !message.is_from_host && !message.is_pinned;
                  const showAvatar = isFirstInGroup || message.is_from_host || message.is_pinned;
                  const isLastMessage = msgIndex === filteredMessages.length - 1;
                  const innerMargin = isFirstInGroup ? '' : 'mt-0.5';
                  const bottomMargin = isLastMessage ? 'mb-3' : 'mb-3';

          return (
            <div key={message.id} data-message-id={message.id} className={`${innerMargin} ${bottomMargin} ${newMessageIds.has(message.id) ? 'animate-message-appear' : ''}`}>
              {/* Main message layout - flex with avatar column */}
              <div className="flex">
                {/* Avatar column - for all messages */}
                <div className={`${avatarSize} flex-shrink-0 ${avatarSpacing}`}>
                  {showAvatar ? (
                    <img
                      src={message.avatar_url || getDiceBearUrl(avatarStyle, message.username, 80)}
                      alt={message.username}
                      className={`${avatarSize} rounded-full bg-zinc-700 ${avatarBorder}`}
                    />
                  ) : (
                    /* Invisible spacer to maintain alignment */
                    <div className="w-full h-full" />
                  )}
                </div>

                {/* Content column */}
                <div className="flex-1 min-w-0">
                  <MessageActionsModal
                  message={message}
                  currentUsername={username}
                  isHost={chatRoom?.host.id === currentUserId}
                  themeIsDarkMode={themeIsDarkMode}
                  sessionToken={sessionToken}
                  themeColors={modalThemeColors}
                  isOutbid={!!(
                    message.is_pinned &&
                    message.sticky_until &&
                    new Date(message.sticky_until) > new Date() &&
                    stickyPinnedMessage?.id !== message.id
                  )}
                  onReply={disableReply ? undefined : handleReply}
                  onPin={handlePin}
                  onAddToPin={handleAddToPin}
                  getPinRequirements={getPinRequirements}
                  onBlock={handleBlockUser}
                  onTip={handleTipUser}
                  onSendGift={handleSendGift}
                  onThankGift={handleThankGift}
                  onDelete={handleDeleteMessage}
                  onReact={handleReactionToggle}
                  onHighlight={highlightMessage}
                  reactions={messageReactions[message.id] || message.reactions || []}
                >
                  {/* Username header for first regular message in thread */}
                  {isRegularMessage && isFirstInGroup && (
                    <div className="mb-1">
                      <div className="flex items-center gap-1">
                        <span
                          className={(() => {
                            const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                            return isMyMessage ? currentDesign.myUsername : currentDesign.regularUsername;
                          })() || 'text-sm font-semibold'}
                          style={{
                            color: (() => {
                              const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                              const field = isMyMessage ? currentDesign.myUsername : currentDesign.regularUsername;
                              const color = getTextColor(field) || '#ffffff';
                              return color;
                            })()
                          }}
                        >
                          {message.username}
                        </span>
                        {message.username_is_reserved && (
                          <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                        )}
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                      </div>
                    </div>
                  )}
                  {/* Host message header - OUTSIDE bubble */}
                  {message.is_from_host && (
                    <div className="mb-1">
                      <div className="flex items-center gap-1">
                        <span
                          className={(() => {
                            const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                            return isMyMessage
                              ? (currentDesign.myHostUsername || currentDesign.hostUsername || 'text-sm font-semibold')
                              : (currentDesign.hostUsername || 'text-sm font-semibold');
                          })()}
                          style={{
                            color: message.username.toLowerCase() === username.toLowerCase()
                              ? getTextColor(currentDesign.myHostUsername) || '#ef4444'  // Your own host messages
                              : getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff'
                          }}
                        >
                          {message.username}
                        </span>
                        {message.username_is_reserved && (
                          <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                        )}
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                        <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                      </div>
                    </div>
                  )}

                  {/* Pinned message header - OUTSIDE bubble (no $ value - only shown in sticky section) */}
                  {message.is_pinned && !message.is_from_host && (
                    <div className="mb-1">
                      <div className="flex items-center gap-1">
                        <span
                          className={(() => {
                            const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                            return isMyMessage ? currentDesign.myUsername : currentDesign.pinnedUsername;
                          })() || 'text-sm font-semibold'}
                          style={{
                            color: getTextColor(
                              message.username.toLowerCase() === username.toLowerCase()
                                ? currentDesign.myUsername
                                : currentDesign.pinnedUsername
                            ) || getTextColor(currentDesign.pinnedText) || '#ffffff'
                          }}
                        >
                          {message.username}
                        </span>
                        {message.username_is_reserved && (
                          <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                        )}
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                        <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full ${
                          themeIsDarkMode ? 'bg-white/10' : 'bg-black/10'
                        }`}>
                          <Pin size={12} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                          {message.pin_amount_paid && parseFloat(message.pin_amount_paid) > 0 && (
                            <span className={`text-xs font-medium ${themeIsDarkMode ? 'text-zinc-300' : 'text-gray-600'}`}>
                              ${message.pin_amount_paid}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Gift message card - special rendering */}
                  {message.message_type === 'gift' ? (
                    (() => {
                      // Parse "sent ☕ Coffee ($1) to @user"
                      const giftMatch = message.content.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
                      const emoji = giftMatch ? giftMatch[1] : '🎁';
                      const giftName = giftMatch ? giftMatch[2] : '';
                      const price = giftMatch ? giftMatch[3] : '';
                      const recipient = giftMatch ? giftMatch[4] : '';
                      const isForMe = recipient.toLowerCase() === username.toLowerCase();
                      return (
                        <div className={`relative rounded-xl px-3 py-2.5 text-center max-w-[calc(100%-2.5%-5rem+5px)] ${
                          isForMe
                            ? themeIsDarkMode
                              ? 'bg-purple-950/50 border border-purple-500/50'
                              : 'bg-purple-100/80 border border-purple-400/50'
                            : themeIsDarkMode
                              ? 'bg-gradient-to-b from-zinc-800 to-zinc-800/60 border border-zinc-700'
                              : 'bg-gradient-to-b from-purple-50/80 to-white border border-purple-200/60'
                        }`}>
                          {message.is_gift_acknowledged && (
                            <div className="absolute top-1.5 left-2 text-sm" title="Thanked">
                              🤗
                            </div>
                          )}
                          {price && (
                            <div className={`absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                              themeIsDarkMode ? 'bg-cyan-900/50 text-cyan-400' : 'bg-purple-100 text-purple-600'
                            }`}>
                              {price}
                            </div>
                          )}
                          <div className="text-3xl mb-1">{emoji}</div>
                          <div className={`text-xs font-bold ${themeIsDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {giftName || message.content}
                          </div>
                          {recipient && (
                            <div className={`text-[10px] mt-1 ${themeIsDarkMode ? 'text-zinc-500' : 'text-gray-400'}`}>
                              to <span className={`font-semibold ${
                                isForMe
                                  ? (themeIsDarkMode ? 'text-purple-400' : 'text-purple-600')
                                  : (themeIsDarkMode ? 'text-zinc-300' : 'text-gray-600')
                              }`}>@{recipient}</span>
                              {isForMe && <span className="ml-1"><YouPill dark={themeIsDarkMode} /></span>}
                            </div>
                          )}
                        </div>
                      );
                    })()
                  ) : (
                  /* Message bubble */
                  <div
                    className={(() => {
                      const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                      const selectedStyle = message.is_from_host
                        ? currentDesign.hostMessage + ' flex-1'
                        : message.is_pinned
                        ? currentDesign.pinnedMessage
                        : isMyMessage
                        ? currentDesign.myMessage
                        : currentDesign.regularMessage;

                      // Add extra margin for media-only messages (no text caption)
                      const hasMedia = message.voice_url || message.photo_url || message.video_url;
                      const hasCaption = message.content && message.content.trim().length > 0;
                      const isMediaOnly = hasMedia && !hasCaption;
                      return isMediaOnly ? `${selectedStyle} mt-2` : selectedStyle;
                    })()}
                  >

                    {/* Reply context preview */}
                    {message.reply_to_message && (
                      <div
                        className={`mb-2 p-2 rounded-lg cursor-pointer transition-colors ${
                          themeIsDarkMode
                            ? message.username.toLowerCase() === username.toLowerCase()
                              ? 'bg-white/10 border border-white/10 hover:bg-white/15'
                              : 'bg-white/10 border border-zinc-600 hover:bg-white/15'
                            : message.username.toLowerCase() === username.toLowerCase()
                              ? 'bg-white/95 border border-gray-200 hover:bg-white shadow-sm'
                              : 'bg-white border border-gray-200 hover:bg-gray-50 shadow-sm'
                        }`}
                        onClick={() => scrollToMessage(message.reply_to_message!.id)}
                      >
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className={`w-3 h-3 flex-shrink-0 ${themeIsDarkMode ? 'text-gray-300' : 'text-blue-600'}`} />
                          <span
                            className="text-xs font-semibold"
                            style={{
                              color: message.reply_to_message.is_from_host
                                ? (getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff')
                                : message.reply_to_message.is_pinned && !message.reply_to_message.is_from_host
                                  ? (getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff')
                                  : message.reply_to_message.username.toLowerCase() === username.toLowerCase()
                                    ? (getTextColor(currentDesign.myUsername) || '#ef4444')
                                    : (getTextColor(currentDesign.regularUsername) || (themeIsDarkMode ? '#ffffff' : '#111827'))
                            }}
                          >
                            {message.reply_to_message.username}
                          </span>
                          {message.reply_to_message.username_is_reserved && (
                            <BadgeCheck size={12} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#34d399' }} />
                          )}
                          {message.reply_to_message.username.toLowerCase() === username.toLowerCase() && <YouPill dark={themeIsDarkMode} />}
                          {message.reply_to_message.is_from_host && (
                            <Crown size={12} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                          )}
                          {message.reply_to_message.is_pinned && !message.reply_to_message.is_from_host && (
                            <Pin size={12} className="flex-shrink-0" style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                          )}
                        </div>
                        {(() => {
                          const c = message.reply_to_message!.content;
                          const isGift = message.reply_to_message!.message_type === 'gift' || c.match(/^sent\s+\S+\s+.+?\s+\(\$[\d,.]+\)\s+to\s+@/);
                          if (isGift) {
                            const m = c.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
                            const emoji = m ? m[1] : '🎁';
                            const name = m ? m[2] : '';
                            const price = m ? m[3] : '';
                            const recipient = m ? m[4] : '';
                            return (
                              <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 mt-1 text-xs ${
                                themeIsDarkMode
                                  ? 'bg-zinc-700/60 border border-zinc-600/50'
                                  : 'bg-gray-100 border border-gray-200/50'
                              }`}>
                                <span className="text-sm flex-shrink-0">{emoji}</span>
                                <span className={themeIsDarkMode ? 'text-zinc-300' : 'text-gray-600'}>
                                  sent to <span className="font-semibold">@{recipient}</span>
                                  {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill dark={themeIsDarkMode} /></span>}
                                </span>
                              </div>
                            );
                          }
                          return (
                            <p className={`text-xs truncate ${themeIsDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                              {c || '[Voice message]'}
                            </p>
                          );
                        })()}
                      </div>
                    )}

                    {/* Caption text - shown above media when message has both */}
                    {message.content && (message.voice_url || message.photo_url || message.video_url) && (
                      <p className={`mb-2 ${
                        message.is_from_host
                          ? currentDesign.hostText
                          : message.is_pinned
                          ? currentDesign.pinnedText
                          : message.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myText
                          : currentDesign.regularText
                      }`}>
                        {message.content}
                      </p>
                    )}

                    {/* Message content + floating reaction pill */}
                    <div className="relative w-fit max-w-full">
                    {message.voice_url ? (
                      <VoiceMessagePlayer
                        voiceUrl={`${message.voice_url}${message.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                        duration={message.voice_duration || 0}
                        waveformData={message.voice_waveform || []}
                        isMyMessage={message.username.toLowerCase() === username.toLowerCase()}
                        voiceContainerBg={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.containerBg
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.containerBg
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.containerBg
                            : currentDesign.voiceMessageStyles?.containerBg
                        }
                        voicePlayButton={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.playButton
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.playButton
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.playButton
                            : currentDesign.voiceMessageStyles?.playButton
                        }
                        voicePlayIconColor={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.playIconColor
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.playIconColor
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.playIconColor
                            : currentDesign.voiceMessageStyles?.playIconColor
                        }
                        voiceWaveformActive={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.waveformActive
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.waveformActive
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.waveformActive
                            : currentDesign.voiceMessageStyles?.waveformActive
                        }
                        voiceWaveformInactive={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.waveformInactive
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.waveformInactive
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.waveformInactive
                            : currentDesign.voiceMessageStyles?.waveformInactive
                        }
                        durationTextColor={
                          message.is_from_host
                            ? currentDesign.hostVoiceMessageStyles?.durationTextColor
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.durationTextColor
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.durationTextColor
                            : currentDesign.voiceMessageStyles?.durationTextColor
                        }
                      />
                    ) : message.photo_url ? (
                      <PhotoMessage
                        photoUrl={`${message.photo_url}${message.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                        width={message.photo_width || 300}
                        height={message.photo_height || 200}
                      />
                    ) : message.video_url ? (
                      <VideoMessage
                        videoUrl={`${message.video_url}${message.video_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                        thumbnailUrl={message.video_thumbnail_url ? `${message.video_thumbnail_url}${message.video_thumbnail_url.includes('?') ? '&' : '?'}session_token=${sessionToken}` : ''}
                        duration={message.video_duration || 0}
                        width={message.video_width}
                        height={message.video_height}
                      />
                    ) : message.content ? (
                      <p className={
                        message.is_from_host
                          ? currentDesign.hostText
                          : message.is_pinned
                          ? currentDesign.pinnedText
                          : message.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myText
                          : currentDesign.regularText
                      }>
                        {message.content}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-500 italic">
                        [Media message - loading...]
                      </p>
                    )}
                    </div>
                  </div>
                  )}
                {/* Timestamp + Reaction pills row */}
                <div className="flex items-center mt-1 gap-2 h-6">
                  <span
                    className="text-[10px] opacity-60"
                    style={{
                      color: getTextColor(
                        message.is_from_host
                          ? currentDesign.hostTimestamp
                          : message.is_pinned
                          ? currentDesign.pinnedTimestamp
                          : message.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myTimestamp
                          : currentDesign.regularTimestamp
                      ) || '#ffffff'
                    }}
                  >
                    {formatTimestamp(message.created_at)}
                  </span>
                  <ReactionBar
                    reactions={messageReactions[message.id] || message.reactions || []}
                    onReactionClick={(emoji) => handleReactionToggle(message.id, emoji)}
                    themeIsDarkMode={themeIsDarkMode}
                    highlightTheme={currentDesign.reactionHighlightBg ? {
                      reaction_highlight_bg: currentDesign.reactionHighlightBg,
                      reaction_highlight_border: currentDesign.reactionHighlightBorder,
                      reaction_highlight_text: currentDesign.reactionHighlightText,
                    } : undefined}
                    fullWidth={message.is_from_host}
                  />
                </div>
                </MessageActionsModal>
              </div>
            </div>
          </div>
                  );
                })}
              </div>
            );
          });
        })()}
        {/* Spacer to ensure last message is visible above input */}
        <div ref={messagesEndRef} style={{ overflowAnchor: 'none' }} />
        </div>
      </div>
    </div>
  );
}

// Memoize to prevent re-renders when parent re-renders but props haven't changed
export default memo(MainChatView);
