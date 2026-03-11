'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('equity-curve');

interface EquityPoint {
  date: string;
  equity: number;
  pnl: number;
  cumulative_pnl: number;
}

interface EquityCurveProps {
  period?: '7d' | '30d' | '90d' | '1y' | 'all';
}

async function fetchWithAuth<T>(endpoint: string): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const url = `/api/orchestrator?path=${encodeURIComponent(endpoint)}`;
  const response = await fetch(url, { headers });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function formatCurrency(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export function EquityCurve({ period = '30d' }: EquityCurveProps) {
  const [data, setData] = useState<EquityPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const result = await fetchWithAuth<EquityPoint[]>(`/api/analytics/equity-curve?period=${period}`);
        setData(result);
        setError(null);
      } catch (e) {
        log.error('Failed to fetch equity curve', { error: String(e) });
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [period]);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">Loading equity curve...</CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6 text-red-500">Error: {error}</CardContent>
      </Card>
    );
  }

  const latestEquity = data.length > 0 ? data[data.length - 1].equity : 100000;
  const totalPnL = data.length > 0 ? data[data.length - 1].cumulative_pnl : 0;
  const isPositive = totalPnL >= 0;

  // Find min/max for chart scaling
  const equities = data.map(d => d.equity);
  const minEquity = Math.min(...equities, 100000);
  const maxEquity = Math.max(...equities, 100000);
  const range = maxEquity - minEquity || 1;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Equity Curve</span>
          <Badge variant={isPositive ? 'default' : 'destructive'}>
            {isPositive ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
            {isPositive ? '+' : ''}{formatCurrency(totalPnL)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* Simple text-based visualization */}
        <div className="mb-4">
          <div className="text-2xl font-bold font-mono">{formatCurrency(latestEquity)}</div>
          <div className={`text-sm ${isPositive ? 'text-green-500' : 'text-red-500'}`}>
            {isPositive ? '+' : ''}{((totalPnL / 100000) * 100).toFixed(2)}% total return
          </div>
        </div>

        {/* Simple bar chart */}
        {data.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-end gap-px h-24">
              {data.slice(-20).map((point, i) => {
                const height = ((point.equity - minEquity) / range) * 100;
                const isUp = point.pnl >= 0;
                return (
                  <div
                    key={i}
                    className={`flex-1 ${isUp ? 'bg-green-500' : 'bg-red-500'} rounded-t`}
                    style={{ height: `${Math.max(height, 2)}%` }}
                    title={`${point.date}: ${formatCurrency(point.equity)}`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{data.length > 0 ? data[Math.max(0, data.length - 20)].date : ''}</span>
              <span>{data.length > 0 ? data[data.length - 1].date : ''}</span>
            </div>
          </div>
        )}

        {data.length === 0 && (
          <div className="text-muted-foreground text-sm text-center py-8">
            No trade data available for this period
          </div>
        )}
      </CardContent>
    </Card>
  );
}
