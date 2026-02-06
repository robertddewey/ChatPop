'use client';

import React, { useState, useCallback, memo, useMemo, useRef, useEffect } from 'react';
import { Crown, Reply, X, MessageSquare, ChevronLeft } from 'lucide-react';
import type { Message, ChatRoom } from '@/lib/api';
import VoiceRecorder from './VoiceRecorder';
import MediaPicker from './MediaPicker';

interface RecordingMetadata {
  duration: number;
  waveformData: number[];
}

interface MessageInputProps {
  chatRoom: ChatRoom | null;
  isHost: boolean;
  hasJoined: boolean;
  sending: boolean;
  replyingTo: Message | null;
  onCancelReply: () => void;
  onSubmitText: (message: string) => void;
  onVoiceRecording: (audioBlob: Blob, metadata: RecordingMetadata, caption: string) => void;
  onPhotoSelected: (file: File, width: number, height: number, caption: string) => void;
  onVideoSelected: (file: File, duration: number, thumbnail: Blob | null, caption: string) => void;
  design: {
    inputArea: string;
    inputField: string;
    replyPreviewContainer?: string;
    replyPreviewIcon?: string;
    replyPreviewUsername?: string;
    replyPreviewContent?: string;
    replyPreviewCloseButton?: string;
    replyPreviewCloseIcon?: string;
  };
}

