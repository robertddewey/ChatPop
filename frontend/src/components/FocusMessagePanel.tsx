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
 *     react, chain-walk, or dismiss. Header reads "Original message".
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
import { ArrowLeft, X, Loader2, Reply } from 'lucide-react';
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
}: FocusMessagePanelProps) {
  // Local cache of fetched messages — keyed by ID. Populated on demand for
  // any focus-stack ID not in the in-memory list.
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

  // Slide-in animation. Mirrors MessageActionsModal: render initial off-screen
  // state on the first frame, then RAF×2 to flip to the on-screen state so
  // the browser commits the start position before applying the transition.
  // Without the double-RAF, the browser may collapse start+end into a
  // single layout pass and the transition won't actually animate.
  const [slideIn, setSlideIn] = useState(false);
  const visible = focusStack.length > 0;
  useEffect(() => {
    if (!visible) {
      setSlideIn(false);
      return;
    }
    const raf1 = requestAnimationFrame(() => {
      requestAnimationFrame(() => setSlideIn(true));
    });
    return () => cancelAnimationFrame(raf1);
  }, [visible]);

  // Hide entirely when stack is empty.
  if (!visible) return null;

  const canGoBack = focusStack.length >= 2;

  return (
    <div
      className="flex-shrink-0 border-t border-zinc-800 bg-zinc-900 shadow-[0_-4px_12px_rgba(0,0,0,0.3)]"
      // touch-action:none on the panel frame itself swallows drag gestures so
      // they can't bubble up and pan the document / visual viewport. The body
      // explicitly re-enables pan-y for its own internal scrolling. Without
      // this, dragging the panel header (which has no scrollable target under
      // it) caused iOS Safari / Android Chrome to slide the panel because
      // the inherited `touch-action: pan-x pan-y` from body.chat-layout *
      // told the browser "this surface is pannable."
      // transform/opacity: slide-up + fade-in on mount so the panel matches
      // the long-press sheet's reveal pattern instead of popping in.
      style={{
        touchAction: 'none',
        transform: slideIn ? 'translateY(0)' : 'translateY(100%)',
        opacity: slideIn ? 1 : 0,
        transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease',
      }}
    >
      {/* Header: back / mode label / close. Compose mode gets a Reply icon
          so it's visually distinct from preview mode.
          Back button styling matches the chat header's back button
          (icon-only, p-1.5 rounded-lg, currentDesign.headerTitle color)
          for consistency. Mode label uses the same font weight + color
          family as the chat header title, just one size down. */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800/60">
        {canGoBack ? (
          <button
            onClick={onBack}
            className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle || 'text-zinc-100'}`}
            aria-label="Back to previous message"
          >
            <ArrowLeft size={18} />
          </button>
        ) : (
          <span className={`flex items-center gap-1.5 text-sm font-semibold ${currentDesign.headerTitle || 'text-zinc-100'}`}>
            {isComposing && <Reply size={14} />}
            <span>{isComposing ? 'Replying to' : 'Original message'}</span>
          </span>
        )}
        <button
          onClick={onClose}
          className={`flex-shrink-0 p-1.5 rounded-lg transition-colors ${currentDesign.headerTitle || 'text-zinc-100'}`}
          aria-label={isComposing ? 'Cancel reply' : 'Close'}
        >
          <X size={18} />
        </button>
      </div>

      {/* Body. max-h uses dvh (dynamic viewport height) so the panel shrinks
          when the mobile keyboard opens — vh would stay at the full viewport
          and the panel would dominate the visible area above the keyboard.
          Falls back to vh on browsers without dvh support (pre-iOS-15.4).
          touch-action: pan-y re-enables vertical scroll inside the body
          (the panel frame above sets touch-action: none). overscroll-contain
          stops the body's bottom/top bounce from bubbling up. */}
      <div
        className="overflow-y-auto max-h-[40dvh] sm:max-h-[50dvh] px-3 py-3"
        style={{ touchAction: 'pan-y', overscrollBehavior: 'contain' }}
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
