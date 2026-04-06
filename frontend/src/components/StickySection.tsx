'use client';

import React, { useMemo, useRef, useState, useLayoutEffect, useEffect, memo } from 'react';
import { BadgeCheck, Crown, Pin, Mic, ImageIcon, Video, ChevronUp, CornerDownRight, Ban } from 'lucide-react';
import MessageActionsModal from './MessageActionsModal';
import { ChatRoom, Message, ReactionSummary } from '@/lib/api';

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

function getIconColor(tailwindClass: string | undefined): string | undefined {
  if (!tailwindClass) return undefined;
  return tailwindColors[tailwindClass.trim()];
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

function getTextColor(classString: string | undefined): string | undefined {
  if (!classString) return undefined;
  const classes = classString.split(' ');
  for (const cls of classes) {
    const cleanClass = cls.replace(/^!/, '').replace(/\\/g, '');
    if (tailwindColors[cleanClass]) return tailwindColors[cleanClass];
    const match = cleanClass.match(/^text-([a-z]+)-(\d+)$/);
    if (match) {
      const [, colorName, shade] = match;
      const shadeNum = parseInt(shade);
      if (tailwindColorValues[colorName]?.[shadeNum]) return tailwindColorValues[colorName][shadeNum];
    }
    if (cleanClass === 'text-white') return '#ffffff';
    if (cleanClass === 'text-black') return '#000000';
  }
  return undefined;
}

function formatTimestamp(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const todayOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterdayOnly = new Date(todayOnly);
  yesterdayOnly.setDate(yesterdayOnly.getDate() - 1);
  const daysDiff = Math.floor((todayOnly.getTime() - dateOnly.getTime()) / (1000 * 60 * 60 * 24));
  if (dateOnly.getTime() === todayOnly.getTime()) return `Today ${time}`;
  if (dateOnly.getTime() === yesterdayOnly.getTime()) return `Yesterday ${time}`;
  if (daysDiff < 7 && daysDiff > 0) {
    const dayName = date.toLocaleDateString('en-US', { weekday: 'short' });
    return `${dayName} ${time}`;
  }
  const month = date.getMonth() + 1;
  const day = date.getDate();
  return `${month}/${day} ${time}`;
}

function getDiceBearUrl(style: string, seed: string, size: number = 80): string {
  return `https://api.dicebear.com/7.x/${style}/svg?seed=${encodeURIComponent(seed)}&size=${size}`;
}

function YouPill({ className }: { className?: string }) {
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none ${
      className || 'bg-white/10 text-zinc-400'
    }`}>you</span>
  );
}

function HostPill({ color }: { color?: string }) {
  const c = color || '#2dd4bf';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none"
      style={{ backgroundColor: `${c}20`, color: c }}
    >host</span>
  );
}

function BannedPill() {
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none inline-flex items-center gap-0.5"
      style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#ef4444' }}
    ><Ban size={9} />banned</span>
  );
}

interface StickySectionProps {
  stickyHostMessages: Message[];
  stickyPinnedMessage: Message | null;
  messageReactions: Record<string, ReactionSummary[]>;
  username: string;
  currentUserId: string | null;
  chatRoom: ChatRoom | null;
  sessionToken: string | null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  currentDesign: Record<string, any>;
  themeIsDarkMode: boolean;
  messagesContainerRef: React.RefObject<HTMLDivElement | null>;
  scrollToMessage: (messageId: string) => void;
  cancelScrollAnimation?: () => void;
  highlightMessage?: (messageId: string) => void;
  expandStickySignal?: number;
  onStickyHeightChange?: (height: number) => void;
  onStickyHiddenChange?: (hidden: boolean) => void;
  // Shared refs for scroll compensation (owned by MainChatView)
  stickyToggleRef: React.MutableRefObject<boolean>;
  pendingToggleRef: React.MutableRefObject<boolean>;
  savedDistFromBottomRef: React.MutableRefObject<number>;
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
  handleBlockUser: (username: string) => void;
  handleUnblockUser: (username: string) => void;
  handleUnmuteUser?: (username: string) => void;
  mutedUsernames?: Set<string>;
  onRequestSignup?: () => void;
  handleTipUser: (username: string) => void;
  handleSendGift: (giftId: string, recipientUsername: string) => Promise<boolean>;
  handleThankGift: (messageId: string) => Promise<boolean>;
  handleBroadcastMessage: (messageId: string) => Promise<boolean>;
  handleDeleteMessage: (messageId: string) => void;
  handleReactionToggle: (messageId: string, emoji: string) => void;
}

function StickySection({
  stickyHostMessages,
  stickyPinnedMessage,
  messageReactions,
  username,
  currentUserId,
  chatRoom,
  sessionToken,
  currentDesign,
  themeIsDarkMode,
  messagesContainerRef,
  scrollToMessage,
  cancelScrollAnimation,
  highlightMessage,
  expandStickySignal,
  onStickyHeightChange,
  onStickyHiddenChange,
  handleReply,
  disableReply = false,
  handlePin,
  handleAddToPin,
  getPinRequirements,
  handleBlockUser,
  handleUnblockUser,
  handleUnmuteUser,
  mutedUsernames,
  onRequestSignup,
  handleTipUser,
  handleSendGift,
  handleThankGift,
  handleBroadcastMessage,
  handleDeleteMessage,
  handleReactionToggle,
  stickyToggleRef,
  pendingToggleRef,
  savedDistFromBottomRef,
}: StickySectionProps) {
  const stickySectionRef = useRef<HTMLDivElement>(null);
  const stickyContentWrapperRef = useRef<HTMLDivElement>(null);
  const stickyContentKeyRef = useRef<string>('');
  const stickyToggleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const touchStartYRef = useRef<number | null>(null);

  const [stickyHidden, setStickyHidden] = useState(false);
  const stickyHiddenRef = useRef(false);
  const [stickyHeight, setStickyHeight] = useState(0);

  const initialRenderDoneRef = useRef(false);
  const [allowAnimations, setAllowAnimations] = useState(false);
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  // Mark a toggle in progress — blocks ResizeObserver and scroll compensation for 220ms
  const markStickyToggle = () => {
    stickyToggleRef.current = true;
    cancelScrollAnimation?.();
    const container = messagesContainerRef.current;
    if (container) {
      savedDistFromBottomRef.current = Math.max(0,
        container.scrollHeight - container.scrollTop - container.clientHeight
      );
    }
    pendingToggleRef.current = true;
    if (stickyToggleTimerRef.current) clearTimeout(stickyToggleTimerRef.current);
    stickyToggleTimerRef.current = setTimeout(() => {
      stickyToggleRef.current = false;
      const el = stickySectionRef.current;
      if (el) {
        setStickyHeight(el.offsetHeight);
      }
    }, 220);
  };

  // Expand sticky section when signaled from parent
  useEffect(() => {
    if (expandStickySignal && stickyHidden) {
      markStickyToggle();
      setStickyHidden(false);
    }
  }, [expandStickySignal]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep stickyHiddenRef in sync
  useEffect(() => {
    stickyHiddenRef.current = stickyHidden;
  }, [stickyHidden]);

  // Notify parent when stickyHidden changes (for FAB strip animation)
  useEffect(() => {
    onStickyHiddenChange?.(stickyHidden);
  }, [stickyHidden, onStickyHiddenChange]);

  // Compute theme colors for modal badges/icons
  const modalThemeColors = useMemo(() => ({
    badgeIcon: getIconColor(currentDesign.badgeIconColor) || '#3b82f6',
    crownIcon: getIconColor(currentDesign.crownIconColor) || '#2dd4bf',
    pinIcon: getIconColor(currentDesign.pinIconColor) || '#fbbf24',
    hostUsername: getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff',
    pinnedUsername: getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff',
    myUsername: getTextColor(currentDesign.myUsername) || '#ef4444',
    regularUsername: getTextColor(currentDesign.regularUsername) || '#ffffff',
  }), [currentDesign]);

  // Measure sticky section height dynamically
  useLayoutEffect(() => {
    const stickyEl = stickySectionRef.current;
    const hasSticky = stickyHostMessages.length > 0 || stickyPinnedMessage;

    if (!stickyEl || !hasSticky) {
      setStickyHeight(0);
      return;
    }

    const height = stickyEl.offsetHeight;
    setStickyHeight(height);

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const height = entry.borderBoxSize?.[0]?.blockSize ?? (entry.target as HTMLElement).offsetHeight;
        if (stickyToggleRef.current) return;
        setStickyHeight(height);
      }
    });

    resizeObserver.observe(stickyEl);
    return () => resizeObserver.disconnect();
  }, [stickyHostMessages.length, stickyPinnedMessage]);

  // Notify parent of sticky height changes
  useEffect(() => {
    onStickyHeightChange?.(stickyHeight);
  }, [stickyHeight, onStickyHeightChange]);

  // Track sticky content identity to detect new arrivals
  const stickyContentKey = useMemo(() => {
    const hostIds = stickyHostMessages.map(m => m.id).join(',');
    const pinnedId = stickyPinnedMessage?.id || '';
    return `${hostIds}|${pinnedId}`;
  }, [stickyHostMessages, stickyPinnedMessage]);

  // Auto-reopen sticky section when new sticky content arrives
  useEffect(() => {
    if (!stickyContentKeyRef.current) {
      stickyContentKeyRef.current = stickyContentKey;
      return;
    }
    if (stickyContentKey !== stickyContentKeyRef.current) {
      stickyContentKeyRef.current = stickyContentKey;
      if (stickyHidden) {
        markStickyToggle();
      }
      setStickyHidden(false);
    }
  }, [stickyContentKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Track new sticky message IDs for animation
  useEffect(() => {
    const allStickyMessages = [...stickyHostMessages];
    if (stickyPinnedMessage) allStickyMessages.push(stickyPinnedMessage);
    for (const message of allStickyMessages) {
      seenMessageIdsRef.current.add(message.id);
    }
    if (!initialRenderDoneRef.current && allStickyMessages.length > 0) {
      setTimeout(() => {
        initialRenderDoneRef.current = true;
        setAllowAnimations(true);
      }, 100);
    }
  }, [stickyHostMessages, stickyPinnedMessage]);

  // Don't render if no sticky content
  if (stickyHostMessages.length === 0 && !stickyPinnedMessage) {
    return null;
  }

  return (
    <div
      ref={stickySectionRef}
      data-sticky-section
      className={`${currentDesign.stickySection} ${stickyHidden ? '!pt-0' : ''}`}
      style={stickyHidden ? { backgroundColor: currentDesign.stickyCollapsedBg || '#18181b' } : undefined}
      onTouchStart={(e) => {
        touchStartYRef.current = e.touches[0].clientY;
      }}
      onTouchEnd={(e) => {
        if (touchStartYRef.current !== null) {
          const deltaY = touchStartYRef.current - e.changedTouches[0].clientY;
          if (deltaY > 30 && !stickyHidden) {
            markStickyToggle();
            setStickyHidden(true);
          } else if (deltaY < -30 && stickyHidden) {
            markStickyToggle();
            setStickyHidden(false);
          }
          touchStartYRef.current = null;
        }
      }}
    >
      <div
        ref={stickyContentWrapperRef}
        style={{
          display: 'grid',
          gridTemplateRows: stickyHidden ? '0fr' : '1fr',
          transition: 'grid-template-rows 200ms ease-out',
        }}
      >
        <div className="space-y-2" style={{ overflow: 'hidden' }}>
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
              modalStyles={currentDesign.modalStyles}
              emojiPickerStyles={currentDesign.emojiPickerStyles}
              giftStyles={currentDesign.giftStyles}
              videoPlayerStyles={currentDesign.videoPlayerStyles}
              onReply={disableReply ? undefined : handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onUnblock={handleUnblockUser}
              onUnmute={handleUnmuteUser}
              mutedUsernames={mutedUsernames}
              onRequestSignup={onRequestSignup}
              onTip={handleTipUser}
              onSendGift={handleSendGift}
              onThankGift={handleThankGift}
              onBroadcast={handleBroadcastMessage}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
              onHighlight={highlightMessage}
              reactions={messageReactions[message.id] || message.reactions || []}
            >
              <div
                className={`${currentDesign.stickyHostMessage} !py-1.5 w-full relative transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <div className="relative flex-shrink-0 mt-1">
                    <img
                      src={message.avatar_url || getDiceBearUrl(currentDesign.avatarStyle || 'pixel-art', message.username, 80)}
                      alt={message.username}
                      className={`${currentDesign.avatarSize || 'w-10 h-10'} rounded-full ${currentDesign.uiStyles?.avatarFallbackBg || 'bg-zinc-700'} ${currentDesign.avatarBorder || ''}`}
                    />
                    <Crown size={14} fill="currentColor" className="absolute -top-1.5 -left-1" style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf', transform: 'rotate(-30deg)' }} />
                    {message.username_is_reserved && (
                      <BadgeCheck size={12} className="absolute -bottom-0.5 -right-0.5 rounded-full" style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6', backgroundColor: currentDesign.uiStyles?.badgeIconBg || '#18181b' }} />
                    )}
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-1">
                      <span
                        className={currentDesign.stickyHostUsername || 'text-sm font-semibold'}
                        style={{ color: getTextColor(currentDesign.stickyHostUsername || currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                      >
                        {message.username}
                      </span>
                      {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
                      <HostPill color={getIconColor(currentDesign.crownIconColor) || '#2dd4bf'} />
                      <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                      {message.is_banned && <BannedPill />}
                    </div>
                <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                  <span
                    className="text-xs opacity-60"
                    style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                  >
                    {formatTimestamp(message.created_at)}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); scrollToMessage(message.id); }}
                    className="p-1 rounded-full opacity-50 hover:opacity-100 active:opacity-100 transition-opacity"
                    aria-label="Go to message"
                  >
                    <CornerDownRight size={14} style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }} />
                  </button>
                </div>
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
                ) : message.message_type === 'gift' ? (() => {
                  const m = message.content.match(/sent\s+(\S+)\s+(.+?)\s+\(\$[\d,.]+\)\s+to\s+@(\S+)/);
                  const emoji = m ? m[1] : '🎁';
                  const recipient = m ? m[3] : '';
                  return (
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className={`${currentDesign.hostText} truncate`}>
                        sent {emoji} to <span className="font-semibold">@{recipient}</span>
                        {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                      </span>
                    </div>
                  );
                })() : (
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
              modalStyles={currentDesign.modalStyles}
              emojiPickerStyles={currentDesign.emojiPickerStyles}
              giftStyles={currentDesign.giftStyles}
              videoPlayerStyles={currentDesign.videoPlayerStyles}
              onReply={disableReply ? undefined : handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onUnblock={handleUnblockUser}
              onUnmute={handleUnmuteUser}
              mutedUsernames={mutedUsernames}
              onRequestSignup={onRequestSignup}
              onTip={handleTipUser}
              onSendGift={handleSendGift}
              onThankGift={handleThankGift}
              onBroadcast={handleBroadcastMessage}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
              onHighlight={highlightMessage}
              reactions={messageReactions[stickyPinnedMessage.id] || stickyPinnedMessage.reactions || []}
            >
              <div
                className={`${currentDesign.stickyPinnedMessage} !py-1.5 w-full relative transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <div className="relative flex-shrink-0 mt-0.5">
                    <img
                      src={stickyPinnedMessage.avatar_url || getDiceBearUrl(currentDesign.avatarStyle || 'pixel-art', stickyPinnedMessage.username, 80)}
                      alt={stickyPinnedMessage.username}
                      className={`${currentDesign.avatarSize || 'w-10 h-10'} rounded-full ${currentDesign.uiStyles?.avatarFallbackBg || 'bg-zinc-700'} ${currentDesign.avatarBorder || ''}`}
                    />
                    {stickyPinnedMessage.username.toLowerCase() === chatRoom?.host?.reserved_username?.toLowerCase() && (
                      <Crown size={14} fill="currentColor" className="absolute -top-1.5 -left-1" style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf', transform: 'rotate(-30deg)' }} />
                    )}
                    {stickyPinnedMessage.username_is_reserved && (
                      <BadgeCheck size={12} className="absolute -bottom-0.5 -right-0.5 rounded-full" style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6', backgroundColor: currentDesign.uiStyles?.badgeIconBg || '#18181b' }} />
                    )}
                  </div>
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1 mb-1">
                      <span
                        className={currentDesign.stickyPinnedUsername || 'text-sm font-semibold'}
                        style={{ color: getTextColor(currentDesign.stickyPinnedUsername || currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                      >
                        {stickyPinnedMessage.username}
                      </span>
                  {stickyPinnedMessage.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
                  {stickyPinnedMessage.is_banned && <BannedPill />}
                  <div className={`flex items-center gap-1 px-1.5 py-0.5 rounded-full ${
                    currentDesign.uiStyles?.pinBadgeBg || 'bg-white/10'
                  }`}>
                    <Pin size={12} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                    <span className={`text-xs font-medium ${currentDesign.pinnedText}`}>
                      ${stickyPinnedMessage.current_pin_amount}
                    </span>
                  </div>
                </div>
                <div className="absolute top-2 right-2 flex flex-col items-end gap-1">
                  <span
                    className="text-xs opacity-60"
                    style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                  >
                    {formatTimestamp(stickyPinnedMessage.created_at)}
                  </span>
                  <button
                    onClick={(e) => { e.stopPropagation(); scrollToMessage(stickyPinnedMessage.id); }}
                    className="p-1 rounded-full opacity-50 hover:opacity-100 active:opacity-100 transition-opacity"
                    aria-label="Go to message"
                  >
                    <CornerDownRight size={14} style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }} />
                  </button>
                </div>
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
                  const recipient = m ? m[4] : '';
                  return (
                    <div className="flex items-center gap-1.5 text-sm">
                      <span className={`${currentDesign.pinnedText} truncate`}>
                        sent {emoji} to <span className="font-semibold">@{recipient}</span>
                        {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                      </span>
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
      </div>
      <button
        onClick={() => {
          markStickyToggle();
          setStickyHidden(h => !h);
        }}
        className={`w-full flex items-center justify-center -my-1 transition-opacity`}
      >
        <ChevronUp
          size={14}
          style={{
            transition: 'transform 200ms ease-out',
            transform: stickyHidden ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>
    </div>
  );
}

export default memo(StickySection);
