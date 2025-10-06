'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Message } from '@/lib/api';
import { Pin, DollarSign, Ban, X, BadgeCheck } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';
import { isDarkTheme } from '@/lib/themes';

interface MessageActionsModalProps {
  message: Message;
  currentUsername?: string;
  isHost?: boolean;
  design?: 'dark-mode';
  children: React.ReactNode;
  onPinSelf?: (messageId: string) => void;
  onPinOther?: (messageId: string) => void;
  onBlock?: (username: string) => void;
  onTip?: (username: string) => void;
}

// Get theme-aware modal styles
const getModalStyles = (design: 'dark-mode') => {
  const useDarkMode = isDarkTheme(design);

  if (useDarkMode) {
    // Always use dark mode for dark-type themes
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
    // Use system preference for light-type themes
    return {
      overlay: 'bg-black/20 dark:bg-black/60 backdrop-blur-sm',
      container: 'bg-white dark:bg-zinc-900',
      messagePreview: 'bg-gray-50 dark:bg-zinc-800 border border-gray-200 dark:border-zinc-600 rounded-2xl dark:rounded-lg shadow-sm dark:shadow-xl',
      messageText: 'text-gray-800 dark:text-zinc-50',
      actionButton: 'bg-gray-100 dark:bg-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-600 active:bg-gray-300 dark:active:bg-zinc-500 text-gray-900 dark:text-zinc-50 dark:border dark:border-zinc-600',
      actionIcon: 'text-purple-600 dark:text-cyan-400',
      dragHandle: 'bg-gray-300 dark:bg-gray-600',
      usernameText: 'text-gray-700 dark:text-gray-300',
    };
  }
};

export default function MessageActionsModal({
  message,
  currentUsername,
  isHost = false,
  design = 'dark-mode',
  children,
  onPinSelf,
  onPinOther,
  onBlock,
  onTip,
}: MessageActionsModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const dragStartY = React.useRef(0);
  const isOwnMessage = message.username === currentUsername;
  const isHostMessage = message.is_from_host;
  const modalStyles = getModalStyles(design);

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
    setIsOpen(false);
    setDragOffset(0);
    setIsDragging(false);
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

  // Pin self (own message, not pinned)
  if (isOwnMessage && !message.is_pinned && onPinSelf) {
    actions.push({
      icon: Pin,
      label: 'Pin My Message',
      action: () => handleAction(() => onPinSelf(message.id)),
    });
  }

  // Keep pinned (own message, already pinned)
  if (isOwnMessage && message.is_pinned && onPinSelf) {
    actions.push({
      icon: Pin,
      label: 'Keep My Message Pinned',
      action: () => handleAction(() => onPinSelf(message.id)),
    });
  }

  // Pin other (not own message, not pinned)
  if (!isOwnMessage && !message.is_pinned && onPinOther) {
    actions.push({
      icon: Pin,
      label: 'Pin Message',
      action: () => handleAction(() => onPinOther(message.id)),
    });
  }

  // Keep pinned (not own message, already pinned)
  if (!isOwnMessage && message.is_pinned && onPinOther) {
    actions.push({
      icon: Pin,
      label: 'Keep Message Pinned',
      action: () => handleAction(() => onPinOther(message.id)),
    });
  }

  if (!isOwnMessage && onTip) {
    actions.push({
      icon: DollarSign,
      label: 'Tip User',
      action: () => handleAction(() => onTip(message.username)),
    });
  }

  // Block should always be last (bottom of modal)
  if (!isOwnMessage && !isHostMessage && onBlock) {
    actions.push({
      icon: Ban,
      label: 'Block User',
      action: () => handleAction(() => onBlock(message.username)),
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

          {/* Modal Content */}
          <div
            className={`relative w-full max-w-lg ${modalStyles.container} rounded-t-3xl pb-safe ${!isDragging && 'animate-slide-up'}`}
            style={{
              transform: `translateY(${dragOffset}px)`,
              transition: isDragging ? 'none' : 'transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
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
                    onClick={action.action}
                    className={`w-full flex items-center gap-4 px-6 py-4 rounded-2xl transition-all active:scale-95 ${modalStyles.actionButton}`}
                  >
                    <Icon className={`w-6 h-6 ${modalStyles.actionIcon}`} />
                    <span className="text-base font-medium">{action.label}</span>
                  </button>
                );
              })}
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

        .animate-slide-up {
          animation: slide-up 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }

        .pb-safe {
          padding-bottom: env(safe-area-inset-bottom, 2rem);
        }
      `}</style>
    </>
  );
}
