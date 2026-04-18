'use client';

/**
 * FocusMessagePanel
 *
 * The unified "show me a message" panel that docks above the chat input.
 * Replaces both the old reply-preview popup AND the old compact reply-target
 * bar. One mental model: the panel above your input shows the message you're
 * currently focused on.
 *
 * Two modes:
 *   - preview: you tapped a reply preview / sticky jump. You can long-press,
 *     react, chain-walk, or dismiss. Header reads "Viewing message".
 *   - compose: a reply is armed (replyingTo is set on the parent). The chat
 *     input below will send to this message. Header reads "Replying to".
 *
 * Both modes render the SAME `<MessageActionsModal><MessageBubbleContent />`
 * pattern as the timeline, so long-press, media players, theming, and
 * reactions all match.
 *
 * Chain-walking: tapping the in-bubble reply preview pushes onto a stack
 * (max depth 20). Back button shown at depth ≥ 2. Closing the panel
 * (X / send) clears the stack.
 *
 * Body is internally scrollable for long content; the panel has a fixed
 * max-height so it doesn't eat the entire viewport.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { ChatRoom, Message, ReactionSummary, messageApi } from '@/lib/api';
import MessageActionsModal from './MessageActionsModal';
import MessageBubbleContent from './MessageBubbleContent';
import ReactionBar from './ReactionBar';
import { formatTimestamp } from '@/lib/formatTimestamp';
import { getTextColor } from '@/lib/themeColors';

const MAX_CHAIN_DEPTH = 20;

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
  /** Reports when the in-bubble long-press sheet opens/closes. The page-level
   *  consumer uses this to suppress the panel's own backdrop while the sheet
   *  is up — avoids stacking two `backdrop-filter: blur` layers, which is
   *  expensive on Android Chrome. */
  onMessageActionsOpenChange?: (open: boolean) => void;
}

interface FocusMessagePanelProps extends PassthroughActionProps {
  /** Stack of message IDs the user is walking back through. Top of stack
   *  is the message currently displayed. Empty = panel hidden. */
  focusStack: string[];
  /** True when a reply is armed for the top-of-stack message. Drives the
   *  header label and visual treatment. */
  isComposing: boolean;
  chatCode: string;
  roomUsername?: string;
  sessionToken?: string;
  username: string;
  /** Look up a message in the in-memory list to avoid a network round-trip
   *  when the parent is already loaded. */
  findInLoadedMessages?: (id: string) => Message | undefined;
  /** Push a message ID onto the stack (chain-walk). */
  onChainWalk: (messageId: string) => void;
  /** Pop one off the stack (back button). */
  onBack: () => void;
  /** Close the panel entirely (X button). Should also cancel any armed reply. */
  onClose: () => void;
  /** Drives the slide-up + fade-in animation. The parent owns this so the
   *  backdrop (rendered separately by the parent) and the panel itself can
   *  animate from the same single source of truth — no two-component RAF
   *  drift on slow devices. Backdrop and panel animate together with the
   *  same duration (no delay), matching the long-press sheet pattern. */
  slideIn: boolean;
}

export default function FocusMessagePanel({
  focusStack,
  isComposing,
  chatCode,
  roomUsername,
  sessionToken,
  username,
  findInLoadedMessages,
  onChainWalk,
  onBack,
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
  onMessageActionsOpenChange,
  slideIn,
}: FocusMessagePanelProps) {
  const [fetched, setFetched] = useState<Record<string, Message>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentId = focusStack[focusStack.length - 1] ?? null;
  // Find the current message — first try in-memory, then fetched cache.
  const current: Message | null = currentId
    ? findInLoadedMessages?.(currentId) ?? fetched[currentId] ?? null
    : null;

  // Fetch any focus-stack ID we don't yet have.
  useEffect(() => {
    if (!currentId) return;
    if (current) return; // already have it
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const { message } = await messageApi.getMessage(chatCode, currentId, roomUsername, sessionToken);
        if (!cancelled) setFetched(prev => ({ ...prev, [message.id]: message }));
      } catch (err) {
        console.error('[FocusMessagePanel] load failed', err);
        if (!cancelled) setError('Message not available.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [currentId, current, chatCode, roomUsername, sessionToken]);

  // Chain-walk handler with depth guard.
  const handleChainWalk = useCallback((parentId: string) => {
    if (focusStack.length >= MAX_CHAIN_DEPTH) {
      setError('Reply chain too deep.');
      return;
    }
    onChainWalk(parentId);
  }, [focusStack.length, onChainWalk]);

  // Hide entirely when stack is empty. slideIn is driven by the parent.
  if (focusStack.length === 0) return null;

  const canGoBack = focusStack.length >= 2;

  return (
    <div
      className="absolute left-0 right-0 bottom-full z-[70]"
      style={{
        transform: slideIn ? 'translateY(0)' : 'translateY(calc(100% + var(--input-height, 80px)))',
        opacity: slideIn ? 1 : 0,
        transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease',
      }}
    >
      {/* Back pill — only shown when chain-walking (depth ≥ 2). */}
      {canGoBack && (
        <div className="flex justify-start pb-2 px-4">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 rounded-full bg-zinc-800/95 backdrop-blur-sm shadow-lg pl-2.5 pr-3 py-1.5 text-sm font-semibold text-zinc-100 transition-colors hover:bg-zinc-700/80"
            aria-label="Back to previous message"
          >
            <ArrowLeft size={16} />
            <span>Back</span>
          </button>
        </div>
      )}

      {/* Body. overflow: hidden — swipe-down-to-dismiss on the outer
          container takes priority over internal scrolling. Tall content is
          clipped; user can long-press the message to see it in full.
          max-height preserves a gap between the panel top and the safe area
          when content is tall + keyboard is open. */}
      <div
        className="px-4 py-3"
        style={{
          overflow: 'hidden',
          maxHeight: 'calc(var(--visible-height, 100dvh) - var(--input-height, 80px) - env(safe-area-inset-top, 0px) - 48px)',
        }}
      >
        {loading && (
          <div className="flex items-center justify-center py-8 text-zinc-400">
            <Loader2 size={20} className="animate-spin" />
          </div>
        )}
        {error && !loading && (
          <div className="flex items-center justify-center py-8 text-zinc-400 text-sm">
            {error}
          </div>
        )}
        {current && !loading && !error && (
          <div className="flex">
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
            <div className="flex-1 min-w-0">
              <MessageActionsModal
                message={current}
                currentUsername={username}
                isHost={isHost}
                themeIsDarkMode={themeIsDarkMode}
                currentDesign={currentDesign}
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
                onOpenChange={onMessageActionsOpenChange}
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
              {/* Timestamp + reactions row — same as the timeline. */}
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
  );
}
