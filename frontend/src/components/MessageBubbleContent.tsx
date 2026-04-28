'use client';

/**
 * MessageBubbleContent
 *
 * The actual rendered chat bubble — username row, reply preview, gift card,
 * media (voice/photo/video), and text content. Extracted from MainChatView
 * so the reply-preview popup can render the exact same bubble.
 *
 * Wrap this in `<MessageActionsModal>` to get long-press behavior. The
 * timeline does this in MainChatView; the docked focus panel does it in
 * FocusMessagePanel.
 *
 * This component is presentational. It does NOT manage scroll, pagination,
 * or modal state. Its only side effect is calling `openMessagePreview` when
 * the user taps the in-bubble reply preview (chain-walk).
 */

import React from 'react';
import { Spotlight, BadgeCheck, HatGlasses, Crown, Reply, Pin, Heart, Star, Megaphone, Mic, ImageIcon, Video } from 'lucide-react';
import { Message } from '@/lib/api';
import { getIconColor, getTextColor } from '@/lib/themeColors';
import { YouPill, HostPill, SpotlightPill, BannedPill } from './MessagePills';
import VoiceMessagePlayer from './VoiceMessagePlayer';
import PhotoMessage from './PhotoMessage';
import VideoMessage from './VideoMessage';

interface MessageBubbleContentProps {
  message: Message;
  /** Current user's username (for "you" pill, ownership styling). */
  username: string;
  /** Theme/design object — Tailwind class strings sourced from the database. */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  currentDesign: Record<string, any>;
  /** Set of usernames flagged as spotlighted in this chat. */
  spotlightUsernames?: Set<string>;
  /** Session token for authenticated media URLs (voice/photo/video). */
  sessionToken: string | null;
  /** ID of the current broadcast message — shows megaphone icon when matched. */
  broadcastMessageId?: string | null;
  /** Viewport height for responsive media sizing. Optional — falls back to fixed cap. */
  viewportHeight?: number;
  /** Whether this message was sent by the chat host. */
  isHostMessage: boolean;
  /** Whether this is the first message in a thread group (controls username header). */
  isFirstInGroup: boolean;
  /** Whether this is a regular (non-host, non-pinned) message. */
  isRegularMessage: boolean;
  /** Open the reply preview popup for a message ID (used by chain-walk). */
  openMessagePreview: (messageId: string) => void;
  /** When true, strip `max-w-[...]` tokens from bubble + gift-card class
   *  strings so the bubble fills its container. The timeline applies the
   *  width constraint to leave room for action icons; the popup has no
   *  such icons and benefits from full width. */
  unconstrainedWidth?: boolean;
}

/** Remove every `max-w-[...]` (Tailwind arbitrary max-width) token from a
 *  Tailwind class string. Used to un-cap bubbles in the preview popup. */
function stripMaxWidth(classString: string | undefined): string | undefined {
  if (!classString) return classString;
  return classString
    .split(' ')
    .filter(c => !c.startsWith('max-w-['))
    .join(' ');
}

