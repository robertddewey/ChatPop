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
import { ArrowLeft, X, Loader2 } from 'lucide-react';
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

  // Hide entirely when stack is empty. slideIn is driven by the parent.
  if (focusStack.length === 0) return null;

  const canGoBack = focusStack.length >= 2;

  return (
    <div
      // Position absolute above the input wrapper (parent has position:relative).
      // bottom-full → panel's bottom edge sits at input's top edge, so the panel
      // floats just above the input regardless of input height. No layout shift,
      // mirroring how the long-press modal mounts.
      // No drawer chrome: the message bubble floats freely above the input on
      // the dimmed/blurred backdrop, just like the long-press preview floats
      // above the action sheet. Mode + close + back live in a small floating
      // pill above the message — keeps the "Replying to @user" status hint
      // without the heavy full-width drawer header.
      // z-[70] → above the backdrop (z-[60]) so the panel renders on top.
      className="absolute left-0 right-0 bottom-full z-[70]"
      // touch-action:none on the panel frame itself swallows drag gestures so
      // they can't bubble up and pan the document / visual viewport. The body
      // explicitly re-enables pan-y for its own internal scrolling.
      //
      // Slide-up: starts fully BELOW the input edge (calc(100% + input height))
      // and slides to translateY(0) above the input. Without the input-height
      // offset, translateY(100%) alone leaves the panel overlapping the input
      // area on first frame.
      // The --input-height CSS variable is set by the parent's ResizeObserver.
      //
      // No transition delay: backdrop and panel animate together (200ms each),
      // matching the long-press sheet's flawless feel.
      style={{
        touchAction: 'none',
        transform: slideIn
          ? 'translateY(0)'
          : 'translateY(calc(100% + var(--input-height, 80px)))',
        opacity: slideIn ? 1 : 0,
        transition: 'transform 200ms cubic-bezier(0.16, 1, 0.3, 1), opacity 200ms ease',
      }}
    >
      {/* Floating mode pill: Back? + mode label + Close, centered above the
          message. rounded-full bg with backdrop-blur so it reads as a soft
          floating chip rather than a full-width header bar. The chip itself
          has touch-action: none to block the iOS visual-viewport-pan
          fallback that body.chat-layout *'s `pan-x pan-y` would otherwise
          allow on its descendants. */}
      <div className="flex justify-center pb-2 px-4" style={{ touchAction: 'none' }}>
        <div className="flex items-center gap-1 rounded-full bg-zinc-800/95 backdrop-blur-sm shadow-lg pl-1 pr-1 py-1 text-sm font-semibold text-zinc-100 max-w-full">
          {canGoBack && (
            <button
              onClick={onBack}
              className="flex-shrink-0 p-1 rounded-full hover:bg-zinc-700/60 transition-colors"
              aria-label="Back to previous message"
            >
              <ArrowLeft size={16} />
            </button>
          )}
          <span className="px-2 truncate">Replying to message</span>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-1 rounded-full hover:bg-zinc-700/60 transition-colors"
            aria-label={isComposing ? 'Cancel reply' : 'Close'}
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Body. max-height = available space above the input minus the top
          safe area minus a breathing gap. Lets tall content (long text, big
          media) use as much vertical room as the chat area can spare while
          still leaving a gap below the URL bar / notch and above the input.
          The body still shrinks to fit short content (max-height isn't a
          forced height). Previously had a 50dvh soft cap, removed so the
          panel can use the full available space when content needs it.
          --visible-height: visualViewport.height set by page.tsx, in px.
            Tracks the actual visible area ABOVE the soft keyboard. dvh on
            iOS Safari only adjusts for browser chrome (URL bar) and does
            NOT shrink when the keyboard opens, so dvh alone wouldn't leave
            a gap when typing a reply.
          --input-height: input wrapper's offsetHeight, set by ResizeObserver
            in page.tsx.
          64px buffer = 24px top gap + 32px pill + 8px pill-to-body gap.
          touch-action: pan-y + overflow-y: auto — body scrolls internally
          when the message is tall (long text, big photo). overscroll-contain
          keeps the scroll from chaining to the page.
          The inner wrapper's `min-height: calc(100% + 1px)` is the trick
          that prevents the iOS visual-viewport-pan fallback when the
          keyboard is open. iOS Safari interprets pan-y on a non-overflowing
          element as "no scroll target" and falls through to panning the
          visual viewport (URL bar / panel / keyboard slide together).
          Forcing the body to always overflow by 1px guarantees pan-y always
          has a scroll target — even when the message content fits naturally.
          The 1px is invisible (no scrollbar shows since we hide them
          globally) and never reaches the user via overscroll because of
          overscrollBehavior: contain. */}
      <div
        className="overflow-y-auto px-4 py-3"
        style={{
          touchAction: 'pan-y',
          overscrollBehavior: 'contain',
          maxHeight: 'calc(var(--visible-height, 100dvh) - var(--input-height, 80px) - env(safe-area-inset-top, 0px) - 64px)',
        }}
      >
        <div style={{ minHeight: 'calc(100% + 1px)' }}>
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
    </div>
  );
}
