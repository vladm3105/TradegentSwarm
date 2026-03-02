'use client';

import { useEffect, useRef, useCallback } from 'react';
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
import { getWebSocket, type ConnectionState } from '@/lib/websocket';
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

  const wsRef = useRef(getWebSocket());
  const reconnectAttemptsRef = useRef(0);

  const handleConnect = useCallback(() => {
    setConnectionState('connected');
    setConnected(true);
    setLastError(null);
    reconnectAttemptsRef.current = 0;
    setReconnectInfo(0, maxReconnectAttempts);
  }, [setConnectionState, setConnected, setLastError, setReconnectInfo, maxReconnectAttempts]);

  const handleDisconnect = useCallback(() => {
    setConnectionState('disconnected');
    setConnected(false);
  }, [setConnectionState, setConnected]);

  const handleError = useCallback((error: Error) => {
    setLastError(error.message);
  }, [setLastError]);

  useEffect(() => {
    const ws = wsRef.current;

    // Override WebSocket callbacks to update store
    const originalOnConnect = ws['options'].onConnect;
    const originalOnDisconnect = ws['options'].onDisconnect;
    const originalOnError = ws['options'].onError;

    ws['options'].onConnect = () => {
      handleConnect();
      originalOnConnect?.();
    };

    ws['options'].onDisconnect = () => {
      handleDisconnect();
      originalOnDisconnect?.();
    };

    ws['options'].onError = (error: Error) => {
      handleError(error);
      originalOnError?.(error);
    };

    // Set up polling to detect reconnect state
    const intervalId = setInterval(() => {
      const state = ws.getState();
      if (state !== connectionState) {
        setConnectionState(state);
        setConnected(state === 'connected');
      }

      // Track reconnect attempts via internal state
      if (state === 'reconnecting') {
        reconnectAttemptsRef.current++;
        setReconnectInfo(reconnectAttemptsRef.current, maxReconnectAttempts);
      }
    }, 500);

    // Connect on mount
    ws.connect();

    return () => {
      clearInterval(intervalId);
    };
  }, [
    connectionState,
    handleConnect,
    handleDisconnect,
    handleError,
    setConnectionState,
    setConnected,
    setReconnectInfo,
    maxReconnectAttempts,
  ]);

  const handleManualReconnect = () => {
    reconnectAttemptsRef.current = 0;
    setReconnectInfo(0, maxReconnectAttempts);
    setLastError(null);
    wsRef.current.disconnect();
    setTimeout(() => {
      wsRef.current.connect();
    }, 100);
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
                onClick={handleManualReconnect}
              >
                <RefreshCw className="h-3 w-3 mr-1" />
                Reconnect
              </Button>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
