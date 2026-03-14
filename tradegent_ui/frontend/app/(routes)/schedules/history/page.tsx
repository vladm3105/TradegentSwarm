'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { listSchedules, getScheduleHistory, type Schedule, type ScheduleRun } from '@/lib/api';
import { ArrowLeft, History, RefreshCw, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

const statusColors: Record<string, string> = {
  success: 'bg-green-500',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  error: 'bg-red-500',
  running: 'bg-yellow-500',
  pending: 'bg-gray-500',
};

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

export default function ScheduleHistoryPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [selectedScheduleId, setSelectedScheduleId] = useState<number | null>(null);
  const [runs, setRuns] = useState<ScheduleRun[]>([]);
  const [loadingSchedules, setLoadingSchedules] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedScheduleName = useMemo(() => {
    return schedules.find((schedule) => schedule.id === selectedScheduleId)?.name || 'Selected Schedule';
  }, [schedules, selectedScheduleId]);

  const loadSchedulesAndDefaultSelection = useCallback(async () => {
    try {
      setLoadingSchedules(true);
      setError(null);

      const data = await listSchedules();
      setSchedules(data);

      if (data.length > 0) {
        const preferred = selectedScheduleId && data.some((schedule) => schedule.id === selectedScheduleId)
          ? selectedScheduleId
          : data[0].id;
        setSelectedScheduleId(preferred);
      } else {
        setSelectedScheduleId(null);
        setRuns([]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingSchedules(false);
    }
  }, [selectedScheduleId]);

  const loadRuns = useCallback(async (scheduleId: number) => {
    try {
      setLoadingRuns(true);
      setError(null);
      const data = await getScheduleHistory(scheduleId, 25);
      setRuns(data.runs);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  useEffect(() => {
    loadSchedulesAndDefaultSelection();
  }, [loadSchedulesAndDefaultSelection]);

  useEffect(() => {
    if (selectedScheduleId != null) {
      loadRuns(selectedScheduleId);
    }
  }, [selectedScheduleId, loadRuns]);

  return (
    <div className="flex-1 space-y-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Schedule History</h1>
          <p className="text-muted-foreground">Review recent execution runs for each configured schedule.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button asChild variant="outline">
            <Link href="/schedules">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Schedules
            </Link>
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              if (selectedScheduleId != null) {
                loadRuns(selectedScheduleId);
              }
            }}
            disabled={loadingSchedules || selectedScheduleId == null || loadingRuns}
          >
            <RefreshCw className={cn('mr-2 h-4 w-4', loadingRuns && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <History className="h-5 w-5" />
            Recent Runs
          </CardTitle>
          <CardDescription>Select a schedule to see its latest execution history.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingSchedules ? (
            <div className="text-sm text-muted-foreground">Loading schedules...</div>
          ) : schedules.length === 0 ? (
            <div className="text-sm text-muted-foreground">No schedules are configured yet.</div>
          ) : (
            <div className="space-y-4">
              <div className="w-full max-w-sm">
                <label className="mb-2 block text-sm font-medium">Schedule</label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={selectedScheduleId ?? ''}
                  onChange={(event) => setSelectedScheduleId(Number(event.target.value))}
                >
                  {schedules.map((schedule) => (
                    <option key={schedule.id} value={schedule.id}>
                      {schedule.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-medium">{selectedScheduleName}</div>
                {loadingRuns ? (
                  <div className="text-sm text-muted-foreground">Loading run history...</div>
                ) : runs.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No runs found for this schedule.</div>
                ) : (
                  runs.map((run) => (
                    <div key={run.id} className="rounded-md border p-3">
                      <div className="flex items-center justify-between gap-2">
                        <Badge className={statusColors[run.status] || 'bg-gray-500'}>{run.status}</Badge>
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Clock className="h-3 w-3" />
                          {formatDuration(run.duration_seconds)}
                        </span>
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">
                        <div>Started: {formatDateTime(run.started_at)}</div>
                        <div>Completed: {formatDateTime(run.completed_at)}</div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {error && <div className="text-sm text-red-500">Error: {error}</div>}
        </CardContent>
      </Card>
    </div>
  );
}