'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Calendar, Play, Pause, Clock, CheckCircle, RefreshCw } from 'lucide-react';
import { createLogger } from '@/lib/logger';
import {
  listSchedules,
  updateSchedule,
  runScheduleNow,
  getScheduleHistory,
  type Schedule,
  type ScheduleRun,
  type ScheduleHistoryResponse,
} from '@/lib/api';

const log = createLogger('schedule-manager');

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return 'Never';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMins = Math.round(diffMs / 60000);

  if (diffMins < 0) {
    const absMins = Math.abs(diffMins);
    if (absMins < 60) return `${absMins}m ago`;
    if (absMins < 1440) return `${Math.round(absMins / 60)}h ago`;
    return `${Math.round(absMins / 1440)}d ago`;
  } else {
    if (diffMins < 60) return `in ${diffMins}m`;
    if (diffMins < 1440) return `in ${Math.round(diffMins / 60)}h`;
    return `in ${Math.round(diffMins / 1440)}d`;
  }
}

const statusColors: Record<string, string> = {
  success: 'bg-green-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  error: 'bg-red-500',
  running: 'bg-yellow-500',
  pending: 'bg-gray-500',
};

export function ScheduleManager() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [expandedScheduleId, setExpandedScheduleId] = useState<number | null>(null);
  const [historyByScheduleId, setHistoryByScheduleId] = useState<Record<number, ScheduleRun[]>>({});
  const [historyLoadingForId, setHistoryLoadingForId] = useState<number | null>(null);
  const [historyErrorById, setHistoryErrorById] = useState<Record<number, string>>({});

  async function loadSchedules() {
    try {
      setLoading(true);
      const data = await listSchedules();
      setSchedules(data);
      setError(null);
    } catch (e) {
      log.error('Failed to load schedules', { error: String(e) });
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadSchedules();
  }, []);

  async function toggleSchedule(id: number, currentEnabled: boolean) {
    setActionLoading(id);
    try {
      await updateSchedule(id, { is_enabled: !currentEnabled });
      await loadSchedules();
      log.action('schedule_toggled', { id, enabled: !currentEnabled });
    } catch (e) {
      log.error('Failed to toggle schedule', { error: String(e) });
    } finally {
      setActionLoading(null);
    }
  }

  async function runNow(id: number) {
    setActionLoading(id);
    try {
      await runScheduleNow(id);
      await loadSchedules();
      log.action('schedule_run_triggered', { id });
    } catch (e) {
      log.error('Failed to run schedule', { error: String(e) });
    } finally {
      setActionLoading(null);
    }
  }

  async function loadHistory(scheduleId: number) {
    try {
      setHistoryLoadingForId(scheduleId);
      setHistoryErrorById((prev) => {
        const copy = { ...prev };
        delete copy[scheduleId];
        return copy;
      });

      const data = await getScheduleHistory(scheduleId);
      setHistoryByScheduleId((prev) => ({
        ...prev,
        [scheduleId]: data.runs,
      }));
    } catch (e) {
      log.error('Failed to load schedule history', { error: String(e), scheduleId });
      setHistoryErrorById((prev) => ({
        ...prev,
        [scheduleId]: String(e),
      }));
    } finally {
      setHistoryLoadingForId(null);
    }
  }

  async function toggleHistory(scheduleId: number) {
    if (expandedScheduleId === scheduleId) {
      setExpandedScheduleId(null);
      return;
    }

    setExpandedScheduleId(scheduleId);
    if (historyByScheduleId[scheduleId] === undefined) {
      await loadHistory(scheduleId);
    }
  }

  function formatDateTime(value: string | null): string {
    if (!value) {
      return 'n/a';
    }
    return new Date(value).toLocaleString();
  }

  function formatDuration(seconds: number | null): string {
    if (seconds == null) {
      return 'n/a';
    }
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    }
    return `${Math.round(seconds / 60)}m`;
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">Loading schedules...</CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="p-6 text-red-500">
          Error: {error}
          <Button type="button" variant="outline" size="sm" className="ml-2" onClick={loadSchedules}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4" />
            Schedule Manager
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={loadSchedules}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {schedules.length === 0 ? (
          <div className="text-muted-foreground text-sm text-center py-4">
            No schedules configured
          </div>
        ) : (
          <div className="space-y-3">
            {schedules.map(schedule => (
              <div
                key={schedule.id}
                className={`p-3 rounded-lg border ${schedule.is_enabled ? 'bg-background' : 'bg-muted/50 opacity-60'}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">{schedule.name}</span>
                      {schedule.last_run_status && (
                        <Badge className={statusColors[schedule.last_run_status] || 'bg-gray-500'}>
                          {schedule.last_run_status}
                        </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1 space-x-3">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {schedule.frequency}
                      </span>
                      <span>Next: {formatRelativeTime(schedule.next_run_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleHistory(schedule.id)}
                      disabled={historyLoadingForId === schedule.id}
                      title="Show run history"
                    >
                      {historyLoadingForId === schedule.id ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Clock className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => runNow(schedule.id)}
                      disabled={!schedule.is_enabled || actionLoading === schedule.id}
                      title="Run now"
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleSchedule(schedule.id, schedule.is_enabled)}
                      disabled={actionLoading === schedule.id}
                      title={schedule.is_enabled ? 'Disable' : 'Enable'}
                    >
                      {schedule.is_enabled ? (
                        <Pause className="h-4 w-4" />
                      ) : (
                        <CheckCircle className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>

                {expandedScheduleId === schedule.id && (
                  <div className="mt-3 border-t pt-3">
                    {historyErrorById[schedule.id] ? (
                      <div className="text-xs text-red-500">
                        Failed to load history: {historyErrorById[schedule.id]}
                      </div>
                    ) : historyLoadingForId === schedule.id ? (
                      <div className="text-xs text-muted-foreground">Loading history...</div>
                    ) : (historyByScheduleId[schedule.id]?.length ?? 0) === 0 ? (
                      <div className="text-xs text-muted-foreground">No recent runs found.</div>
                    ) : (
                      <div className="space-y-2">
                        {(historyByScheduleId[schedule.id] ?? []).slice(0, 5).map((run) => (
                          <div key={run.id} className="rounded-md border p-2 text-xs">
                            <div className="flex items-center justify-between gap-2">
                              <Badge className={statusColors[run.status] || 'bg-gray-500'}>
                                {run.status}
                              </Badge>
                              <span className="text-muted-foreground">{formatDuration(run.duration_seconds)}</span>
                            </div>
                            <div className="mt-1 text-muted-foreground">
                              <div>Started: {formatDateTime(run.started_at)}</div>
                              <div>Completed: {formatDateTime(run.completed_at)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
