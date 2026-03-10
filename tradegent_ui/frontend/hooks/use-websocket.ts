'use client';

import { useEffect, useCallback, useRef } from 'react';
import { signOut } from 'next-auth/react';
import {
  TradegentWebSocket,
  getWebSocket,
  getWebSocketIfExists,
  resetWebSocket,
} from '@/lib/websocket';
import { useChatStore } from '@/stores/chat-store';
import type { WSResponse } from '@/types/api';
import { validateA2UIResponse } from '@/types/a2ui';
import { logger } from '@/lib/logger';

let sharedWebSocket: TradegentWebSocket | null = null;
let activeWebSocketConsumers = 0;

export function useWebSocket() {
  const wsRef = useRef<TradegentWebSocket | null>(null);
  const handleMessageRef = useRef<((data: WSResponse) => void) | null>(null);
  const authRedirectInProgressRef = useRef(false);
  const {
    setConnected,
    setStreaming,
    addMessage,
    updateMessage,
    setSessionId,
  } = useChatStore();

  // Keep handleMessage ref up to date
  handleMessageRef.current = (data: WSResponse) => {
    switch (data.type) {
      case 'response': {
        // Log A2UI response received
        logger.a2uiReceived(data.a2ui, { source: 'websocket' });

        // Full response received
        // Backend sends: { type: 'response', success, text, a2ui, error }
        const a2ui = validateA2UIResponse(data.a2ui);
        logger.a2uiValidated(!!a2ui, a2ui ? undefined : 'Validation returned null');

        // Log full payload in A2UI debug mode
        logger.a2uiPayload('websocket-response', data);

        const responseData = data as { text?: string; error?: string; success?: boolean };

        // Find pending or streaming assistant message
        const messages = useChatStore.getState().messages;
        const pendingMessage = messages.find(
          (m) => m.role === 'assistant' && (m.status === 'pending' || m.status === 'streaming')
        );

        // Determine content: use a2ui.text if available, else top-level text
        const content = a2ui?.text ?? responseData.text ?? '';

        if (pendingMessage) {
          updateMessage(pendingMessage.id, {
            content,
            a2ui: a2ui ?? undefined,
            status: responseData.error ? 'error' : 'complete',
            error: responseData.error,
          });
        } else if (content || a2ui) {
          addMessage({
            role: 'assistant',
            content,
            a2ui: a2ui ?? undefined,
            status: responseData.error ? 'error' : 'complete',
            error: responseData.error,
          });
        }
        setStreaming(false);
        break;
      }

      case 'progress': {
        // Task progress update - find pending message and update progress
        const messages = useChatStore.getState().messages;
        const pendingMessage = messages.find(
          (m) => m.role === 'assistant' && (m.status === 'pending' || m.status === 'streaming')
        );

        if (pendingMessage) {
          updateMessage(pendingMessage.id, {
            status: 'streaming',
            progress: data.progress,
            progressMessage: data.message || `Processing...`,
            taskId: data.task_id,
          });
        }
        break;
      }

      case 'error': {
        // Error response - find pending or streaming message
        const messages = useChatStore.getState().messages;
        const pendingMessage = messages.find(
          (m) => m.role === 'assistant' && (m.status === 'pending' || m.status === 'streaming')
        );
        if (pendingMessage) {
          updateMessage(pendingMessage.id, {
            content: data.error || 'An error occurred',
            status: 'error',
            error: data.error,
          });
        }
        setStreaming(false);
        break;
      }
    }
  };

  // Stable message handler that delegates to ref
  const handleMessage = useCallback((data: WSResponse) => {
    handleMessageRef.current?.(data);
  }, []);

  const handleAuthError = useCallback(() => {
    if (authRedirectInProgressRef.current) {
      return;
    }

    authRedirectInProgressRef.current = true;
    setConnected(false);
    setStreaming(false);
    logger.warn('WebSocket auth failed, redirecting user to login');

    void signOut({ callbackUrl: '/login' });
  }, [setConnected, setStreaming]);

  const connect = useCallback(() => {
    if (!sharedWebSocket) {
      sharedWebSocket = getWebSocket({
        onMessage: handleMessage,
        onConnect: () => {
          authRedirectInProgressRef.current = false;
          setConnected(true);
          const sessionId = sharedWebSocket?.getSessionId();
          if (sessionId) {
            setSessionId(sessionId);
          }
        },
        onDisconnect: () => {
          setConnected(false);
        },
        onError: (error) => {
          console.error('WebSocket error:', error);
        },
        onAuthError: handleAuthError,
      });
    }

    wsRef.current = sharedWebSocket;

    if (sharedWebSocket.getState() === 'disconnected') {
      void sharedWebSocket.connect();
    }
  }, [handleAuthError, handleMessage, setConnected, setSessionId]);

  const disconnect = useCallback(() => {
    sharedWebSocket?.disconnect();
    resetWebSocket();
    sharedWebSocket = null;
    wsRef.current = null;
    setConnected(false);
  }, [setConnected]);

  const sendMessage = useCallback(
    (content: string, async = false) => {
      if (!wsRef.current) {
        connect();
      }
      setStreaming(true);

      // Add pending assistant message
      addMessage({
        role: 'assistant',
        content: '',
        status: 'pending',
      });

      wsRef.current?.sendChatMessage(content, async);
    },
    [connect, setStreaming, addMessage]
  );

  const subscribeToTask = useCallback((taskId: string) => {
    wsRef.current?.subscribeToTask(taskId);
  }, []);

  const unsubscribeFromTask = useCallback((taskId: string) => {
    wsRef.current?.unsubscribeFromTask(taskId);
  }, []);

  // Auto-connect on mount only.
  // Uses a short defer to survive React StrictMode's double-mount:
  // StrictMode mounts → runs effect → unmounts within the same tick →
  // remounts. The 50 ms timer ensures the cleanup (decrements counter,
  // disconnects) fires before the deferred connect runs on the final mount.
  useEffect(() => {
    let cancelled = false;

    activeWebSocketConsumers += 1;

    const timer = setTimeout(() => {
      if (!cancelled) {
        connect();
      }
    }, 50);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      activeWebSocketConsumers = Math.max(0, activeWebSocketConsumers - 1);
      if (activeWebSocketConsumers === 0) {
        disconnect();
      }
    };
    // Only run on mount/unmount, not on callback changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reconnect when the browser tab regains focus or becomes visible.
  // This handles two scenarios:
  //   1. HMR hot-reload: module-level vars reset to null but effects don't re-run.
  //      When the user clicks back into the tab, we recover automatically.
  //   2. Long idle: OS sleep / network interruption can silently drop the WS.
  useEffect(() => {
    const handleVisible = () => {
      const ws = getWebSocketIfExists();
      // If the singleton is gone (HMR reset) or disconnected, reconnect.
      if (!ws || ws.getState() === 'disconnected') {
        connect();
      }
    };
    document.addEventListener('visibilitychange', handleVisible);
    window.addEventListener('focus', handleVisible);
    return () => {
      document.removeEventListener('visibilitychange', handleVisible);
      window.removeEventListener('focus', handleVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connect]);

  return {
    connect,
    disconnect,
    sendMessage,
    subscribeToTask,
    unsubscribeFromTask,
    isConnected: wsRef.current?.isConnected() ?? false,
    getState: () => wsRef.current?.getState() ?? 'disconnected',
  };
}
