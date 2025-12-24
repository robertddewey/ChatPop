'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Message } from '@/lib/api';
import { Pin, DollarSign, Ban, X, BadgeCheck, Reply, Trash2, Plus, Minus } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';
import { isDarkTheme } from '@/lib/themes';

interface PinRequirements {
  current_pin_cents: number;
  minimum_cents: number;
  required_cents: number;
  duration_minutes: number;
}

interface MessageActionsModalProps {
  message: Message;
  currentUsername?: string;
  isHost?: boolean;
  themeIsDarkMode?: boolean;
  children: React.ReactNode;
  onReply?: (message: Message) => void;
  onPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  onAddToPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  getPinRequirements?: (messageId: string) => Promise<PinRequirements>;
  onBlock?: (username: string) => void;
  onTip?: (username: string) => void;
  onReact?: (messageId: string, emoji: string) => void;
  onDelete?: (messageId: string) => void;
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
      actionButton: 'bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500 text-zinc-50 border border-zinc-600',
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

export default function MessageActionsModal({
  message,
  currentUsername,
  isHost = false,
  themeIsDarkMode = true,
  children,
  onReply,
  onPin,
  onAddToPin,
  getPinRequirements,
  onBlock,
  onTip,
  onReact,
  onDelete,
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
  const [pinAmount, setPinAmount] = useState(0);
  const [isPinning, setIsPinning] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);

  const dragStartY = React.useRef(0);
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
          document.body.style.overflow = 'unset';
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
      setPinAmount(0);
      setPinError(null);
    }, 250); // Match animation duration
  };

  // Handle opening the pin input step
  const handleOpenPinInput = async () => {
    if (getPinRequirements) {
      try {
        const requirements = await getPinRequirements(message.id);
        setPinRequirements(requirements);
        setPinAmount(requirements.required_cents);
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
        minimum_cents: 25,
        required_cents: 25,
        duration_minutes: 120,
      });
      setPinAmount(25);
      setShowPinInput(true);
    }
  };

  // Handle pin submission
  const handlePinSubmit = async () => {
    if (!pinRequirements) return;

    // Validate amount
    if (pinAmount < pinRequirements.required_cents) {
      setPinError(`Must pay at least $${(pinRequirements.required_cents / 100).toFixed(2)}`);
      return;
    }

    setIsPinning(true);
    setPinError(null);

    try {
      const isAddToPin = message.is_pinned;
      const handler = isAddToPin ? onAddToPin : onPin;

      if (handler) {
        const success = await handler(message.id, pinAmount);
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
    } catch (error: any) {
      setPinError(error.message || 'Failed to pin message');
    } finally {
      setIsPinning(false);
    }
  };

  // Increment/decrement pin amount
  const adjustPinAmount = (delta: number) => {
    const newAmount = Math.max(pinRequirements?.required_cents || 25, pinAmount + delta);
    setPinAmount(newAmount);
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

  // Reply (always available, always first)
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

  // Pin actions (new API with amount input)
  const hasPinSupport = onPin || onAddToPin || getPinRequirements || onPinSelf || onPinOther;

  if (hasPinSupport) {
    if (!message.is_pinned) {
      // Not pinned - show "Pin Message" or "Pin My Message"
      actions.push({
        icon: Pin,
        label: isOwnMessage ? 'Pin My Message' : 'Pin Message',
        action: handleOpenPinInput,
      });
    } else {
      // Already pinned - show "Add to Pin" to increase value
      actions.push({
        icon: Pin,
        label: isOwnMessage ? 'Add to My Pin' : 'Add to Pin',
        action: handleOpenPinInput,
      });
    }
  }

  if (!isOwnMessage && onTip) {
    actions.push({
      icon: DollarSign,
      label: 'Tip User',
      action: () => {
        onTip(message.username);
        handleClose();
      },
    });
  }

  // Delete message (host only)
  if (isHost && onDelete) {
    actions.push({
      icon: Trash2,
      label: 'Delete Message',
      action: () => {
        if (confirm('Are you sure you want to delete this message?')) {
          onDelete(message.id);
          handleClose();
        } else {
          // Don't close if cancelled
          return;
        }
      },
    });
  }

  // Block/Mute should always be last (bottom of modal)
  // Only show mute/ban for authenticated users (anonymous users cannot mute)
  if (!isOwnMessage && !isHostMessage && onBlock) {
    const authToken = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

    if (authToken) {
      actions.push({
        icon: Ban,
        label: isHost ? 'Ban from Chat' : 'Mute User',
        action: () => {
          onBlock(message.username);
          handleClose();
        },
      });
    }
  }

  return (
    <>
      {/* Trigger: Long-press enabled message */}
      {React.cloneElement(children as React.ReactElement, {
        ...longPressHandlers,
        onContextMenu: (e: React.MouseEvent) => e.preventDefault(),
      })}

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

          {/* Emoji Reactions - Floating above modal */}
          {onReact && (
            <div
              className="absolute bottom-0 left-0 right-0 flex justify-center items-end"
              style={{
                transform: `translateY(${dragOffset}px)`,
                transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
                marginBottom: 'calc(env(safe-area-inset-bottom, 2rem) + 480px)',
              }}
            >
              <div className="flex items-center gap-3 justify-center px-6 mb-6">
                {REACTION_EMOJIS.map((emoji) => (
                  <button
                    key={emoji}
                    onClick={(e) => {
                      e.stopPropagation();
                      onReact(message.id, emoji);
                      handleClose();
                    }}
                    onTouchStart={(e) => e.stopPropagation()}
                    onTouchMove={(e) => e.stopPropagation()}
                    onTouchEnd={(e) => e.stopPropagation()}
                    className={`flex items-center justify-center w-14 h-14 rounded-full transition-all active:scale-110 shadow-lg cursor-pointer ${
                      themeIsDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-white hover:bg-gray-50'
                    }`}
                  >
                    <span className="text-2xl">{emoji}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Modal Container */}
          <div
            className={`relative w-full max-w-lg ${isClosing ? 'animate-slide-down' : (!hasAnimatedIn && 'animate-slide-up')}`}
            style={{
              transform: `translateY(${dragOffset}px)`,
              transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <div
              className={`w-full ${modalStyles.container} rounded-t-3xl`}
              onClick={(e) => e.stopPropagation()}
              onTouchStart={handleDragStart}
              onTouchMove={handleDragMove}
              onTouchEnd={handleDragEnd}
            >
              {/* Drag handle */}
              <div className="pt-3 pb-2 flex justify-center">
                <div className={`w-12 h-1.5 ${modalStyles.dragHandle} rounded-full`} />
              </div>

              {/* Message Preview */}
              <div className="px-6 pt-2 pb-6">
                <div className={`p-4 ${modalStyles.messagePreview}`}>
                  <div className="flex items-center gap-1 mb-2">
                    <span className={`font-semibold text-sm ${modalStyles.usernameText}`}>
                      {message.username}
                    </span>
                    {message.username_is_reserved && (
                      <BadgeCheck className="text-blue-500 flex-shrink-0" size={14} />
                    )}
                    {message.is_from_host && <span className="text-xs">👑</span>}
                    {message.is_pinned && <span className="text-xs">📌</span>}
                  </div>
                  <p className={`text-base ${modalStyles.messageText}`}>
                    {message.content}
                  </p>
                </div>
              </div>

              {/* Actions or Pin Input */}
              {showPinInput && pinRequirements ? (
                <div className="px-6 pb-8 space-y-4">
                  {/* Pin Amount Header */}
                  <div className="text-center">
                    <h3 className={`text-lg font-semibold ${themeIsDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      {message.is_pinned ? 'Add to Pin' : 'Pin Message'}
                    </h3>
                    <p className={`text-sm mt-1 ${themeIsDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>
                      {message.is_pinned
                        ? 'Add value to keep your message pinned'
                        : pinRequirements.current_pin_cents > 0
                          ? `Current pin: $${(pinRequirements.current_pin_cents / 100).toFixed(2)}`
                          : `Duration: ${pinRequirements.duration_minutes} minutes`
                      }
                    </p>
                  </div>

                  {/* Amount Input */}
                  <div className="flex items-center justify-center gap-4">
                    <button
                      onClick={(e) => { e.stopPropagation(); adjustPinAmount(-25); }}
                      disabled={pinAmount <= pinRequirements.required_cents}
                      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all ${
                        pinAmount <= pinRequirements.required_cents
                          ? 'opacity-50 cursor-not-allowed'
                          : 'active:scale-95'
                      } ${themeIsDarkMode ? 'bg-zinc-700 text-white' : 'bg-gray-200 text-gray-700'}`}
                    >
                      <Minus className="w-5 h-5" />
                    </button>

                    <div className={`text-3xl font-bold ${themeIsDarkMode ? 'text-white' : 'text-gray-900'}`}>
                      ${(pinAmount / 100).toFixed(2)}
                    </div>

                    <button
                      onClick={(e) => { e.stopPropagation(); adjustPinAmount(25); }}
                      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all active:scale-95 ${
                        themeIsDarkMode ? 'bg-zinc-700 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      <Plus className="w-5 h-5" />
                    </button>
                  </div>

                  {/* Minimum required */}
                  <p className={`text-center text-xs ${themeIsDarkMode ? 'text-gray-500' : 'text-gray-400'}`}>
                    Minimum: ${(pinRequirements.required_cents / 100).toFixed(2)}
                  </p>

                  {/* Error message */}
                  {pinError && (
                    <p className="text-center text-sm text-red-500">{pinError}</p>
                  )}

                  {/* Buttons */}
                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowPinInput(false); }}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        themeIsDarkMode ? 'bg-zinc-700 text-white' : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      Back
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); handlePinSubmit(); }}
                      disabled={isPinning}
                      className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all active:scale-95 ${
                        isPinning ? 'opacity-50 cursor-not-allowed' : ''
                      } ${themeIsDarkMode ? 'bg-cyan-600 text-white' : 'bg-purple-600 text-white'}`}
                    >
                      {isPinning ? 'Pinning...' : message.is_pinned ? 'Add to Pin' : 'Pin Message'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="px-6 pb-8 space-y-3">
                  {actions.map((action, index) => {
                    const Icon = action.icon;
                    return (
                      <button
                        key={index}
                        onClick={(e) => {
                          e.stopPropagation();
                          action.action();
                        }}
                        onTouchStart={(e) => e.stopPropagation()}
                        onTouchMove={(e) => e.stopPropagation()}
                        onTouchEnd={(e) => e.stopPropagation()}
                        className={`w-full flex items-center gap-4 px-6 py-4 rounded-2xl transition-all active:scale-95 cursor-pointer ${modalStyles.actionButton}`}
                      >
                        <Icon className={`w-6 h-6 ${modalStyles.actionIcon}`} />
                        <span className="text-base font-medium">{action.label}</span>
                      </button>
                    );
                  })}
                </div>
              )}
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
    </>
  );
}
