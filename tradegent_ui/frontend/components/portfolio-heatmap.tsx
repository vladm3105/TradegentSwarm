'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('portfolio-heatmap');
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

interface HeatmapEntry {
  ticker: string;
  sector: string | null;
  market_value: number;
  weight_pct: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

async function fetchWithAuth<T>(endpoint: string): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }
  const response = await fetch(`${API_URL}${endpoint}`, { headers });
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

function getColorClass(pnlPct: number): string {
  if (pnlPct >= 10) return 'bg-green-600 text-white';
  if (pnlPct >= 5) return 'bg-green-500 text-white';
  if (pnlPct >= 0) return 'bg-green-400 text-white';
  if (pnlPct >= -5) return 'bg-red-400 text-white';
  if (pnlPct >= -10) return 'bg-red-500 text-white';
  return 'bg-red-600 text-white';
}

export function PortfolioHeatmap() {
  const [data, setData] = useState<HeatmapEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const result = await fetchWithAuth<HeatmapEntry[]>('/api/analytics/position-heatmap');
        setData(result);
        setError(null);
      } catch (e) {
        log.error('Failed to fetch heatmap', { error: String(e) });
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">Loading portfolio heatmap...</CardContent>
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

  const totalValue = data.reduce((sum, d) => sum + Math.abs(d.market_value), 0);
  const totalPnL = data.reduce((sum, d) => sum + d.unrealized_pnl, 0);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <span>Portfolio Heatmap</span>
          <Badge variant={totalPnL >= 0 ? 'default' : 'destructive'}>
            {totalPnL >= 0 ? '+' : ''}{formatCurrency(totalPnL)} unrealized
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <div className="text-muted-foreground text-sm text-center py-8">
            No open positions
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            {data.map(position => (
              <div
                key={position.ticker}
                className={`p-3 rounded-lg ${getColorClass(position.unrealized_pnl_pct)}`}
                style={{
                  // Size based on portfolio weight
                  minHeight: `${Math.max(60, position.weight_pct * 3)}px`,
                }}
              >
                <div className="font-bold text-sm">{position.ticker}</div>
                <div className="text-xs opacity-90">{position.weight_pct.toFixed(1)}%</div>
                <div className="text-xs font-mono">
                  {position.unrealized_pnl_pct >= 0 ? '+' : ''}
                  {position.unrealized_pnl_pct.toFixed(1)}%
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Legend */}
        {data.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex items-center justify-center gap-2 text-xs">
              <span className="text-muted-foreground">Loss</span>
              <div className="flex gap-0.5">
                <div className="w-4 h-4 bg-red-600 rounded" />
                <div className="w-4 h-4 bg-red-500 rounded" />
                <div className="w-4 h-4 bg-red-400 rounded" />
                <div className="w-4 h-4 bg-green-400 rounded" />
                <div className="w-4 h-4 bg-green-500 rounded" />
                <div className="w-4 h-4 bg-green-600 rounded" />
              </div>
              <span className="text-muted-foreground">Gain</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
