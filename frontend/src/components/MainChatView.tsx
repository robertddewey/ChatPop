'use client';

import React, { useMemo } from 'react';
import { BadgeCheck, Reply, Crown, Pin } from 'lucide-react';
import MessageActionsModal from './MessageActionsModal';
import VoiceMessagePlayer from './VoiceMessagePlayer';
import ReactionBar from './ReactionBar';
import { ChatRoom, Message } from '@/types';
import { ReactionSummary } from '@/lib/api';

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
      style.opacity = parseFloat(value);
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
      style.mixBlendMode = blendModeMatch[1] as any;
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
  }

  return undefined;
}

interface MainChatViewProps {
  chatRoom: ChatRoom | null;
  currentUserId: number | null;
  username: string;
  hasJoined: boolean;
  sessionToken: string | null;
  filteredMessages: Message[];
  stickyHostMessages: Message[];
  stickyPinnedMessage: Message | null;
  messagesContainerRef: React.RefObject<HTMLDivElement>;
  messagesEndRef: React.RefObject<HTMLDivElement>;
  currentDesign: any;
  themeIsDarkMode?: boolean;
  handleScroll: () => void;
  scrollToMessage: (messageId: string) => void;
  handleReply: (message: Message) => void;
  handlePinSelf: (messageId: string) => void;
  handlePinOther: (messageId: string) => void;
  handleBlockUser: (username: string) => void;
  handleTipUser: (username: string) => void;
  handleReactionToggle: (messageId: string, emoji: string) => void;
  messageReactions: Record<string, ReactionSummary[]>;
  loadingOlder?: boolean;
}

export default function MainChatView({
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
  handlePinSelf,
  handlePinOther,
  handleBlockUser,
  handleTipUser,
  handleReactionToggle,
  messageReactions,
  loadingOlder = false,
}: MainChatViewProps) {
  // Extract inline styles from messagesAreaBg for dynamic opacity/filter support
  const backgroundStyles = useMemo(() => {
    if (!currentDesign?.messagesAreaBg) return { classes: '', style: {} };
    const result = extractInlineStyles(currentDesign.messagesAreaBg);
    return result;
  }, [currentDesign?.messagesAreaBg]);

  return (
    <div className={`h-full overflow-hidden relative ${currentDesign.messagesAreaContainer || 'bg-white'}`}>
      {/* Sticky Section: Host + Pinned Messages - Absolutely positioned overlay */}
      {hasJoined && (stickyHostMessages.length > 0 || stickyPinnedMessage) && (
        <div data-sticky-section className={currentDesign.stickySection}>
          {/* Host Messages */}
          {stickyHostMessages.map((message) => (
            <MessageActionsModal
              key={`sticky-${message.id}`}
              message={message}
              currentUsername={username}
              isHost={chatRoom?.host.id === currentUserId}
              themeIsDarkMode={themeIsDarkMode}
              onReply={handleReply}
              onPinSelf={handlePinSelf}
              onPinOther={handlePinOther}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onReact={handleReactionToggle}
            >
              <div
                className={`${currentDesign.stickyHostMessage} cursor-pointer hover:opacity-90 transition-opacity animate-bounce-in`}
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
                  <span
                    className="text-xs opacity-60 ml-auto"
                    style={{ color: getTextColor(currentDesign.hostTimestamp) || getTextColor(currentDesign.hostText) || '#ffffff' }}
                  >
                    {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
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
              onPinSelf={handlePinSelf}
              onPinOther={handlePinOther}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
              onReact={handleReactionToggle}
            >
              <div
                className={`${currentDesign.stickyPinnedMessage} cursor-pointer hover:opacity-90 transition-opacity animate-bounce-in`}
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
                      ${stickyPinnedMessage.pin_amount_paid}
                    </span>
                  </div>
                  <span
                    className="text-xs opacity-60 ml-auto"
                    style={{ color: getTextColor(currentDesign.pinnedTimestamp) || getTextColor(currentDesign.pinnedText) || '#ffffff' }}
                  >
                    {new Date(stickyPinnedMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
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
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className={currentDesign.messagesArea}
      >
        {/* Add padding-top when sticky messages are present to avoid overlap */}
        <div className={`space-y-3 relative z-10 ${(stickyHostMessages.length > 0 || stickyPinnedMessage) ? 'pt-4' : ''}`}>
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
            <div key={message.id} data-message-id={message.id}>
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
                        style={{ color: getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff' }}
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

                  {/* Pinned message header - OUTSIDE bubble */}
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
                      <span className={`text-xs opacity-70`} style={{ color: getTextColor(currentDesign.pinnedText) || '#fbbf24' }}>
                        ${message.pin_amount_paid}
                      </span>
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
                  onReply={handleReply}
                  onPinSelf={handlePinSelf}
                  onPinOther={handlePinOther}
                  onBlock={handleBlockUser}
                  onTip={handleTipUser}
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
                        [Voice message - loading...]
                        <br />
                        <small>Debug: voice_url={JSON.stringify(message.voice_url)}, id={message.id}</small>
                      </p>
                    )}
                  </div>
                </MessageActionsModal>

                  {/* Reaction Bar */}
                  <ReactionBar
                    reactions={messageReactions[message.id] || message.reactions || []}
                    onReactionClick={(emoji) => handleReactionToggle(message.id, emoji)}
                    themeIsDarkMode={themeIsDarkMode}
                  />
              </div>
            </div>
          </div>
          );
        })}
        <div ref={messagesEndRef} />
        </div>
      </div>
    </div>
  );
}
