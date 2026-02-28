'use client';

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Message, ReactionSummary } from '@/lib/api';
import { Pin, DollarSign, Ban, BadgeCheck, Reply, Trash2, Copy, Flag, Play, Pause, Mic, Crown } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';

interface PinTier {
  amount_cents: number;
  duration_minutes: number;
}

interface PinRequirements {
  current_pin_cents: number;
  minimum_cents?: number;  // Legacy, deprecated
  required_cents?: number;  // Legacy, deprecated
  minimum_required_cents?: number;  // Total amount needed to win sticky
  minimum_add_cents?: number;  // For reclaim: minimum tier to ADD (additive)
  my_investment_cents?: number;  // User's existing investment (for reclaim)
  duration_minutes: number;
  tiers?: PinTier[];  // Available tiers
  is_current_sticky?: boolean;  // Is this message the current sticky holder
  is_outbid?: boolean;  // Was this message outbid but has time remaining (can reclaim)
  time_remaining_seconds?: number;  // Remaining time if outbid (for reclaim stacking)
}

interface ThemeColors {
  badgeIcon?: string;    // BadgeCheck icon color
  crownIcon?: string;    // Crown icon color
  pinIcon?: string;      // Pin icon color
  hostUsername?: string;  // Host username text color
  pinnedUsername?: string; // Pinned username text color
  myUsername?: string;    // Own username text color
  regularUsername?: string; // Regular username text color
}

interface MessageActionsModalProps {
  message: Message;
  currentUsername?: string;
  isHost?: boolean;
  themeIsDarkMode?: boolean;
  isOutbid?: boolean;  // Message was pinned but outbid (has time remaining, not current sticky)
  children: React.ReactNode;
  onReply?: (message: Message) => void;
  onPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  onAddToPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  getPinRequirements?: (messageId: string) => Promise<PinRequirements>;
  onBlock?: (username: string) => void;
  onTip?: (username: string) => void;
  onReact?: (messageId: string, emoji: string) => void;
  reactions?: ReactionSummary[];
  onDelete?: (messageId: string) => void;
  onReport?: (messageId: string, username: string) => void;
  sessionToken?: string | null;
  themeColors?: ThemeColors;
  // Legacy props (deprecated, will be removed)
  onPinSelf?: (messageId: string) => void;
  onPinOther?: (messageId: string) => void;
}

// Get theme-aware modal styles (no system preference - force theme mode)
const getModalStyles = (themeIsDarkMode: boolean) => {
  if (themeIsDarkMode) {
    // Dark theme styles
    return {
      overlay: 'bg-black/60 backdrop-blur-sm',
      container: 'bg-zinc-900',
      messagePreview: 'bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl',
      messageText: 'text-zinc-50',
      actionButton: 'bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500 text-zinc-50 border border-zinc-500',
      actionIcon: 'text-cyan-400',
      dragHandle: 'bg-gray-600',
      usernameText: 'text-gray-300',
    };
  } else {
    // Light theme styles
    return {
      overlay: 'bg-black/20 backdrop-blur-sm',
      container: 'bg-white',
      messagePreview: 'bg-gray-50 border border-gray-200 rounded-2xl shadow-sm',
      messageText: 'text-gray-800',
      actionButton: 'bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-900',
      actionIcon: 'text-purple-600',
      dragHandle: 'bg-gray-300',
      usernameText: 'text-gray-700',
    };
  }
};

// Allowed reaction emojis (matching backend)
const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '😡'];

