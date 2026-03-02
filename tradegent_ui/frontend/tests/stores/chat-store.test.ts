import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from '@/stores/chat-store';

describe('Chat Store', () => {
  beforeEach(() => {
    // Reset store state
    useChatStore.setState({
      messages: [],
      sessionId: null,
      isConnected: false,
      isStreaming: false,
      connectionState: 'disconnected',
      reconnectAttempts: 0,
      maxReconnectAttempts: 10,
      lastError: null,
    });
  });

  describe('messages', () => {
    it('adds a message and returns the id', () => {
      const store = useChatStore.getState();
      const id = store.addMessage({
        role: 'user',
        content: 'Hello',
      });

      expect(id).toBeDefined();
      expect(typeof id).toBe('string');

      const messages = useChatStore.getState().messages;
      expect(messages).toHaveLength(1);
      expect(messages[0].content).toBe('Hello');
      expect(messages[0].role).toBe('user');
    });

    it('updates a message', () => {
      const store = useChatStore.getState();
      const id = store.addMessage({
        role: 'assistant',
        content: 'Processing...',
        status: 'pending',
      });

      store.updateMessage(id, {
        content: 'Done!',
        status: 'complete',
      });

      const message = useChatStore.getState().messages.find((m) => m.id === id);
      expect(message?.content).toBe('Done!');
      expect(message?.status).toBe('complete');
    });

    it('clears all messages', () => {
      const store = useChatStore.getState();
      store.addMessage({ role: 'user', content: 'Test 1' });
      store.addMessage({ role: 'assistant', content: 'Test 2' });

      expect(useChatStore.getState().messages).toHaveLength(2);

      store.clearMessages();
      expect(useChatStore.getState().messages).toHaveLength(0);
    });
  });

  describe('connection state', () => {
    it('sets connected state', () => {
      const store = useChatStore.getState();
      expect(store.isConnected).toBe(false);

      store.setConnected(true);
      expect(useChatStore.getState().isConnected).toBe(true);
    });

    it('sets connection state', () => {
      const store = useChatStore.getState();
      store.setConnectionState('connecting');
      expect(useChatStore.getState().connectionState).toBe('connecting');

      store.setConnectionState('connected');
      expect(useChatStore.getState().connectionState).toBe('connected');
    });

    it('sets reconnect info', () => {
      const store = useChatStore.getState();
      store.setReconnectInfo(3, 10);

      const state = useChatStore.getState();
      expect(state.reconnectAttempts).toBe(3);
      expect(state.maxReconnectAttempts).toBe(10);
    });

    it('sets last error', () => {
      const store = useChatStore.getState();
      store.setLastError('Connection timeout');
      expect(useChatStore.getState().lastError).toBe('Connection timeout');

      store.setLastError(null);
      expect(useChatStore.getState().lastError).toBeNull();
    });
  });

  describe('streaming', () => {
    it('sets streaming state', () => {
      const store = useChatStore.getState();
      expect(store.isStreaming).toBe(false);

      store.setStreaming(true);
      expect(useChatStore.getState().isStreaming).toBe(true);
    });
  });

  describe('session', () => {
    it('sets session id', () => {
      const store = useChatStore.getState();
      store.setSessionId('test-session-123');
      expect(useChatStore.getState().sessionId).toBe('test-session-123');
    });
  });
});
