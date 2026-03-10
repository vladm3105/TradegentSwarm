'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';
import {
  createAuthenticatedWebSocket,
  resolveWebSocketEndpoint,
} from '@/lib/websocket-auth';

const log = createLogger('use-order-stream');

const STREAM_WS_URL = resolveWebSocketEndpoint(
  process.env.NEXT_PUBLIC_WS_URL,
  '/ws/stream'
);

export interface Order {
  order_id: string;
  symbol: string;
  action: 'BUY' | 'SELL';
  quantity: number;
  order_type: string;
  limit_price?: number;
  stop_price?: number;
  status: string;
  filled: number;
  remaining: number;
  avg_fill_price?: number;
  created_at: string;
}

export interface UseOrderStreamOptions {
  enabled?: boolean;
}

export interface UseOrderStreamResult {
  orders: Order[];
  connected: boolean;
  error: string | null;
}

export function useOrderStream({ enabled = true }: UseOrderStreamOptions = {}): UseOrderStreamResult {
  const [orders, setOrders] = useState<Order[]>([]);
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
        log.info('Order stream connected');
        setConnected(true);
        setError(null);

        // Subscribe to order updates
        ws.send(JSON.stringify({
          type: 'subscribe',
          channel: 'orders',
        }));
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'orders_snapshot') {
            setOrders(data.data || []);
          } else if (data.type === 'orders_update') {
            setOrders(prev => {
              let next = [...prev];

              // Remove orders
              if (data.removed?.length) {
                const removedIds = new Set(
                  (data.removed as Order[]).map((o) => o.order_id)
                );
                next = next.filter(o => !removedIds.has(o.order_id));
              }

              // Update orders
              if (data.updated?.length) {
                const updatedMap = new Map<string, Order>(
                  (data.updated as Order[]).map((o) => [o.order_id, o])
                );
                next = next.map(o => updatedMap.get(o.order_id) || o);
              }

              // Add new orders
              if (data.added?.length) {
                next = [...next, ...data.added];
              }

              return next;
            });
          } else if (data.type === 'order_event') {
            log.info('Order event', { event: data.event, order: data.order });
          }
        } catch (e) {
          log.error('Failed to parse order message', { error: String(e) });
        }
      };

      ws.onerror = (event) => {
        log.error('Order stream error', { error: String(event) });
        setError('Connection error');
      };

      ws.onclose = () => {
        log.info('Order stream disconnected');
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
      log.error('Failed to connect order stream', { error: String(e) });
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

  return { orders, connected, error };
}
