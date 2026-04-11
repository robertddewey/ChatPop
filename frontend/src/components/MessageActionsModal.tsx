'use client';

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Message, ReactionSummary } from '@/lib/api';
import { Pin, Gift, Ban, ShieldCheck, BadgeCheck, Reply, Trash2, Copy, Flag, Play, Pause, Mic, Crown, Heart, Star, Radio, Megaphone, Spotlight } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';
import ReactionBar from './ReactionBar';
import { GIFT_CATEGORIES, getGiftsByCategory, formatGiftPrice, type GiftItem, type GiftCategory } from '@/lib/gifts';
import { getModalTheme } from '@/lib/modal-theme';

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

function SpotlightPill({ color }: { color?: string }) {
  const c = color || '#facc15';
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-full leading-none"
      style={{ backgroundColor: `${c}20`, color: c }}
    >spotlight</span>
  );
}

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
  spotlightIcon?: string; // Spotlight icon color
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
  onUnblock?: (username: string) => void;
  onUnmute?: (username: string) => void;
  mutedUsernames?: Set<string>;
  onSpotlightAdd?: (username: string) => void;
  onSpotlightRemove?: (username: string) => void;
  spotlightUsernames?: Set<string>;
  onRequestSignup?: () => void;
  onTip?: (username: string) => void;
  onSendGift?: (giftId: string, recipientUsername: string) => Promise<boolean>;
  onThankGift?: (messageId: string) => Promise<boolean>;
  onToggleHighlight?: (messageId: string) => Promise<boolean>;
  onToggleBroadcast?: (messageId: string) => void;
  broadcastMessageId?: string | null;
  onReact?: (messageId: string, emoji: string) => void;
  reactions?: ReactionSummary[];
  onDelete?: (messageId: string) => void;
  onUnpin?: (messageId: string) => void;
  onReport?: (messageId: string, username: string) => void;
  onHighlight?: (messageId: string) => void;
  sessionToken?: string | null;
  themeColors?: ThemeColors;
  modalStyles?: Record<string, string>;
  emojiPickerStyles?: Record<string, string>;
  giftStyles?: Record<string, string>;
  videoPlayerStyles?: Record<string, string>;
  // Legacy props (deprecated, will be removed)
  onPinSelf?: (messageId: string) => void;
  onPinOther?: (messageId: string) => void;
}

// Get theme-aware modal styles (dark-mode only)
const getModalStyles = (themeIsDarkMode: boolean, themeModalStyles?: Record<string, string>) => {
  const mt = getModalTheme(themeIsDarkMode);
  return {
    overlay: mt.backdrop,
    container: mt.container,
    messagePreview: themeModalStyles?.messagePreview || 'bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl',
    messageText: mt.title,
    actionButton: themeModalStyles?.actionButton || 'bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500 text-zinc-50 border border-zinc-500',
    actionIcon: themeModalStyles?.actionIcon || 'text-cyan-400',
    dragHandle: themeModalStyles?.dragHandle || 'bg-gray-600',
    usernameText: themeModalStyles?.usernameText || 'text-gray-300',
    divider: themeModalStyles?.divider || 'border-zinc-700/50',
  };
};

// Allowed reaction emojis (matching backend)
const REACTION_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '😡'];

