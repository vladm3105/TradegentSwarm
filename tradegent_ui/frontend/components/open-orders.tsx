'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { X, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('open-orders');

interface Order {
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
}

async function fetchWithAuth<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const url = `/api/orchestrator?path=${encodeURIComponent(endpoint)}`;

  const response = await fetch(url, {
    ...options,
    headers: { ...headers, ...options?.headers },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function formatPrice(price: number | undefined): string {
  if (price === undefined) return '--';
  return price.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  });
}

const statusColors: Record<string, string> = {
  Submitted: 'bg-yellow-500',
  PreSubmitted: 'bg-yellow-500',
  PendingSubmit: 'bg-yellow-500',
  Filled: 'bg-green-500',
  PartiallyFilled: 'bg-blue-500',
  Cancelled: 'bg-gray-500',
  ApiCancelled: 'bg-gray-500',
};

export function OpenOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  async function loadOrders() {
    try {
      setLoading(true);
      const data = await fetchWithAuth<{ orders: Order[] }>('/api/orders/open');
      setOrders(data.orders || []);
      setError(null);
    } catch (e) {
      log.error('Failed to load orders', { error: String(e) });
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOrders();
    // Poll every 10 seconds
    const interval = setInterval(loadOrders, 10000);
    return () => clearInterval(interval);
  }, []);

  async function cancelOrder(orderId: string) {
    setCancellingId(orderId);
    try {
      await fetchWithAuth(`/api/orders/cancel/${orderId}`, { method: 'POST' });
      await loadOrders();
      log.action('order_cancelled', { orderId });
    } catch (e) {
      log.error('Failed to cancel order', { error: String(e) });
    } finally {
      setCancellingId(null);
    }
  }

  if (loading && orders.length === 0) {
    return (
      <Card>
        <CardContent className="p-6">Loading orders...</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Open Orders ({orders.length})</span>
          <Button type="button" variant="ghost" size="sm" onClick={loadOrders}>
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="text-red-500 text-sm mb-2">{error}</div>
        )}

        {orders.length === 0 ? (
          <div className="text-muted-foreground text-sm text-center py-4">
            No open orders
          </div>
        ) : (
          <ScrollArea className="h-[300px]">
            <div className="space-y-2">
              {orders.map(order => (
                <div
                  key={order.order_id}
                  className="p-3 rounded-lg border bg-background"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        {order.action === 'BUY' ? (
                          <TrendingUp className="h-4 w-4 text-green-500" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-red-500" />
                        )}
                        <span className="font-medium">{order.symbol}</span>
                        <Badge variant="outline" className="text-xs">
                          {order.order_type}
                        </Badge>
                        <Badge className={statusColors[order.status] || 'bg-gray-500'}>
                          {order.status}
                        </Badge>
                      </div>
                      <div className="text-sm text-muted-foreground mt-1 grid grid-cols-2 gap-x-4">
                        <span>Qty: {order.quantity} ({order.filled} filled)</span>
                        {order.limit_price && <span>Limit: {formatPrice(order.limit_price)}</span>}
                        {order.stop_price && <span>Stop: {formatPrice(order.stop_price)}</span>}
                        {order.avg_fill_price && <span>Avg Fill: {formatPrice(order.avg_fill_price)}</span>}
                      </div>
                    </div>

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => cancelOrder(order.order_id)}
                      disabled={cancellingId === order.order_id}
                      className="text-red-500 hover:text-red-600"
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}
