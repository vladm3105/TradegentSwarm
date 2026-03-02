'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Eye, Clock, Plus, Trash2, RefreshCw, Loader2, AlertCircle } from 'lucide-react';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import { listWatchlist, type WatchlistEntry, type WatchlistStats } from '@/lib/api';
import { useChat } from '@/hooks/use-chat';
import { useUIStore } from '@/stores/ui-store';

export default function WatchlistPage() {
  const [filter, setFilter] = useState<'all' | 'high' | 'expiring'>('all');
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [stats, setStats] = useState<WatchlistStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const { sendMessage } = useChat();
  const { setChatPanelOpen } = useUIStore();

  const fetchWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await listWatchlist({
        status: 'active',
        priority: filter === 'high' ? 'high' : undefined,
        limit: 50,
      });

      let filtered = response.entries;
      if (filter === 'expiring') {
        filtered = filtered.filter(e => e.days_until_expiry !== null && e.days_until_expiry <= 7);
      }

      setEntries(filtered);
      setStats(response.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlist');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const handleAddEntry = () => {
    setChatPanelOpen(true);
    sendMessage('add to watchlist');
  };

  const priorityColors: Record<string, string> = {
    high: 'bg-loss/20 text-loss',
    medium: 'bg-yellow-500/20 text-yellow-500',
    low: 'bg-muted text-muted-foreground',
  };

  const highPriorityCount = stats?.by_priority?.high || 0;
  const expiringSoonCount = entries.filter(e => e.days_until_expiry !== null && e.days_until_expiry <= 7).length;

  return (
    <div className="flex-1 space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Watchlist</h1>
          <p className="text-muted-foreground">
            Track potential trades and trigger conditions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchWatchlist} disabled={loading}>
            <RefreshCw className={cn('h-4 w-4 mr-2', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button onClick={handleAddEntry}>
            <Plus className="h-4 w-4 mr-2" />
            Add Entry
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-2 py-4">
            <AlertCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button variant="outline" size="sm" onClick={fetchWatchlist} className="ml-auto">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Total Entries</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold">{stats?.total || 0}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Active</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold text-gain">{stats?.active || 0}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">High Priority</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold text-loss">{highPriorityCount}</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">Expiring Soon</p>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin mt-2" />
            ) : (
              <p className="text-2xl font-bold text-yellow-500">{expiringSoonCount}</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Watchlist */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Active Watchlist
            </CardTitle>
            <Tabs value={filter} onValueChange={(v) => setFilter(v as typeof filter)}>
              <TabsList>
                <TabsTrigger value="all">All</TabsTrigger>
                <TabsTrigger value="high">High Priority</TabsTrigger>
                <TabsTrigger value="expiring">Expiring Soon</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : entries.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Eye className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No watchlist entries found</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={handleAddEntry}>
                Add your first entry
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                      <Eye className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold">{entry.ticker}</span>
                        <Badge className={priorityColors[entry.priority.toLowerCase()] || priorityColors.medium}>
                          {entry.priority.toUpperCase()}
                        </Badge>
                        <Badge variant="outline">{entry.status}</Badge>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        {entry.entry_trigger && (
                          <span className="truncate max-w-[300px]">{entry.entry_trigger}</span>
                        )}
                        {entry.entry_price && (
                          <>
                            <span>•</span>
                            <span>Target: {formatCurrency(entry.entry_price)}</span>
                          </>
                        )}
                      </div>
                      {entry.notes && (
                        <p className="text-sm text-muted-foreground mt-1 truncate max-w-[400px]">
                          {entry.notes}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      {entry.days_until_expiry !== null && (
                        <div className="flex items-center gap-1 text-sm">
                          <Clock className="h-3 w-3" />
                          <span
                            className={cn(
                              entry.days_until_expiry <= 3
                                ? 'text-loss'
                                : entry.days_until_expiry <= 7
                                ? 'text-yellow-500'
                                : 'text-muted-foreground'
                            )}
                          >
                            {entry.days_until_expiry} days left
                          </span>
                        </div>
                      )}
                      {entry.expires_at && (
                        <p className="text-xs text-muted-foreground">
                          Expires {formatDate(entry.expires_at)}
                        </p>
                      )}
                    </div>
                    <Button variant="ghost" size="icon">
                      <Trash2 className="h-4 w-4" />
                    </Button>
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