// Inline video player for modal preview (matches chat VideoMessage style)
function ModalVideoPlayer({ videoUrl, thumbnailUrl, duration }: { videoUrl: string; thumbnailUrl: string; duration: number }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const formatTime = (seconds: number): string => {
    if (!isFinite(seconds) || seconds < 0) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const togglePlayPause = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const video = videoRef.current;
    if (!video) return;

    try {
      if (isPlaying) {
        video.pause();
        setIsPlaying(false);
      } else {
        setIsLoading(true);
        await video.play();
        setIsPlaying(true);
        setIsLoading(false);
      }
    } catch {
      setIsPlaying(false);
      setIsLoading(false);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    e.stopPropagation();
    const video = videoRef.current;
    if (!video) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const percentage = (e.clientX - rect.left) / rect.width;
    video.currentTime = percentage * duration;
    setCurrentTime(video.currentTime);
  };

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="mt-1 max-w-[240px] rounded-lg overflow-hidden bg-black relative" onClick={(e) => e.stopPropagation()}>
      <video
        ref={videoRef}
        src={videoUrl}
        poster={thumbnailUrl}
        className="w-full h-auto rounded-lg"
        playsInline
        onTimeUpdate={() => videoRef.current && setCurrentTime(videoRef.current.currentTime)}
        onEnded={() => { setIsPlaying(false); setCurrentTime(0); if (videoRef.current) videoRef.current.currentTime = 0; }}
      />

      {/* Play/Pause overlay */}
      <div
        className="absolute inset-0 flex items-center justify-center cursor-pointer"
        onClick={togglePlayPause}
      >
        {!isPlaying && (
          <>
            <div className="absolute inset-0 bg-black/30 rounded-lg" />
            <div className="relative z-10 w-12 h-12 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-gray-600 border-t-transparent rounded-full animate-spin" />
              ) : (
                <Play size={20} className="text-gray-800 ml-1" fill="currentColor" />
              )}
            </div>
          </>
        )}
        {isPlaying && (
          <div className="absolute inset-0 bg-black/20 opacity-0 hover:opacity-100 active:opacity-100 transition-opacity flex items-center justify-center rounded-lg">
            <Pause size={32} className="text-white" fill="white" />
          </div>
        )}
      </div>

      {/* Duration badge */}
      <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/70 text-white text-xs font-mono">
        {formatTime(isPlaying ? currentTime : duration)}
      </div>

      {/* Progress bar */}
      {isPlaying && (
        <div
          className="absolute bottom-0 left-0 right-0 h-1 bg-black/30 cursor-pointer rounded-b-lg"
          onClick={handleSeek}
        >
          <div className="h-full bg-white transition-all" style={{ width: `${progress}%` }} />
        </div>
      )}
    </div>
  );
}

