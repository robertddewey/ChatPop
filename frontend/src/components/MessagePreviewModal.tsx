'use client';

/**
 * MessagePreviewModal
 *
 * Shows a single message in a popup so the user can see what was being
 * replied to (or what a sticky message refers to) without scrolling back
 * through the timeline. Solves two problems at once:
 *   1. The reply preview's parent may be outside the currently-loaded
 *      pagination window (50-message default). Scroll-to-find can't reach
 *      it without paginating; this fetches by ID directly.
 *   2. Sticky pinned/host messages may point to messages from days ago.
 *      A scroll would be jarring even if the data were available.
 *
 * Bubble fidelity: renders the SAME `<MessageBubbleContent>` the timeline
 * uses, wrapped in `<MessageActionsModal>` for long-press behavior. So
 * media players, theme styling, badges, and reactions all match the timeline.
 *
 * Chain-walking: tapping the in-popup reply preview pushes onto a stack;
 * back button pops. Max depth 20 as a safety cap.
 *
 * Body is scrollable for long content.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { ArrowLeft, X, Loader2 } from 'lucide-react';
import { ChatRoom, Message, ReactionSummary, messageApi } from '@/lib/api';
import MessageActionsModal from './MessageActionsModal';
import MessageBubbleContent from './MessageBubbleContent';
import ReactionBar from './ReactionBar';
import { formatTimestamp } from '@/lib/formatTimestamp';
import { getTextColor } from '@/lib/themeColors';

const MAX_CHAIN_DEPTH = 20;

// All the props MessageActionsModal needs to render its long-press sheet.
// Threaded from page.tsx so the popup can offer the same actions as the
// timeline (reply, react, pin, gift, highlight, etc.).
interface PassthroughActionProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  currentDesign: Record<string, any>;
  themeIsDarkMode?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  modalThemeColors?: Record<string, any>;
  isHost: boolean;
  spotlightUsernames?: Set<string>;
  mutedUsernames?: Set<string>;
  broadcastMessageId?: string | null;
  viewportHeight?: number;
  chatRoom?: ChatRoom | null;

  onReply?: (message: Message) => void;
  onPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  onAddToPin?: (messageId: string, amountCents: number) => Promise<boolean>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  getPinRequirements?: (messageId: string) => Promise<any>;
  onBlock?: (username: string, fingerprint?: string, userId?: number) => Promise<boolean> | void;
  onUnblock?: (username: string) => Promise<boolean> | void;
  onUnmute?: (username: string) => Promise<boolean> | void;
  onSpotlightAdd?: (username: string) => Promise<void>;
  onSpotlightRemove?: (username: string) => Promise<void>;
  onRequestSignup?: () => void;
  onTip?: (username: string, amountCents: number) => Promise<boolean>;
  onSendGift?: (username: string, giftId: string) => Promise<boolean>;
  onThankGift?: (messageId: string) => Promise<void> | void;
  onToggleHighlight?: (messageId: string) => Promise<void> | void;
  onToggleBroadcast?: (messageId: string) => Promise<void> | void;
  onDelete?: (messageId: string) => Promise<void> | void;
  onUnpin?: (messageId: string) => Promise<void> | void;
  onReact?: (messageId: string, emoji: string) => void;
  messageReactions?: Record<string, ReactionSummary[]>;
}

interface MessagePreviewModalProps extends PassthroughActionProps {
  isOpen: boolean;
  initialMessageId?: string | null;
  chatCode: string;
  roomUsername?: string;
  sessionToken?: string;
  /** Username of the current user — for ownership checks in the bubble. */
  username: string;
  /** Lookup function — avoids a network round-trip when the parent is already
   *  in the in-memory messages list. */
  findInLoadedMessages?: (id: string) => Message | undefined;
  onClose: () => void;
}

