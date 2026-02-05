'use client';

import React, { useMemo, useRef, useState, useLayoutEffect, useEffect, memo } from 'react';
import { BadgeCheck, Reply, Crown, Pin } from 'lucide-react';
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
  handleReply: (message: Message) => void;
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
  handleReply,
  handlePin,
  handleAddToPin,
  getPinRequirements,
  handlePinSelf,
  handlePinOther,
  handleBlockUser,
  handleTipUser,
  handleDeleteMessage,
  handleReactionToggle,
  messageReactions,
  loadingOlder = false,
}: MainChatViewProps) {
  // Ref for measuring sticky section height
  const stickySectionRef = useRef<HTMLDivElement>(null);
  const [stickyHeight, setStickyHeight] = useState(0);

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
        const height = entry.borderBoxSize?.[0]?.blockSize ?? entry.target.offsetHeight;
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
  const newMessageIds = useMemo(() => {
    // Don't animate anything until initial render is complete
    if (!initialRenderDoneRef.current) {
      return new Set<string>();
    }
    const newIds = new Set<string>();
    for (const message of filteredMessages) {
      if (!seenMessageIdsRef.current.has(message.id)) {
        newIds.add(message.id);
      }
    }
    return newIds;
  }, [filteredMessages]);

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
              onReply={handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
            >
              <div
                className={`${currentDesign.stickyHostMessage} w-full relative cursor-pointer hover:opacity-90 transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
                onClick={() => scrollToMessage(message.id)}
              >
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
                  <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                </div>
                <span
                  className="absolute top-3 right-3 text-xs opacity-60"
                  style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                >
                  {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {message.voice_url ? (
                  <div className={`px-3 py-2 rounded-lg ${currentDesign.hostVoiceMessageStyles?.containerBg || 'bg-teal-800'}`}>
                    <VoiceMessagePlayer
                      voiceUrl={`${message.voice_url}${message.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                      duration={message.voice_duration || 0}
                      waveformData={message.voice_waveform || []}
                      isMyMessage={false}
                      voicePlayButton={currentDesign.hostVoiceMessageStyles?.playButton}
                      voicePlayIconColor={currentDesign.hostVoiceMessageStyles?.playIconColor}
                      voiceWaveformActive={currentDesign.hostVoiceMessageStyles?.waveformActive}
                      voiceWaveformInactive={currentDesign.hostVoiceMessageStyles?.waveformInactive}
                      durationTextColor={currentDesign.hostVoiceMessageStyles?.durationTextColor}
                    />
                  </div>
                ) : message.photo_url ? (
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0">
                      <img
                        src={`${message.photo_url}${message.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                        alt="Host photo"
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <span className={`text-sm ${currentDesign.hostText} opacity-70`}>
                      Photo
                    </span>
                  </div>
                ) : message.video_url ? (
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 relative bg-black">
                      {message.video_thumbnail_url ? (
                        <img
                          src={`${message.video_thumbnail_url}${message.video_thumbnail_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                          alt="Video thumbnail"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full bg-zinc-700" />
                      )}
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-6 h-6 rounded-full bg-black/50 flex items-center justify-center">
                          <div className="w-0 h-0 border-l-[6px] border-l-white border-y-[4px] border-y-transparent ml-0.5" />
                        </div>
                      </div>
                    </div>
                    <span className={`text-sm ${currentDesign.hostText} opacity-70`}>
                      Video
                    </span>
                  </div>
                ) : (
                  <p className={`text-sm ${currentDesign.hostText} truncate`}>
                    {message.content}
                  </p>
                )}
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
              onReply={handleReply}
              onPin={handlePin}
              onAddToPin={handleAddToPin}
              getPinRequirements={getPinRequirements}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onDelete={handleDeleteMessage}
              onReact={handleReactionToggle}
            >
              <div
                className={`${currentDesign.stickyPinnedMessage} w-full relative cursor-pointer hover:opacity-90 transition-opacity ${allowAnimations ? 'animate-bounce-in' : ''}`}
                onClick={() => scrollToMessage(stickyPinnedMessage.id)}
              >
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
                  <div className="flex items-center gap-1">
                    <Pin size={14} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                    <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                      ${stickyPinnedMessage.current_pin_amount}
                    </span>
                  </div>
                </div>
                <span
                  className="absolute top-3 right-3 text-xs opacity-60"
                  style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                >
                  {new Date(stickyPinnedMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                {stickyPinnedMessage.voice_url ? (
                  <div className={`px-3 py-2 rounded-lg ${currentDesign.pinnedVoiceMessageStyles?.containerBg || 'bg-teal-800'}`}>
                    <VoiceMessagePlayer
                      voiceUrl={`${stickyPinnedMessage.voice_url}${stickyPinnedMessage.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                      duration={stickyPinnedMessage.voice_duration || 0}
                      waveformData={stickyPinnedMessage.voice_waveform || []}
                      isMyMessage={false}
                      voicePlayButton={currentDesign.pinnedVoiceMessageStyles?.playButton}
                      voicePlayIconColor={currentDesign.pinnedVoiceMessageStyles?.playIconColor}
                      voiceWaveformActive={currentDesign.pinnedVoiceMessageStyles?.waveformActive}
                      voiceWaveformInactive={currentDesign.pinnedVoiceMessageStyles?.waveformInactive}
                      durationTextColor={currentDesign.pinnedVoiceMessageStyles?.durationTextColor}
                    />
                  </div>
                ) : stickyPinnedMessage.photo_url ? (
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0">
                      <img
                        src={`${stickyPinnedMessage.photo_url}${stickyPinnedMessage.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                        alt="Pinned photo"
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <span className={`text-sm ${currentDesign.pinnedText} opacity-70`}>
                      Photo
                    </span>
                  </div>
                ) : stickyPinnedMessage.video_url ? (
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0 relative bg-black">
                      {stickyPinnedMessage.video_thumbnail_url ? (
                        <img
                          src={`${stickyPinnedMessage.video_thumbnail_url}${stickyPinnedMessage.video_thumbnail_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                          alt="Video thumbnail"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full bg-zinc-700" />
                      )}
                      <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-6 h-6 rounded-full bg-black/50 flex items-center justify-center">
                          <div className="w-0 h-0 border-l-[6px] border-l-white border-y-[4px] border-y-transparent ml-0.5" />
                        </div>
                      </div>
                    </div>
                    <span className={`text-sm ${currentDesign.pinnedText} opacity-70`}>
                      Video
                    </span>
                  </div>
                ) : (
                  <p className={`text-sm ${currentDesign.pinnedText} truncate`}>
                    {stickyPinnedMessage.content}
                  </p>
                )}
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
          className="space-y-3 relative z-10"
          style={{ paddingTop: stickyHeight > 0 ? `${stickyHeight + 8}px` : undefined }}
        >
        {/* Loading indicator for infinite scroll */}
        {loadingOlder && (
          <div className="flex justify-center py-2">
            <div className="animate-pulse text-gray-400 text-sm">Loading older messages...</div>
          </div>
        )}
        {hasJoined && filteredMessages.map((message, index) => {
          const prevMessage = index > 0 ? filteredMessages[index - 1] : null;

          // Time-based threading: break thread if >5 minutes gap
          const THREAD_WINDOW_MS = 5 * 60 * 1000; // 5 minutes
          const timeDiff = prevMessage ?
            new Date(message.created_at).getTime() - new Date(prevMessage.created_at).getTime() :
            Infinity;

          const isFirstInThread = !prevMessage ||
            prevMessage.username !== message.username ||
            prevMessage.is_from_host ||
            message.is_from_host ||
            message.is_pinned ||
            timeDiff > THREAD_WINDOW_MS;

          const nextMessage = index < filteredMessages.length - 1 ? filteredMessages[index + 1] : null;
          const nextTimeDiff = nextMessage ?
            new Date(nextMessage.created_at).getTime() - new Date(message.created_at).getTime() :
            Infinity;

          const isLastInThread = !nextMessage ||
            nextMessage.username !== message.username ||
            nextMessage.is_from_host ||
            message.is_from_host ||
            message.is_pinned ||
            nextTimeDiff > THREAD_WINDOW_MS;

          // Find the last message in this thread to get its timestamp
          let lastMessageInThread = message;
          if (isFirstInThread && !isLastInThread && !message.is_from_host && !message.is_pinned) {
            for (let i = index + 1; i < filteredMessages.length; i++) {
              const futureMsg = filteredMessages[i];
              const futureMsgTimeDiff = new Date(futureMsg.created_at).getTime() - new Date(lastMessageInThread.created_at).getTime();

              if (futureMsg.username === message.username &&
                  !futureMsg.is_from_host &&
                  !futureMsg.is_pinned &&
                  futureMsgTimeDiff <= THREAD_WINDOW_MS) {
                lastMessageInThread = futureMsg;
              } else {
                break;
              }
            }
          }

          return (
            <div key={message.id} data-message-id={message.id} className={newMessageIds.has(message.id) ? 'animate-message-appear' : undefined}>
              {/* Show username header for first message in thread */}
              {isFirstInThread && !message.is_from_host && !message.is_pinned && (
                <div className="mb-1 flex items-center gap-1">
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: '600',
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
                  <span
                    className="text-xs opacity-60"
                    style={{
                      color: getTextColor(
                        message.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myTimestamp
                          : currentDesign.regularTimestamp
                      ) || '#ffffff'
                    }}
                  >
                    {new Date(lastMessageInThread.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>
              )}

              {/* Message with threading line */}
              <div className="flex gap-0">
                {/* Vertical thread line for consecutive messages */}
                {!isFirstInThread && !message.is_from_host && !message.is_pinned && (
                  <div className="w-0.5 mr-2 bg-gray-400 dark:bg-gray-600 opacity-30"></div>
                )}

                {/* Wrapper for header + bubble */}
                <div className="flex-1">
                  {/* Host message header - OUTSIDE bubble */}
                  {message.is_from_host && (
                    <div className="mb-1 flex items-center gap-1">
                      <span
                        className="text-xs font-semibold"
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
                      <Crown size={16} style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
                      <span
                        className="text-xs opacity-60"
                        style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                      >
                        {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                      </span>
                    </div>
                  )}

                  {/* Pinned message header - OUTSIDE bubble (no $ value - only shown in sticky section) */}
                  {message.is_pinned && !message.is_from_host && (
                    <div className="mb-1 flex items-center gap-1">
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: '600',
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
                      <Pin size={14} style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                      <span
                        className="text-xs opacity-60"
                        style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                      >
                        {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                      </span>
                    </div>
                  )}

                  {/* Message bubble with action modal */}
                  <MessageActionsModal
                  message={message}
                  currentUsername={username}
                  isHost={chatRoom?.host.id === currentUserId}
                  themeIsDarkMode={themeIsDarkMode}
                  isOutbid={!!(
                    message.is_pinned &&
                    message.sticky_until &&
                    new Date(message.sticky_until) > new Date() &&
                    stickyPinnedMessage?.id !== message.id
                  )}
                  onReply={handleReply}
                  onPin={handlePin}
                  onAddToPin={handleAddToPin}
                  getPinRequirements={getPinRequirements}
                  onBlock={handleBlockUser}
                  onTip={handleTipUser}
                  onDelete={handleDeleteMessage}
                  onReact={handleReactionToggle}
                >
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

                      return selectedStyle;
                    })()}
                  >

                    {/* Reply context preview */}
                    {message.reply_to_message && (
                      <div
                        className={`mb-2 p-2 rounded-lg cursor-pointer transition-colors ${
                          themeIsDarkMode
                            ? message.username.toLowerCase() === username.toLowerCase()
                              ? 'bg-black/60 backdrop-blur-sm border border-white/10 hover:bg-black/70'
                              : 'bg-zinc-800/60 backdrop-blur-sm border border-zinc-600 hover:bg-zinc-800/80'
                            : message.username.toLowerCase() === username.toLowerCase()
                              ? 'bg-white/95 border border-gray-200 hover:bg-white shadow-sm'
                              : 'bg-white border border-gray-200 hover:bg-gray-50 shadow-sm'
                        }`}
                        onClick={() => scrollToMessage(message.reply_to_message!.id)}
                      >
                        <div className="flex items-center gap-1 mb-0.5">
                          <Reply className={`w-3 h-3 flex-shrink-0 ${themeIsDarkMode ? 'text-gray-300' : 'text-blue-600'}`} />
                          <span className={`text-xs font-semibold ${themeIsDarkMode ? 'text-white' : 'text-gray-900'}`}>
                            {message.reply_to_message.username}
                          </span>
                        </div>
                        <p className={`text-xs truncate ${themeIsDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                          {message.reply_to_message.content || '[Voice message]'}
                        </p>
                      </div>
                    )}

                    {/* Message content */}
                    {message.voice_url ? (
                      <div className={`px-3 py-2 rounded-lg ${
                        message.is_from_host
                          ? currentDesign.hostVoiceMessageStyles?.containerBg || 'bg-teal-800'
                          : message.is_pinned
                          ? currentDesign.pinnedVoiceMessageStyles?.containerBg || 'bg-teal-800'
                          : message.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myVoiceMessageStyles?.containerBg || 'bg-emerald-800/70'
                          : currentDesign.voiceMessageStyles?.containerBg || 'bg-zinc-600/40'
                      }`}>
                        <VoiceMessagePlayer
                          voiceUrl={`${message.voice_url}${message.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`}
                          duration={message.voice_duration || 0}
                          waveformData={message.voice_waveform || []}
                          isMyMessage={message.username.toLowerCase() === username.toLowerCase()}
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
                      </div>
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
                      />
                    ) : message.content ? (
                      <p className={`text-sm ${
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
                    ) : (
                      <p className="text-sm text-gray-500 italic">
                        [Media message - loading...]
                      </p>
                    )}
                  </div>
                </MessageActionsModal>

                  {/* Reaction Bar */}
                  <ReactionBar
                    reactions={messageReactions[message.id] || message.reactions || []}
                    onReactionClick={(emoji) => handleReactionToggle(message.id, emoji)}
                    themeIsDarkMode={themeIsDarkMode}
                    highlightTheme={currentDesign.reactionHighlightBg ? {
                      reaction_highlight_bg: currentDesign.reactionHighlightBg,
                      reaction_highlight_border: currentDesign.reactionHighlightBorder,
                      reaction_highlight_text: currentDesign.reactionHighlightText,
                    } : undefined}
                  />
              </div>
            </div>
          </div>
          );
        })}
        {/* Spacer to ensure last message is visible above input */}
        <div ref={messagesEndRef} className="h-4" style={{ overflowAnchor: 'none' }} />
        </div>
      </div>
    </div>
  );
}

// Memoize to prevent re-renders when parent re-renders but props haven't changed
export default memo(MainChatView);
