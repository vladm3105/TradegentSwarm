'use client';

import { useEffect, useCallback, useRef } from 'react';
import {
  TradegentWebSocket,
  getWebSocket,
  type ConnectionState,
} from '@/lib/websocket';
import { useChatStore } from '@/stores/chat-store';
import type { WSResponse } from '@/types/api';
import { validateA2UIResponse } from '@/types/a2ui';

export function useWebSocket() {
  const wsRef = useRef<TradegentWebSocket | null>(null);
  const {
    setConnected,
    setStreaming,
    addMessage,
    updateMessage,
    setSessionId,
  } = useChatStore();

  const handleMessage = useCallback(
    (data: WSResponse) => {
      switch (data.type) {
        case 'response': {
          // Full response received
          const a2ui = validateA2UIResponse(data.data);
          if (a2ui) {
            // Find pending assistant message and update it
            const messages = useChatStore.getState().messages;
            const pendingMessage = messages.find(
              (m) => m.role === 'assistant' && m.status === 'pending'
            );
            if (pendingMessage) {
              updateMessage(pendingMessage.id, {
                content: a2ui.text,
                a2ui,
                status: 'complete',
              });
            } else {
              addMessage({
                role: 'assistant',
                content: a2ui.text,
                a2ui,
                status: 'complete',
              });
            }
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
          // Error response
          const messages = useChatStore.getState().messages;
          const pendingMessage = messages.find(
            (m) => m.role === 'assistant' && m.status === 'pending'
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
    },
    [addMessage, updateMessage, setStreaming]
  );

  const connect = useCallback(() => {
    if (wsRef.current) return;

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
    wsRef.current?.disconnect();
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

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

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
