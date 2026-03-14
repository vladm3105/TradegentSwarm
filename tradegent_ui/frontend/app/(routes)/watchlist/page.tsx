'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Eye,
  Clock,
  Plus,
  RefreshCw,
  Loader2,
  AlertCircle,
  ListPlus,
  Sparkles,
} from 'lucide-react';
import { cn, formatCurrency, formatDate } from '@/lib/utils';
import {
  createWatchlist,
  createWatchlistEntry,
  listWatchlist,
  listWatchlists,
  type CreateWatchlistPayload,
  type CreateWatchlistEntryPayload,
  type WatchlistEntry,
  type WatchlistStats,
  type WatchlistSummary,
} from '@/lib/api';

const priorityColors: Record<string, string> = {
  high: 'bg-loss/20 text-loss',
  medium: 'bg-yellow-500/20 text-yellow-500',
  low: 'bg-muted text-muted-foreground',
};

type EntryFilter = 'all' | 'high' | 'expiring';

export default function WatchlistPage() {
  const [filter, setFilter] = useState<EntryFilter>('all');
  const [selectedWatchlistId, setSelectedWatchlistId] = useState<number | 'all'>('all');
  const [watchlists, setWatchlists] = useState<WatchlistSummary[]>([]);
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [stats, setStats] = useState<WatchlistStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [entryOpen, setEntryOpen] = useState(false);
  const [entryLoading, setEntryLoading] = useState(false);
  const [newWatchlist, setNewWatchlist] = useState<CreateWatchlistPayload>({
    name: '',
    description: '',
    color: '#3b82f6',
    is_pinned: false,
  });
  const [newEntry, setNewEntry] = useState<CreateWatchlistEntryPayload>({
    ticker: '',
    entry_trigger: '',
    priority: 'medium',
    source: 'manual_form',
    notes: '',
  });

  const fetchWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [watchlistsResponse, entriesResponse] = await Promise.all([
        listWatchlists(),
        listWatchlist({
          status: 'active',
          priority: filter === 'high' ? 'high' : undefined,
          watchlistId: selectedWatchlistId === 'all' ? undefined : selectedWatchlistId,
          limit: 100,
        }),
      ]);

      let filteredEntries = entriesResponse.entries;
      if (filter === 'expiring') {
        filteredEntries = filteredEntries.filter(
          (entry) => entry.days_until_expiry !== null && entry.days_until_expiry <= 7,
        );
      }

      setWatchlists(watchlistsResponse.watchlists);
      setEntries(filteredEntries);
      setStats(entriesResponse.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load watchlists');
    } finally {
      setLoading(false);
    }
  }, [filter, selectedWatchlistId]);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const selectedWatchlist =
    selectedWatchlistId === 'all'
      ? null
      : watchlists.find((watchlist) => watchlist.id === selectedWatchlistId) ?? null;

  const handleAddEntry = () => {
    const defaultWatchlistId =
      selectedWatchlistId === 'all' ? watchlists[0]?.id : selectedWatchlistId;

    setNewEntry((current) => ({
      ...current,
      watchlist_id: defaultWatchlistId,
    }));
    setEntryOpen(true);
  };

  const handleCreateWatchlist = async () => {
    if (!newWatchlist.name?.trim()) {
      setError('Watchlist name is required');
      return;
    }

    setCreateLoading(true);
    setError(null);
    try {
      const created = await createWatchlist({
        name: newWatchlist.name.trim(),
        description: newWatchlist.description?.trim() || null,
        color: newWatchlist.color || '#3b82f6',
        is_pinned: newWatchlist.is_pinned ?? false,
      });
      setCreateOpen(false);
      setNewWatchlist({
        name: '',
        description: '',
        color: '#3b82f6',
        is_pinned: false,
      });
      setSelectedWatchlistId(created.id);
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create watchlist');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleCreateEntry = async () => {
    if (!newEntry.ticker?.trim()) {
      setError('Ticker is required');
      return;
    }
    if (!newEntry.entry_trigger?.trim()) {
      setError('Entry trigger is required');
      return;
    }

    setEntryLoading(true);
    setError(null);
    try {
      const payload: CreateWatchlistEntryPayload = {
        ...newEntry,
        ticker: newEntry.ticker.trim().toUpperCase(),
        entry_trigger: newEntry.entry_trigger.trim(),
        expires_at: newEntry.expires_at ? new Date(newEntry.expires_at).toISOString() : null,
      };

      await createWatchlistEntry(payload);
      setEntryOpen(false);
      setNewEntry({
        ticker: '',
        entry_trigger: '',
        priority: 'medium',
        source: 'manual_form',
        notes: '',
      });
      await fetchWatchlist();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create watchlist entry');
    } finally {
      setEntryLoading(false);
    }
  };

  const highPriorityCount = stats?.by_priority?.high || 0;
  const expiringSoonCount = entries.filter(
    (entry) => entry.days_until_expiry !== null && entry.days_until_expiry <= 7,
  ).length;
  const allEntriesCount = watchlists.reduce((sum, watchlist) => sum + watchlist.active_entries, 0);

  return (
    <div className="flex-1 space-y-6 p-6">
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ListPlus className="h-5 w-5" />
              Create Watchlist
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Name</label>
              <Input
                value={newWatchlist.name ?? ''}
                onChange={(event) => setNewWatchlist((current) => ({ ...current, name: event.target.value }))}
                placeholder="Swing Pullbacks"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <Input
                value={newWatchlist.description ?? ''}
                onChange={(event) => setNewWatchlist((current) => ({ ...current, description: event.target.value }))}
                placeholder="Manual list for setups that need a cleaner entry"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Accent Color</label>
              <input
                className="h-10 w-full rounded-md border border-input bg-background px-2"
                type="color"
                value={newWatchlist.color ?? '#3b82f6'}
                onChange={(event) => setNewWatchlist((current) => ({ ...current, color: event.target.value }))}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={createLoading}>
                Cancel
              </Button>
              <Button onClick={handleCreateWatchlist} disabled={createLoading}>
                {createLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                Create
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" />
              Add Watchlist Entry
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Watchlist</label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={newEntry.watchlist_id ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, watchlist_id: Number(event.target.value) || undefined }))}
                >
                  <option value="">No specific list</option>
                  {watchlists.map((watchlist) => (
                    <option key={watchlist.id} value={watchlist.id}>{watchlist.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Ticker</label>
                <Input
                  value={newEntry.ticker ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, ticker: event.target.value.toUpperCase() }))}
                  placeholder="NVDA"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Entry Trigger</label>
              <Input
                value={newEntry.entry_trigger ?? ''}
                onChange={(event) => setNewEntry((current) => ({ ...current, entry_trigger: event.target.value }))}
                placeholder="Price above 960 with strong volume"
              />
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">Entry Price</label>
                <Input
                  type="number"
                  step="0.01"
                  value={newEntry.entry_price ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, entry_price: event.target.value ? Number(event.target.value) : null }))}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Invalidation Price</label>
                <Input
                  type="number"
                  step="0.01"
                  value={newEntry.invalidation_price ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, invalidation_price: event.target.value ? Number(event.target.value) : null }))}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Priority</label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={newEntry.priority ?? 'medium'}
                  onChange={(event) => setNewEntry((current) => ({ ...current, priority: event.target.value as 'high' | 'medium' | 'low' }))}
                >
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Invalidation Rule</label>
                <Input
                  value={newEntry.invalidation ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, invalidation: event.target.value }))}
                  placeholder="Close below 940"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Expires At</label>
                <Input
                  type="datetime-local"
                  value={newEntry.expires_at ?? ''}
                  onChange={(event) => setNewEntry((current) => ({ ...current, expires_at: event.target.value || null }))}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Notes</label>
              <Input
                value={newEntry.notes ?? ''}
                onChange={(event) => setNewEntry((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Reason, catalyst, and what to monitor"
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setEntryOpen(false)} disabled={entryLoading}>
                Cancel
              </Button>
              <Button onClick={handleCreateEntry} disabled={entryLoading}>
                {entryLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />}
                Add Entry
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Watchlists</h1>
          <p className="text-muted-foreground">
            Organize setups by source and keep manual lists separate from scanners and analysis signals.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchWatchlist} disabled={loading}>
            <RefreshCw className={cn('mr-2 h-4 w-4', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button variant="outline" onClick={() => setCreateOpen(true)}>
            <ListPlus className="mr-2 h-4 w-4" />
            Create List
          </Button>
          <Button onClick={handleAddEntry}>
            <Plus className="mr-2 h-4 w-4" />
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

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle className="text-base">Named Lists</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <button
              className={cn(
                'flex w-full items-center justify-between rounded-lg border px-3 py-3 text-left transition-colors',
                selectedWatchlistId === 'all' ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
              )}
              onClick={() => setSelectedWatchlistId('all')}
              type="button"
            >
              <div>
                <p className="font-medium">All Entries</p>
                <p className="text-xs text-muted-foreground">Combined view across every named watchlist</p>
              </div>
              <Badge variant="secondary">{allEntriesCount}</Badge>
            </button>

            {watchlists.map((watchlist) => (
              <button
                key={watchlist.id}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg border px-3 py-3 text-left transition-colors',
                  selectedWatchlistId === watchlist.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/50',
                )}
                onClick={() => setSelectedWatchlistId(watchlist.id)}
                type="button"
              >
                <div className="min-w-0 pr-3">
                  <div className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 rounded-full"
                      style={{ backgroundColor: watchlist.color || '#3b82f6' }}
                    />
                    <p className="truncate font-medium">{watchlist.name}</p>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="capitalize">{watchlist.source_type}</span>
                    {watchlist.is_default && <span>• default</span>}
                    {watchlist.is_pinned && <span>• pinned</span>}
                  </div>
                </div>
                <Badge variant="secondary">{watchlist.active_entries}</Badge>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Selected List</p>
                {loading ? <Loader2 className="mt-2 h-4 w-4 animate-spin" /> : <p className="text-2xl font-bold">{selectedWatchlist?.name || 'All'}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Active Entries</p>
                {loading ? <Loader2 className="mt-2 h-4 w-4 animate-spin" /> : <p className="text-2xl font-bold text-gain">{stats?.active || 0}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">High Priority</p>
                {loading ? <Loader2 className="mt-2 h-4 w-4 animate-spin" /> : <p className="text-2xl font-bold text-loss">{highPriorityCount}</p>}
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-sm text-muted-foreground">Expiring Soon</p>
                {loading ? <Loader2 className="mt-2 h-4 w-4 animate-spin" /> : <p className="text-2xl font-bold text-yellow-500">{expiringSoonCount}</p>}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-lg">
                    <Eye className="h-5 w-5" />
                    {selectedWatchlist?.name || 'All Watchlists'}
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {selectedWatchlist?.description || 'Review active setups, grouped by the list that produced them.'}
                  </p>
                </div>
                <Tabs value={filter} onValueChange={(value) => setFilter(value as EntryFilter)}>
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
                <div className="flex items-center justify-center py-10">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : entries.length === 0 ? (
                <div className="py-10 text-center text-muted-foreground">
                  <Sparkles className="mx-auto mb-4 h-12 w-12 opacity-40" />
                  <p>No entries found for this selection</p>
                  <Button variant="outline" size="sm" className="mt-4" onClick={handleAddEntry}>
                    Add an entry
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {entries.map((entry) => (
                    <div
                      key={entry.id}
                      className="flex flex-col gap-4 rounded-xl border p-4 transition-colors hover:bg-muted/40 lg:flex-row lg:items-center lg:justify-between"
                    >
                      <div className="flex items-start gap-4">
                        <div
                          className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                          style={{ backgroundColor: `${entry.watchlist_color || '#3b82f6'}22` }}
                        >
                          <Eye className="h-5 w-5" style={{ color: entry.watchlist_color || '#3b82f6' }} />
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold tracking-wide">{entry.ticker}</span>
                            <Badge className={priorityColors[entry.priority.toLowerCase()] || priorityColors.medium}>
                              {entry.priority.toUpperCase()}
                            </Badge>
                            <Badge variant="outline">{entry.status}</Badge>
                            {selectedWatchlistId === 'all' && entry.watchlist_name && (
                              <Badge variant="secondary">{entry.watchlist_name}</Badge>
                            )}
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                            {entry.entry_trigger && <span>{entry.entry_trigger}</span>}
                            {entry.entry_price !== null && (
                              <>
                                <span>•</span>
                                <span>Target {formatCurrency(entry.entry_price)}</span>
                              </>
                            )}
                          </div>
                          {entry.notes && (
                            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{entry.notes}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-start gap-2 text-sm lg:items-end">
                        {entry.days_until_expiry !== null && (
                          <div className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            <span
                              className={cn(
                                entry.days_until_expiry <= 3
                                  ? 'text-loss'
                                  : entry.days_until_expiry <= 7
                                    ? 'text-yellow-500'
                                    : 'text-muted-foreground',
                              )}
                            >
                              {entry.days_until_expiry} days left
                            </span>
                          </div>
                        )}
                        {entry.expires_at && (
                          <p className="text-xs text-muted-foreground">Expires {formatDate(entry.expires_at)}</p>
                        )}
                        <p className="text-xs text-muted-foreground">
                          Last analysis {entry.last_analysis_at ? formatDate(entry.last_analysis_at) : 'n/a'}
                        </p>
                        {entry.watchlist_source_type && (
                          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground/80">
                            {entry.watchlist_source_type}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
