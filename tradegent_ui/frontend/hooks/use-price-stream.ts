'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('use-price-stream');

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081';

export interface PriceData {
  last: number;
  bid: number;
  ask: number;
  high: number;
  low: number;
  volume: number;
  change: number;
  changePct: number;
  timestamp: number;
}

export interface UsePriceStreamOptions {
  tickers: string[];
  enabled?: boolean;
}

export interface UsePriceStreamResult {
  prices: Record<string, PriceData>;
  connected: boolean;
  error: string | null;
  subscribe: (tickers: string[]) => void;
  unsubscribe: (tickers: string[]) => void;
}

export function usePriceStream({ tickers, enabled = true }: UsePriceStreamOptions): UsePriceStreamResult {
  const [prices, setPrices] = useState<Record<string, PriceData>>({});
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

      const ws = new WebSocket(`${WS_URL}/ws/stream?token=${session.accessToken}`);

      ws.onopen = () => {
        log.info('Price stream connected');
        setConnected(true);
        setError(null);

        // Subscribe to initial tickers
        if (tickers.length > 0) {
          ws.send(JSON.stringify({
            type: 'subscribe',
            channel: 'prices',
            tickers,
          }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'price_update') {
            setPrices(prev => ({
              ...prev,
              [data.ticker]: data.data,
            }));
          }
        } catch (e) {
          log.error('Failed to parse price message', { error: String(e) });
        }
      };

      ws.onerror = (event) => {
        log.error('Price stream error', { error: String(event) });
        setError('Connection error');
      };

      ws.onclose = () => {
        log.info('Price stream disconnected');
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
      log.error('Failed to connect price stream', { error: String(e) });
      setError(String(e));
    }
  }, [tickers, enabled]);

  const subscribe = useCallback((newTickers: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && newTickers.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'subscribe',
        channel: 'prices',
        tickers: newTickers,
      }));
    }
  }, []);

  const unsubscribe = useCallback((tickersToRemove: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && tickersToRemove.length > 0) {
      wsRef.current.send(JSON.stringify({
        type: 'unsubscribe',
        channel: 'prices',
        tickers: tickersToRemove,
      }));
      setPrices(prev => {
        const next = { ...prev };
        tickersToRemove.forEach(t => delete next[t]);
        return next;
      });
    }
  }, []);

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

  // Subscribe to new tickers when they change
  useEffect(() => {
    if (connected && tickers.length > 0) {
      subscribe(tickers);
    }
  }, [connected, tickers, subscribe]);

  return { prices, connected, error, subscribe, unsubscribe };
}
