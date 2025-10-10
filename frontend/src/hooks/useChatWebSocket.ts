import { useEffect, useRef, useCallback, useState } from 'react';
import type { Message } from '@/lib/api';

interface UseChatWebSocketOptions {
  chatCode: string;
  sessionToken: string | null;
  onMessage?: (message: Message) => void;
  onUserBlocked?: (message: string) => void;
  onReaction?: (data: any) => void;
  onError?: (error: Event) => void;
  enabled?: boolean;
}

export function useChatWebSocket({
  chatCode,
  sessionToken,
  onMessage,
  onUserBlocked,
  onReaction,
  onError,
  enabled = true,
}: UseChatWebSocketOptions) {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 2000;

  const connect = useCallback(() => {
    if (!enabled || !sessionToken || ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setIsConnecting(true);

    // Determine WebSocket URL based on environment
    // Use WSS (secure WebSocket) when page is HTTPS, WS when HTTP
    const isSecure = window.location.protocol === 'https:';
    const wsProtocol = isSecure ? 'wss:' : 'ws:';
    const wsHost = isSecure ? window.location.hostname : 'localhost';
    const wsPort = '9000';
    const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/ws/chat/${chatCode}/?session_token=${sessionToken}`;

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
          if (onUserBlocked) {
            onUserBlocked(data.message);
          }
          return;
        }

        // Handle reaction events
        if (data.type === 'reaction') {
          console.log('[WebSocket] Reaction event received:', data);
          if (onReaction) {
            onReaction(data);
          }
          return;
        }

        // Handle chat messages (has an id field)
        if (onMessage && data.id) {
          onMessage(data as Message);
        }
      } catch (error) {
        console.error('[WebSocket] Failed to parse message:', error);
      }
    };

    socket.onerror = (error) => {
      console.error('[WebSocket] Error:', error);
      if (onError) {
        onError(error);
      }
    };

    socket.onclose = (event) => {
      console.log('[WebSocket] Disconnected:', event.code, event.reason);
      setIsConnected(false);
      setIsConnecting(false);
      ws.current = null;

      // Attempt to reconnect if not a normal closure and we haven't exceeded max attempts
      if (
        enabled &&
        sessionToken &&
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
  }, [chatCode, sessionToken, onMessage, onUserBlocked, onReaction, onError, enabled]);

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
    if (enabled && sessionToken) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, sessionToken, connect, disconnect]);

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