function MessageInputComponent({
  chatRoom,
  isHost,
  hasJoined,
  sending,
  replyingTo,
  onCancelReply,
  onSubmitText,
  onVoiceRecording,
  onPhotoSelected,
  onVideoSelected,
  design,
}: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [hasVoiceRecording, setHasVoiceRecording] = useState(false);
  const [hasMediaSelected, setHasMediaSelected] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea when expanded and typing
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    if (isExpanded) {
      // Auto-grow when expanded (reset to auto first, then measure)
      textarea.style.height = 'auto';
      const newHeight = Math.min(textarea.scrollHeight, 120);
      textarea.style.height = `${newHeight}px`;
    } else {
      // Reset height when collapsed - let CSS handle single-line height
      textarea.style.height = '';
    }
  }, [message, isExpanded]);

  // Handle focus - expand the input and move cursor to end
  const handleFocus = useCallback(() => {
    setIsExpanded(true);
    // Move cursor to end of text
    const textarea = textareaRef.current;
    if (textarea) {
      const len = textarea.value.length;
      // Use setTimeout to ensure it happens after focus
      setTimeout(() => {
        textarea.setSelectionRange(len, len);
      }, 0);
    }
  }, []);

  // Handle blur - collapse the input
  const handleBlur = useCallback(() => {
    setIsExpanded(false);
  }, []);

  // Handle collapse button click
  const handleCollapse = useCallback(() => {
    setIsExpanded(false);
    textareaRef.current?.blur();
  }, []);

  // Handle text change
  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  }, []);

  // Handle form submission
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();

    const chatWindow = window as Window & {
      __voiceRecorderSendMethod?: () => void;
      __mediaPickerHasMedia?: boolean;
      __mediaPickerSendMethod?: () => void;
    };

    if (hasVoiceRecording && chatWindow.__voiceRecorderSendMethod) {
      chatWindow.__voiceRecorderSendMethod();
      return;
    }

    if (hasMediaSelected && chatWindow.__mediaPickerSendMethod) {
      chatWindow.__mediaPickerSendMethod();
      return;
    }

    if (message.trim()) {
      onSubmitText(message.trim());
      setMessage('');
    }
  }, [message, onSubmitText, hasVoiceRecording, hasMediaSelected]);

  // Check if submit should be disabled
  const isSubmitDisabled = useMemo(() => {
    return sending || (!message.trim() && !hasVoiceRecording && !hasMediaSelected);
  }, [sending, message, hasVoiceRecording, hasMediaSelected]);

  // Handle Enter key for submit (Shift+Enter for new line)
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (message.trim() || hasVoiceRecording || hasMediaSelected) {
        handleSubmit(e as unknown as React.FormEvent);
      }
    }
  }, [message, hasVoiceRecording, hasMediaSelected, handleSubmit]);

  // Check if media buttons should be shown
  const hasVoiceButton = chatRoom?.voice_enabled;
  const hasMediaButton = chatRoom?.photo_enabled || chatRoom?.video_enabled;
  const showMediaButtons = !isExpanded && (hasVoiceButton || hasMediaButton);

  return (
    <div className={design.inputArea}>
      {/* Reply Preview Bar */}
      {replyingTo && (
        <div className={design.replyPreviewContainer}>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Reply className={design.replyPreviewIcon} />
            <div className="flex-1 min-w-0">
              <div className={design.replyPreviewUsername}>
                Replying to {replyingTo.username}
              </div>
              <div className={design.replyPreviewContent}>
                {replyingTo.content}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancelReply}
            className={design.replyPreviewCloseButton}
            aria-label="Cancel reply"
          >
            <X className={design.replyPreviewCloseIcon} />
          </button>
        </div>
      )}

      <form onSubmit={handleSubmit} className={`flex items-center gap-2 ${replyingTo ? 'mt-2' : ''}`}>
        {/* Text input container */}
        <div className="relative flex-1 min-w-0 flex items-center">
          {/* Crown for host - always visible */}
          {isHost && (
            <Crown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-yellow-500 pointer-events-none z-10" />
          )}

          {/* Placeholder - only show when empty and collapsed */}
          {!message && !isExpanded && (
            <div className={`absolute ${isHost ? 'left-10' : 'left-3'} top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-gray-400 pointer-events-none`}>
              <MessageSquare className="w-4 h-4" />
              <span className="text-sm">Aa</span>
            </div>
          )}

          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={handleFocus}
            onBlur={handleBlur}
            className={`w-full ${design.inputField} ${isHost ? 'pl-10' : ''} text-sm resize-none leading-5 !py-[7px] ${
              isExpanded ? '' : '!h-9 overflow-hidden whitespace-nowrap'
            }`}
            disabled={sending}
            rows={1}
            style={{
              WebkitUserSelect: 'text',
              userSelect: 'text',
            }}
          />

          {/* Fade overlay on right edge when collapsed with text */}
          {!isExpanded && message && (
            <div
              className="absolute right-0 top-0 bottom-0 w-8 pointer-events-none rounded-r-lg"
              style={{
                background: 'linear-gradient(to right, transparent, rgb(39, 39, 42))',
              }}
            />
          )}
        </div>

        {/* Media buttons - hidden when expanded but not unmounted to preserve state */}
        <div className={showMediaButtons ? 'flex items-center gap-2' : 'hidden'}>
          {hasVoiceButton && (
            <VoiceRecorder
              onRecordingComplete={onVoiceRecording}
              onRecordingReady={setHasVoiceRecording}
              onSendComplete={() => setMessage('')}
              caption={message}
              disabled={sending || !hasJoined}
            />
          )}
          {hasMediaButton && (
            <MediaPicker
              onPhotoSelected={onPhotoSelected}
              onVideoSelected={onVideoSelected}
              onMediaReady={setHasMediaSelected}
              onSendComplete={() => setMessage('')}
              caption={message}
              photoEnabled={chatRoom?.photo_enabled}
              videoEnabled={chatRoom?.video_enabled}
              disabled={sending || !hasJoined}
              maxVideoDuration={30}
            />
          )}
        </div>

        {/* Collapse button - only show when expanded, positioned between text and Send */}
        {isExpanded && (
          <button
            type="button"
            onMouseDown={(e) => {
              e.preventDefault(); // Prevent blur before click registers
              handleCollapse();
            }}
            className="w-9 h-9 flex items-center justify-center rounded-lg bg-zinc-700 text-gray-400 hover:bg-zinc-600 transition-colors flex-shrink-0"
            aria-label="Collapse input"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}

        {/* Send button */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="h-9 px-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default memo(MessageInputComponent);
