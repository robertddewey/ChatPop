'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Message } from '@/lib/api';
import { Pin, DollarSign, Ban, X, BadgeCheck, Reply, Trash2 } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';
import { isDarkTheme } from '@/lib/themes';

interface MessageActionsModalProps {
  message: Message;
  currentUsername?: string;
  isHost?: boolean;
  themeIsDarkMode?: boolean;
  children: React.ReactNode;
  onReply?: (message: Message) => void;
  onPinSelf?: (messageId: string) => void;
  onPinOther?: (messageId: string) => void;
  onBlock?: (username: string) => void;
  onTip?: (username: string) => void;
  onReact?: (messageId: string, emoji: string) => void;
  onDelete?: (messageId: string) => void;
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
  onPinSelf,
  onPinOther,
  onBlock,
  onTip,
  onReact,
  onDelete,
}: MessageActionsModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
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
      setDragOffset(0);
    }, 250); // Match animation duration
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

  // Pin self (own message, not pinned)
  if (isOwnMessage && !message.is_pinned && onPinSelf) {
    actions.push({
      icon: Pin,
      label: 'Pin My Message',
      action: () => {
        onPinSelf(message.id);
        handleClose();
      },
    });
  }

  // Keep pinned (own message, already pinned)
  if (isOwnMessage && message.is_pinned && onPinSelf) {
    actions.push({
      icon: Pin,
      label: 'Keep My Message Pinned',
      action: () => {
        onPinSelf(message.id);
        handleClose();
      },
    });
  }

  // Pin other (not own message, not pinned)
  if (!isOwnMessage && !message.is_pinned && onPinOther) {
    actions.push({
      icon: Pin,
      label: 'Pin Message',
      action: () => {
        onPinOther(message.id);
        handleClose();
      },
    });
  }

  // Keep pinned (not own message, already pinned)
  if (!isOwnMessage && message.is_pinned && onPinOther) {
    actions.push({
      icon: Pin,
      label: 'Keep Message Pinned',
      action: () => {
        onPinOther(message.id);
        handleClose();
      },
    });
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

  // Block should always be last (bottom of modal)
  if (!isOwnMessage && !isHostMessage && onBlock) {
    actions.push({
      icon: Ban,
      label: isHost ? 'Chat Block' : 'Block User',
      action: () => {
        onBlock(message.username);
        handleClose();
      },
    });
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
            className={`relative w-full max-w-lg ${isClosing ? 'animate-slide-down' : (!isDragging && 'animate-slide-up')}`}
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

              {/* Actions */}
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
