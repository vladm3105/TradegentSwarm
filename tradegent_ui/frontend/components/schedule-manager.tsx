'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Calendar, Play, Pause, Clock, CheckCircle, RefreshCw, Plus, Pencil, X, Save } from 'lucide-react';
import { createLogger } from '@/lib/logger';
import { toast } from '@/hooks/use-toast';
import {
  listSchedules,
  createSchedule,
  updateSchedule,
  enableSchedule,
  disableSchedule,
  runScheduleNow,
  getScheduleHistory,
  type Schedule,
  type ScheduleRun,
  type CreateSchedulePayload,
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

type EditableSchedulePayload = Omit<
  CreateSchedulePayload,
  'time_of_day' | 'day_of_week' | 'interval_minutes'
> & {
  time_of_day?: string | null;
  day_of_week?: string | null;
  interval_minutes?: number | null;
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
  const [showCreate, setShowCreate] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [editingScheduleId, setEditingScheduleId] = useState<number | null>(null);
  const [editLoading, setEditLoading] = useState(false);

  const [createForm, setCreateForm] = useState<CreateSchedulePayload>({
    name: '',
    task_type: 'run_all_scanners',
    frequency: 'daily',
    is_enabled: true,
    time_of_day: '09:30',
  });

  const [editForm, setEditForm] = useState<CreateSchedulePayload>({
    name: '',
    task_type: 'run_all_scanners',
    frequency: 'daily',
    is_enabled: true,
    time_of_day: '09:30',
  });

  const dayOptions = [
    { value: 'mon', label: 'Monday' },
    { value: 'tue', label: 'Tuesday' },
    { value: 'wed', label: 'Wednesday' },
    { value: 'thu', label: 'Thursday' },
    { value: 'fri', label: 'Friday' },
    { value: 'sat', label: 'Saturday' },
    { value: 'sun', label: 'Sunday' },
  ];

  const taskTypeOptions = [
    'analyze_stock',
    'analyze_watchlist',
    'run_scanner',
    'run_all_scanners',
    'pipeline',
    'portfolio_review',
    'postmortem',
    'custom',
  ];

  function toTimeInput(value: string | null | undefined): string {
    if (!value) return '';
    return value.length >= 5 ? value.slice(0, 5) : value;
  }

  function buildSchedulePayload(form: CreateSchedulePayload): CreateSchedulePayload {
    const payload: CreateSchedulePayload = {
      name: (form.name || '').trim(),
      task_type: form.task_type || 'run_all_scanners',
      frequency: form.frequency || 'daily',
      is_enabled: form.is_enabled ?? true,
    };

    if (payload.frequency === 'daily' || payload.frequency === 'weekly') {
      if (form.time_of_day) {
        payload.time_of_day = form.time_of_day;
      }
    }

    if (payload.frequency === 'weekly' && form.day_of_week) {
      payload.day_of_week = form.day_of_week;
    }

    if (payload.frequency === 'interval' && form.interval_minutes) {
      payload.interval_minutes = form.interval_minutes;
    }

    return payload;
  }

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
      if (currentEnabled) {
        await disableSchedule(id);
      } else {
        await enableSchedule(id);
      }
      await loadSchedules();
      toast({
        title: currentEnabled ? 'Schedule disabled' : 'Schedule enabled',
        description: `Schedule #${id} is now ${currentEnabled ? 'disabled' : 'enabled'}.`,
      });
      log.action('schedule_toggled', { id, enabled: !currentEnabled });
    } catch (e) {
      setError(String(e));
      toast({
        title: 'Failed to update schedule',
        description: String(e),
      });
      log.error('Failed to toggle schedule', { error: String(e) });
    } finally {
      setActionLoading(null);
    }
  }

  async function createNewSchedule() {
    setCreateLoading(true);
    setError(null);
    try {
      const payload = buildSchedulePayload(createForm);
      if (!payload.name) {
        throw new Error('Schedule name is required');
      }
      await createSchedule(payload);
      setShowCreate(false);
      setCreateForm({
        name: '',
        task_type: 'run_all_scanners',
        frequency: 'daily',
        is_enabled: true,
        time_of_day: '09:30',
      });
      await loadSchedules();
      log.action('schedule_created', { name: payload.name });
    } catch (e) {
      setError(String(e));
      log.error('Failed to create schedule', { error: String(e) });
    } finally {
      setCreateLoading(false);
    }
  }

  function startEdit(schedule: Schedule) {
    setEditingScheduleId(schedule.id);
    setEditForm({
      name: schedule.name,
      task_type: schedule.task_type,
      frequency: schedule.frequency,
      is_enabled: schedule.is_enabled,
      time_of_day: toTimeInput(schedule.time_of_day),
      day_of_week: schedule.day_of_week || undefined,
      interval_minutes: schedule.interval_minutes || undefined,
    });
  }

  async function saveEdit(scheduleId: number) {
    setEditLoading(true);
    setError(null);
    try {
      const payload = buildSchedulePayload(editForm) as EditableSchedulePayload;

      if (payload.frequency === 'daily') {
        payload.day_of_week = null;
        payload.interval_minutes = null;
      }
      if (payload.frequency === 'weekly') {
        payload.interval_minutes = null;
      }
      if (payload.frequency === 'interval') {
        payload.time_of_day = null;
        payload.day_of_week = null;
      }

      await updateSchedule(scheduleId, payload);
      setEditingScheduleId(null);
      await loadSchedules();
      log.action('schedule_updated', { scheduleId });
    } catch (e) {
      setError(String(e));
      log.error('Failed to update schedule', { error: String(e), scheduleId });
    } finally {
      setEditLoading(false);
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
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={loadSchedules}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {showCreate && (
          <div className="mb-4 rounded-lg border p-3 space-y-3">
            <div className="grid gap-2 md:grid-cols-2">
              <Input
                placeholder="Schedule name"
                value={createForm.name || ''}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, name: e.target.value }))}
              />
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={createForm.task_type}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, task_type: e.target.value }))}
              >
                {taskTypeOptions.map((taskType) => (
                  <option key={taskType} value={taskType}>{taskType}</option>
                ))}
              </select>
            </div>

            <div className="grid gap-2 md:grid-cols-3">
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={createForm.frequency}
                onChange={(e) => setCreateForm((prev) => ({ ...prev, frequency: e.target.value, day_of_week: undefined, interval_minutes: undefined }))}
              >
                <option value="daily">daily</option>
                <option value="weekly">weekly</option>
                <option value="interval">interval</option>
              </select>

              {(createForm.frequency === 'daily' || createForm.frequency === 'weekly') && (
                <Input
                  type="time"
                  value={createForm.time_of_day || ''}
                  onChange={(e) => setCreateForm((prev) => ({ ...prev, time_of_day: e.target.value }))}
                />
              )}

              {createForm.frequency === 'weekly' && (
                <select
                  className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                  value={createForm.day_of_week || 'mon'}
                  onChange={(e) => setCreateForm((prev) => ({ ...prev, day_of_week: e.target.value }))}
                >
                  {dayOptions.map((day) => (
                    <option key={day.value} value={day.value}>{day.label}</option>
                  ))}
                </select>
              )}

              {createForm.frequency === 'interval' && (
                <Input
                  type="number"
                  min={1}
                  placeholder="Interval minutes"
                  value={createForm.interval_minutes || ''}
                  onChange={(e) => setCreateForm((prev) => ({ ...prev, interval_minutes: e.target.value ? Number(e.target.value) : undefined }))}
                />
              )}
            </div>

            <div className="flex justify-end">
              <Button type="button" size="sm" onClick={createNewSchedule} disabled={createLoading}>
                {createLoading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                Create Schedule
              </Button>
            </div>
          </div>
        )}

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
                      <Badge variant={schedule.is_enabled ? 'default' : 'secondary'}>
                        {schedule.is_enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
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
                      <span>Task: {schedule.task_type}</span>
                      <span>Last run: {formatRelativeTime(schedule.last_run_at)}</span>
                      <span>Next: {formatRelativeTime(schedule.next_run_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => startEdit(schedule)}
                      title="Edit schedule"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
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
                      variant={schedule.is_enabled ? 'outline' : 'default'}
                      size="sm"
                      onClick={() => toggleSchedule(schedule.id, schedule.is_enabled)}
                      disabled={actionLoading === schedule.id}
                      title={schedule.is_enabled ? 'Disable' : 'Enable'}
                    >
                      {actionLoading === schedule.id ? (
                        <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                      ) : schedule.is_enabled ? (
                        <Pause className="h-4 w-4 mr-1" />
                      ) : (
                        <CheckCircle className="h-4 w-4 mr-1" />
                      )}
                      {schedule.is_enabled ? 'Disable' : 'Enable'}
                    </Button>
                  </div>
                </div>

                {editingScheduleId === schedule.id && (
                  <div className="mt-3 border-t pt-3 space-y-3">
                    <div className="grid gap-2 md:grid-cols-2">
                      <Input
                        value={editForm.name || ''}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, name: e.target.value }))}
                        placeholder="Schedule name"
                      />
                      <select
                        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                        value={editForm.task_type}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, task_type: e.target.value }))}
                      >
                        {taskTypeOptions.map((taskType) => (
                          <option key={taskType} value={taskType}>{taskType}</option>
                        ))}
                      </select>
                    </div>

                    <div className="grid gap-2 md:grid-cols-3">
                      <select
                        className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                        value={editForm.frequency}
                        onChange={(e) => setEditForm((prev) => ({ ...prev, frequency: e.target.value, day_of_week: undefined, interval_minutes: undefined }))}
                      >
                        <option value="daily">daily</option>
                        <option value="weekly">weekly</option>
                        <option value="interval">interval</option>
                      </select>

                      {(editForm.frequency === 'daily' || editForm.frequency === 'weekly') && (
                        <Input
                          type="time"
                          value={editForm.time_of_day || ''}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, time_of_day: e.target.value }))}
                        />
                      )}

                      {editForm.frequency === 'weekly' && (
                        <select
                          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                          value={editForm.day_of_week || 'mon'}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, day_of_week: e.target.value }))}
                        >
                          {dayOptions.map((day) => (
                            <option key={day.value} value={day.value}>{day.label}</option>
                          ))}
                        </select>
                      )}

                      {editForm.frequency === 'interval' && (
                        <Input
                          type="number"
                          min={1}
                          placeholder="Interval minutes"
                          value={editForm.interval_minutes || ''}
                          onChange={(e) => setEditForm((prev) => ({ ...prev, interval_minutes: e.target.value ? Number(e.target.value) : undefined }))}
                        />
                      )}
                    </div>

                    <div className="flex justify-end gap-2">
                      <Button type="button" size="sm" variant="outline" onClick={() => setEditingScheduleId(null)}>
                        <X className="h-4 w-4 mr-2" />
                        Cancel
                      </Button>
                      <Button type="button" size="sm" onClick={() => saveEdit(schedule.id)} disabled={editLoading}>
                        {editLoading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                        Save
                      </Button>
                    </div>
                  </div>
                )}

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
