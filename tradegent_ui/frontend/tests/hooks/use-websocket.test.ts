import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { signOut } from 'next-auth/react';
import { useWebSocket } from '@/hooks/use-websocket';

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
});
