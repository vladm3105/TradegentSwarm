'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';
import {
  createAuthenticatedWebSocket,
  resolveWebSocketEndpoint,
} from '@/lib/websocket-auth';

const log = createLogger('use-portfolio-stream');

const STREAM_WS_URL = resolveWebSocketEndpoint(
  process.env.NEXT_PUBLIC_WS_URL,
  '/ws/stream'
);

export interface Position {
  symbol: string;
  quantity: number;
  avgCost: number;
  marketValue: number;
  unrealizedPnl: number;
  realizedPnl: number;
}

export interface PortfolioData {
  positions: Position[];
  pnl: {
    daily_pnl: number;
    unrealized_pnl: number;
    realized_pnl: number;
    net_liquidation: number;
  };
  timestamp: number;
}

export interface UsePortfolioStreamOptions {
  enabled?: boolean;
}

export interface UsePortfolioStreamResult {
  portfolio: PortfolioData | null;
  connected: boolean;
  error: string | null;
}

export function usePortfolioStream({ enabled = true }: UsePortfolioStreamOptions = {}): UsePortfolioStreamResult {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(async () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const session = await getSession();
      if (!session?.accessToken) {
        setError('Not authenticated');
        return;
      }

      const ws = createAuthenticatedWebSocket(STREAM_WS_URL, session.accessToken);

      ws.onopen = () => {
        log.info('Portfolio stream connected');
        setConnected(true);
        setError(null);

        // Subscribe to portfolio updates
        ws.send(JSON.stringify({
          type: 'subscribe',
          channel: 'portfolio',
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'portfolio_update') {
            setPortfolio(data.data);
          }
        } catch (e) {
          log.error('Failed to parse portfolio message', { error: String(e) });
        }
      };

      ws.onerror = (event) => {
        log.error('Portfolio stream error', { error: String(event) });
        setError('Connection error');
      };

      ws.onclose = () => {
        log.info('Portfolio stream disconnected');
        setConnected(false);
        wsRef.current = null;

        // Attempt reconnect after 5 seconds
        if (enabled) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 5000);
        }
      };

      wsRef.current = ws;
    } catch (e) {
      log.error('Failed to connect portfolio stream', { error: String(e) });
      setError(String(e));
    }
  }, [enabled]);

  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [enabled, connect]);

  return { portfolio, connected, error };
}
