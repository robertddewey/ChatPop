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
  onMessageDeleted?: (messageId: string) => void;
  onMessagePinned?: (message: Message, isTopPin: boolean) => void;
  onMessageBroadcast?: (message: Message, isBroadcast: boolean) => void;
  onGiftReceived?: (gift: GiftNotification) => void;
  onGiftQueue?: (gifts: GiftNotification[]) => void;
  onGiftAcknowledged?: (messageIds: string[]) => void;
  onBlockUpdate?: (action: 'add' | 'remove', blockedUsername: string) => void;
  onError?: (error: Event) => void;
  onVisibilityChange?: (isVisible: boolean) => void;
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
  onMessagePinned,
  onMessageBroadcast,
  onGiftReceived,
  onGiftQueue,
  onGiftAcknowledged,
  onBlockUpdate,
  onError,
  onVisibilityChange,
  enabled = true,
}: UseChatWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = Infinity; // Infinite reconnection attempts with polling fallback
  const RECONNECT_DELAY = 2000;

  // Use refs for callbacks to avoid stale closures in WebSocket handlers
  const onMessageRef = useRef(onMessage);
  const onUserBlockedRef = useRef(onUserBlocked);
  const onUserKickedRef = useRef(onUserKicked);
  const onBanStatusChangedRef = useRef(onBanStatusChanged);
  const onReactionRef = useRef(onReaction);
  const onMessageDeletedRef = useRef(onMessageDeleted);
  const onMessagePinnedRef = useRef(onMessagePinned);
  const onMessageBroadcastRef = useRef(onMessageBroadcast);
  const onGiftReceivedRef = useRef(onGiftReceived);
  const onGiftQueueRef = useRef(onGiftQueue);
  const onGiftAcknowledgedRef = useRef(onGiftAcknowledged);
  const onBlockUpdateRef = useRef(onBlockUpdate);
  const onErrorRef = useRef(onError);
  const onVisibilityChangeRef = useRef(onVisibilityChange);

  // Keep refs up to date
  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onUserBlockedRef.current = onUserBlocked; }, [onUserBlocked]);
  useEffect(() => { onUserKickedRef.current = onUserKicked; }, [onUserKicked]);
  useEffect(() => { onBanStatusChangedRef.current = onBanStatusChanged; }, [onBanStatusChanged]);
  useEffect(() => { onReactionRef.current = onReaction; }, [onReaction]);
  useEffect(() => { onMessageDeletedRef.current = onMessageDeleted; }, [onMessageDeleted]);
  useEffect(() => { onMessagePinnedRef.current = onMessagePinned; }, [onMessagePinned]);
  useEffect(() => { onMessageBroadcastRef.current = onMessageBroadcast; }, [onMessageBroadcast]);
  useEffect(() => { onGiftReceivedRef.current = onGiftReceived; }, [onGiftReceived]);
  useEffect(() => { onGiftQueueRef.current = onGiftQueue; }, [onGiftQueue]);
  useEffect(() => { onGiftAcknowledgedRef.current = onGiftAcknowledged; }, [onGiftAcknowledged]);
  useEffect(() => { onBlockUpdateRef.current = onBlockUpdate; }, [onBlockUpdate]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onVisibilityChangeRef.current = onVisibilityChange; }, [onVisibilityChange]);

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
    };

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle error messages
        if (data.error) {
          console.error('[WebSocket] Error:', data.error);
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
            onMessageDeletedRef.current(data.message_id);
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

        // Handle message broadcast events
        if (data.type === 'message_broadcast') {
          if (onMessageBroadcastRef.current) {
            onMessageBroadcastRef.current(data.message, data.is_broadcast);
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

      // Attempt to reconnect if not a normal closure and we haven't exceeded max attempts
      if (
        enabled &&
        event.code !== 1000 && // Normal closure
        event.code !== 1001 && // Going away
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

    if (ws.current) {
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
        // Page became visible - reconnect if needed and notify callback
        if (ws.current?.readyState !== WebSocket.OPEN) {
          console.log('[WebSocket] Page visible, reconnecting...');
          connect();
        }

        // Notify callback so page can refetch data
        if (onVisibilityChangeRef.current) {
          onVisibilityChangeRef.current(true);
        }
      } else {
        // Page hidden - optionally notify callback
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
