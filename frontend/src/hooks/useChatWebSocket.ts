import { useEffect, useRef, useCallback, useState } from 'react';
import type { Message, GiftNotification } from '@/lib/api';

interface ReactionEventData {
  type: 'reaction';
  message_id: string;
  action: 'add' | 'remove';
  emoji: string;
}

interface UseChatWebSocketOptions {
  chatCode: string;
  sessionToken: string | null;
  onMessage?: (message: Message) => void;
  onUserBlocked?: (message: string) => void;
  onUserKicked?: (message: string) => void;
  onBanStatusChanged?: (username: string, isBanned: boolean) => void;
  onReaction?: (data: ReactionEventData) => void;
  onMessageDeleted?: (messageId: string, pinnedMessages: Message[]) => void;
  onMessageUnpinned?: (messageId: string, pinnedMessages: Message[]) => void;
  onMessagePinned?: (message: Message, isTopPin: boolean) => void;
  onMessageHighlight?: (message: Message, isHighlight: boolean) => void;
  onBroadcastStickyUpdate?: (message: Message | null) => void;
  onGiftReceived?: (gift: GiftNotification) => void;
  onGiftQueue?: (gifts: GiftNotification[]) => void;
  onGiftAcknowledged?: (messageIds: string[]) => void;
  onBlockUpdate?: (action: 'add' | 'remove', blockedUsername: string) => void;
  onSpotlightUpdate?: (action: 'add' | 'remove', username: string) => void;
  onError?: (error: Event) => void;
  onVisibilityChange?: (isVisible: boolean) => void;
  // Reconnect-handshake hooks: the client tells the server its last_seen_id
  // on (re)connect, server responds with only the messages newer than that.
  // Avoids a full N-message refetch on every WS reconnect at scale.
  // getLastSeenId is called by the WS hook each time the socket opens; if it
  // returns a non-null id, a {type:'hello', last_seen_id} frame is sent.
  // Returning null suppresses the hello (e.g., on first connect with no
  // local messages yet — the initial loadMessages will populate everything).
  getLastSeenId?: () => string | null | undefined;
  // Server returned a delta (0..N messages strictly newer than last_seen_id).
  // Caller merges into its message list (dedupe by id).
  onBackfill?: (messages: Message[]) => void;
  // Server can't compute a delta (last_seen_id evicted from cache OR more
  // messages missed than we'll ship in one frame). Caller should fall back
  // to a full loadMessages() refetch.
  onBackfillOverflow?: () => void;
  enabled?: boolean;
}

