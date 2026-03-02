'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { PnLChart, PerformanceChart, WinRateChart } from '@/components/charts';
import { ChartErrorBoundary } from '@/components/error-boundary';
import { cn } from '@/lib/utils';
import { useDashboardPnL } from '@/hooks/use-dashboard';
import { mockDailyPnL, mockTopPerformers, mockAnalysisQuality, mockDashboardStats } from '@/lib/mock-data';

export default function ChartsPage() {
  const [timeframe, setTimeframe] = useState<'7d' | '30d' | '90d'>('30d');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://localhost:3000';

  // Use real data when available, fall back to mock
  const { pnl, isLoading, refetch } = useDashboardPnL(timeframe);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refetch();
    setIsRefreshing(false);
  };

  // Use API data if available, otherwise mock
  const dailyData = pnl?.daily.length ? pnl.daily : mockDailyPnL;

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Charts</h1>
          <p className="text-muted-foreground">
            Performance analytics and visualizations
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Tabs value={timeframe} onValueChange={(v) => setTimeframe(v as typeof timeframe)}>
            <TabsList>
              <TabsTrigger value="7d">7D</TabsTrigger>
              <TabsTrigger value="30d">30D</TabsTrigger>
              <TabsTrigger value="90d">90D</TabsTrigger>
            </TabsList>
          </Tabs>
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={isRefreshing}>
            <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
          </Button>
          <a
            href={grafanaUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            Open Grafana <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* P&L Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {isLoading ? (
          <>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-6 w-24" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-[300px] w-full" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <Skeleton className="h-6 w-32" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-[300px] w-full" />
              </CardContent>
            </Card>
          </>
        ) : (
          <>
            <ChartErrorBoundary>
              <PnLChart
                data={dailyData}
                title="Daily P&L"
                showCumulative={false}
              />
            </ChartErrorBoundary>
            <ChartErrorBoundary>
              <PnLChart
                data={dailyData}
                title="Cumulative Returns"
                showCumulative={true}
              />
            </ChartErrorBoundary>
          </>
        )}
      </div>

      {/* Ticker Performance & Win Rate */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <ChartErrorBoundary>
            <PerformanceChart
              data={mockTopPerformers}
              title="Top Performing Tickers"
            />
          </ChartErrorBoundary>
        </div>
        <ChartErrorBoundary>
          <WinRateChart
            winRate={mockDashboardStats.win_rate}
            totalTrades={mockDashboardStats.total_trades}
          />
        </ChartErrorBoundary>
      </div>

      {/* Analysis Quality */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Gate Pass Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-center h-[200px]">
              <div className="text-center">
                <p className="text-5xl font-bold text-gain">
                  {mockAnalysisQuality.gate_pass_rate}%
                </p>
                <p className="text-muted-foreground mt-2">Analyses passing gate</p>
                <p className="text-sm text-muted-foreground">(Last 30 days)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Recommendation Distribution</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(mockAnalysisQuality.recommendation_distribution).map(
                ([rec, pct]) => (
                  <div key={rec} className="space-y-1">
                    <div className="flex items-center justify-between text-sm">
                      <span>{rec.replace('_', ' ')}</span>
                      <span>{pct}%</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          rec === 'BUY'
                            ? 'bg-gain'
                            : rec === 'AVOID'
                            ? 'bg-loss'
                            : rec === 'WATCH'
                            ? 'bg-blue-500'
                            : 'bg-muted-foreground'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Grafana Embed Placeholder */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">System Metrics (Grafana)</CardTitle>
            <Badge variant="outline">Live</Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] bg-muted/50 rounded-lg flex items-center justify-center">
            <div className="text-center">
              <p className="text-muted-foreground">
                Grafana panels will be embedded here
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Configure NEXT_PUBLIC_GRAFANA_URL to enable
              </p>
              <a
                href={grafanaUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary mt-4 hover:underline"
              >
                Open Grafana Dashboard <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