export default function MessageActionsModal({
  message,
  currentUsername,
  isHost = false,
  themeIsDarkMode = true,
  isOutbid = false,
  children,
  onReply,
  onPin,
  onAddToPin,
  getPinRequirements,
  onBlock,
  onTip,
  onReact,
  reactions = [],
  onDelete,
  onReport,
  sessionToken,
  themeColors,
  // Legacy props
  onPinSelf,
  onPinOther,
}: MessageActionsModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [hasAnimatedIn, setHasAnimatedIn] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // Pin input state
  const [showPinInput, setShowPinInput] = useState(false);
  const [pinRequirements, setPinRequirements] = useState<PinRequirements | null>(null);
  const [selectedTier, setSelectedTier] = useState<PinTier | null>(null);
  const [isPinning, setIsPinning] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);

  const dragStartY = React.useRef(0);
  const actionsRef = React.useRef<HTMLDivElement>(null);
  const pinRef = React.useRef<HTMLDivElement>(null);
  const [containerHeight, setContainerHeight] = useState<number | undefined>(undefined);

  // Measure active panel height for smooth height transitions
  useEffect(() => {
    // Use requestAnimationFrame to ensure DOM has updated before measuring
    const raf = requestAnimationFrame(() => {
      const activeRef = showPinInput && pinRequirements ? pinRef : actionsRef;
      if (activeRef.current) {
        setContainerHeight(activeRef.current.scrollHeight);
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [showPinInput, pinRequirements, selectedTier, pinError]);
  const isOwnMessage = message.username === currentUsername;
  const isHostMessage = message.is_from_host;

  const modalStyles = getModalStyles(themeIsDarkMode);

  // Prevent body scrolling when modal is open (only on non-chat routes)
  // Chat routes already have body scroll locked via chat-layout.css
  useEffect(() => {
    if (isOpen) {
      const isChatRoute = window.location.pathname.startsWith('/chat/');
      if (!isChatRoute) {
        document.body.style.overflow = 'hidden';
      }
      return () => {
        if (!isChatRoute) {
          document.body.style.overflow = '';
        }
      };
    }
  }, [isOpen]);

  const handleOpen = () => {
    setIsOpen(true);
    setDragOffset(0);
    setHasAnimatedIn(false);

    // Mark animation as complete after it finishes (300ms)
    setTimeout(() => setHasAnimatedIn(true), 300);

    // Haptic feedback (Android only)
    if (typeof window !== 'undefined' && 'vibrate' in navigator) {
      try {
        navigator.vibrate(50);
      } catch (e) {
        // Silent fail
      }
    }
  };

  const handleClose = () => {
    // Trigger closing animation
    setIsClosing(true);
    setIsDragging(false);

    // Wait for animation to complete before removing from DOM
    setTimeout(() => {
      setIsOpen(false);
      setIsClosing(false);
      setHasAnimatedIn(false);
      setDragOffset(0);
      // Reset pin state
      setShowPinInput(false);
      setPinRequirements(null);
      setSelectedTier(null);
      setPinError(null);
    }, 250); // Match animation duration
  };

  // Handle opening the pin input step
  const handleOpenPinInput = async () => {
    if (getPinRequirements) {
      try {
        const requirements = await getPinRequirements(message.id);
        setPinRequirements(requirements);
        setSelectedTier(null);  // Reset selection
        setShowPinInput(true);
        setPinError(null);
      } catch (error) {
        console.error('Failed to get pin requirements:', error);
        setPinError('Failed to load pin requirements');
      }
    } else {
      // Fallback: use defaults if no getPinRequirements provided
      setPinRequirements({
        current_pin_cents: 0,
        duration_minutes: 60,
        tiers: [
          { amount_cents: 100, duration_minutes: 10 },
          { amount_cents: 200, duration_minutes: 15 },
          { amount_cents: 500, duration_minutes: 20 },
          { amount_cents: 1000, duration_minutes: 30 },
          { amount_cents: 1500, duration_minutes: 45 },
          { amount_cents: 2000, duration_minutes: 60 },
        ],
      });
      setSelectedTier(null);
      setShowPinInput(true);
    }
  };

  // Handle pin submission
  const handlePinSubmit = async () => {
    if (!pinRequirements || !selectedTier) {
      setPinError('Please select a tier');
      return;
    }

    setIsPinning(true);
    setPinError(null);

    try {
      // Determine if this is add-to-pin (current sticky holder) or new pin/re-pin/reclaim
      const handler = pinRequirements?.is_current_sticky ? onAddToPin : onPin;

      if (handler) {
        const success = await handler(message.id, selectedTier.amount_cents);
        if (success) {
          handleClose();
        } else {
          setPinError('Failed to pin message');
        }
      } else {
        // Legacy fallback
        if (isOwnMessage && onPinSelf) {
          onPinSelf(message.id);
          handleClose();
        } else if (!isOwnMessage && onPinOther) {
          onPinOther(message.id);
          handleClose();
        }
      }
    } catch (err: unknown) {
      const error = err as Error;
      setPinError(error.message || 'Failed to pin message');
    } finally {
      setIsPinning(false);
    }
  };

  // Check if a tier is available (for outbidding, must be above current)
  const isTierAvailable = (tier: PinTier): boolean => {
    if (!pinRequirements) return true;

    // For Add-to-Pin (current sticky holder), all tiers are available
    if (pinRequirements.is_current_sticky) return true;

    // For reclaim (outbid but has time remaining): use minimum_add_cents
    // This is additive - tier + existing investment must beat current sticky
    if (pinRequirements.is_outbid && pinRequirements.minimum_add_cents) {
      return tier.amount_cents >= pinRequirements.minimum_add_cents;
    }

    // For new pin or re-pin: must be at or above minimum required total
    const minRequired = pinRequirements.minimum_required_cents || pinRequirements.required_cents || 0;
    return tier.amount_cents >= minRequired;
  };

  // Format duration for display (short form for pills)
  const formatDuration = (minutes: number): string => {
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
  };

  const formatDurationMedium = (minutes: number): string => {
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (mins > 0) return `${hours} hr ${mins} min`;
    return `${hours} hour${hours !== 1 ? 's' : ''}`;
  };

  // Format duration for display (long form for headers)
  const formatDurationLong = (minutes: number): string => {
    if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    if (mins > 0) return `${hours} hour${hours !== 1 ? 's' : ''} ${mins} minute${mins !== 1 ? 's' : ''}`;
    return `${hours} hour${hours !== 1 ? 's' : ''}`;
  };

  const handleDragStart = (e: React.TouchEvent) => {
    dragStartY.current = e.touches[0].clientY;
    setIsDragging(true);
  };

  const handleDragMove = (e: React.TouchEvent) => {
    if (!isDragging) return;

    const currentY = e.touches[0].clientY;
    const delta = currentY - dragStartY.current;

    // Only allow dragging down (positive delta)
    if (delta > 0) {
      setDragOffset(delta);
    }
  };

  const handleDragEnd = () => {
    if (!isDragging) return;

    setIsDragging(false);

    // Close if dragged down more than 100px
    if (dragOffset > 100) {
      handleClose();
    } else {
      // Snap back to original position
      setDragOffset(0);
    }
  };

  const handleAction = (action: () => void) => {
    action();
    handleClose();
  };

  const longPressHandlers = useLongPress({
    onLongPress: handleOpen,
    threshold: 500,
  });

  // Filter actions based on context
  const actions = [];

  // 1. Reply — always
  if (onReply) {
    actions.push({
      icon: Reply,
      label: 'Reply',
      action: () => {
        onReply(message);
        handleClose();
      },
    });
  }

  // 2. Pin — always (non-host messages, pin support required)
  const hasPinSupport = !message.is_from_host && (onPin || onAddToPin || getPinRequirements || onPinSelf || onPinOther);
  const isPinExpired = message.is_pinned && message.sticky_until && new Date(message.sticky_until) < new Date();

  if (hasPinSupport) {
    if (!message.is_pinned) {
      actions.push({ icon: Pin, label: 'Pin', action: handleOpenPinInput });
    } else if (isPinExpired) {
      actions.push({ icon: Pin, label: 'Re-pin', action: handleOpenPinInput });
    } else if (isOutbid) {
      actions.push({ icon: Pin, label: 'Reclaim', action: handleOpenPinInput });
    } else {
      actions.push({ icon: Pin, label: 'Add Pin', action: handleOpenPinInput });
    }
  }

  // 3. Tip — others only
  if (!isOwnMessage && onTip) {
    actions.push({
      icon: DollarSign,
      label: 'Tip',
      action: () => {
        onTip(message.username);
        handleClose();
      },
    });
  }

  // 4. Copy — always (copies "username: content" to clipboard, disabled for media-only)
  const hasTextContent = !!message.content?.trim();
  actions.push({
    icon: Copy,
    label: 'Copy',
    disabled: !hasTextContent,
    action: () => {
      if (!hasTextContent) return;
      const text = message.username + ': ' + message.content;
      // Use textarea approach for reliable plain-text copy on iOS
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.setAttribute('readonly', '');
      textarea.style.position = 'fixed';
      textarea.style.left = '-9999px';
      document.body.appendChild(textarea);
      textarea.select();
      textarea.setSelectionRange(0, text.length);
      document.execCommand('copy');
      document.body.removeChild(textarea);
      handleClose();
    },
  });

  // 5. Delete — host only (destructive)
  if (isHost && onDelete) {
    actions.push({
      icon: Trash2,
      label: 'Delete',
      destructive: true,
      action: () => {
        if (confirm('Are you sure you want to delete this message?')) {
          onDelete(message.id);
          handleClose();
        }
      },
    });
  }

  // 6. Mute/Ban — registered users, others only (destructive)
  if (!isOwnMessage && !isHostMessage && onBlock) {
    const authToken = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (authToken) {
      actions.push({
        icon: Ban,
        label: isHost ? 'Ban' : 'Mute',
        destructive: true,
        action: () => {
          onBlock(message.username);
          handleClose();
        },
      });
    }
  }

  // 7. Report — others only (destructive, inactive placeholder for now)
  if (!isOwnMessage) {
    actions.push({
      icon: Flag,
      label: 'Report',
      destructive: true,
      action: () => {
        if (onReport) {
          onReport(message.id, message.username);
        }
        handleClose();
      },
    });
  }

  return (
    <>
      {/* Trigger: Long-press enabled wrapper */}
      <div
        {...longPressHandlers}
        onContextMenu={(e: React.MouseEvent) => e.preventDefault()}
        style={{ WebkitTouchCallout: 'none', WebkitUserSelect: 'none', userSelect: 'none' }}
      >
        {children}
      </div>

      {/* Full-screen Modal */}
      {isOpen && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-end justify-center"
          onClick={handleClose}
          style={{
            WebkitUserSelect: 'none',
            userSelect: 'none',
            WebkitTouchCallout: 'none',
          }}
        >
          {/* Backdrop with blur */}
          <div className={`absolute inset-0 ${modalStyles.overlay}`} />

          {/* E4 Layout: Message docked above sheet, slides up as one unit */}
          <div
            className={`relative w-full max-w-lg ${isClosing ? 'animate-slide-down' : (!hasAnimatedIn && 'animate-slide-up')}`}
            style={{
              transform: `translateY(${dragOffset}px)`,
              transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            {/* Floating Message Preview — docked above sheet, rendered like actual chat message */}
            <div className="px-4 pb-6">
              <div className="flex">
                <div className="w-10 flex-shrink-0 mr-3">
                  <img
                    src={message.avatar_url}
                    alt={message.username}
                    className="w-10 h-10 rounded-full bg-zinc-700"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mb-1">
                    <span
                      className="text-sm font-bold"
                      style={{
                        color: message.is_from_host
                          ? (themeColors?.hostUsername || '#fbbf24')
                          : isOwnMessage
                            ? (themeColors?.myUsername || '#ef4444')
                            : message.is_pinned
                              ? (themeColors?.pinnedUsername || '#c084fc')
                              : (themeColors?.regularUsername || (themeIsDarkMode ? '#ffffff' : '#111827'))
                      }}
                    >
                      {message.username}
                    </span>
                    {message.username_is_reserved && (
                      <BadgeCheck className="inline-block ml-1 flex-shrink-0" size={14} style={{ color: themeColors?.badgeIcon || '#34d399' }} />
                    )}
                    {message.is_from_host && (
                      <Crown className="inline-block ml-1 flex-shrink-0" size={14} style={{ color: themeColors?.crownIcon || '#2dd4bf' }} />
                    )}
                    {message.is_pinned && !message.is_from_host && (
                      <Pin className="inline-block ml-1 flex-shrink-0" size={14} style={{ color: themeColors?.pinIcon || '#fbbf24' }} />
                    )}
                    <span className={`text-xs ${themeIsDarkMode ? 'text-white opacity-60' : 'text-gray-500'} -mt-0.5 block`}>
                      {new Date(message.created_at).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </span>
                  </div>
                  {/* Text content */}
                  {message.content && (
                    <p className={`text-sm ${themeIsDarkMode ? 'text-white' : 'text-gray-800'}`}>
                      {message.content}
                    </p>
                  )}
                  {/* Photo */}
                  {message.photo_url && (
                    <div
                      className="mt-1 max-w-[240px] rounded-lg overflow-hidden bg-zinc-700"
                      style={message.photo_width && message.photo_height ? { aspectRatio: `${message.photo_width} / ${message.photo_height}` } : undefined}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <img src={`${message.photo_url}${message.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`} alt="Photo" className="w-full h-full object-cover rounded-lg" />
                    </div>
                  )}
                  {/* Video player */}
                  {message.video_url && (
                    <ModalVideoPlayer
                      videoUrl={`${message.video_url}${message.video_url.includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`}
                      thumbnailUrl={`${message.video_thumbnail_url || ''}${(message.video_thumbnail_url || '').includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`}
                      duration={message.video_duration || 0}
                    />
                  )}
                  {/* Voice message */}
                  {message.voice_url && !message.content && (
                    <div className="flex items-center gap-2 mt-1" onClick={(e) => e.stopPropagation()}>
                      <Mic className={`w-4 h-4 ${themeIsDarkMode ? 'text-white/60' : 'text-gray-500'}`} />
                      <span className={`text-sm ${themeIsDarkMode ? 'text-white/60' : 'text-gray-500'}`}>
                        Voice message{message.voice_duration ? ` (${Math.floor(message.voice_duration / 60)}:${String(Math.floor(message.voice_duration % 60)).padStart(2, '0')})` : ''}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Sheet */}
            <div
              className={`w-full ${modalStyles.container} rounded-t-3xl`}
              onClick={(e) => e.stopPropagation()}
              style={{ paddingBottom: `calc(1.5rem + env(safe-area-inset-bottom, 0px))` }}
            >
              {/* Draggable handle area */}
              <div
                onTouchStart={handleDragStart}
                onTouchMove={handleDragMove}
                onTouchEnd={handleDragEnd}
              >
                <div className="pt-3 pb-2 flex justify-center">
                  <div className={`w-12 h-1.5 ${modalStyles.dragHandle} rounded-full`} />
                </div>
              </div>

              {/* Actions / Pin Input — slide transition */}
              <div
                className="overflow-hidden relative transition-[height] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
                style={{ height: containerHeight ? `${containerHeight}px` : 'auto' }}
              >
                <div
                  className="flex items-start transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]"
                  style={{ transform: showPinInput && pinRequirements ? 'translateX(-100%)' : 'translateX(0)' }}
                >
                  {/* Panel 1: Actions (emoji + action buttons) */}
                  <div className="w-full flex-shrink-0" ref={actionsRef}>
                  {/* Emoji Reactions Row */}
                  {onReact && (
                    <div className="px-5 pb-4">
                      <div className="flex items-center justify-between">
                        {REACTION_EMOJIS.map((emoji) => {
                          const hasReacted = reactions.some(r => r.emoji === emoji && r.has_reacted);
                          return (
                            <button
                              key={emoji}
                              onClick={(e) => {
                                e.stopPropagation();
                                onReact(message.id, emoji);
                              }}
                              onTouchStart={(e) => e.stopPropagation()}
                              onTouchMove={(e) => e.stopPropagation()}
                              onTouchEnd={(e) => e.stopPropagation()}
                              className={`flex items-center justify-center rounded-full transition-all active:scale-110 cursor-pointer ${
                                hasReacted
                                  ? themeIsDarkMode
                                    ? 'bg-purple-500/30 ring-2 ring-purple-500/60'
                                    : 'bg-purple-100 ring-2 ring-purple-400'
                                  : themeIsDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-gray-100 hover:bg-gray-200'
                              }`}
                              style={{ width: '52px', height: '52px' }}
                            >
                              <span className="text-2xl">{emoji}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Divider */}
                  <div className={`mx-5 border-t ${themeIsDarkMode ? 'border-zinc-700/50' : 'border-gray-200'}`} />

                  {/* Horizontal Scrollable Action Row */}
                  <div className="pt-3">
                    <div
                      className="overflow-x-scroll actions-scrollbar-hide actions-scroll-container px-5"
                      style={{ WebkitOverflowScrolling: 'touch' }}
                    >
                      <div className="flex gap-2 w-max mx-auto">
                        {actions.map((action, index) => {
                          const Icon = action.icon;
                          return (
                            <div
                              key={index}
                              role="button"
                              tabIndex={action.disabled ? -1 : 0}
                              onClick={(e) => {
                                e.stopPropagation();
                                if (!action.disabled) action.action();
                              }}
                              className={`flex flex-col items-center justify-center gap-2 py-3 rounded-2xl transition-all w-[88px] h-[80px] action-btn ${action.disabled ? 'opacity-30 cursor-not-allowed' : 'active:scale-95 cursor-pointer'}`}
                            >
                              <Icon className={`w-6 h-6 ${action.destructive ? 'text-red-400' : modalStyles.actionIcon}`} />
                              <span className={`text-xs font-medium truncate w-full text-center ${action.destructive ? 'text-red-400' : themeIsDarkMode ? 'text-zinc-50' : 'text-gray-900'}`}>{action.label}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                  </div>

                  {/* Panel 2: Pin Input */}
                  <div className="w-full flex-shrink-0" ref={pinRef}>
                {pinRequirements && (
                <div className="space-y-4 max-h-[320px] overflow-y-auto w-full">
                  {/* Pin Amount Header */}
                  <div className="text-center px-6">
                    <h3 className={`text-lg font-semibold ${themeIsDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {pinRequirements.is_current_sticky
                        ? 'Add to Pin'
                        : pinRequirements.is_outbid
                          ? 'Reclaim Pin'
                          : !message.is_pinned
                            ? 'Pin Message'
                            : 'Re-pin Message'
                      }
                    </h3>
                    <p className={`text-sm mt-1 ${themeIsDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      {(() => {
                        if (pinRequirements.is_current_sticky) {
                          return 'Extend pin duration';
                        } else if (pinRequirements.is_outbid) {
                          const minAdd = pinRequirements.minimum_add_cents || 0;
                          const timeRemaining = pinRequirements.time_remaining_seconds || 0;
                          const hours = Math.floor(timeRemaining / 3600);
                          const mins = Math.ceil((timeRemaining % 3600) / 60);
                          const timeStr = hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
                          return `Add $${(minAdd / 100).toFixed(0)}+ to reclaim • ${timeStr} remaining`;
                        } else if (pinRequirements.current_pin_cents > 0) {
                          const minRequired = pinRequirements.minimum_required_cents || 0;
                          return `Outbid current pin (min $${(minRequired / 100).toFixed(0)})`;
                        } else {
                          return `Pin for ${formatDurationLong(pinRequirements.duration_minutes)}, or until outbid`;
                        }
                      })()}
                    </p>
                  </div>

                  {/* Tier Selection - Horizontal Scroll */}
                  {pinRequirements.tiers && pinRequirements.tiers.length > 0 && (
                    <div>
                      {(() => {
                        const availableTiers = pinRequirements.tiers.filter(t => isTierAvailable(t));
                        const showTimeExtension = pinRequirements.is_current_sticky || pinRequirements.is_outbid;

                        return (
                          <div
                            className="overflow-x-scroll actions-scrollbar-hide actions-scroll-container px-5"
                            style={{ WebkitOverflowScrolling: 'touch' }}
                          >
                            <div className="flex gap-2 w-max mx-auto py-1">
                              {availableTiers.map((tier) => {
                                const isSelected = selectedTier?.amount_cents === tier.amount_cents;

                                return (
                                  <div
                                    key={tier.amount_cents}
                                    role="button"
                                    tabIndex={0}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setSelectedTier(tier);
                                    }}
                                    className={`flex flex-col items-center justify-center gap-2 py-3 rounded-2xl transition-all w-[88px] h-[80px] action-btn active:scale-95 cursor-pointer ${
                                      isSelected
                                        ? themeIsDarkMode
                                          ? 'ring-2 ring-cyan-400'
                                          : 'ring-2 ring-purple-400'
                                        : ''
                                    }`}
                                  >
                                    <span className={`font-bold text-base ${
                                      isSelected
                                        ? modalStyles.actionIcon
                                        : modalStyles.actionIcon
                                    }`}>
                                      ${(tier.amount_cents / 100).toFixed(0)}
                                    </span>
                                    <span className={`text-xs font-medium whitespace-nowrap ${
                                      themeIsDarkMode ? 'text-zinc-50' : 'text-gray-900'
                                    }`}>
                                      {showTimeExtension ? `+${formatDurationMedium(tier.duration_minutes)}` : formatDurationMedium(pinRequirements.duration_minutes)}
                                    </span>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  )}

                  {/* Error message */}
                  {pinError && (
                    <p className="text-center text-sm text-red-500 px-6">{pinError}</p>
                  )}

                  {/* Buttons */}
                  <div className="flex gap-3 pt-2 px-6">
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowPinInput(false); setSelectedTier(null); }}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        themeIsDarkMode ? 'bg-zinc-700 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Back
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePinSubmit(); }}
                      disabled={isPinning || !selectedTier}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        (isPinning || !selectedTier) ? 'opacity-50 cursor-not-allowed' : ''
                      } ${themeIsDarkMode ? 'bg-cyan-600 text-white' : 'bg-purple-600 text-white'}`}
                    >
                      {isPinning
                        ? 'Processing...'
                        : pinRequirements.is_current_sticky
                          ? 'Add to Pin'
                          : pinRequirements.is_outbid
                            ? 'Reclaim Pin'
                            : !message.is_pinned
                              ? 'Pin Message'
                              : 'Re-pin'
                      }
                    </button>
                  </div>
                </div>
                )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      <style jsx>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        @keyframes slide-down {
          from {
            transform: translateY(0);
            opacity: 1;
          }
          to {
            transform: translateY(100%);
            opacity: 0;
          }
        }

        .animate-slide-up {
          animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .animate-slide-down {
          animation: slide-down 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .pb-safe {
          padding-bottom: env(safe-area-inset-bottom, 2rem);
        }
      `}</style>
      <style jsx global>{`
        .actions-scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
        .actions-scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .actions-scroll-container,
        .actions-scroll-container * {
          touch-action: pan-x pan-y !important;
        }
        .action-btn {
          background-color: #27272a !important;
          border: 1px solid #3f3f46 !important;
        }
      `}</style>
    </>
  );
}
