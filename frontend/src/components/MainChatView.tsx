'use client';

// Tailwind safelist: dynamic theme classes from database that must be generated
// bg-[#1f1f23] border-[#1f1f23] bg-zinc-800/40 border-zinc-800/40 border-transparent
// bg-purple-900 border-purple-500/40 bg-purple-500/30
// bg-gradient-to-t from-purple-500 to-blue-500
// bg-zinc-900/95 bg-zinc-900/90 border-purple-500/30

import React, { useMemo, useRef, useState, useLayoutEffect, useEffect, memo } from 'react';
import { BadgeCheck, Reply, Crown, Pin, Radio, Mic, ImageIcon, Video, Gift, Frown, Eye, ChevronDown } from 'lucide-react';
import MessageActionsModal from './MessageActionsModal';
import VoiceMessagePlayer from './VoiceMessagePlayer';
import PhotoMessage from './PhotoMessage';
import VideoMessage from './VideoMessage';
import ReactionBar from './ReactionBar';
import StickySection from './StickySection';
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
function YouPill({ className }: { className?: string }) {
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none ${
      className || 'bg-white/10 text-zinc-400'
    }`}>you</span>
  );
}

// "host" pill shown next to host usernames
function HostPill({ color }: { color?: string }) {
  const c = color || '#2dd4bf';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none"
      style={{ backgroundColor: `${c}20`, color: c }}
    >host</span>
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
  cancelScrollAnimation?: () => void;
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
  handleBroadcastMessage: (messageId: string) => Promise<boolean>;
  handleDeleteMessage: (messageId: string) => void;
  handleReactionToggle: (messageId: string, emoji: string) => void;
  messageReactions: Record<string, ReactionSummary[]>;
  loadingOlder?: boolean;
  filterLoading?: boolean;
  filterMode?: 'all' | 'focus' | 'gifts' | 'broadcast';
  filterLoadingText?: string;
  onStickyHeightChange?: (height: number) => void;
  onStickyHiddenChange?: (hidden: boolean) => void;
  showScrollToBottom?: boolean;
  onScrollToBottom?: () => void;
  expandStickySignal?: number;
  hiddenMode?: boolean;
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
  cancelScrollAnimation,
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
  handleBroadcastMessage,
  handleDeleteMessage,
  handleReactionToggle,
  messageReactions,
  loadingOlder = false,
  filterLoading = false,
  filterMode = 'all',
  filterLoadingText = 'Loading...',
  onStickyHeightChange,
  onStickyHiddenChange,
  showScrollToBottom = false,
  onScrollToBottom,
  expandStickySignal,
  hiddenMode = false,
}: MainChatViewProps) {
  // Local stickyHeight for paddingTop — updated via callback from StickySection
  const [stickyHeight, setStickyHeight] = useState(0);

  // Shared refs for scroll compensation — StickySection writes, MainChatView reads
  const stickyToggleRef = useRef(false);
  const pendingToggleRef = useRef(false);
  const savedDistFromBottomRef = useRef(0);
  const prevStickyHeightRef = useRef(0);

  // Track viewport height for responsive photo sizing
  const [viewportHeight, setViewportHeight] = useState(0);
  useEffect(() => {
    setViewportHeight(window.innerHeight);
    const handleResize = () => setViewportHeight(window.innerHeight);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Compute theme colors for modal badges/icons (memoized)
  const modalThemeColors = useMemo(() => ({
    badgeIcon: getIconColor(currentDesign.badgeIconColor) || '#3b82f6',
    crownIcon: getIconColor(currentDesign.crownIconColor) || '#2dd4bf',
    pinIcon: getIconColor(currentDesign.pinIconColor) || '#fbbf24',
    hostUsername: getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff',
    pinnedUsername: getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff',
    myUsername: getTextColor(currentDesign.myUsername) || '#ef4444',
    regularUsername: getTextColor(currentDesign.regularUsername) || '#ffffff',
  }), [currentDesign]);

  // Track if initial render is complete - skip all animations until then
  const initialRenderDoneRef = useRef(false);

  // Track message IDs we've already seen to only animate new messages
  const seenMessageIdsRef = useRef<Set<string>>(new Set());

  // Notify parent of sticky height changes (for FAB strip positioning)
  useEffect(() => {
    onStickyHeightChange?.(stickyHeight);
  }, [stickyHeight, onStickyHeightChange]);

  // Compensate scroll position when sticky height changes (runs in same render as paddingTop update)
  useLayoutEffect(() => {
    if (stickyToggleRef.current) {
      prevStickyHeightRef.current = stickyHeight;
      return;
    }
    if (pendingToggleRef.current) {
      pendingToggleRef.current = false;
      const container = messagesContainerRef.current;
      if (container) {
        const currentDist = container.scrollHeight - container.scrollTop - container.clientHeight;
        if (currentDist < 50) {
          container.scrollTo({ top: container.scrollHeight - container.clientHeight, behavior: 'instant' });
        } else {
          const maxScroll = container.scrollHeight - container.clientHeight;
          const savedDist = Math.max(0, savedDistFromBottomRef.current);
          container.scrollTo({ top: Math.max(0, Math.min(maxScroll, maxScroll - savedDist)), behavior: 'instant' });
        }
      }
      prevStickyHeightRef.current = stickyHeight;
      return;
    }
    const container = messagesContainerRef.current;
    if (container) {
      const delta = stickyHeight - prevStickyHeightRef.current;
      if (delta !== 0) {
        const distFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
        const wasAtBottom = distFromBottom < 150;
        if (wasAtBottom) {
          container.scrollTo({ top: container.scrollHeight - container.clientHeight, behavior: 'instant' });
        } else {
          container.scrollTo({ top: container.scrollTop + delta, behavior: 'instant' });
        }
      }
    }
    prevStickyHeightRef.current = stickyHeight;
  }, [stickyHeight]);

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
      setTimeout(() => {
        initialRenderDoneRef.current = true;
      }, 100);
    }
  }, [filteredMessages]);

  return (
    <div className={`h-full overflow-hidden relative ${currentDesign.messagesAreaContainer || 'bg-zinc-900'}`}>
      {/* Sticky Section: Host + Pinned Messages - Extracted component for Android perf */}
      <StickySection
        stickyHostMessages={stickyHostMessages}
        stickyPinnedMessage={stickyPinnedMessage}
        messageReactions={messageReactions}
        username={username}
        currentUserId={currentUserId}
        chatRoom={chatRoom}
        sessionToken={sessionToken}
        currentDesign={currentDesign}
        themeIsDarkMode={themeIsDarkMode}
        messagesContainerRef={messagesContainerRef}
        scrollToMessage={scrollToMessage}
        cancelScrollAnimation={cancelScrollAnimation}
        highlightMessage={highlightMessage}
        expandStickySignal={expandStickySignal}
        onStickyHeightChange={setStickyHeight}
        onStickyHiddenChange={onStickyHiddenChange}
        handleReply={handleReply}
        disableReply={disableReply}
        handlePin={handlePin}
        handleAddToPin={handleAddToPin}
        getPinRequirements={getPinRequirements}
        handleBlockUser={handleBlockUser}
        handleTipUser={handleTipUser}
        handleSendGift={handleSendGift}
        handleThankGift={handleThankGift}
        handleBroadcastMessage={handleBroadcastMessage}
        handleDeleteMessage={handleDeleteMessage}
        handleReactionToggle={handleReactionToggle}
        stickyToggleRef={stickyToggleRef}
        pendingToggleRef={pendingToggleRef}
        savedDistFromBottomRef={savedDistFromBottomRef}
      />

      {/* Content below sticky — hidden when in separate view rooms (game room) */}
      <div className={hiddenMode ? 'hidden' : 'contents'}>

      {/* Background Pattern Layer - Fixed behind everything */}
      <div
        className={`absolute inset-0 pointer-events-none ${backgroundStyles.classes}`}
        style={backgroundStyles.style}
      />

      {/* Filter Loading Overlay — z-[15] sits above messages (z-10) but below sticky section (z-20) */}
      {filterLoading && (
        <div className={`absolute inset-0 z-[15] flex items-center justify-center ${
          currentDesign.uiStyles?.loadingBg || 'bg-zinc-900'
        }`}>
          <div className={`flex items-center gap-2.5 px-5 py-3 rounded-2xl ${
            currentDesign.uiStyles?.loadingCard || 'bg-zinc-800 text-zinc-200'
          }`}>
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium">
              {filterLoadingText}
            </span>
          </div>
        </div>
      )}

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
            <div className={`animate-pulse text-sm px-3 py-1 rounded-full ${currentDesign.uiStyles?.loadingIndicatorText || 'text-gray-400'} ${currentDesign.uiStyles?.loadingIndicatorBg || 'bg-black/50'}`}>Loading...</div>
          </div>
        )}
        {/* Empty state for filtered views */}
        {hasJoined && !filterLoading && filteredMessages.length === 0 && filterMode !== 'all' && (
          <div className="flex flex-col items-center justify-center py-20 gap-3 pr-14">
            <div className={`flex items-center gap-1.5 ${currentDesign.uiStyles?.emptyStateText || 'text-zinc-600'}`}>
              {filterMode === 'gifts'
                ? <><Gift size={96} /><Frown size={96} /></>
                : filterMode === 'broadcast'
                ? <><Radio size={96} /><Frown size={96} /></>
                : <><Eye size={96} /><Frown size={96} /></>
              }
            </div>
            <span className={`text-sm ${currentDesign.uiStyles?.emptyStateSubtext || 'text-zinc-500'}`}>
              {filterMode === 'gifts' ? 'No gifts yet' : filterMode === 'broadcast' ? 'No broadcasts yet' : 'Nothing in focus yet'}
            </span>
          </div>
        )}
        {(hasJoined || filteredMessages.length > 0) && (() => {
          // Helper: check if message is from host (trust backend flag as single source of truth)
          const isMsgFromHost = (msg: Message) => msg.is_from_host;
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
              isMsgFromHost(prevMessage) ||
              isMsgFromHost(message) ||
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
                    className={`absolute w-0.5 ${currentDesign.uiStyles?.avatarConnector || 'bg-zinc-600/30'} pointer-events-none`}
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
                  const isHostMessage = isMsgFromHost(message);
                  const isRegularMessage = !isHostMessage && !message.is_pinned;
                  const showAvatar = isFirstInGroup || isHostMessage || message.is_pinned;
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
                    <div className="relative">
                      <img
                        src={message.avatar_url || getDiceBearUrl(avatarStyle, message.username, 80)}
                        alt={message.username}
                        className={`${avatarSize} rounded-full ${currentDesign.uiStyles?.avatarFallbackBg || 'bg-zinc-700'} ${avatarBorder}`}
                      />
                      {isHostMessage && (
                        <Crown size={14} fill="currentColor" className="absolute -top-1.5 -left-1" style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf', transform: 'rotate(-30deg)' }} />
                      )}
                      {message.username_is_reserved && (
                        <BadgeCheck size={12} className="absolute -bottom-0.5 -right-0.5 rounded-full" style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6', backgroundColor: currentDesign.uiStyles?.badgeIconBg || '#18181b' }} />
                      )}
                    </div>
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
                  modalStyles={currentDesign.modalStyles}
                  emojiPickerStyles={currentDesign.emojiPickerStyles}
                  giftStyles={currentDesign.giftStyles}
                  videoPlayerStyles={currentDesign.videoPlayerStyles}
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
                  onBroadcast={handleBroadcastMessage}
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
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
                      </div>
                    </div>
                  )}
                  {/* Host message header - OUTSIDE bubble */}
                  {isHostMessage && (
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
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
                        <HostPill color={getIconColor(currentDesign.crownIconColor) || '#2dd4bf'} />
                        <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                      </div>
                    </div>
                  )}

                  {/* Pinned message header - OUTSIDE bubble */}
                  {message.is_pinned && !isHostMessage && (
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
                        {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
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
                        <div className={`relative rounded-xl px-3 py-2.5 flex items-center gap-2.5 max-w-[calc(100%-2.5%-5rem+5px)] ${
                          isForMe
                            ? currentDesign.giftStyles?.cardBgForMe || 'bg-purple-950/50 border border-purple-500/50'
                            : message.is_pinned
                            ? 'bg-purple-950/50 border border-purple-500/50'
                            : currentDesign.giftStyles?.cardBg || 'bg-zinc-800/80 border border-zinc-700'
                        }`}>
                          {(message.is_pinned || message.is_gift_acknowledged || message.is_broadcast) && (
                            <div className="absolute -top-2.5 -right-2 z-10 flex flex-row-reverse items-center gap-0.5">
                              {message.is_pinned && (
                                <span className="animate-wobble-b drop-shadow-md">
                                  <Pin size={14} strokeWidth={2.5} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                                </span>
                              )}
                              {message.is_gift_acknowledged && (
                                <span className="text-sm animate-wobble-a drop-shadow-md" title="Thanked">🤗</span>
                              )}
                              {message.is_broadcast && (
                                <span className="animate-wobble-a drop-shadow-md">
                                  <Radio size={14} strokeWidth={2.5} style={{ color: getIconColor(currentDesign.broadcastIconColor) || '#60a5fa' }} />
                                </span>
                              )}
                            </div>
                          )}
                          {price && (
                            <span className={`absolute top-1.5 right-2 text-[8px] font-medium px-1 py-0.5 rounded-full ${
                              currentDesign.giftStyles?.priceBadge || 'bg-cyan-900/50 text-cyan-400'
                            }`}>{price}</span>
                          )}
                          <div className={`text-3xl flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center animate-gift-breath ${
                            currentDesign.giftStyles?.emojiContainer || 'bg-zinc-700/80'
                          }`}>
                            {emoji}
                          </div>
                          <div className="min-w-0 -mt-0.5">
                            <div className="flex items-center gap-1.5">
                              <span className={`text-base font-semibold leading-tight ${currentDesign.giftStyles?.nameText || 'text-white'}`}>{giftName || message.content}</span>
                            </div>
                            {recipient && (
                              <div className={`text-xs mt-0.5 ${currentDesign.giftStyles?.toPrefix || 'text-zinc-400'}`}>
                                to <span className={`font-semibold ${
                                  isForMe
                                    ? (currentDesign.giftStyles?.recipientTextForMe || 'text-purple-400')
                                    : (currentDesign.giftStyles?.recipientText || 'text-zinc-300')
                                }`}>@{recipient}</span>
                                {isForMe && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()
                  ) : (
                  /* Message bubble */
                  <div
                    className={(() => {
                      const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                      const selectedStyle = isHostMessage
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
                      const base = isMediaOnly ? `${selectedStyle} mt-2` : selectedStyle;
                      return (message.is_pinned || message.is_broadcast) ? `${base} relative` : base;
                    })()}
                  >
                    {/* Pin icon on corner of pinned messages */}
                    {(message.is_pinned || message.is_broadcast) && (
                      <div className="absolute -top-2 -right-2 z-10 flex flex-row-reverse items-center gap-0.5">
                        {message.is_pinned && (
                          <span className="animate-wobble-b drop-shadow-md">
                            <Pin size={14} strokeWidth={2.5} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                          </span>
                        )}
                        {message.is_broadcast && (
                          <span className="animate-wobble-a drop-shadow-md">
                            <Radio size={14} strokeWidth={2.5} style={{ color: getIconColor(currentDesign.broadcastIconColor) || '#60a5fa' }} />
                          </span>
                        )}
                      </div>
                    )}

                    {/* Reply context preview */}
                    {message.reply_to_message && (
                      <div
                        className={`mb-2 p-2 rounded-lg cursor-pointer transition-colors ${
                          message.is_pinned
                            ? currentDesign.uiStyles?.replyContextPinned || 'bg-white/10 border border-purple-500/30 hover:bg-white/15'
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.uiStyles?.replyContextOwn || 'bg-white/10 border border-white/10 hover:bg-white/15'
                            : currentDesign.uiStyles?.replyContextOther || 'bg-white/10 border border-zinc-600 hover:bg-white/15'
                        }`}
                        onClick={() => scrollToMessage(message.reply_to_message!.id)}
                      >
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className={`w-3 h-3 flex-shrink-0 ${currentDesign.uiStyles?.replyIconColor || 'text-gray-300'}`} />
                          <span
                            className="text-xs font-semibold"
                            style={{
                              color: message.reply_to_message.is_from_host
                                ? (getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff')
                                : message.reply_to_message.is_pinned && !message.reply_to_message.is_from_host
                                  ? (getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff')
                                  : message.reply_to_message.username.toLowerCase() === username.toLowerCase()
                                    ? (getTextColor(currentDesign.myUsername) || '#ef4444')
                                    : (getTextColor(currentDesign.regularUsername) || '#ffffff')
                            }}
                          >
                            {message.reply_to_message.username}
                          </span>
                          {message.reply_to_message.username_is_reserved && (
                            <BadgeCheck size={12} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6' }} />
                          )}
                          {message.reply_to_message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
                          {message.reply_to_message.is_from_host && (
                            <>
                              <HostPill color={getIconColor(currentDesign.crownIconColor) || '#2dd4bf'} />
                              <Crown size={12} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                            </>
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
                            const recipient = m ? m[4] : '';
                            return (
                              <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 mt-1 text-xs ${currentDesign.uiStyles?.replyGiftBadge || 'bg-zinc-700/60 border border-zinc-600/50'}`}>
                                <span className={currentDesign.uiStyles?.replyGiftText || 'text-zinc-300'}>
                                  sent {emoji} to <span className="font-semibold">@{recipient}</span>
                                  {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                                </span>
                              </div>
                            );
                          }
                          return (
                            <p className={`text-xs truncate ${currentDesign.uiStyles?.replyPreviewText || 'text-gray-300'}`}>
                              {c || '[Voice message]'}
                            </p>
                          );
                        })()}
                      </div>
                    )}

                    {/* Caption text - shown above media when message has both */}
                    {message.content && (message.voice_url || message.photo_url || message.video_url) && (
                      <p className={`mb-2 ${
                        isHostMessage
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
                          isHostMessage
                            ? currentDesign.hostVoiceMessageStyles?.containerBg
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.containerBg
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.containerBg
                            : currentDesign.voiceMessageStyles?.containerBg
                        }
                        voicePlayButton={
                          isHostMessage
                            ? currentDesign.hostVoiceMessageStyles?.playButton
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.playButton
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.playButton
                            : currentDesign.voiceMessageStyles?.playButton
                        }
                        voicePlayIconColor={
                          isHostMessage
                            ? currentDesign.hostVoiceMessageStyles?.playIconColor
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.playIconColor
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.playIconColor
                            : currentDesign.voiceMessageStyles?.playIconColor
                        }
                        voiceWaveformActive={
                          isHostMessage
                            ? currentDesign.hostVoiceMessageStyles?.waveformActive
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.waveformActive
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.waveformActive
                            : currentDesign.voiceMessageStyles?.waveformActive
                        }
                        voiceWaveformInactive={
                          isHostMessage
                            ? currentDesign.hostVoiceMessageStyles?.waveformInactive
                            : message.is_pinned
                            ? currentDesign.pinnedVoiceMessageStyles?.waveformInactive
                            : message.username.toLowerCase() === username.toLowerCase()
                            ? currentDesign.myVoiceMessageStyles?.waveformInactive
                            : currentDesign.voiceMessageStyles?.waveformInactive
                        }
                        durationTextColor={
                          isHostMessage
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
                        maxDisplayHeight={viewportHeight ? Math.min(320, Math.round(viewportHeight * 0.4)) : 320}
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
                        isHostMessage
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
                      <p className={`text-sm italic ${currentDesign.uiStyles?.mediaLoadingText || 'text-gray-500'}`}>
                        [Media message - loading...]
                      </p>
                    )}
                    </div>
                  </div>
                  )}
                </MessageActionsModal>
                {/* Timestamp + Reaction pills row — outside MessageActionsModal so touch scroll works */}
                <div className={`flex items-center gap-2 h-6 pr-14 ${
                  message.message_type === 'gift'
                    ? 'mt-1'
                    : 'mt-0.5'
                }`}>
                  <span
                    className="text-[10px] opacity-60 whitespace-nowrap flex-shrink-0"
                    style={{
                      color: getTextColor(
                        isHostMessage
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
                    highlightTheme={currentDesign.reactionHighlightBg ? {
                      reaction_highlight_bg: currentDesign.reactionHighlightBg,
                      reaction_highlight_border: currentDesign.reactionHighlightBorder,
                      reaction_highlight_text: currentDesign.reactionHighlightText,
                    } : undefined}
                    uiStyles={currentDesign.uiStyles}
                  />
                </div>
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

      {/* Scroll to bottom button */}
      {showScrollToBottom && (
        <button
          onClick={onScrollToBottom}
          className={`absolute bottom-4 left-1/2 -translate-x-1/2 z-30 rounded-full p-2 shadow-lg transition-opacity ${
            themeIsDarkMode
              ? 'bg-zinc-800/90 text-zinc-200 border border-zinc-700'
              : 'bg-white/90 text-gray-700 border border-gray-200'
          }`}
        >
          <ChevronDown size={20} />
        </button>
      )}
      </div>
    </div>
  );
}

// Memoize to prevent re-renders when parent re-renders but props haven't changed
export default memo(MainChatView);