export default function MessageBubbleContent({
  message,
  username,
  currentDesign,
  spotlightUsernames,
  sessionToken,
  broadcastMessageId,
  viewportHeight,
  isHostMessage,
  isFirstInGroup,
  isRegularMessage,
  openMessagePreview,
  unconstrainedWidth = false,
}: MessageBubbleContentProps) {
  return (
    <>
      {/* Username header for first regular message in thread */}
      {isRegularMessage && isFirstInGroup && (
        <div className="mb-1">
          <div className="flex items-center gap-1">
            <span
              className={(() => {
                const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                const isSpotlight = !isMyMessage && spotlightUsernames?.has(message.username);
                return isMyMessage
                  ? currentDesign.myUsername
                  : isSpotlight
                  ? (currentDesign.hostUsername || 'text-sm font-semibold')
                  : currentDesign.regularUsername;
              })() || 'text-sm font-semibold'}
              style={{
                color: (() => {
                  const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                  const isSpotlight = !isMyMessage && spotlightUsernames?.has(message.username);
                  if (isMyMessage) return getTextColor(currentDesign.myUsername) || '#ffffff';
                  if (isSpotlight) return getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff';
                  return getTextColor(currentDesign.regularUsername) || '#ffffff';
                })()
              }}
            >
              {message.username}
            </span>
            {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
            {spotlightUsernames?.has(message.username) && (
              <>
                <SpotlightPill color={getIconColor(currentDesign.spotlightIconColor) || '#facc15'} />
                <Spotlight size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.spotlightIconColor) || '#facc15' }} />
              </>
            )}
            {message.username_is_reserved ? (
              <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6' }} />
            ) : (
              <HatGlasses size={14} style={{ color: '#ef4444' }} />
            )}
            {message.is_banned && <BannedPill />}
          </div>
        </div>
      )}
      {/* Host message header - OUTSIDE bubble */}
      {isHostMessage && (
        <div className="mb-1">
          <div className="flex items-center gap-1">
            <span
              className={(() => {
                const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                return isMyMessage
                  ? (currentDesign.myHostUsername || currentDesign.hostUsername || 'text-sm font-semibold')
                  : (currentDesign.hostUsername || 'text-sm font-semibold');
              })()}
              style={{
                color: message.username.toLowerCase() === username.toLowerCase()
                  ? getTextColor(currentDesign.myHostUsername) || '#ef4444'
                  : getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff'
              }}
            >
              {message.username}
            </span>
            {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
            {message.username.toLowerCase() !== username.toLowerCase() && <HostPill color={getIconColor(currentDesign.crownIconColor) || '#2dd4bf'} />}
            <Crown size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
            {message.username_is_reserved ? (
              <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6' }} />
            ) : (
              <HatGlasses size={14} style={{ color: '#ef4444' }} />
            )}
            {message.is_banned && <BannedPill />}
          </div>
        </div>
      )}

      {/* Pinned message header - OUTSIDE bubble */}
      {message.is_pinned && !isHostMessage && (
        <div className="mb-1">
          <div className="flex items-center gap-1">
            <span
              className={(() => {
                const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                const isSpotlight = !isMyMessage && spotlightUsernames?.has(message.username);
                return isMyMessage
                  ? currentDesign.myUsername
                  : isSpotlight
                  ? (currentDesign.hostUsername || 'text-sm font-semibold')
                  : currentDesign.pinnedUsername;
              })() || 'text-sm font-semibold'}
              style={{
                color: (() => {
                  const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
                  const isSpotlight = !isMyMessage && spotlightUsernames?.has(message.username);
                  if (isMyMessage) return getTextColor(currentDesign.myUsername) || '#ffffff';
                  if (isSpotlight) return getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff';
                  return getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff';
                })()
              }}
            >
              {message.username}
            </span>
            {message.username.toLowerCase() === username.toLowerCase() && <YouPill className={currentDesign.inputStyles?.youPill} />}
            {spotlightUsernames?.has(message.username) && (
              <>
                <SpotlightPill color={getIconColor(currentDesign.spotlightIconColor) || '#facc15'} />
                <Spotlight size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.spotlightIconColor) || '#facc15' }} />
              </>
            )}
            {message.username_is_reserved ? (
              <BadgeCheck size={14} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6' }} />
            ) : (
              <HatGlasses size={14} style={{ color: '#ef4444' }} />
            )}
            {message.is_banned && <BannedPill />}
          </div>
        </div>
      )}

      {/* Gift message card - special rendering */}
      {message.message_type === 'gift' ? (
        (() => {
          // Parse "sent ☕ Coffee ($1) to @user"
          const giftMatch = message.content.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
          const emoji = giftMatch ? giftMatch[1] : '🎁';
          const giftName = giftMatch ? giftMatch[2] : '';
          const price = giftMatch ? giftMatch[3] : '';
          const recipient = giftMatch ? giftMatch[4] : '';
          const isForMe = recipient.toLowerCase() === username.toLowerCase();
          return (
            <div className={`relative rounded-xl px-3 py-2.5 flex items-center gap-2.5 ${
              unconstrainedWidth ? '' : 'max-w-[calc(100%-2.5%-5rem+5px)]'
            } ${
              isForMe
                ? currentDesign.giftStyles?.cardBgForMe || 'bg-purple-950/50 border border-purple-500/50'
                : message.is_pinned
                ? 'bg-purple-950/50 border border-purple-500/50'
                : currentDesign.giftStyles?.cardBg || 'bg-zinc-800/80 border border-zinc-700'
            }`}>
              {(message.is_pinned || message.is_gift_acknowledged || message.is_highlight || message.id === broadcastMessageId) && (
                <div className="absolute -top-2.5 -right-2 z-10 flex flex-row-reverse items-center gap-0.5">
                  {message.is_pinned && (
                    <span className="animate-wobble-b drop-shadow-md">
                      <Pin size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
                    </span>
                  )}
                  {message.is_gift_acknowledged && (
                    <span className="animate-wobble-a drop-shadow-md" title="Thanked">
                      <Heart size={14} fill="currentColor" style={{ color: '#ef4444' }} />
                    </span>
                  )}
                  {message.is_highlight && (
                    <span className="animate-wobble-a drop-shadow-md">
                      <Star size={14} fill="currentColor" style={{ color: '#facc15' }} />
                    </span>
                  )}
                  {message.id === broadcastMessageId && (
                    <span className="animate-wobble-a drop-shadow-md">
                      <Megaphone size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.highlightIconColor) || '#60a5fa' }} />
                    </span>
                  )}
                </div>
              )}
              {price && (
                <span className={`absolute top-1.5 right-2 text-[8px] font-medium px-1 py-0.5 rounded-full ${
                  currentDesign.giftStyles?.priceBadge || 'bg-cyan-900/50 text-cyan-400'
                }`}>{price}</span>
              )}
              <div className={`text-3xl flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center animate-gift-breath ${
                currentDesign.giftStyles?.emojiContainer || 'bg-zinc-700/80'
              }`}>
                {emoji}
              </div>
              <div className="min-w-0 -mt-0.5">
                <div className="flex items-center gap-1.5">
                  <span className={`text-base font-semibold leading-tight ${currentDesign.giftStyles?.nameText || 'text-white'}`}>{giftName || message.content}</span>
                </div>
                {recipient && (
                  <div className={`text-xs mt-0.5 ${currentDesign.giftStyles?.toPrefix || 'text-zinc-400'}`}>
                    to <span className={`font-semibold ${
                      isForMe
                        ? (currentDesign.giftStyles?.recipientTextForMe || 'text-purple-400')
                        : (currentDesign.giftStyles?.recipientText || 'text-zinc-300')
                    }`}>@{recipient}</span>
                    {isForMe && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                  </div>
                )}
              </div>
            </div>
          );
        })()
      ) : (
      /* Message bubble */
      <div
        className={(() => {
          const isMyMessage = message.username.toLowerCase() === username.toLowerCase();
          const isSpotlightBubble =
            !isHostMessage &&
            !message.is_pinned &&
            spotlightUsernames?.has(message.username);
          const rawStyle = isHostMessage
            ? currentDesign.hostMessage + ' flex-1'
            : message.is_pinned
            ? currentDesign.pinnedMessage
            : isSpotlightBubble
            ? currentDesign.spotlightMessage
            : isMyMessage
            ? currentDesign.myMessage
            : currentDesign.regularMessage;
          // Theme bubble classes embed `max-w-[...]` to leave room for the
          // timeline's action icons. Strip that in the popup so the bubble
          // fills the modal width.
          const selectedStyle = unconstrainedWidth ? stripMaxWidth(rawStyle) : rawStyle;

          // Add extra margin for media-only messages (no text caption)
          const hasMedia = message.voice_url || message.photo_url || message.video_url;
          const hasCaption = message.content && message.content.trim().length > 0;
          const isMediaOnly = hasMedia && !hasCaption;
          const base = isMediaOnly ? `${selectedStyle} mt-2` : selectedStyle;
          return (message.is_pinned || message.is_highlight || message.id === broadcastMessageId) ? `${base} relative` : base;
        })()}
      >
        {/* Status icons on corner of messages */}
        {(message.is_pinned || message.is_highlight || message.id === broadcastMessageId) && (
          <div className="absolute -top-2 -right-2 z-10 flex flex-row-reverse items-center gap-0.5">
            {message.is_pinned && (
              <span className="animate-wobble-b drop-shadow-md">
                <Pin size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.pinIconColor) || '#fbbf24' }} />
              </span>
            )}
            {message.is_highlight && (
              <span className="animate-wobble-a drop-shadow-md">
                <Star size={14} fill="currentColor" style={{ color: '#facc15' }} />
              </span>
            )}
            {message.id === broadcastMessageId && (
              <span className="animate-wobble-a drop-shadow-md">
                <Megaphone size={14} fill="currentColor" style={{ color: getIconColor(currentDesign.highlightIconColor) || '#60a5fa' }} />
              </span>
            )}
          </div>
        )}

        {/* Reply context preview */}
        {message.reply_to_message && (
          <div
            className={`mb-2 p-2 rounded-lg cursor-pointer transition-colors ${
              message.is_pinned
                ? currentDesign.uiStyles?.replyContextPinned || 'bg-white/10 border border-purple-500/30 hover:bg-white/15'
                : (isHostMessage || (!isHostMessage && spotlightUsernames?.has(message.username)))
                ? currentDesign.uiStyles?.replyContextHighlighted || 'bg-yellow-950/40 border border-yellow-900/40 hover:bg-yellow-950/60'
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.uiStyles?.replyContextOwn || 'bg-white/10 border border-white/10 hover:bg-white/15'
                : currentDesign.uiStyles?.replyContextOther || 'bg-white/10 border border-zinc-600 hover:bg-white/15'
            }`}
            onClick={() => openMessagePreview(message.reply_to_message!.id)}
          >
            <div className="flex items-center gap-1 mb-0.5">
              <Reply className={`w-3 h-3 flex-shrink-0 ${currentDesign.uiStyles?.replyIconColor || 'text-gray-300'}`} />
              <span
                className="text-xs font-semibold"
                style={{
                  color: message.reply_to_message.username.toLowerCase() === username.toLowerCase()
                    ? (getTextColor(currentDesign.myUsername) || '#ef4444')
                    : message.reply_to_message.is_from_host
                      ? (getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff')
                      : spotlightUsernames?.has(message.reply_to_message.username)
                        ? (getTextColor(currentDesign.hostUsername) || getTextColor(currentDesign.hostText) || '#ffffff')
                        : message.reply_to_message.is_pinned
                          ? (getTextColor(currentDesign.pinnedUsername) || getTextColor(currentDesign.pinnedText) || '#ffffff')
                          : (getTextColor(currentDesign.regularUsername) || '#ffffff')
                }}
              >
                {message.reply_to_message.username}
              </span>
              {message.reply_to_message.username_is_reserved ? (
                <BadgeCheck size={12} style={{ color: getIconColor(currentDesign.badgeIconColor) || '#3b82f6' }} />
              ) : (
                <HatGlasses size={12} style={{ color: '#ef4444' }} />
              )}
              {message.reply_to_message.is_from_host && (
                <Crown size={12} fill="currentColor" style={{ color: getIconColor(currentDesign.crownIconColor) || '#2dd4bf' }} />
              )}
              {!message.reply_to_message.is_from_host && spotlightUsernames?.has(message.reply_to_message.username) && (
                <Spotlight size={12} fill="currentColor" style={{ color: getIconColor(currentDesign.spotlightIconColor) || '#facc15' }} />
              )}
            </div>
            {(() => {
              const parent = message.reply_to_message!;
              const c = parent.content;
              const isGift = parent.message_type === 'gift' || c.match(/^sent\s+\S+\s+.+?\s+\(\$[\d,.]+\)\s+to\s+@/);
              if (isGift) {
                const m = c.match(/sent\s+(\S+)\s+(.+?)\s+\((\$[\d,.]+)\)\s+to\s+@(\S+)/);
                const emoji = m ? m[1] : '🎁';
                const recipient = m ? m[4] : '';
                return (
                  <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 mt-1 text-xs ${currentDesign.uiStyles?.replyGiftBadge || 'bg-zinc-700/60 border border-zinc-600/50'}`}>
                    <span className={currentDesign.uiStyles?.replyGiftText || 'text-zinc-300'}>
                      sent {emoji} to <span className="font-semibold">@{recipient}</span>
                      {recipient.toLowerCase() === username.toLowerCase() && <span className="ml-1"><YouPill className={currentDesign.inputStyles?.youPill} /></span>}
                    </span>
                  </div>
                );
              }
              // Media-only parent: show icon + label, matching StickySection.
              const previewClass = `text-xs truncate ${currentDesign.uiStyles?.replyPreviewText || 'text-gray-300'}`;
              if (!c) {
                if (parent.has_voice) {
                  return (
                    <div className={`flex items-center gap-1.5 ${previewClass}`}>
                      <Mic size={12} style={{ opacity: 0.7 }} />
                      <span>Voice</span>
                    </div>
                  );
                }
                if (parent.has_photo) {
                  return (
                    <div className={`flex items-center gap-1.5 ${previewClass}`}>
                      <ImageIcon size={12} style={{ opacity: 0.7 }} />
                      <span>Photo</span>
                    </div>
                  );
                }
                if (parent.has_video) {
                  return (
                    <div className={`flex items-center gap-1.5 ${previewClass}`}>
                      <Video size={12} style={{ opacity: 0.7 }} />
                      <span>Video</span>
                    </div>
                  );
                }
              }
              return (
                <p className={previewClass}>
                  {c}
                </p>
              );
            })()}
          </div>
        )}

        {/* Caption text - shown above media when message has both */}
        {message.content && (message.voice_url || message.photo_url || message.video_url) && (
          <p className={`mb-2 ${
            isHostMessage
              ? currentDesign.hostText
              : message.is_pinned
              ? currentDesign.pinnedText
              : message.username.toLowerCase() === username.toLowerCase()
              ? currentDesign.myText
              : currentDesign.regularText
          }`}>
            {message.content}
          </p>
        )}

        {/* Message content + floating reaction pill */}
        <div className="relative w-fit max-w-full">
        {message.voice_url ? (
          <VoiceMessagePlayer
            // message.voice_url is already a direct CDN-signed URL when
            // S3+CloudFront are configured (cache enricher overwrites the
            // stored proxy URL on every read). When it's still a proxy
            // URL (local-storage dev or signing failure), append the
            // session_token so Daphne can validate before redirecting.
            voiceUrl={
              message.voice_url.startsWith('/api/chats/media/')
                ? `${message.voice_url}${message.voice_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`
                : message.voice_url
            }
            duration={message.voice_duration || 0}
            waveformData={message.voice_waveform || []}
            isMyMessage={message.username.toLowerCase() === username.toLowerCase()}
            voiceContainerBg={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.containerBg
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.containerBg
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.containerBg
                : currentDesign.voiceMessageStyles?.containerBg
            }
            voicePlayButton={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.playButton
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.playButton
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.playButton
                : currentDesign.voiceMessageStyles?.playButton
            }
            voicePlayIconColor={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.playIconColor
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.playIconColor
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.playIconColor
                : currentDesign.voiceMessageStyles?.playIconColor
            }
            voiceWaveformActive={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.waveformActive
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.waveformActive
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.waveformActive
                : currentDesign.voiceMessageStyles?.waveformActive
            }
            voiceWaveformInactive={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.waveformInactive
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.waveformInactive
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.waveformInactive
                : currentDesign.voiceMessageStyles?.waveformInactive
            }
            durationTextColor={
              isHostMessage
                ? currentDesign.hostVoiceMessageStyles?.durationTextColor
                : message.is_pinned
                ? currentDesign.pinnedVoiceMessageStyles?.durationTextColor
                : message.username.toLowerCase() === username.toLowerCase()
                ? currentDesign.myVoiceMessageStyles?.durationTextColor
                : currentDesign.voiceMessageStyles?.durationTextColor
            }
          />
        ) : message.photo_url ? (
          <PhotoMessage
            photoUrl={
              message.photo_url.startsWith('/api/chats/media/')
                ? `${message.photo_url}${message.photo_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`
                : message.photo_url
            }
            width={message.photo_width || 300}
            height={message.photo_height || 200}
            maxDisplayHeight={viewportHeight ? Math.min(320, Math.round(viewportHeight * 0.4)) : 320}
          />
        ) : message.video_url ? (
          <VideoMessage
            videoUrl={
              message.video_url.startsWith('/api/chats/media/')
                ? `${message.video_url}${message.video_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`
                : message.video_url
            }
            thumbnailUrl={
              message.video_thumbnail_url
                ? message.video_thumbnail_url.startsWith('/api/chats/media/')
                  ? `${message.video_thumbnail_url}${message.video_thumbnail_url.includes('?') ? '&' : '?'}session_token=${sessionToken}`
                  : message.video_thumbnail_url
                : ''
            }
            duration={message.video_duration || 0}
            width={message.video_width}
            height={message.video_height}
          />
        ) : message.content ? (
          <p className={
            isHostMessage
              ? currentDesign.hostText
              : message.is_pinned
              ? currentDesign.pinnedText
              : message.username.toLowerCase() === username.toLowerCase()
              ? currentDesign.myText
              : currentDesign.regularText
          }>
            {message.content}
          </p>
        ) : (
          <p className={`text-sm italic ${currentDesign.uiStyles?.mediaLoadingText || 'text-gray-500'}`}>
            [Media message - loading...]
          </p>
        )}
        </div>
      </div>
      )}
    </>
  );
}
