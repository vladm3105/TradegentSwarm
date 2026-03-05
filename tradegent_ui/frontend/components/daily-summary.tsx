'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Calendar,
  TrendingUp,
  TrendingDown,
  Target,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { getSession } from 'next-auth/react';
import { createLogger } from '@/lib/logger';

const log = createLogger('daily-summary');
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

interface DailySummary {
  date: string;
  trading: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    gross_pnl: number;
    net_pnl: number;
    fees: number;
    largest_win: number;
    largest_loss: number;
  };
  orders: {
    submitted: number;
    filled: number;
    cancelled: number;
    rejected: number;
  };
  alerts: {
    triggered: number;
    stop_losses_hit: number;
    targets_hit: number;
  };
  system: {
    circuit_breaker_triggered: boolean;
    max_drawdown_reached: number;
    api_errors: number;
  };
}

async function fetchWithAuth<T>(endpoint: string): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const response = await fetch(`${API_URL}${endpoint}`, { headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

function formatCurrency(value: number): string {
  const formatted = Math.abs(value).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  });
  return value < 0 ? `-${formatted}` : formatted;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

export function DailySummary() {
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().split('T')[0]
  );

  async function loadSummary(date: string) {
    try {
      setLoading(true);
      const data = await fetchWithAuth<DailySummary>(`/api/analytics/daily-summary?date=${date}`);
      setSummary(data);
      setError(null);
    } catch (e) {
      log.error('Failed to load daily summary', { error: String(e) });
      // Create mock data if API not ready
      setSummary({
        date,
        trading: {
          total_trades: 0,
          winning_trades: 0,
          losing_trades: 0,
          win_rate: 0,
          gross_pnl: 0,
          net_pnl: 0,
          fees: 0,
          largest_win: 0,
          largest_loss: 0,
        },
        orders: { submitted: 0, filled: 0, cancelled: 0, rejected: 0 },
        alerts: { triggered: 0, stop_losses_hit: 0, targets_hit: 0 },
        system: { circuit_breaker_triggered: false, max_drawdown_reached: 0, api_errors: 0 },
      });
      setError(null); // Don't show error for missing data
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSummary(selectedDate);
  }, [selectedDate]);

  function changeDate(days: number) {
    const current = new Date(selectedDate);
    current.setDate(current.getDate() + days);
    const today = new Date();
    if (current <= today) {
      setSelectedDate(current.toISOString().split('T')[0]);
    }
  }

  const isToday = selectedDate === new Date().toISOString().split('T')[0];

  if (loading && !summary) {
    return (
      <Card>
        <CardContent className="p-6">Loading daily summary...</CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Daily Summary
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => changeDate(-1)}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm font-normal min-w-[100px] text-center">
              {formatDate(selectedDate)}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => changeDate(1)}
              disabled={isToday}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => loadSummary(selectedDate)}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="text-red-500 text-sm mb-4">{error}</div>
        )}

        {summary && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* P&L Card */}
            <div className="p-4 rounded-lg border bg-background">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                {summary.trading.net_pnl >= 0 ? (
                  <TrendingUp className="h-4 w-4 text-green-500" />
                ) : (
                  <TrendingDown className="h-4 w-4 text-red-500" />
                )}
                Net P&L
              </div>
              <div className={`text-2xl font-bold ${
                summary.trading.net_pnl >= 0 ? 'text-green-500' : 'text-red-500'
              }`}>
                {formatCurrency(summary.trading.net_pnl)}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                Gross: {formatCurrency(summary.trading.gross_pnl)} | Fees: {formatCurrency(summary.trading.fees)}
              </div>
            </div>

            {/* Win Rate Card */}
            <div className="p-4 rounded-lg border bg-background">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <Target className="h-4 w-4" />
                Win Rate
              </div>
              <div className="text-2xl font-bold">
                {summary.trading.win_rate.toFixed(1)}%
              </div>
              <div className="text-xs text-muted-foreground mt-1 flex gap-3">
                <span className="text-green-500">W: {summary.trading.winning_trades}</span>
                <span className="text-red-500">L: {summary.trading.losing_trades}</span>
                <span>Total: {summary.trading.total_trades}</span>
              </div>
            </div>

            {/* Orders Card */}
            <div className="p-4 rounded-lg border bg-background">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <CheckCircle className="h-4 w-4 text-blue-500" />
                Orders
              </div>
              <div className="text-2xl font-bold">
                {summary.orders.filled}/{summary.orders.submitted}
              </div>
              <div className="text-xs text-muted-foreground mt-1 flex gap-3">
                <span className="text-yellow-500">Cancelled: {summary.orders.cancelled}</span>
                <span className="text-red-500">Rejected: {summary.orders.rejected}</span>
              </div>
            </div>

            {/* Alerts Card */}
            <div className="p-4 rounded-lg border bg-background">
              <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                <AlertTriangle className="h-4 w-4 text-yellow-500" />
                Alerts
              </div>
              <div className="text-2xl font-bold">
                {summary.alerts.triggered}
              </div>
              <div className="text-xs text-muted-foreground mt-1 flex gap-3">
                <span className="text-red-500">Stops: {summary.alerts.stop_losses_hit}</span>
                <span className="text-green-500">Targets: {summary.alerts.targets_hit}</span>
              </div>
            </div>
          </div>
        )}

        {/* System Status */}
        {summary && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">Circuit Breaker:</span>
                {summary.system.circuit_breaker_triggered ? (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <XCircle className="h-3 w-3" />
                    Triggered
                  </Badge>
                ) : (
                  <Badge variant="outline" className="flex items-center gap-1 text-green-500">
                    <CheckCircle className="h-3 w-3" />
                    Clear
                  </Badge>
                )}
              </div>

              {summary.system.max_drawdown_reached > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Max Drawdown:</span>
                  <span className="text-red-500 font-mono">
                    {formatCurrency(summary.system.max_drawdown_reached)}
                  </span>
                </div>
              )}

              {summary.system.api_errors > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">API Errors:</span>
                  <Badge variant="destructive">{summary.system.api_errors}</Badge>
                </div>
              )}

              {/* Extreme values */}
              {(summary.trading.largest_win > 0 || summary.trading.largest_loss < 0) && (
                <>
                  {summary.trading.largest_win > 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">Best:</span>
                      <span className="text-green-500 font-mono">
                        +{formatCurrency(summary.trading.largest_win)}
                      </span>
                    </div>
                  )}
                  {summary.trading.largest_loss < 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-muted-foreground">Worst:</span>
                      <span className="text-red-500 font-mono">
                        {formatCurrency(summary.trading.largest_loss)}
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