export default function MessagePreviewModal({
  isOpen,
  initialMessageId,
  chatCode,
  roomUsername,
  sessionToken,
  username,
  findInLoadedMessages,
  onClose,
  // passthrough action props
  currentDesign,
  themeIsDarkMode,
  modalThemeColors,
  isHost,
  spotlightUsernames,
  mutedUsernames,
  broadcastMessageId,
  viewportHeight,
  chatRoom,
  onReply,
  onPin,
  onAddToPin,
  getPinRequirements,
  onBlock,
  onUnblock,
  onUnmute,
  onSpotlightAdd,
  onSpotlightRemove,
  onRequestSignup,
  onTip,
  onSendGift,
  onThankGift,
  onToggleHighlight,
  onToggleBroadcast,
  onDelete,
  onUnpin,
  onReact,
  messageReactions,
}: MessagePreviewModalProps) {
  const [stack, setStack] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMessageById = useCallback(async (id: string, push: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const local = findInLoadedMessages?.(id);
      const msg = local ?? (await messageApi.getMessage(chatCode, id, roomUsername, sessionToken)).message;
      setStack(prev => push ? [...prev, msg] : [msg]);
    } catch (err) {
      console.error('[MessagePreview] load failed', err);
      setError('Message not available.');
    } finally {
      setLoading(false);
    }
  }, [chatCode, roomUsername, sessionToken, findInLoadedMessages]);

  // Reset stack when modal opens with a new initial target
  useEffect(() => {
    if (!isOpen) {
      setStack([]);
      setError(null);
      return;
    }
    if (initialMessageId) {
      const local = findInLoadedMessages?.(initialMessageId);
      if (local) {
        setStack([local]);
        return;
      }
      void loadMessageById(initialMessageId, false);
    }
  }, [isOpen, initialMessageId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ESC closes
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  // Re-implementation of the chain-walk handler exposed to the rendered
  // bubble. When the user taps the in-bubble reply preview, push onto stack.
  const handleChainWalk = useCallback((parentId: string) => {
    if (stack.length >= MAX_CHAIN_DEPTH) {
      setError('Reply chain too deep.');
      return;
    }
    void loadMessageById(parentId, true);
  }, [stack.length, loadMessageById]);

  if (!isOpen || typeof document === 'undefined') return null;

  const current = stack[stack.length - 1];
  const canGoBack = stack.length >= 2;

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-end sm:items-center justify-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal frame */}
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full sm:max-w-lg bg-zinc-900 sm:rounded-2xl rounded-t-2xl shadow-2xl flex flex-col max-h-[85vh] sm:max-h-[85vh] animate-slide-up"
      >
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 border-b border-zinc-800">
          {canGoBack ? (
            <button
              onClick={() => setStack(prev => prev.slice(0, -1))}
              className="flex items-center gap-1 text-sm text-zinc-300 hover:text-white"
              aria-label="Back to previous message"
            >
              <ArrowLeft size={16} />
              <span>Back</span>
            </button>
          ) : (
            <span className="text-sm text-zinc-400">
              {current?.reply_to_message ? 'Original message' : 'Message'}
            </span>
          )}
          <button onClick={onClose} className="text-zinc-400 hover:text-white" aria-label="Close">
            <X size={20} />
          </button>
        </div>

        {/* Body — scrollable */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-zinc-400">
              <Loader2 size={24} className="animate-spin" />
            </div>
          )}
          {error && !loading && (
            <div className="flex items-center justify-center py-12 text-zinc-400 text-sm">
              {error}
            </div>
          )}
          {current && !loading && !error && (
            <div className="flex">
              {/* Avatar column — same layout the timeline uses */}
              <div className="w-10 flex-shrink-0 mr-3">
                {current.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={current.avatar_url}
                    alt={current.username}
                    className={`w-10 h-10 rounded-full ${currentDesign.uiStyles?.avatarFallbackBg || 'bg-zinc-700'}`}
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-zinc-700" />
                )}
              </div>
              {/* Content column — wrap bubble in MessageActionsModal so long-press works */}
              <div className="flex-1 min-w-0">
                <MessageActionsModal
                  message={current}
                  currentUsername={username}
                  isHost={isHost}
                  themeIsDarkMode={themeIsDarkMode}
                  sessionToken={sessionToken ?? null}
                  themeColors={modalThemeColors}
                  modalStyles={currentDesign.modalStyles}
                  emojiPickerStyles={currentDesign.emojiPickerStyles}
                  giftStyles={currentDesign.giftStyles}
                  videoPlayerStyles={currentDesign.videoPlayerStyles}
                  isOutbid={false}
                  onReply={onReply}
                  onPin={onPin}
                  onAddToPin={onAddToPin}
                  getPinRequirements={getPinRequirements}
                  onBlock={onBlock}
                  onUnblock={onUnblock}
                  onUnmute={onUnmute}
                  mutedUsernames={mutedUsernames}
                  spotlightUsernames={spotlightUsernames}
                  onSpotlightAdd={onSpotlightAdd}
                  onSpotlightRemove={onSpotlightRemove}
                  onRequestSignup={onRequestSignup}
                  onTip={onTip}
                  onSendGift={onSendGift}
                  onThankGift={onThankGift}
                  onToggleHighlight={onToggleHighlight}
                  onToggleBroadcast={onToggleBroadcast}
                  broadcastMessageId={broadcastMessageId}
                  onDelete={onDelete}
                  onUnpin={onUnpin}
                  onReact={onReact}
                  reactions={messageReactions?.[current.id] || current.reactions || []}
                  chatRoom={chatRoom}
                >
                  <MessageBubbleContent
                    message={current}
                    username={username}
                    currentDesign={currentDesign}
                    spotlightUsernames={spotlightUsernames}
                    sessionToken={sessionToken ?? null}
                    broadcastMessageId={broadcastMessageId}
                    viewportHeight={viewportHeight}
                    isHostMessage={!!current.is_from_host}
                    isFirstInGroup={true}
                    isRegularMessage={!current.is_from_host && !current.is_pinned}
                    openMessagePreview={handleChainWalk}
                    unconstrainedWidth
                  />
                </MessageActionsModal>
                {/* Timestamp + reaction pills row — same as the main timeline.
                    Outside MessageActionsModal so taps on reactions don't
                    trigger the long-press sheet. */}
                <div className={`flex items-center gap-2 h-6 ${
                  current.message_type === 'gift' ? 'mt-1' : 'mt-0.5'
                }`}>
                  <span
                    className="text-[10px] opacity-60 whitespace-nowrap flex-shrink-0"
                    style={{
                      color: getTextColor(
                        current.is_from_host
                          ? currentDesign.hostTimestamp
                          : current.is_pinned
                          ? currentDesign.pinnedTimestamp
                          : current.username.toLowerCase() === username.toLowerCase()
                          ? currentDesign.myTimestamp
                          : currentDesign.regularTimestamp
                      ) || '#ffffff'
                    }}
                  >
                    {formatTimestamp(current.created_at)}
                  </span>
                  <ReactionBar
                    reactions={messageReactions?.[current.id] || current.reactions || []}
                    onReactionClick={(emoji) => onReact?.(current.id, emoji)}
                    highlightTheme={currentDesign.reactionHighlightBg ? {
                      reaction_highlight_bg: currentDesign.reactionHighlightBg,
                      reaction_highlight_border: currentDesign.reactionHighlightBorder,
                      reaction_highlight_text: currentDesign.reactionHighlightText,
                    } : undefined}
                    uiStyles={currentDesign.uiStyles}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        @keyframes slide-up {
          from { transform: translateY(20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .animate-slide-up {
          animation: slide-up 200ms cubic-bezier(0.16, 1, 0.3, 1);
        }
      `}</style>
    </div>,
    document.body,
  );
}
