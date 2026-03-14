import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { signOut } from 'next-auth/react';
import { useWebSocket } from '@/hooks/use-websocket';
import { useChatStore } from '@/stores/chat-store';

type MockWsOptions = {
  onMessage?: (data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Error) => void;
  onAuthError?: () => void;
};

let capturedOptions: MockWsOptions = {};

const mockWsInstance = {
  connect: vi.fn(),
  disconnect: vi.fn(),
  sendChatMessage: vi.fn(),
  subscribeToTask: vi.fn(),
  unsubscribeFromTask: vi.fn(),
  isConnected: vi.fn(() => false),
  getState: vi.fn(() => 'disconnected'),
  getSessionId: vi.fn(() => 'test-session-id'),
};

vi.mock('@/lib/websocket', () => ({
  getWebSocket: vi.fn((options: MockWsOptions) => {
    capturedOptions = options;
    return mockWsInstance;
  }),
  resetWebSocket: vi.fn(),
}));

describe('useWebSocket auth handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    capturedOptions = {};
    useChatStore.setState({
      messages: [],
      sessionId: null,
      currentSession: null,
      savedSessions: [],
      sessionsDirty: false,
      isConnected: false,
      isStreaming: false,
      connectionState: 'disconnected',
      reconnectAttempts: 0,
      maxReconnectAttempts: 10,
      lastError: null,
    });
  });

  it('redirects to login via signOut on websocket auth error', async () => {
    renderHook(() => useWebSocket());

    await waitFor(() => {
      expect(mockWsInstance.connect).toHaveBeenCalled();
      expect(capturedOptions.onAuthError).toBeTypeOf('function');
    });

    act(() => {
      capturedOptions.onAuthError?.();
    });

    await waitFor(() => {
      expect(signOut).toHaveBeenCalledWith({ callbackUrl: '/login' });
    });
  });

  it('updates pending assistant message on task_created', async () => {
    renderHook(() => useWebSocket());

    await waitFor(() => {
      expect(capturedOptions.onMessage).toBeTypeOf('function');
    });

    let pendingId = '';
    act(() => {
      pendingId = useChatStore.getState().addMessage({
        role: 'assistant',
        content: '',
        status: 'pending',
      });
    });

    act(() => {
      capturedOptions.onMessage?.({ type: 'task_created', task_id: 'task-123' });
    });

    const pending = useChatStore.getState().messages.find((m) => m.id === pendingId);
    expect(pending?.taskId).toBe('task-123');
    expect(pending?.status).toBe('streaming');
    expect(pending?.progress).toBe(0);
  });

  it('marks pending assistant message complete on async complete event', async () => {
    renderHook(() => useWebSocket());

    await waitFor(() => {
      expect(capturedOptions.onMessage).toBeTypeOf('function');
    });

    let pendingId = '';
    act(() => {
      useChatStore.getState().setStreaming(true);
      pendingId = useChatStore.getState().addMessage({
        role: 'assistant',
        content: '',
        status: 'streaming',
      });
    });

    act(() => {
      capturedOptions.onMessage?.({
        type: 'complete',
        task_id: 'task-123',
        result: {
          success: true,
          text: 'Async done',
          error: null,
        },
      });
    });

    const pending = useChatStore.getState().messages.find((m) => m.id === pendingId);
    expect(pending?.status).toBe('complete');
    expect(pending?.content).toBe('Async done');
    expect(useChatStore.getState().isStreaming).toBe(false);
  });
});
