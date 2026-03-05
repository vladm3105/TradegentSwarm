'use client';

import { useEffect, useCallback, useRef } from 'react';
import {
  TradegentWebSocket,
  getWebSocket,
  resetWebSocket,
  type ConnectionState,
} from '@/lib/websocket';
import { useChatStore } from '@/stores/chat-store';
import type { WSResponse } from '@/types/api';
import { validateA2UIResponse } from '@/types/a2ui';
import { logger } from '@/lib/logger';

export function useWebSocket() {
  const wsRef = useRef<TradegentWebSocket | null>(null);
  const handleMessageRef = useRef<((data: WSResponse) => void) | null>(null);
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

  const connect = useCallback(() => {
    if (wsRef.current) return;

    // Reset singleton to ensure fresh instance with new callback
    resetWebSocket();

    wsRef.current = getWebSocket({
      onMessage: handleMessage,
      onConnect: () => {
        setConnected(true);
        const sessionId = wsRef.current?.getSessionId();
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
    });

    wsRef.current.connect();
  }, [handleMessage, setConnected, setSessionId]);

  const disconnect = useCallback(() => {
    resetWebSocket();
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

  // Auto-connect on mount only
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
    // Only run on mount/unmount, not on callback changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
