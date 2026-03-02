'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  TrendingUp,
  TrendingDown,
  BarChart3,
  Briefcase,
  Target,
  Clock,
  Activity,
  Eye,
  Loader2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';
import { cn, formatCurrency, formatPercent } from '@/lib/utils';
import { getDashboardStats, type DashboardStats } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface StatCardProps {
  title: string;
  value: string | number;
  subValue?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
  loading?: boolean;
}

function StatCard({
  title,
  value,
  subValue,
  icon,
  trend,
  className,
  loading,
}: StatCardProps) {
  return (
    <Card className={cn('', className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div className="h-4 w-4 text-muted-foreground">{icon}</div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-muted-foreground">Loading...</span>
          </div>
        ) : (
          <>
            <div
              className={cn(
                'text-2xl font-bold tabular-nums',
                trend === 'up' && 'text-gain',
                trend === 'down' && 'text-loss'
              )}
            >
              {value}
            </div>
            {subValue && (
              <p className="text-xs text-muted-foreground mt-1">{subValue}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function QuickActions() {
  const actions = [
    { label: 'Run Scanner', icon: Target, href: '/scanner' },
    { label: 'New Analysis', icon: BarChart3, href: '/analysis' },
    { label: 'View Watchlist', icon: Eye, href: '/watchlist' },
    { label: 'Trade Journal', icon: Briefcase, href: '/trades' },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {actions.map((action) => (
            <a
              key={action.label}
              href={action.href}
              className="flex items-center gap-3 rounded-lg border p-3 hover:bg-accent transition-colors"
            >
              <action.icon className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">{action.label}</span>
            </a>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RecentActivity() {
  const activities = [
    {
      type: 'analysis',
      ticker: 'NVDA',
      action: 'Analysis completed',
      time: '2 hours ago',
      result: 'WATCH',
    },
    {
      type: 'trade',
      ticker: 'AAPL',
      action: 'Position closed',
      time: '5 hours ago',
      result: '+2.3%',
    },
    {
      type: 'watchlist',
      ticker: 'MSFT',
      action: 'Trigger fired',
      time: '1 day ago',
      result: 'Entry signal',
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {activities.map((activity, i) => (
            <div
              key={i}
              className="flex items-center justify-between border-b last:border-0 pb-3 last:pb-0"
            >
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Activity className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-sm font-medium">
                    {activity.ticker} - {activity.action}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {activity.time}
                  </p>
                </div>
              </div>
              <span
                className={cn(
                  'text-sm font-medium',
                  activity.result.startsWith('+') && 'text-gain',
                  activity.result.startsWith('-') && 'text-loss'
                )}
              >
                {activity.result}
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MarketStatus() {
  const [status, setStatus] = useState<{ isOpen: boolean; label: string; next: string }>({
    isOpen: false,
    label: 'Checking...',
    next: '',
  });

  useEffect(() => {
    const checkMarketStatus = () => {
      const now = new Date();
      const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
      const day = et.getDay();
      const hour = et.getHours();
      const minute = et.getMinutes();
      const time = hour * 60 + minute;

      // Market hours: 9:30 AM - 4:00 PM ET, Mon-Fri
      const marketOpen = 9 * 60 + 30; // 9:30 AM
      const marketClose = 16 * 60; // 4:00 PM

      if (day >= 1 && day <= 5 && time >= marketOpen && time < marketClose) {
        setStatus({ isOpen: true, label: 'Market Open', next: 'Closes 4:00 PM ET' });
      } else if (day >= 1 && day <= 5 && time < marketOpen) {
        setStatus({ isOpen: false, label: 'Pre-Market', next: 'Opens 9:30 AM ET' });
      } else if (day >= 1 && day <= 5 && time >= marketClose) {
        setStatus({ isOpen: false, label: 'After Hours', next: 'Opens 9:30 AM ET' });
      } else {
        setStatus({ isOpen: false, label: 'Weekend', next: 'Opens Mon 9:30 AM ET' });
      }
    };

    checkMarketStatus();
    const interval = setInterval(checkMarketStatus, 60000); // Check every minute
    return () => clearInterval(interval);
  }, []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Market Status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <div
            className={cn(
              'h-2 w-2 rounded-full',
              status.isOpen ? 'bg-gain animate-pulse' : 'bg-yellow-500'
            )}
          />
          <span className="text-sm font-medium">{status.label}</span>
        </div>
        <p className="text-xs text-muted-foreground mt-1">{status.next}</p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard stats');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
  }, []);

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            Portfolio overview and trading performance
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchStats}
          disabled={loading}
        >
          <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 py-4">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button variant="outline" size="sm" onClick={fetchStats} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total P&L"
          value={stats ? formatCurrency(stats.total_pnl, { showSign: true }) : '-'}
          subValue={stats ? formatPercent(stats.total_pnl_pct) : undefined}
          icon={!stats || stats.total_pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
          trend={stats ? (stats.total_pnl >= 0 ? 'up' : 'down') : undefined}
          loading={loading}
        />
        <StatCard
          title="Today's P&L"
          value={stats ? formatCurrency(stats.today_pnl, { showSign: true }) : '-'}
          subValue={stats ? formatPercent(stats.today_pnl_pct) : undefined}
          icon={!stats || stats.today_pnl >= 0 ? <TrendingUp /> : <TrendingDown />}
          trend={stats ? (stats.today_pnl >= 0 ? 'up' : 'down') : undefined}
          loading={loading}
        />
        <StatCard
          title="Open Positions"
          value={stats?.open_positions ?? '-'}
          subValue={stats ? formatCurrency(stats.total_market_value) : undefined}
          icon={<Briefcase />}
          loading={loading}
        />
        <StatCard
          title="Win Rate"
          value={stats ? formatPercent(stats.win_rate, { showSign: false }) : '-'}
          subValue={stats ? `${stats.total_trades} total trades` : undefined}
          icon={<Target />}
          trend={stats ? (stats.win_rate >= 60 ? 'up' : stats.win_rate < 50 ? 'down' : 'neutral') : undefined}
          loading={loading}
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Active Analyses"
          value={stats?.active_analyses ?? '-'}
          icon={<BarChart3 />}
          loading={loading}
        />
        <StatCard
          title="Watchlist Items"
          value={stats?.watchlist_count ?? '-'}
          icon={<Eye />}
          loading={loading}
        />
        <MarketStatus />
      </div>

      {/* Actions and Activity */}
      <div className="grid gap-4 md:grid-cols-2">
        <QuickActions />
        <RecentActivity />
      </div>
    </div>
  );
}
