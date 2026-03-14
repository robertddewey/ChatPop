'use client';

import React, { useState, useCallback, memo, useMemo, useRef, useEffect } from 'react';
import { BadgeCheck, Reply, X, MessageSquare, ChevronLeft, Play, Pause, Volume2, VolumeOff, Crown } from 'lucide-react';
import type { Message, ChatRoom } from '@/lib/api';
import VoiceRecorder from './VoiceRecorder';
import MediaPicker from './MediaPicker';
import type { MediaPreview } from './MediaPicker';

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
  username?: string;
  avatarUrl?: string | null;
  hasReservedUsername?: boolean;
  disabled?: boolean;
  disabledMessage?: string;
  design: {
    inputArea: string;
    inputField: string;
    replyPreviewContainer?: string;
    replyPreviewIcon?: string;
    replyPreviewUsername?: string;
    replyPreviewContent?: string;
    replyPreviewCloseButton?: string;
    replyPreviewCloseIcon?: string;
    inputStyles?: Record<string, string>;
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
  username,
  avatarUrl,
  hasReservedUsername = false,
  disabled = false,
  disabledMessage,
  design,
}: MessageInputProps) {
  const inputStyles = design.inputStyles;
  const [message, setMessage] = useState('');
  const [hasVoiceRecording, setHasVoiceRecording] = useState(false);
  const [hasMediaSelected, setHasMediaSelected] = useState(false);
  const [mediaPreview, setMediaPreview] = useState<MediaPreview | null>(null);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);
  const [isVideoMuted, setIsVideoMuted] = useState(true);
  const [isExpanded, setIsExpanded] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const clearMediaRef = useRef<(() => void) | null>(null);
  const videoPreviewRef = useRef<HTMLVideoElement>(null);

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

  if (disabled) {
    return (
      <div className={design.inputArea} style={{ paddingBottom: `calc(0.75rem + env(safe-area-inset-bottom, 0px))` }}>
        <div className={`flex items-center justify-center h-9 rounded-lg ${inputStyles?.disabledBg || 'bg-zinc-800/60 border border-zinc-700/50'}`}>
          <span className={`text-sm ${inputStyles?.disabledText || 'text-zinc-500'}`}>{disabledMessage || 'Messaging disabled'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={design.inputArea} style={{ paddingBottom: `calc(0.75rem + env(safe-area-inset-bottom, 0px))` }}>
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

      {/* Media Preview Card */}
      {mediaPreview && (() => {
        const MAX = 120;
        const d = mediaPreview.dimensions;
        let w = MAX, h = MAX;
        if (d) {
          const scale = Math.min(MAX / Math.max(d.width, d.height), 1);
          w = Math.round(d.width * scale);
          h = Math.round(d.height * scale);
        }
        return (
          <div className={`${replyingTo ? 'mt-2' : ''} mb-2`}>
            <div className="relative inline-block">
              <div
                className="rounded-lg overflow-hidden bg-zinc-700"
                style={{ width: w, height: h }}
              >
                {mediaPreview.type === 'photo' ? (
                  <img src={mediaPreview.url} alt="Preview" className="w-full h-full object-cover" />
                ) : (
                  <div className="relative w-full h-full">
                    <video
                      ref={videoPreviewRef}
                      src={mediaPreview.url}
                      poster={mediaPreview.thumbnailUrl}
                      className="w-full h-full object-cover"
                      muted={isVideoMuted}
                      playsInline
                      preload="metadata"
                      onEnded={() => setIsVideoPlaying(false)}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const vid = videoPreviewRef.current;
                        if (!vid) return;
                        if (isVideoPlaying) { vid.pause(); } else { vid.play(); }
                        setIsVideoPlaying(!isVideoPlaying);
                      }}
                      className={`absolute inset-0 flex items-center justify-center ${isVideoPlaying ? '' : 'bg-black/30'}`}
                    >
                      {isVideoPlaying ? null : (
                        <Play size={20} className="text-white" fill="white" />
                      )}
                    </button>
                    {/* Mute/unmute toggle — bottom-left, always visible */}
                    <button
                        type="button"
                        onClick={() => {
                          const vid = videoPreviewRef.current;
                          if (vid) vid.muted = !isVideoMuted;
                          setIsVideoMuted(!isVideoMuted);
                        }}
                        className="absolute bottom-1 left-1 w-5 h-5 flex items-center justify-center rounded-full bg-black/60 text-white"
                      >
                        {isVideoMuted ? <VolumeOff size={10} /> : <Volume2 size={10} />}
                      </button>
                    {mediaPreview.duration != null && (
                      <span className="absolute bottom-1 right-1 text-[10px] text-white bg-black/60 px-1 py-0.5 rounded">
                        {`${Math.floor(mediaPreview.duration / 60)}:${Math.floor(mediaPreview.duration % 60).toString().padStart(2, '0')}`}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => { setIsVideoPlaying(false); setIsVideoMuted(true); clearMediaRef.current?.(); }}
                className="absolute -top-2 -right-2 w-6 h-6 bg-zinc-700 hover:bg-zinc-600 text-white rounded-full flex items-center justify-center shadow-md transition-colors"
                aria-label="Remove media"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        );
      })()}

      {/* Username indicator */}
      {username && (
        <div className={`flex items-center gap-1 ${replyingTo || mediaPreview ? 'mt-0.5' : '-mt-2'} mb-0.5 px-1`}>
          <span className={`text-[10px] ${inputStyles?.chattingAsText || 'text-zinc-600'} flex items-center gap-0.5`}>
            You are <span className="font-medium">@{username}</span>
            {isHost && <Crown size={10} style={{ color: inputStyles?.crownIconColor || '#2dd4bf' }} />}
          </span>
        </div>
      )}

      <form onSubmit={handleSubmit} className={`flex items-center gap-2 ${replyingTo && !mediaPreview ? 'mt-2' : ''}`}>
        {/* Text input container */}
        <div className="relative flex-1 min-w-0 flex items-center">
          {/* User avatar - always visible */}
          <div className="absolute left-1.5 top-1/2 -translate-y-1/2 pointer-events-none z-10">
            <div className="relative">
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  className={`w-6 h-6 rounded-full ${inputStyles?.avatarFallbackBg || 'bg-zinc-700'}`}
                />
              ) : (
                <div className={`w-6 h-6 rounded-full ${inputStyles?.avatarFallbackBg || 'bg-zinc-700'}`} />
              )}
              {hasReservedUsername && (
                <BadgeCheck size={10} className="absolute -bottom-0.5 -right-0.5 text-blue-500 bg-zinc-900 rounded-full" />
              )}
            </div>
          </div>

          {/* Placeholder - only show when empty and collapsed */}
          {!message && !isExpanded && (
            <div className="absolute left-10 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-gray-400 pointer-events-none">
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
            className={`w-full ${design.inputField} pl-10 text-sm resize-none leading-5 !py-[7px] ${
              isExpanded ? '' : '!h-9 overflow-hidden whitespace-nowrap'
            }`}
            disabled={sending}
            rows={1}
            style={{
              WebkitUserSelect: 'text',
              userSelect: 'text',
              WebkitTapHighlightColor: 'transparent',
              outline: 'none',
            }}
          />

          {/* Fade overlay on right edge when collapsed with text */}
          {!isExpanded && message && (
            <div
              className="absolute right-0 top-0 bottom-0 w-8 pointer-events-none rounded-r-lg"
              style={{
                background: `linear-gradient(to right, transparent, ${inputStyles?.textFadeGradient || 'rgb(39, 39, 42)'})`,
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
              onPreviewChange={setMediaPreview}
              clearRef={clearMediaRef}
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
            className={`w-9 h-9 flex items-center justify-center rounded-lg ${inputStyles?.collapseButton || 'bg-zinc-700 text-gray-400 hover:bg-zinc-600'} transition-colors flex-shrink-0`}
            aria-label="Collapse input"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}

        {/* Send button */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          onMouseDown={(e) => e.preventDefault()}
          className={`h-9 px-4 ${inputStyles?.sendButton || 'bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700'} text-sm font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0`}
        >
          Send
        </button>
      </form>
    </div>
  );
}

export default memo(MessageInputComponent);
