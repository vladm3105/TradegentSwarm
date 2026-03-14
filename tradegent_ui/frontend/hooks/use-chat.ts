'use client';

import { useCallback } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useWebSocket } from '@/hooks/use-websocket';
import type { A2UIResponse } from '@/types/a2ui';

export function useChat() {
  const {
    messages,
    sessionId,
    isConnected,
    isStreaming,
    currentSession,
    sessionsDirty,
    addMessage,
    updateMessage,
    clearMessages,
    loadSession,
    newSession,
    markSessionClean,
  } = useChatStore();

  const { sendMessage: wsSendMessage, subscribeToTask, unsubscribeFromTask } =
    useWebSocket();

  const sendMessage = useCallback(
    async (content: string) => {
      // Add user message immediately
      addMessage({
        role: 'user',
        content,
        status: 'complete',
      });

      // Send via WebSocket
      wsSendMessage(content, false);
    },
    [addMessage, wsSendMessage]
  );

  const sendAsyncMessage = useCallback(
    async (content: string) => {
      // Add user message immediately
      addMessage({
        role: 'user',
        content,
        status: 'complete',
      });

      // Send via WebSocket with async flag
      wsSendMessage(content, true);
    },
    [addMessage, wsSendMessage]
  );

  const cancelMessage = useCallback(
    (messageId: string) => {
      const message = messages.find((m) => m.id === messageId);
      if (message?.taskId) {
        unsubscribeFromTask(message.taskId);
        updateMessage(messageId, {
          status: 'error',
          error: 'Cancelled by user',
        });
      }
    },
    [messages, unsubscribeFromTask, updateMessage]
  );

  return {
    messages,
    sessionId,
    isConnected,
    isStreaming,
    currentSession,
    sessionsDirty,
    sendMessage,
    sendAsyncMessage,
    cancelMessage,
    clearMessages,
    loadSession,
    newSession,
    markSessionClean,
  };
}