// Inline video player for modal preview (matches chat VideoMessage style)
function ModalVideoPlayer({ videoUrl, thumbnailUrl, duration, videoPlayerStyles }: { videoUrl: string; thumbnailUrl: string; duration: number; videoPlayerStyles?: Record<string, string> }) {
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
    <div className={`mt-1 max-w-[240px] rounded-lg overflow-hidden relative ${videoPlayerStyles?.container || 'bg-black'}`} onClick={(e) => e.stopPropagation()}>
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
            <div className={`absolute inset-0 rounded-lg ${videoPlayerStyles?.pausedOverlay || 'bg-black/30'}`} />
            <div className={`relative z-10 w-12 h-12 rounded-full flex items-center justify-center shadow-lg ${videoPlayerStyles?.playButton || 'bg-white/90'}`}>
              {isLoading ? (
                <div className={`w-5 h-5 border-2 border-t-transparent rounded-full animate-spin ${videoPlayerStyles?.spinner || 'border-gray-600'}`} />
              ) : (
                <Play size={20} className={`ml-1 ${videoPlayerStyles?.playIcon || 'text-gray-800'}`} fill="currentColor" />
              )}
            </div>
          </>
        )}
        {isPlaying && (
          <div className={`absolute inset-0 opacity-0 hover:opacity-100 active:opacity-100 transition-opacity flex items-center justify-center rounded-lg ${videoPlayerStyles?.playingOverlay || 'bg-black/20'}`}>
            <Pause size={32} className={videoPlayerStyles?.pauseIcon || 'text-white'} fill={videoPlayerStyles?.pauseIconFill || 'white'} />
          </div>
        )}
      </div>

      {/* Duration badge */}
      <div className={`absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-xs font-mono ${videoPlayerStyles?.durationBadge || 'bg-black/70 text-white'}`}>
        {formatTime(isPlaying ? currentTime : duration)}
      </div>

      {/* Progress bar */}
      {isPlaying && (
        <div
          className={`absolute bottom-0 left-0 right-0 h-1 cursor-pointer rounded-b-lg ${videoPlayerStyles?.progressTrack || 'bg-black/30'}`}
          onClick={handleSeek}
        >
          <div className={`h-full transition-all ${videoPlayerStyles?.progressBar || 'bg-white'}`} style={{ width: `${progress}%` }} />
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
  onUnblock,
  onUnmute,
  mutedUsernames,
  onSpotlightAdd,
  onSpotlightRemove,
  spotlightUsernames,
  onRequestSignup,
  onTip,
  onSendGift,
  onThankGift,
  onToggleHighlight,
  onToggleBroadcast,
  broadcastMessageId,
  onReact,
  reactions = [],
  onDelete,
  onUnpin,
  onReport,
  onHighlight,
  sessionToken,
  themeColors,
  modalStyles: themeModalStyles,
  emojiPickerStyles: themeEmojiPickerStyles,
  giftStyles: themeGiftStyles,
  videoPlayerStyles: themeVideoPlayerStyles,
  // Legacy props
  onPinSelf,
  onPinOther,
}: MessageActionsModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [confirmAction, setConfirmAction] = useState<string | null>(null);
  const [muteLockedHint, setMuteLockedHint] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [slideIn, setSlideIn] = useState(false);

  // Local reaction state for optimistic updates while modal is open
  const [localReactions, setLocalReactions] = useState<ReactionSummary[]>(reactions);

  // Panel state: which panel is visible
  type ActivePanel = 'actions' | 'pin' | 'gift';
  const [activePanel, setActivePanel] = useState<ActivePanel>('actions');

  // Pin input state
  const [pinRequirements, setPinRequirements] = useState<PinRequirements | null>(null);
  const [selectedTier, setSelectedTier] = useState<PinTier | null>(null);
  const [isPinning, setIsPinning] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);

  // Gift state
  const [selectedCategory, setSelectedCategory] = useState<GiftCategory>('food');
  const [selectedGift, setSelectedGift] = useState<GiftItem | null>(null);
  const [showGiftConfirmation, setShowGiftConfirmation] = useState(false);
  const [isGiftSending, setIsGiftSending] = useState(false);

  // Sync local reactions with prop when it changes
  useEffect(() => {
    setLocalReactions(reactions);
  }, [reactions]);

  const handleReactLocal = React.useCallback((emoji: string) => {
    if (!onReact) return;
    onReact(message.id, emoji);
    // Optimistic update
    setLocalReactions(prev => {
      const existing = prev.find(r => r.emoji === emoji);
      if (existing) {
        if (existing.has_reacted) {
          // Remove reaction
          const newCount = existing.count - 1;
          return newCount <= 0
            ? prev.filter(r => r.emoji !== emoji)
            : prev.map(r => r.emoji === emoji ? { ...r, count: newCount, has_reacted: false } : r);
        } else {
          // Add reaction
          return prev.map(r => r.emoji === emoji ? { ...r, count: r.count + 1, has_reacted: true } : r);
        }
      } else {
        // New reaction
        return [...prev, { emoji, count: 1, has_reacted: true }];
      }
    });
  }, [onReact, message.id]);

  const dragStartY = React.useRef(0);
  const actionsRef = React.useRef<HTMLDivElement>(null);
  const pinRef = React.useRef<HTMLDivElement>(null);
  const giftRef = React.useRef<HTMLDivElement>(null);
  const [containerHeight, setContainerHeight] = useState<number | undefined>(undefined);

  // Measure active panel height for smooth height transitions
  useEffect(() => {
    if (!isOpen) return;
    const raf = requestAnimationFrame(() => {
      let activeRef = actionsRef;
      if (activePanel === 'pin' && pinRequirements) activeRef = pinRef;
      if (activePanel === 'gift') activeRef = giftRef;
      if (activeRef.current) {
        setContainerHeight(activeRef.current.scrollHeight);
      }
    });
    return () => cancelAnimationFrame(raf);
  }, [isOpen, activePanel, pinRequirements, selectedTier, pinError, selectedCategory, selectedGift, showGiftConfirmation]);

  const isOwnMessage = message.username === currentUsername;
  const isHostMessage = message.is_from_host;

  const modalStyles = getModalStyles(themeIsDarkMode, themeModalStyles);
  const mt = getModalTheme(themeIsDarkMode);

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
    setIsClosing(false);
    setSlideIn(false);

    // Trigger slide-in on next frame so the initial off-screen position renders first
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        setSlideIn(true);
      });
    });

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
    setIsClosing(true);
    setSlideIn(false);
    setIsDragging(false);
    setConfirmAction(null);
    setMuteLockedHint(false);

    // Wait for transition to complete before removing from DOM
    setTimeout(() => {
      setIsOpen(false);
      setIsClosing(false);
      setDragOffset(0);
      // Reset panel state
      setActivePanel('actions');
      setPinRequirements(null);
      setSelectedTier(null);
      setPinError(null);
      setSelectedCategory('food');
      setSelectedGift(null);
      setShowGiftConfirmation(false);
      setIsGiftSending(false);
      setContainerHeight(undefined);
    }, 300);
  };

  // Handle opening the pin input step
  const handleOpenPinInput = async () => {
    if (getPinRequirements) {
      try {
        const requirements = await getPinRequirements(message.id);
        setPinRequirements(requirements);
        setSelectedTier(null);  // Reset selection
        setActivePanel('pin');
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
      setActivePanel('pin');
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
          setTimeout(() => onHighlight?.(message.id), 300);
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

  // 1. Thank — gift messages addressed to me, not yet acknowledged
  if (message.message_type === 'gift' && !message.is_gift_acknowledged && onThankGift) {
    const recipientMatch = message.content.match(/to\s+@(\S+)\s*$/);
    const giftRecipient = recipientMatch ? recipientMatch[1] : '';
    if (giftRecipient.toLowerCase() === currentUsername?.toLowerCase()) {
      actions.push({
        icon: Heart,
        label: 'Thank',
        action: async () => {
          await onThankGift(message.id);
          handleClose();
        },
      });
    }
  }

  // 2. Reply — always
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

  // 3. Pin actions — regular users get paid pin (host uses Unpin in section 5)
  if (!isHost) {
    // Regular users: paid pin (existing logic)
    const hasPinSupport = !message.is_from_host && !message.is_banned && (onPin || onAddToPin || getPinRequirements || onPinSelf || onPinOther);
    const isPinExpired = message.is_pinned && message.sticky_until && new Date(message.sticky_until) < new Date();

    if (hasPinSupport) {
      if (!message.is_pinned) {
        actions.push({ icon: Pin, label: 'Paid Pin', action: handleOpenPinInput });
      } else if (isPinExpired) {
        actions.push({ icon: Pin, label: 'Re-pin', action: handleOpenPinInput });
      } else if (isOutbid) {
        actions.push({ icon: Pin, label: 'Reclaim', action: handleOpenPinInput });
      } else {
        actions.push({ icon: Pin, label: 'Add Pin', action: handleOpenPinInput });
      }
    }
  }

  // 4. Gift — others only
  if (!isOwnMessage) {
    actions.push({
      icon: Gift,
      label: 'Gift',
      action: () => setActivePanel('gift'),
    });
  }

  // 4b. Announce — host-only toggle (sticky slot)
  if (isHost && onToggleBroadcast) {
    const isBroadcast = message.id === broadcastMessageId;
    actions.push({
      icon: Megaphone,
      label: isBroadcast ? 'Unannounce' : 'Announce',
      destructive: isBroadcast,
      action: () => setConfirmAction(isBroadcast ? 'unannounce' : 'announce'),
    });
  }

  // 4c. Highlight — host-only toggle (highlight room)
  if (isHost && onToggleHighlight) {
    actions.push({
      icon: Star,
      label: message.is_highlight ? 'Unstar' : 'Star',
      destructive: !!message.is_highlight,
      action: () => setConfirmAction(message.is_highlight ? 'unhighlight' : 'highlight'),
    });
  }

  // 4d. Spotlight — host-only, on others' (non-host) messages
  if (isHost && !isOwnMessage && !isHostMessage && (onSpotlightAdd || onSpotlightRemove)) {
    const isSpotlit = spotlightUsernames?.has(message.username) || false;
    actions.push({
      icon: Spotlight,
      label: isSpotlit ? 'Unspotlight' : 'Spotlight',
      destructive: isSpotlit,
      action: () => setConfirmAction(isSpotlit ? 'unspotlight' : 'spotlight'),
    });
  }

  // 5. Copy — always (copies "username: content" to clipboard, disabled for media-only)
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

  // 5. Unpin — host only, pinned messages only
  if (isHost && message.is_pinned && onUnpin) {
    actions.push({
      icon: Pin,
      label: 'Unpin',
      destructive: true,
      action: () => setConfirmAction('unpin'),
    });
  }

  // 6. Delete — host only (destructive)
  if (isHost && onDelete) {
    actions.push({
      icon: Trash2,
      label: 'Delete',
      destructive: true,
      action: () => {
        setConfirmAction('delete');
      },
    });
  }

  // 6. Mute/Ban/Unban — registered users, others only
  if (!isOwnMessage && !isHostMessage) {
    const authToken = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (!authToken && !isHost) {
      // Anonymous users see a locked Mute action
      actions.push({
        icon: Ban,
        label: 'Mute',
        destructive: true,
        action: () => {
          setMuteLockedHint(true);
        },
      });
    } else if (authToken) {
      if (isHost && message.is_banned && onUnblock) {
        // Host sees "Unban" for already-banned users
        actions.push({
          icon: ShieldCheck,
          label: 'Unban',
          destructive: true,
          action: () => {
            setConfirmAction('unban');
          },
        });
      } else if (!isHost && mutedUsernames && mutedUsernames.has(message.username) && onUnmute) {
        actions.push({
          icon: ShieldCheck,
          label: 'Unmute',
          destructive: true,
          action: () => {
            onUnmute(message.username);
            handleClose();
          },
        });
      } else if (onBlock) {
        actions.push({
          icon: Ban,
          label: isHost ? 'Ban' : 'Mute',
          destructive: true,
          action: () => {
            if (isHost) {
              setConfirmAction('ban');
            } else {
              setConfirmAction('mute');
            }
          },
        });
      }
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
            className="relative w-full max-w-lg"
            style={{
              transform: isDragging
                ? `translateY(${dragOffset}px)`
                : slideIn && !isClosing
                  ? 'translateY(0)'
                  : 'translateY(100%)',
              opacity: slideIn && !isClosing ? 1 : 0,
              transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease',
            }}
          >
            {/* Floating Message Preview — docked above sheet, rendered like actual chat message */}
            <div className="px-4 pb-6">
              <div className="flex">
                <div className="w-10 flex-shrink-0 mr-3">
                  <div className="relative w-10 h-10">
                    <img
                      src={message.avatar_url}
                      alt={message.username}
                      className={`w-10 h-10 rounded-full ${themeModalStyles?.avatarFallbackBg || 'bg-zinc-700'}`}
                    />
                    {message.username_is_reserved && (
                      <BadgeCheck size={12} className="absolute -bottom-0.5 -right-0.5 rounded-full" style={{ color: themeColors?.badgeIcon || '#3b82f6', backgroundColor: themeModalStyles?.badgeIconBg || '#18181b' }} />
                    )}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mb-1">
                    {(() => {
                      const isSpotlight = !message.is_from_host && spotlightUsernames?.has(message.username);
                      const usernameColor = isOwnMessage
                        ? (themeColors?.myUsername || '#ef4444')
                        : (message.is_from_host || isSpotlight)
                          ? (themeColors?.hostUsername || '#fbbf24')
                          : message.is_pinned
                            ? (themeColors?.pinnedUsername || '#c084fc')
                            : (themeColors?.regularUsername || '#ffffff');
                      return (
                        <>
                          <span
                            className="text-sm font-bold"
                            style={{ color: usernameColor }}
                          >
                            {message.username}
                          </span>
                          {isOwnMessage && <span className="ml-1"><YouPill className={themeModalStyles?.youPill} /></span>}
                          {message.is_from_host && (
                            <>
                              <span className="ml-1"><HostPill color={themeColors?.crownIcon || '#2dd4bf'} /></span>
                              <Crown className="inline-block ml-1 flex-shrink-0" size={14} fill="currentColor" style={{ color: themeColors?.crownIcon || '#2dd4bf' }} />
                            </>
                          )}
                          {isSpotlight && (
                            <>
                              <span className="ml-1"><SpotlightPill color={themeColors?.spotlightIcon || '#facc15'} /></span>
                              <Spotlight className="inline-block ml-1 flex-shrink-0" size={14} fill="currentColor" style={{ color: themeColors?.spotlightIcon || '#facc15' }} />
                            </>
                          )}
                        </>
                      );
                    })()}
                  </div>
                  {/* Text content or gift card */}
                  {message.message_type === 'gift' ? (() => {
                    const giftMatch = message.content.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
                    const emoji = giftMatch ? giftMatch[1] : '🎁';
                    const giftName = giftMatch ? giftMatch[2] : '';
                    const price = giftMatch ? giftMatch[3] : '';
                    const recipient = giftMatch ? giftMatch[4] : '';
                    const isForMe = recipient.toLowerCase() === currentUsername?.toLowerCase();
                    return (
                      <div className={`relative rounded-xl px-2.5 py-2 flex items-center gap-2 max-w-[calc(100%-2.5%-5rem+5px)] ${
                        isForMe
                          ? themeGiftStyles?.cardForMe || 'bg-purple-950/50 border border-purple-500/50'
                          : themeGiftStyles?.card || 'bg-zinc-800/80 border border-zinc-700'
                      }`}>
                        {price && (
                          <span className={`absolute top-1.5 right-2 text-[8px] font-medium px-1 py-0.5 rounded-full ${
                            themeGiftStyles?.priceBadge || 'bg-cyan-900/50 text-cyan-400'
                          }`}>{price}</span>
                        )}
                        <div className={`text-xl flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center animate-gift-breath ${
                          themeGiftStyles?.emojiBox || 'bg-zinc-700/80'
                        }`}>
                          {emoji}
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className={`text-xs font-semibold ${themeGiftStyles?.nameText || 'text-white'}`}>{giftName}</span>
                          </div>
                          {recipient && (
                            <div className={`text-[10px] ${themeGiftStyles?.toPrefix || themeGiftStyles?.recipientText || 'text-zinc-400'}`}>
                              to <span className={`font-semibold ${
                                isForMe
                                  ? (themeGiftStyles?.recipientHighlight || 'text-purple-400')
                                  : (themeGiftStyles?.recipientNormal || 'text-zinc-300')
                              }`}>@{recipient}</span>
                              {isForMe && <span className="ml-1"><YouPill className={themeGiftStyles?.youPill} /></span>}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })() : message.content && (
                    <p className={`text-sm ${themeModalStyles?.messageText || 'text-white'}`}>
                      {message.content}
                    </p>
                  )}
                  {/* Photo — sized to fit available space above the sheet */}
                  {message.photo_url && (() => {
                    const imgW = message.photo_width || 300;
                    const imgH = message.photo_height || 200;
                    const aspect = imgW / imgH;

                    // Available height: viewport minus sheet (~280px) minus preview chrome
                    // (username ~24px, timestamp ~20px, padding ~48px = ~92px)
                    const maxH = Math.max(120, (typeof window !== 'undefined' ? window.innerHeight : 800) - 280 - 92);
                    const maxW = 240;

                    let w = Math.min(maxW, imgW);
                    let h = Math.round(w / aspect);

                    // If height exceeds budget, scale down by height
                    if (h > maxH) {
                      h = maxH;
                      w = Math.round(h * aspect);
                    }

                    return (
                      <div
                        className={`mt-1 rounded-lg overflow-hidden ${themeModalStyles?.photoThumbnailBg || 'bg-zinc-700'}`}
                        style={{ width: w, height: h }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <img src={`${message.photo_url}${message.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`} alt="Photo" className="w-full h-full object-cover rounded-lg" draggable={false} />
                      </div>
                    );
                  })()}
                  {/* Video player */}
                  {message.video_url && (
                    <ModalVideoPlayer
                      videoUrl={`${message.video_url}${message.video_url.includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`}
                      thumbnailUrl={`${message.video_thumbnail_url || ''}${(message.video_thumbnail_url || '').includes('?') ? '&' : '?'}session_token=${sessionToken || ''}`}
                      duration={message.video_duration || 0}
                      videoPlayerStyles={themeVideoPlayerStyles}
                    />
                  )}
                  {/* Voice message */}
                  {message.voice_url && !message.content && (
                    <div className="flex items-center gap-2 mt-1" onClick={(e) => e.stopPropagation()}>
                      <Mic className={`w-4 h-4 ${themeModalStyles?.voiceText || 'text-white/60'}`} />
                      <span className={`text-sm ${themeModalStyles?.voiceText || 'text-white/60'}`}>
                        Voice message{message.voice_duration ? ` (${Math.floor(message.voice_duration / 60)}:${String(Math.floor(message.voice_duration % 60)).padStart(2, '0')})` : ''}
                      </span>
                    </div>
                  )}
                  {/* Timestamp + Reactions — min-h prevents layout shift when first reaction is added */}
                  <div className="flex items-center gap-2 mt-1 min-h-[24px]">
                    <span className={`text-[10px] flex-shrink-0 whitespace-nowrap ${themeModalStyles?.timestampText || 'text-white opacity-60'}`}>
                      {new Date(message.created_at).toLocaleString(undefined, { month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                    </span>
                    <ReactionBar
                      reactions={localReactions}
                      maxVisible={20}
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Sheet */}
            <div
              className={`w-full ${modalStyles.container} rounded-t-3xl`}
              onClick={(e) => e.stopPropagation()}
              style={{
                paddingBottom: `calc(1.5rem + env(safe-area-inset-bottom, 0px))`,
                '--action-btn-bg': themeModalStyles?.actionBtnBg || '#27272a',
                '--action-btn-border': themeModalStyles?.actionBtnBorder || '#3f3f46',
              } as React.CSSProperties}
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
                  style={{ transform: activePanel === 'gift' ? 'translateX(-200%)' : activePanel === 'pin' ? 'translateX(-100%)' : 'translateX(0)' }}
                >
                  {/* Panel 1: Actions (emoji + action buttons) */}
                  <div className="w-full flex-shrink-0" ref={actionsRef}>
                  {/* Emoji Reactions Row */}
                  {onReact && (
                    <div className="px-5 pb-4 pt-1">
                      <div className="flex items-center justify-between">
                        {REACTION_EMOJIS.map((emoji) => {
                          const hasReacted = localReactions.some(r => r.emoji === emoji && r.has_reacted);
                          return (
                            <button
                              key={emoji}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleReactLocal(emoji);
                              }}
                              onTouchStart={(e) => e.stopPropagation()}
                              onTouchMove={(e) => e.stopPropagation()}
                              onTouchEnd={(e) => e.stopPropagation()}
                              className={`flex items-center justify-center rounded-full transition-all active:scale-110 cursor-pointer ${
                                hasReacted
                                  ? themeEmojiPickerStyles?.selected || 'bg-purple-500/30 ring-2 ring-purple-500/60'
                                  : themeEmojiPickerStyles?.unselected || 'bg-zinc-800 hover:bg-zinc-700'
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
                  <div className={`mx-5 border-t ${modalStyles.divider}`} />

                  {/* Horizontal Scrollable Action Row OR Ban Confirmation */}
                  {muteLockedHint ? (
                    <div className="px-5 py-4 space-y-3">
                      <p className={`text-sm font-medium text-center ${themeModalStyles?.actionLabel || 'text-zinc-50'}`}>
                        🤫 Muting is a members-only superpower.
                      </p>
                      <div className="flex gap-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setMuteLockedHint(false);
                          }}
                          className={`flex-1 px-4 py-2.5 rounded-xl font-medium text-sm transition-all active:scale-95 cursor-pointer ${themeModalStyles?.secondaryButton || 'bg-zinc-700 text-zinc-200 hover:bg-zinc-600'}`}
                        >
                          Not now
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setMuteLockedHint(false);
                            handleClose();
                            onRequestSignup?.();
                          }}
                          className="flex-1 px-4 py-2.5 rounded-xl font-medium text-sm bg-blue-500 text-white hover:bg-blue-600 transition-all active:scale-95 cursor-pointer text-center"
                        >
                          Sign up
                        </button>
                      </div>
                    </div>
                  ) : confirmAction ? (
                    <div className="px-5 py-4 space-y-3">
                      <p className={`text-sm font-medium text-center ${themeModalStyles?.actionLabel || 'text-zinc-50'}`}>
                        {confirmAction === 'delete' && <>Delete this message?</>}
                        {confirmAction === 'ban' && <>Ban <span className="font-bold">{message.username}</span> from this chat?</>}
                        {confirmAction === 'unban' && <>Unban <span className="font-bold">{message.username}</span>?</>}
                        {confirmAction === 'mute' && <>Mute <span className="font-bold">{message.username}</span>?</>}
                        {confirmAction === 'unpin' && <>Unpin this message?</>}
                        {confirmAction === 'spotlight' && <>Spotlight this user? They&apos;ll appear in the Focus room.</>}
                        {confirmAction === 'unspotlight' && <>Remove this user from the spotlight?</>}
                        {confirmAction === 'highlight' && <>Add this message to the Star room?</>}
                        {confirmAction === 'unhighlight' && <>Remove this message from the Star room?</>}
                        {confirmAction === 'announce' && <>Pin this message to the top?</>}
                        {confirmAction === 'unannounce' && <>Unpin this from the top?</>}
                      </p>
                      <div className="flex gap-3">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmAction(null);
                          }}
                          className={`flex-1 px-4 py-2.5 rounded-xl font-medium text-sm transition-all active:scale-95 cursor-pointer ${themeModalStyles?.secondaryButton || 'bg-zinc-700 text-zinc-200 hover:bg-zinc-600'}`}
                        >
                          Cancel
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirmAction === 'delete' && onDelete) {
                              onDelete(message.id);
                            } else if (confirmAction === 'ban' && onBlock) {
                              onBlock(message.username);
                            } else if (confirmAction === 'mute' && onBlock) {
                              onBlock(message.username);
                            } else if (confirmAction === 'unban' && onUnblock) {
                              onUnblock(message.username);
                            } else if (confirmAction === 'unpin' && onUnpin) {
                              onUnpin(message.id);
                            } else if (confirmAction === 'spotlight' && onSpotlightAdd) {
                              onSpotlightAdd(message.username);
                            } else if (confirmAction === 'unspotlight' && onSpotlightRemove) {
                              onSpotlightRemove(message.username);
                            } else if (confirmAction === 'highlight' && onToggleHighlight) {
                              onToggleHighlight(message.id);
                            } else if (confirmAction === 'unhighlight' && onToggleHighlight) {
                              onToggleHighlight(message.id);
                            } else if (confirmAction === 'announce' && onToggleBroadcast) {
                              onToggleBroadcast(message.id);
                            } else if (confirmAction === 'unannounce' && onToggleBroadcast) {
                              onToggleBroadcast(message.id);
                            }
                            setConfirmAction(null);
                            handleClose();
                          }}
                          className="flex-1 px-4 py-2.5 rounded-xl font-medium text-sm bg-red-500 text-white hover:bg-red-600 transition-all active:scale-95 cursor-pointer"
                        >
                          {{
                            delete: 'Delete',
                            ban: 'Ban',
                            unban: 'Unban',
                            mute: 'Mute',
                            unpin: 'Unpin',
                            spotlight: 'Spotlight',
                            unspotlight: 'Remove',
                            highlight: 'Add',
                            unhighlight: 'Remove',
                            announce: 'Pin',
                            unannounce: 'Unpin',
                          }[confirmAction]}
                        </button>
                      </div>
                    </div>
                  ) : (
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
                              <Icon className={`w-6 h-6 ${action.destructive ? (themeModalStyles?.destructiveText || 'text-red-400') : modalStyles.actionIcon}`} />
                              <span className={`text-xs font-medium truncate w-full text-center ${action.destructive ? (themeModalStyles?.destructiveText || 'text-red-400') : themeModalStyles?.actionLabel || 'text-zinc-50'}`}>{action.label}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                  )}
                  </div>

                  {/* Panel 2: Pin Input */}
                  <div className="w-full flex-shrink-0" ref={pinRef}>
                {pinRequirements && (
                <div className="space-y-4 max-h-[320px] overflow-y-auto w-full">
                  {/* Pin Amount Header */}
                  <div className="text-center px-6">
                    <h3 className={`text-lg font-semibold ${themeModalStyles?.messageText || 'text-white'}`}>
                      {pinRequirements.is_current_sticky
                        ? 'Add to Pin'
                        : pinRequirements.is_outbid
                          ? 'Reclaim Pin'
                          : !message.is_pinned
                            ? 'Pin Message'
                            : 'Re-pin Message'
                      }
                    </h3>
                    <p className={`text-sm mt-1 ${themeModalStyles?.subtitle || 'text-gray-400'}`}>
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
                                        ? 'ring-2 ring-cyan-400'
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
                                      themeModalStyles?.actionLabel || 'text-zinc-50'
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
                    <p className={`text-center text-sm px-6 ${themeModalStyles?.destructiveText || 'text-red-400'}`}>{pinError}</p>
                  )}

                  {/* Buttons */}
                  <div className="flex gap-3 pt-2 px-6">
                    <button
                      onClick={(e) => { e.stopPropagation(); setActivePanel('actions'); setSelectedTier(null); }}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        themeModalStyles?.inputField || 'bg-zinc-700 text-white'
                      }`}
                    >
                      Back
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePinSubmit(); }}
                      disabled={isPinning || !selectedTier}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        (isPinning || !selectedTier) ? 'opacity-50 cursor-not-allowed' : ''
                      } ${mt.primaryButton}`}
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

                  {/* Panel 3: Gift Selection */}
                  <div className="w-full flex-shrink-0" ref={giftRef}>
                    <div className="space-y-4 max-h-[420px] overflow-y-auto w-full">
                      {!showGiftConfirmation ? (
                        <>
                          {/* Header */}
                          <div className="text-center px-6">
                            <h3 className={`text-lg font-semibold ${themeModalStyles?.messageText || 'text-white'}`}>
                              Send a Gift
                            </h3>
                            <p className={`text-sm mt-1 ${themeModalStyles?.subtitle || 'text-gray-400'}`}>
                              to <span className={`font-semibold ${themeModalStyles?.messageText || 'text-white'}`}>@{message.username}</span>
                            </p>
                          </div>

                          {/* Category Tabs */}
                          <div
                            className="overflow-x-scroll actions-scrollbar-hide actions-scroll-container px-5"
                            style={{ WebkitOverflowScrolling: 'touch' }}
                          >
                            <div className="flex gap-2 w-max mx-auto">
                              {GIFT_CATEGORIES.map((cat) => (
                                <button
                                  key={cat.id}
                                  onClick={(e) => { e.stopPropagation(); setSelectedCategory(cat.id); }}
                                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all active:scale-95 whitespace-nowrap ${
                                    selectedCategory === cat.id
                                      ? mt.primaryButton
                                      : `${mt.secondaryButton} border ${themeModalStyles?.inputBorder || 'border-zinc-500'}`
                                  }`}
                                >
                                  {cat.emoji} {cat.label}
                                </button>
                              ))}
                            </div>
                          </div>

                          {/* Gift Items — Horizontal Scroll */}
                          <div
                            className="overflow-x-scroll actions-scrollbar-hide actions-scroll-container px-5"
                            style={{ WebkitOverflowScrolling: 'touch' }}
                          >
                            <div className="flex gap-2 w-max">
                              {getGiftsByCategory(selectedCategory).map((gift) => (
                                <div
                                  key={gift.id}
                                  role="button"
                                  tabIndex={0}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedGift(gift);
                                    setShowGiftConfirmation(true);
                                  }}
                                  className="flex flex-col items-center justify-center gap-1 py-3 rounded-2xl transition-all w-[72px] h-[72px] action-btn active:scale-95 cursor-pointer"
                                >
                                  <span className="text-2xl">{gift.emoji}</span>
                                  <span className={`text-[10px] font-medium ${themeModalStyles?.actionLabel || 'text-zinc-50'}`}>
                                    {formatGiftPrice(gift.price)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Back Button */}
                          <div className="px-6 pt-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); setActivePanel('actions'); }}
                              className={`w-full py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                                themeModalStyles?.inputField || 'bg-zinc-700 text-white'
                              }`}
                            >
                              Back
                            </button>
                          </div>
                        </>
                      ) : selectedGift && (
                        <>
                          {/* Confirmation View */}
                          <div className="text-center px-6 pt-2">
                            <span className="text-6xl block mb-3">{selectedGift.emoji}</span>
                            <h3 className={`text-lg font-semibold ${themeModalStyles?.messageText || 'text-white'}`}>
                              {selectedGift.name}
                            </h3>
                            <p className={`text-2xl font-bold mt-1 ${modalStyles.actionIcon}`}>
                              {formatGiftPrice(selectedGift.price)}
                            </p>
                            <p className={`text-sm mt-2 ${themeModalStyles?.subtitle || 'text-gray-400'}`}>
                              Send to <span className={`font-semibold ${themeModalStyles?.messageText || 'text-white'}`}>@{message.username}</span>
                            </p>
                          </div>

                          {/* Confirm / Back Buttons */}
                          <div className="flex gap-3 pt-2 px-6">
                            <button
                              onClick={(e) => { e.stopPropagation(); setShowGiftConfirmation(false); setSelectedGift(null); }}
                              disabled={isGiftSending}
                              className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                                isGiftSending ? 'opacity-50 cursor-not-allowed' : ''
                              } ${themeModalStyles?.inputField || 'bg-zinc-700 text-white'}`}
                            >
                              Back
                            </button>
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (!onSendGift || !selectedGift) return;
                                setIsGiftSending(true);
                                try {
                                  const success = await onSendGift(selectedGift.id, message.username);
                                  if (success) {
                                    handleClose();
                                  }
                                } catch (err) {
                                  console.error('[Gift] Send failed:', err);
                                } finally {
                                  setIsGiftSending(false);
                                }
                              }}
                              disabled={isGiftSending}
                              className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                                isGiftSending ? 'opacity-50 cursor-not-allowed' : ''
                              } ${mt.primaryButton}`}
                            >
                              {isGiftSending ? 'Sending...' : `Send ${formatGiftPrice(selectedGift.price)}`}
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      <style jsx>{`
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
          background-color: var(--action-btn-bg, #27272a) !important;
          border: 1px solid var(--action-btn-border, #3f3f46) !important;
        }
      `}</style>
    </>
  );
}
