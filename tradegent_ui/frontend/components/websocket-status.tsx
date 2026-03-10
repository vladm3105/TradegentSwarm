'use client';

import { useEffect, useState } from 'react';
import {
  Wifi,
  WifiOff,
  RefreshCw,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useChatStore } from '@/stores/chat-store';
import { getWebSocket, getWebSocketIfExists, type ConnectionState } from '@/lib/websocket';
import { getHealth } from '@/lib/api';
import { cn } from '@/lib/utils';

interface ConnectionStateConfig {
  icon: React.ReactNode;
  label: string;
  className: string;
  animate?: boolean;
}

const CONNECTION_STATE_CONFIG: Record<ConnectionState, ConnectionStateConfig> = {
  connected: {
    icon: <Wifi className="h-3 w-3" />,
    label: 'Connected',
    className: 'bg-gain/10 text-gain',
  },
  connecting: {
    icon: <Loader2 className="h-3 w-3 animate-spin" />,
    label: 'Connecting',
    className: 'bg-warning/10 text-warning',
    animate: true,
  },
  reconnecting: {
    icon: <RefreshCw className="h-3 w-3" />,
    label: 'Reconnecting',
    className: 'bg-warning/10 text-warning',
    animate: true,
  },
  disconnected: {
    icon: <WifiOff className="h-3 w-3" />,
    label: 'Disconnected',
    className: 'bg-loss/10 text-loss',
  },
};

export function WebSocketStatus() {
  const [isConnectingBackend, setIsConnectingBackend] = useState(false);
  const {
    connectionState,
    reconnectAttempts,
    maxReconnectAttempts,
    lastError,
    setConnectionState,
    setReconnectInfo,
    setConnected,
    setLastError,
  } = useChatStore();

  useEffect(() => {
    // Use getWebSocketIfExists() so that we never create the singleton here.
    // WebSocketStatus mounts inside <Header>, which renders before <ChatPanel>
    // (and therefore before use-websocket.ts sets real callbacks).  Creating the
    // singleton here would produce a bare instance with no-op handlers — the root
    // cause of the reconnect loop.  If the singleton doesn't exist yet, skip
    // polling; store updates from use-websocket.ts's onConnect / onDisconnect
    // callbacks will keep the UI in sync once ChatPanel mounts.
    const intervalId = setInterval(() => {
      const ws = getWebSocketIfExists();
      if (!ws) {
        // Singleton was destroyed (HMR module reset or explicit resetWebSocket).
        // Clear any stale 'reconnecting' state so the UI doesn't show a phantom
        // retry counter indefinitely.
        const storeState = useChatStore.getState().connectionState;
        if (storeState !== 'disconnected') {
          setConnectionState('disconnected');
          setConnected(false);
          setReconnectInfo(0, maxReconnectAttempts);
        }
        return;
      }

      const state = ws.getState();
      if (state !== useChatStore.getState().connectionState) {
        setConnectionState(state);
        setConnected(state === 'connected');
      }

      // Track reconnect attempts via internal state
      if (state === 'reconnecting') {
        const current = useChatStore.getState().reconnectAttempts;
        setReconnectInfo(current + 1, maxReconnectAttempts);
      }
    }, 1000);

    return () => {
      clearInterval(intervalId);
    };
  }, [
    setConnectionState,
    setConnected,
    setReconnectInfo,
    maxReconnectAttempts,
  ]);

  const handleConnectBackend = async () => {
    if (isConnectingBackend) {
      return;
    }

    setIsConnectingBackend(true);
    setReconnectInfo(0, maxReconnectAttempts);
    setLastError(null);

    // By the time the user clicks "Connect Backend", use-websocket.ts will have
    // already called getWebSocket(options), so the singleton has real callbacks.
    // Fall back to creating it if somehow called before ChatPanel mounts.
    const ws = getWebSocket();
    try {
      // Verify backend API is reachable before opening a websocket.
      await getHealth();

      if (ws.getState() === 'connected') {
        setConnectionState('connected');
        setConnected(true);
        return;
      }

      // refreshToken() disconnects (if needed), resets the reconnect-attempt
      // counter to 0, then reconnects — preventing the counter exhaustion that
      // makes manual reconnect silently fail after repeated auth retries.
      await ws.refreshToken();

      const nextState = ws.getState();
      setConnectionState(nextState);
      setConnected(nextState === 'connected');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setLastError(message);
      setConnectionState('disconnected');
      setConnected(false);
    } finally {
      setIsConnectingBackend(false);
    }
  };

  const config = CONNECTION_STATE_CONFIG[connectionState];
  const showReconnectProgress = connectionState === 'reconnecting' && reconnectAttempts > 0;
  const isDisconnected = connectionState === 'disconnected';
  const hasError = !!lastError;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={cn(
              'flex items-center gap-1 px-2 py-1 rounded-md text-xs transition-colors cursor-default',
              config.className,
              config.animate && connectionState === 'reconnecting' && 'animate-pulse'
            )}
          >
            {config.icon}
            <span className="hidden sm:inline">{config.label}</span>
            {showReconnectProgress && (
              <span className="text-[10px] opacity-75">
                ({reconnectAttempts}/{maxReconnectAttempts})
              </span>
            )}
            {hasError && (
              <AlertCircle className="h-3 w-3 ml-1 text-loss" />
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-1">
            <p className="font-medium">
              WebSocket: {config.label}
            </p>
            {showReconnectProgress && (
              <p className="text-xs text-muted-foreground">
                Attempt {reconnectAttempts} of {maxReconnectAttempts}
              </p>
            )}
            {lastError && (
              <p className="text-xs text-loss">
                Error: {lastError}
              </p>
            )}
            {isDisconnected && (
              <Button
                variant="outline"
                size="sm"
                className="mt-2 w-full text-xs"
                onClick={() => {
                  void handleConnectBackend();
                }}
                disabled={isConnectingBackend}
              >
                {isConnectingBackend ? (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                ) : (
                  <RefreshCw className="h-3 w-3 mr-1" />
                )}
                Connect Backend
              </Button>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
