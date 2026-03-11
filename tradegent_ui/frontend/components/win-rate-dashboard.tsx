'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Target, BarChart3 } from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('win-rate-dashboard');

interface PerformanceStats {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  expectancy: number;
  max_drawdown: number;
  sharpe_ratio: number | null;
  total_pnl: number;
  total_return_pct: number;
}

interface SetupStats {
  setup_type: string;
  total_trades: number;
  wins: number;
  win_rate: number;
  avg_pnl: number;
  total_pnl: number;
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
    minimumFractionDigits: 2,
  });
}

function StatCard({ label, value, subValue, icon: Icon, positive }: {
  label: string;
  value: string;
  subValue?: string;
  icon?: React.ComponentType<{ className?: string }>;
  positive?: boolean;
}) {
  return (
    <div className="p-3 rounded-lg bg-muted/50">
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
        {Icon && <Icon className="h-3 w-3" />}
        {label}
      </div>
      <div className={`text-lg font-bold font-mono ${
        positive === true ? 'text-green-500' :
        positive === false ? 'text-red-500' : ''
      }`}>
        {value}
      </div>
      {subValue && (
        <div className="text-xs text-muted-foreground">{subValue}</div>
      )}
    </div>
  );
}

interface WinRateDashboardProps {
  period?: '7d' | '30d' | '90d' | '1y' | 'all';
}

export function WinRateDashboard({ period = '30d' }: WinRateDashboardProps) {
  const [stats, setStats] = useState<PerformanceStats | null>(null);
  const [setupStats, setSetupStats] = useState<SetupStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [perfStats, bySetup] = await Promise.all([
          fetchWithAuth<PerformanceStats>(`/api/analytics/performance?period=${period}`),
          fetchWithAuth<SetupStats[]>('/api/analytics/win-rate-by-setup'),
        ]);
        setStats(perfStats);
        setSetupStats(bySetup);
        setError(null);
      } catch (e) {
        log.error('Failed to fetch performance stats', { error: String(e) });
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
        <CardContent className="p-6">Loading performance stats...</CardContent>
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

  if (!stats) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">No data available</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Performance Dashboard
          </div>
          <Badge variant={stats.total_pnl >= 0 ? 'default' : 'destructive'}>
            {stats.total_pnl >= 0 ? '+' : ''}{formatCurrency(stats.total_pnl)}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <StatCard
            label="Win Rate"
            value={`${stats.win_rate.toFixed(1)}%`}
            subValue={`${stats.winning_trades}W / ${stats.losing_trades}L`}
            icon={Target}
            positive={stats.win_rate >= 50}
          />
          <StatCard
            label="Avg Win"
            value={formatCurrency(stats.avg_win)}
            icon={TrendingUp}
            positive
          />
          <StatCard
            label="Avg Loss"
            value={formatCurrency(stats.avg_loss)}
            icon={TrendingDown}
            positive={false}
          />
          <StatCard
            label="Profit Factor"
            value={stats.profit_factor.toFixed(2)}
            subValue={stats.profit_factor >= 1.5 ? 'Good' : stats.profit_factor >= 1 ? 'Break-even' : 'Poor'}
            positive={stats.profit_factor >= 1}
          />
        </div>

        {/* Expectancy */}
        <div className="p-4 rounded-lg bg-muted/30">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Expectancy per Trade</span>
            <span className={`font-bold font-mono ${stats.expectancy >= 0 ? 'text-green-500' : 'text-red-500'}`}>
              {stats.expectancy >= 0 ? '+' : ''}{formatCurrency(stats.expectancy)}
            </span>
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Expected average profit/loss per trade based on win rate and avg win/loss
          </div>
        </div>

        {/* Win Rate by Setup */}
        {setupStats.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-2">By Setup Type</h4>
            <div className="space-y-2">
              {setupStats.map(setup => (
                <div key={setup.setup_type} className="flex items-center justify-between text-sm p-2 rounded bg-muted/30">
                  <div>
                    <span className="font-medium">{setup.setup_type}</span>
                    <span className="text-muted-foreground ml-2">({setup.total_trades} trades)</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <Badge variant={setup.win_rate >= 50 ? 'default' : 'secondary'}>
                      {setup.win_rate.toFixed(0)}% WR
                    </Badge>
                    <span className={`font-mono ${setup.total_pnl >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                      {setup.total_pnl >= 0 ? '+' : ''}{formatCurrency(setup.total_pnl)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Trade count */}
        <div className="text-xs text-muted-foreground text-center pt-2 border-t">
          Based on {stats.total_trades} closed trades
        </div>
      </CardContent>
    </Card>
  );
}
