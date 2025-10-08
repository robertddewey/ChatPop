'use client';

import React, { useMemo } from 'react';
import { BadgeCheck } from 'lucide-react';
import MessageActionsModal from './MessageActionsModal';
import VoiceMessagePlayer from './VoiceMessagePlayer';
import { ChatRoom, Message } from '@/types';

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
      console.log('[FILTER EXTRACTED]', filterValue);
      style.filter = filterValue;
      return;
    }

    // Match [mix-blend-mode:...] arbitrary value
    const blendModeMatch = cls.match(/^\[mix-blend-mode:(.+)\]$/);
    if (blendModeMatch) {
      style.mixBlendMode = blendModeMatch[1] as any;
      console.log('[BLEND MODE EXTRACTED]', blendModeMatch[1]);
      return;
    }

    // Keep all other classes
    classes.push(cls);
  });

  return { classes: classes.join(' '), style };
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
  handleScroll: () => void;
  scrollToMessage: (messageId: string) => void;
  handlePinSelf: (messageId: string, amount: number) => void;
  handlePinOther: (messageId: string, amount: number) => void;
  handleBlockUser: (messageId: string) => void;
  handleTipUser: (messageId: string, amount: number) => void;
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
  handleScroll,
  scrollToMessage,
  handlePinSelf,
  handlePinOther,
  handleBlockUser,
  handleTipUser,
}: MainChatViewProps) {
  // Extract inline styles from messagesAreaBg for dynamic opacity/filter support
  const backgroundStyles = useMemo(() => {
    if (!currentDesign?.messagesAreaBg) return { classes: '', style: {} };
    const result = extractInlineStyles(currentDesign.messagesAreaBg);
    console.log('[BACKGROUND STYLES]', {
      input: currentDesign.messagesAreaBg,
      extractedClasses: result.classes,
      extractedStyle: JSON.stringify(result.style)
    });
    return result;
  }, [currentDesign?.messagesAreaBg]);

  console.log('[MESSAGES AREA CONTAINER]', currentDesign.messagesAreaContainer);
  console.log('[MY MESSAGE STYLE]', currentDesign.myMessage);
  console.log('[REGULAR MESSAGE STYLE]', currentDesign.regularMessage);
  console.log('[CURRENT USERNAME]', username);

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
              design={'dark-mode'}
              onPinSelf={handlePinSelf}
              onPinOther={handlePinOther}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
            >
              <div
                className={`${currentDesign.stickyHostMessage} cursor-pointer hover:opacity-90 transition-opacity animate-bounce-in`}
                onClick={() => scrollToMessage(message.id)}
              >
                <div className="flex items-center gap-1 mb-1">
                  <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                    {message.username}
                  </span>
                  {message.username_is_reserved && (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                  )}
                  <span className={`text-sm ${currentDesign.hostText} opacity-80`}>
                    👑
                  </span>
                  <span className={`text-xs ${currentDesign.hostText} opacity-60 ml-auto`}>
                    {new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <p className={`text-sm ${currentDesign.hostText} truncate`}>
                  {message.content}
                </p>
              </div>
            </MessageActionsModal>
          ))}

          {/* Pinned Message */}
          {stickyPinnedMessage && (
            <MessageActionsModal
              message={stickyPinnedMessage}
              currentUsername={username}
              isHost={chatRoom?.host.id === currentUserId}
              design={'dark-mode'}
              onPinSelf={handlePinSelf}
              onPinOther={handlePinOther}
              onBlock={handleBlockUser}
              onTip={handleTipUser}
            >
              <div
                className={`${currentDesign.stickyPinnedMessage} cursor-pointer hover:opacity-90 transition-opacity animate-bounce-in`}
                onClick={() => scrollToMessage(stickyPinnedMessage.id)}
              >
                <div className="flex items-center gap-1 mb-1">
                  <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                    {stickyPinnedMessage.username}
                  </span>
                  {stickyPinnedMessage.username_is_reserved && (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                  )}
                  <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                    📌 ${stickyPinnedMessage.pin_amount_paid}
                  </span>
                  <span className={`text-xs ${currentDesign.pinnedText} opacity-60 ml-auto`}>
                    {new Date(stickyPinnedMessage.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <p className={`text-sm ${currentDesign.pinnedText} truncate`}>
                  {stickyPinnedMessage.content}
                </p>
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
                <div className={`text-xs mb-1 flex items-center gap-1 text-red-500`}>
                  <span className="font-semibold">
                    {message.username}
                  </span>
                  {message.username_is_reserved && (
                    <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                  )}
                  <span className="opacity-80">
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

                {/* Message bubble with action modal */}
                <MessageActionsModal
                  message={message}
                  currentUsername={username}
                  isHost={chatRoom?.host.id === currentUserId}
                  design={'dark-mode'}
                  onPinSelf={handlePinSelf}
                  onPinOther={handlePinOther}
                  onBlock={handleBlockUser}
                  onTip={handleTipUser}
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

                      console.log(`[MSG ${message.id.slice(0,8)}] username: "${message.username}", currentUser: "${username}", isMyMessage: ${isMyMessage}, style: ${selectedStyle?.slice(0, 50)}`);
                      return selectedStyle;
                    })()}
                  >
                    {/* Host message header */}
                    {message.is_from_host && (
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-1">
                          <span className={`text-sm font-semibold ${currentDesign.hostText}`}>
                            {message.username}
                          </span>
                          {message.username_is_reserved && (
                            <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                          )}
                          <span className={`text-sm ${currentDesign.hostText} opacity-80`}>
                            👑
                          </span>
                        </div>
                        <span className={`text-xs ${currentDesign.hostText} opacity-60`}>
                          {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </div>
                    )}

                    {/* Pinned message header */}
                    {message.is_pinned && !message.is_from_host && (
                      <div className="flex items-center justify-between mb-1 gap-3">
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <span className={`text-sm font-semibold ${currentDesign.pinnedText}`}>
                            {message.username}
                          </span>
                          {message.username_is_reserved && (
                            <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                          )}
                          <span className={`text-xs ${currentDesign.pinnedText} opacity-70`}>
                            📌 ${message.pin_amount_paid}
                          </span>
                        </div>
                        <span className={`text-xs ${currentDesign.pinnedText} opacity-60 ml-auto`}>
                          {new Date(message.created_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                        </span>
                      </div>
                    )}

                    {/* Message content */}
                    {message.voice_url ? (
                      <div className="-mt-px">
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
