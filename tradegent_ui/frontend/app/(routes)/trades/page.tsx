'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Briefcase, TrendingUp, TrendingDown, RefreshCw, Loader2, AlertCircle } from 'lucide-react';
import { cn, formatCurrency, formatPercent, getPnlColor } from '@/lib/utils';
import { listTrades, type TradeSummary, type TradeStats } from '@/lib/api';
import { useChat } from '@/hooks/use-chat';
import { useUIStore } from '@/stores/ui-store';

export default function TradesPage() {
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');
  const [trades, setTrades] = useState<TradeSummary[]>([]);
  const [stats, setStats] = useState<TradeStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sendMessage } = useChat();
  const { setChatPanelOpen } = useUIStore();

  const fetchTrades = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listTrades({
        status: filter === 'all' ? undefined : filter,
        limit: 50,
      });
      setTrades(response.trades);
      setStats(response.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load trades');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  const handleLogTrade = () => {
    setChatPanelOpen(true);
    sendMessage('log trade');
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Trade Journal</h1>
          <p className="text-muted-foreground">Track and analyze your trades</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchTrades} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button onClick={handleLogTrade}>
            <Briefcase className="h-4 w-4 mr-2" />
            Log Trade
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 py-4">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button variant="outline" size="sm" onClick={fetchTrades} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total P&L</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <>
                <p className={cn('text-2xl font-bold', getPnlColor(stats?.total_pnl || 0))}>
                  {formatCurrency(stats?.total_pnl || 0, { showSign: true })}
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Win Rate</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <>
                <p className="text-2xl font-bold">{(stats?.win_rate || 0).toFixed(1)}%</p>
                <p className="text-sm text-muted-foreground">
                  {stats?.total_trades || 0} trades
                </p>
              </>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Avg Win</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold text-gain">
                {formatCurrency(stats?.avg_win || 0)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Avg Loss</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold text-loss">
                {formatCurrency(stats?.avg_loss || 0)}
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Trades List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Trade History</CardTitle>
            <Tabs value={filter} onValueChange={(v) => setFilter(v as typeof filter)}>
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="open">Open ({stats?.open_trades || 0})</TabsTrigger>
                <TabsTrigger value="closed">Closed ({stats?.closed_trades || 0})</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : trades.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Briefcase className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No trades found</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={handleLogTrade}>
                Log your first trade
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {trades.map((trade) => (
                <div
                  key={trade.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div
                      className={cn(
                        'h-10 w-10 rounded-full flex items-center justify-center',
                        (trade.pnl_dollars || 0) >= 0 ? 'bg-gain/10' : 'bg-loss/10'
                      )}
                    >
                      {(trade.pnl_dollars || 0) >= 0 ? (
                        <TrendingUp className="h-5 w-5 text-gain" />
                      ) : (
                        <TrendingDown className="h-5 w-5 text-loss" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{trade.ticker}</span>
                        {trade.direction && (
                          <Badge
                            variant="outline"
                            className={trade.direction === 'LONG' ? 'text-gain' : 'text-loss'}
                          >
                            {trade.direction}
                          </Badge>
                        )}
                        <Badge
                          variant="outline"
                          className={
                            trade.status === 'open'
                              ? 'bg-blue-500/20 text-blue-500'
                              : trade.status === 'closed'
                              ? 'bg-muted'
                              : 'bg-yellow-500/20 text-yellow-600'
                          }
                        >
                          {trade.status.toUpperCase()}
                        </Badge>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {trade.entry_size} shares @ {formatCurrency(trade.entry_price)}
                        {trade.exit_price && ` → ${formatCurrency(trade.exit_price)}`}
                        <span className="mx-2">•</span>
                        {formatDate(trade.entry_date)}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    {trade.pnl_dollars !== null ? (
                      <>
                        <p className={cn('font-semibold', getPnlColor(trade.pnl_dollars))}>
                          {formatCurrency(trade.pnl_dollars, { showSign: true })}
                        </p>
                        {trade.pnl_pct !== null && (
                          <p className={cn('text-sm', getPnlColor(trade.pnl_pct))}>
                            {formatPercent(trade.pnl_pct)}
                          </p>
                        )}
                      </>
                    ) : (
                      <p className="text-muted-foreground">-</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
