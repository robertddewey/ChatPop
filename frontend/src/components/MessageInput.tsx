'use client';

import React, { useState, useCallback, memo, useMemo } from 'react';
import { Crown, Reply, X } from 'lucide-react';
import type { Message, ChatRoom } from '@/lib/api';
import VoiceRecorder from './VoiceRecorder';
import MediaPicker from './MediaPicker';

// Memoized style object to prevent recreation on each render
const INPUT_STYLE: React.CSSProperties = {
  WebkitUserSelect: 'text',
  userSelect: 'text',
};

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
  onVoiceRecording: (audioBlob: Blob, metadata: RecordingMetadata) => void;
  onPhotoSelected: (file: File) => void;
  onVideoSelected: (file: File, duration: number, thumbnail: Blob | null) => void;
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
  // Local state for the input - typing only affects this component
  const [message, setMessage] = useState('');
  const [hasVoiceRecording, setHasVoiceRecording] = useState(false);
  const [hasMediaSelected, setHasMediaSelected] = useState(false);

  // Memoized change handler
  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setMessage(e.target.value);
  }, []);

  // Handle form submission
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();

    // Check for voice recording via global method
    const chatWindow = window as Window & {
      __voiceRecorderSendMethod?: () => void;
      __mediaPickerHasMedia?: boolean;
      __mediaPickerSendMethod?: () => void;
    };

    // Only call voice send method if there's actually a recording ready
    if (hasVoiceRecording && chatWindow.__voiceRecorderSendMethod) {
      chatWindow.__voiceRecorderSendMethod();
      return;
    }

    // If there's media selected, send it via the global method
    if (hasMediaSelected && chatWindow.__mediaPickerSendMethod) {
      chatWindow.__mediaPickerSendMethod();
      return;
    }

    // Send text message
    if (message.trim()) {
      onSubmitText(message.trim());
      setMessage(''); // Clear local state immediately
    }
  }, [message, onSubmitText, hasVoiceRecording, hasMediaSelected]);

  // Compute if submit should be disabled
  const isSubmitDisabled = useMemo(() => {
    return sending || (!message.trim() && !hasVoiceRecording && !hasMediaSelected);
  }, [sending, message, hasVoiceRecording, hasMediaSelected]);

  // Input class with host prefix
  const inputClassName = useMemo(() => {
    return `w-full ${design.inputField} ${isHost ? 'pl-10' : ''}`;
  }, [design.inputField, isHost]);

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
      <form onSubmit={handleSubmit} className={`flex gap-2 ${replyingTo ? 'mt-2' : ''}`}>
        <div className="relative flex-1">
          {isHost && (
            <Crown className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-yellow-500 pointer-events-none z-10" />
          )}
          <input
            type="text"
            value={message}
            onChange={handleChange}
            placeholder="Type a message..."
            className={inputClassName}
            disabled={sending}
            style={INPUT_STYLE}
          />
        </div>
        {chatRoom?.voice_enabled && (
          <VoiceRecorder
            onRecordingComplete={onVoiceRecording}
            onRecordingReady={setHasVoiceRecording}
            disabled={sending || !hasJoined}
          />
        )}
        {(chatRoom?.photo_enabled || chatRoom?.video_enabled) && (
          <MediaPicker
            onPhotoSelected={onPhotoSelected}
            onVideoSelected={onVideoSelected}
            onMediaReady={setHasMediaSelected}
            photoEnabled={chatRoom?.photo_enabled}
            videoEnabled={chatRoom?.video_enabled}
            disabled={sending || !hasJoined}
            maxVideoDuration={30}
          />
        )}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="px-6 py-2 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-semibold rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}

// Memoize to prevent re-renders when parent re-renders but props haven't changed
export default memo(MessageInputComponent);
