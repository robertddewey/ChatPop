'use client';

import React, { useState } from 'react';
import { createPortal } from 'react-dom';
import { Message } from '@/lib/api';
import { Pin, DollarSign, Ban, X } from 'lucide-react';
import { useLongPress } from '@/hooks/useLongPress';

interface MessageActionsModalProps {
  message: Message;
  currentUsername?: string;
  isHost?: boolean;
  design?: 'design1' | 'design2' | 'design3';
  children: React.ReactNode;
  onPinSelf?: (messageId: string) => void;
  onPinOther?: (messageId: string) => void;
  onBlock?: (username: string) => void;
  onTip?: (username: string) => void;
}

// Theme configurations for the modal
const modalStyles = {
  design1: {
    overlay: 'bg-black/40 backdrop-blur-md',
    container: 'bg-gradient-to-br from-purple-50 to-pink-50 dark:from-gray-900 dark:to-gray-800',
    messagePreview: 'bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border-2 border-purple-200 dark:border-purple-800 rounded-2xl shadow-lg',
    messageText: 'text-gray-800 dark:text-gray-200',
    actionButton: 'bg-white/80 dark:bg-gray-800/80 hover:bg-purple-100 dark:hover:bg-purple-900/40 border-2 border-purple-200 dark:border-purple-700 text-gray-800 dark:text-gray-200',
    actionIcon: 'text-purple-600 dark:text-purple-400',
  },
  design2: {
    overlay: 'bg-black/40 backdrop-blur-md',
    container: 'bg-gradient-to-br from-sky-50 to-cyan-50 dark:from-gray-900 dark:to-gray-800',
    messagePreview: 'bg-white/90 dark:bg-gray-800/90 backdrop-blur-sm border-2 border-blue-200 dark:border-blue-800 rounded-2xl shadow-lg',
    messageText: 'text-gray-800 dark:text-gray-200',
    actionButton: 'bg-white/80 dark:bg-gray-800/80 hover:bg-blue-100 dark:hover:bg-blue-900/40 border-2 border-blue-200 dark:border-blue-700 text-gray-800 dark:text-gray-200',
    actionIcon: 'text-blue-600 dark:text-blue-400',
  },
  design3: {
    overlay: 'bg-black/60 backdrop-blur-sm',
    container: 'bg-zinc-900',
    messagePreview: 'bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl',
    messageText: 'text-zinc-50',
    actionButton: 'bg-zinc-700 hover:bg-zinc-600 border border-zinc-600 text-zinc-50',
    actionIcon: 'text-cyan-400',
  },
};

export default function MessageActionsModal({
  message,
  currentUsername,
  isHost = false,
  design = 'design1',
  children,
  onPinSelf,
  onPinOther,
  onBlock,
  onTip,
}: MessageActionsModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const styles = modalStyles[design];
  const isOwnMessage = message.username === currentUsername;
  const isHostMessage = message.is_from_host;

  const handleOpen = () => {
    setIsOpen(true);
    // Trigger haptic feedback (Android only)
    if (typeof window !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(50);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
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

  if (isOwnMessage && !message.is_pinned && onPinSelf) {
    actions.push({
      icon: Pin,
      label: 'Pin My Message',
      action: () => handleAction(() => onPinSelf(message.id)),
    });
  }

  if (isHost && !isOwnMessage && !message.is_pinned && onPinOther) {
    actions.push({
      icon: Pin,
      label: 'Pin Message',
      action: () => handleAction(() => onPinOther(message.id)),
    });
  }

  if (!isOwnMessage && !isHostMessage && onBlock) {
    actions.push({
      icon: Ban,
      label: `Block ${message.username}`,
      action: () => handleAction(() => onBlock(message.username)),
    });
  }

  if (!isOwnMessage && onTip) {
    actions.push({
      icon: DollarSign,
      label: `Tip ${message.username}`,
      action: () => handleAction(() => onTip(message.username)),
    });
  }

  return (
    <>
      {/* Trigger: Long-press enabled message */}
      {React.cloneElement(children as React.ReactElement, {
        ...longPressHandlers,
        className: `${(children as React.ReactElement).props.className} select-none`,
        style: {
          ...(children as React.ReactElement).props.style,
          WebkitUserSelect: 'none',
          userSelect: 'none',
          WebkitTouchCallout: 'none',
          touchAction: 'manipulation',
          WebkitTapHighlightColor: 'transparent',
        },
        onContextMenu: (e: React.MouseEvent) => e.preventDefault(),
      })}

      {/* Full-screen Modal */}
      {isOpen && typeof document !== 'undefined' && createPortal(
        <div
          className="fixed inset-0 z-[9999] flex items-end justify-center"
          onClick={handleClose}
        >
          {/* Backdrop with blur */}
          <div className={`absolute inset-0 ${styles.overlay}`} />

          {/* Modal Content */}
          <div
            className={`relative w-full max-w-lg ${styles.container} rounded-t-3xl pb-safe animate-slide-up`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drag handle */}
            <div className="pt-3 pb-2 flex justify-center">
              <div className="w-12 h-1.5 bg-gray-300 dark:bg-gray-600 rounded-full" />
            </div>

            {/* Message Preview */}
            <div className="px-6 pt-2 pb-6">
              <div className={`p-4 ${styles.messagePreview}`}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-semibold text-sm text-gray-700 dark:text-gray-300">
                    {message.username}
                  </span>
                  {message.is_from_host && <span className="text-xs">👑</span>}
                  {message.is_pinned && <span className="text-xs">📌</span>}
                </div>
                <p className={`text-base ${styles.messageText}`}>
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
                    className={`w-full flex items-center gap-4 px-6 py-4 rounded-2xl transition-all active:scale-95 ${styles.actionButton}`}
                  >
                    <Icon className={`w-6 h-6 ${styles.actionIcon}`} />
                    <span className="text-lg font-medium">{action.label}</span>
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