export function useChatWebSocket({
  chatCode,
  sessionToken,
  onMessage,
  onUserBlocked,
  onUserKicked,
  onBanStatusChanged,
  onReaction,
  onMessageDeleted,
  onMessageUnpinned,
  onMessagePinned,
  onMessageHighlight,
  onBroadcastStickyUpdate,
  onGiftReceived,
  onGiftQueue,
  onGiftAcknowledged,
  onBlockUpdate,
  onSpotlightUpdate,
  onError,
  onVisibilityChange,
  getLastSeenId,
  onBackfill,
  onBackfillOverflow,
  enabled = true,
}: UseChatWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = Infinity; // Infinite reconnection attempts with polling fallback
  const RECONNECT_DELAY = 2000;

  // Heartbeat: prevents intermediaries (ngrok, load balancers, proxies) from
  // idle-closing the WebSocket. ngrok specifically times out at ~60s of
  // inactivity. 30s is a safe interval. Backend `chats/consumers.py` no-ops
  // these.
  const HEARTBEAT_INTERVAL_MS = 30000;
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Marks intentional disconnects (component unmount / explicit disconnect()
  // call) so the close handler can distinguish those from server-initiated
  // closures. Without this, a server close (even with code 1000) would be
  // treated as terminal and we'd never reconnect.
  const intentionalDisconnectRef = useRef(false);

  // Use refs for callbacks to avoid stale closures in WebSocket handlers
  const onMessageRef = useRef(onMessage);
  const onUserBlockedRef = useRef(onUserBlocked);
  const onUserKickedRef = useRef(onUserKicked);
  const onBanStatusChangedRef = useRef(onBanStatusChanged);
  const onReactionRef = useRef(onReaction);
  const onMessageDeletedRef = useRef(onMessageDeleted);
  const onMessageUnpinnedRef = useRef(onMessageUnpinned);
  const onMessagePinnedRef = useRef(onMessagePinned);
  const onMessageHighlightRef = useRef(onMessageHighlight);
  const onBroadcastStickyUpdateRef = useRef(onBroadcastStickyUpdate);
  const onGiftReceivedRef = useRef(onGiftReceived);
  const onGiftQueueRef = useRef(onGiftQueue);
  const onGiftAcknowledgedRef = useRef(onGiftAcknowledged);
  const onBlockUpdateRef = useRef(onBlockUpdate);
  const onSpotlightUpdateRef = useRef(onSpotlightUpdate);
  const onErrorRef = useRef(onError);
  const onVisibilityChangeRef = useRef(onVisibilityChange);
  const getLastSeenIdRef = useRef(getLastSeenId);
  const onBackfillRef = useRef(onBackfill);
  const onBackfillOverflowRef = useRef(onBackfillOverflow);

  // Keep refs up to date
  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onUserBlockedRef.current = onUserBlocked; }, [onUserBlocked]);
  useEffect(() => { onUserKickedRef.current = onUserKicked; }, [onUserKicked]);
  useEffect(() => { onBanStatusChangedRef.current = onBanStatusChanged; }, [onBanStatusChanged]);
  useEffect(() => { onReactionRef.current = onReaction; }, [onReaction]);
  useEffect(() => { onMessageDeletedRef.current = onMessageDeleted; }, [onMessageDeleted]);
  useEffect(() => { onMessageUnpinnedRef.current = onMessageUnpinned; }, [onMessageUnpinned]);
  useEffect(() => { onMessagePinnedRef.current = onMessagePinned; }, [onMessagePinned]);
  useEffect(() => { onMessageHighlightRef.current = onMessageHighlight; }, [onMessageHighlight]);
  useEffect(() => { onBroadcastStickyUpdateRef.current = onBroadcastStickyUpdate; }, [onBroadcastStickyUpdate]);
  useEffect(() => { onGiftReceivedRef.current = onGiftReceived; }, [onGiftReceived]);
  useEffect(() => { onGiftQueueRef.current = onGiftQueue; }, [onGiftQueue]);
  useEffect(() => { onGiftAcknowledgedRef.current = onGiftAcknowledged; }, [onGiftAcknowledged]);
  useEffect(() => { onBlockUpdateRef.current = onBlockUpdate; }, [onBlockUpdate]);
  useEffect(() => { onSpotlightUpdateRef.current = onSpotlightUpdate; }, [onSpotlightUpdate]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onVisibilityChangeRef.current = onVisibilityChange; }, [onVisibilityChange]);
  useEffect(() => { getLastSeenIdRef.current = getLastSeenId; }, [getLastSeenId]);
  useEffect(() => { onBackfillRef.current = onBackfill; }, [onBackfill]);
  useEffect(() => { onBackfillOverflowRef.current = onBackfillOverflow; }, [onBackfillOverflow]);

  const connect = useCallback(() => {
    if (!enabled || ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setIsConnecting(true);

    // Connect to frontend server which proxies WebSocket to backend
    // This avoids SSL certificate issues when accessing from network IP
    const isSecure = window.location.protocol === 'https:';
    const wsProtocol = isSecure ? 'wss:' : 'ws:';
    const wsHost = window.location.hostname;
    const wsPort = window.location.port || (isSecure ? '443' : '80');
    let wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/chat/${chatCode}/`;
    if (sessionToken) {
      wsUrl += `?session_token=${sessionToken}`;
    }

    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      setIsConnected(true);
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0;

      // Reconnect handshake — if the caller provided a last_seen_id, ask
      // the server for any messages newer than it. Skipped on first connect
      // (when there's nothing to compare against) — the regular initial
      // loadMessages() handles that case. The server's reply lands as a
      // 'backfill' or 'backfill_overflow' event below.
      try {
        const lastSeenId = getLastSeenIdRef.current?.();
        if (lastSeenId) {
          socket.send(JSON.stringify({ type: 'hello', last_seen_id: lastSeenId }));
        }
      } catch {
        // Non-fatal — if hello fails the user just doesn't get the delta;
        // the next visibility-return loadMessages() will reconcile.
      }

      // Start heartbeat. Sends a tiny ping frame every 30s on the same socket
      // closure (the variable `socket`) — if a reconnect happens, that new
      // socket gets its own onopen + its own heartbeat.
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) {
          try {
            socket.send(JSON.stringify({ type: 'ping' }));
          } catch {
            // If sending fails, the socket will fire onclose; reconnect logic
            // there will take over.
          }
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle error messages
        if (data.error) {
          console.error('[WebSocket] Error:', data.error);
          return;
        }

        // Reconnect handshake response — server returned the delta of
        // messages we missed since `last_seen_id`. May be empty.
        if (data.type === 'backfill') {
          if (onBackfillRef.current) {
            onBackfillRef.current(data.messages || []);
          }
          return;
        }

        // Reconnect handshake overflow — server can't compute a delta
        // (last_seen_id evicted, or > BACKFILL_LIMIT messages missed).
        // Caller falls back to a full loadMessages().
        if (data.type === 'backfill_overflow') {
          if (onBackfillOverflowRef.current) {
            onBackfillOverflowRef.current();
          }
          return;
        }

        // Handle user_blocked event
        if (data.type === 'user_blocked') {
          console.log('[WebSocket] User blocked event received:', data.message);
          if (onUserBlockedRef.current) {
            onUserBlockedRef.current(data.message);
          }
          return;
        }

        // Handle user_kicked event (user was kicked/banned from chat)
        if (data.type === 'kicked') {
          console.log('[WebSocket] User kicked event received:', data.message);
          if (onUserKickedRef.current) {
            onUserKickedRef.current(data.message);
          }
          return;
        }

        // Handle ban status change (update badges for all clients)
        if (data.type === 'ban_status_changed') {
          if (onBanStatusChangedRef.current) {
            onBanStatusChangedRef.current(data.username, data.is_banned);
          }
          return;
        }

        // Handle reaction events
        if (data.type === 'reaction') {
          console.log('[WebSocket] Reaction event received:', data);
          if (onReactionRef.current) {
            onReactionRef.current(data);
          }
          return;
        }

        // Handle message deletion events
        if (data.type === 'message_deleted') {
          console.log('[WebSocket] Message deleted event received:', data.message_id);
          if (onMessageDeletedRef.current) {
            onMessageDeletedRef.current(data.message_id, data.pinned_messages || []);
          }
          return;
        }

        // Handle message unpinned events
        if (data.type === 'message_unpinned') {
          console.log('[WebSocket] Message unpinned event received:', data.message_id);
          if (onMessageUnpinnedRef.current) {
            onMessageUnpinnedRef.current(data.message_id, data.pinned_messages || []);
          }
          return;
        }

        // Handle message pinned events
        if (data.type === 'message_pinned') {
          console.log('[WebSocket] Message pinned event received:', data.message);
          if (onMessagePinnedRef.current) {
            onMessagePinnedRef.current(data.message, data.is_top_pin);
          }
          return;
        }

        // Handle message highlight events
        if (data.type === 'message_highlight') {
          if (onMessageHighlightRef.current) {
            onMessageHighlightRef.current(data.message, data.is_highlight);
          }
          return;
        }

        // Handle broadcast sticky update events
        if (data.type === 'broadcast_sticky_update') {
          if (onBroadcastStickyUpdateRef.current) {
            onBroadcastStickyUpdateRef.current(data.message || null);
          }
          return;
        }

        // Handle gift received notification (popup for recipient)
        if (data.type === 'gift_received') {
          if (onGiftReceivedRef.current) {
            onGiftReceivedRef.current(data.gift);
          }
          return;
        }

        // Handle gift queue (unacked gifts on reconnect)
        if (data.type === 'gift_queue') {
          if (onGiftQueueRef.current) {
            onGiftQueueRef.current(data.gifts);
          }
          return;
        }

        // Handle block_update events (mute/unmute sync)
        if (data.type === 'block_update') {
          if (onBlockUpdateRef.current) {
            onBlockUpdateRef.current(data.action, data.blocked_username);
          }
          return;
        }

        // Handle spotlight_update events (host added/removed someone from spotlight)
        if (data.type === 'spotlight_update') {
          if (onSpotlightUpdateRef.current) {
            onSpotlightUpdateRef.current(data.action, data.username);
          }
          return;
        }

        // Handle gift acknowledged events
        if (data.type === 'gift_acknowledged') {
          if (onGiftAcknowledgedRef.current) {
            onGiftAcknowledgedRef.current(data.message_ids);
          }
          return;
        }

        // Handle chat messages (has an id field)
        if (onMessageRef.current && data.id) {
          onMessageRef.current(data as Message);
        }
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };

    socket.onerror = (error) => {
      console.warn('[WebSocket] Connection error (will reconnect)');
      if (onErrorRef.current) {
        onErrorRef.current(error);
      }
    };

    socket.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason);
      // Only update state if this is still the active socket (not replaced by a new connection)
      if (ws.current !== socket) return;
      setIsConnected(false);
      setIsConnecting(false);
      ws.current = null;

      // Stop heartbeat for the now-closed socket; the next connect() will
      // start a fresh one in onopen.
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }

      // Reconnect on every server-side close. The previous logic skipped
      // codes 1000 (normal close) and 1001 (going away), but ngrok and
      // many production proxies send 1000 on idle timeout — that's exactly
      // when we want to reconnect, not give up. The intentional-disconnect
      // ref distinguishes "we initiated this" from "the network did".
      // Backend-initiated 4xxx codes (auth fail, ban) intentionally don't
      // reconnect — those have an unrecoverable cause.
      const isAuthOrBanClose = event.code >= 4000 && event.code <= 4999;
      const wasIntentional = intentionalDisconnectRef.current;
      intentionalDisconnectRef.current = false; // reset for the next cycle

      if (
        enabled &&
        !wasIntentional &&
        !isAuthOrBanClose &&
        reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS
      ) {
        reconnectAttemptsRef.current += 1;
        console.log(
          `[WebSocket] Reconnecting (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})...`
        );

        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, RECONNECT_DELAY);
      }
    };

    ws.current = socket;
  }, [chatCode, sessionToken, enabled]); // Callbacks use refs, no need to include them

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }

    if (ws.current) {
      // Mark as intentional so the close handler doesn't trigger reconnect.
      intentionalDisconnectRef.current = true;
      ws.current.close(1000, 'Client disconnect');
      ws.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
    reconnectAttemptsRef.current = 0;
  }, []);

  const sendMessage = useCallback(
    (message: string, replyToId?: string) => {
      if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
        throw new Error('WebSocket is not connected');
      }

      if (!sessionToken) {
        throw new Error('Session token is required');
      }

      ws.current.send(
        JSON.stringify({
          message,
          session_token: sessionToken,
          reply_to_id: replyToId,
        })
      );
    },
    [sessionToken]
  );

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, sessionToken, connect, disconnect]);

  // Handle visibility changes (mobile app switching, tab switching)
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      const isVisible = document.visibilityState === 'visible';

      if (isVisible) {
        // Page became visible — reconnect if needed and notify callback.
        if (ws.current?.readyState !== WebSocket.OPEN) {
          console.log('[WebSocket] Page visible, reconnecting...');
          connect();
        }

        if (onVisibilityChangeRef.current) {
          onVisibilityChangeRef.current(true);
        }
      } else {
        // Page hidden — actively close the socket and cancel timers so the
        // backgrounded tab does no work. Mobile OSes throttle setInterval to
        // ~1/min in hidden tabs, which would let our 30s heartbeat slip past
        // ngrok's 60s idle timeout anyway. Cleaner to close ourselves and
        // reconnect on visibility-return. The intentional flag prevents
        // onclose from queueing a reconnect.
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
        if (heartbeatTimerRef.current) {
          clearInterval(heartbeatTimerRef.current);
          heartbeatTimerRef.current = null;
        }
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
          intentionalDisconnectRef.current = true;
          ws.current.close(1000, 'Tab hidden');
        }

        if (onVisibilityChangeRef.current) {
          onVisibilityChangeRef.current(false);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [enabled, connect]);

  const sendRawMessage = useCallback(
    (data: object) => {
      if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
        throw new Error('WebSocket is not connected');
      }

      if (!sessionToken) {
        throw new Error('Session token is required');
      }

      ws.current.send(
        JSON.stringify({
          ...data,
          session_token: sessionToken,
        })
      );
    },
    [sessionToken]
  );

  return {
    isConnected,
    isConnecting,
    sendMessage,
    sendRawMessage,
    reconnect: connect,
    disconnect,
  };
}
