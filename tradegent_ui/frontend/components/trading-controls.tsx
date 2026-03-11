'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { AlertTriangle, Play, Pause, Shield, RefreshCw } from 'lucide-react';
import { createLogger } from '@/lib/logger';
import { getSession } from 'next-auth/react';

const log = createLogger('trading-controls');

interface AutomationStatus {
  mode: 'dry_run' | 'paper' | 'live';
  auto_execute: boolean;
  is_paused: boolean;
  circuit_breaker_triggered: boolean;
  circuit_breaker_triggered_at: string | null;
}

async function fetchWithAuth<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const session = await getSession();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (session?.accessToken) {
    headers['Authorization'] = `Bearer ${session.accessToken}`;
  }

  const url = `/api/orchestrator?path=${encodeURIComponent(endpoint)}`;

  const response = await fetch(url, {
    ...options,
    headers: { ...headers, ...options?.headers },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export function TradingControls() {
  const [status, setStatus] = useState<AutomationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchWithAuth<AutomationStatus>('/api/automation/status');
      setStatus(data);
    } catch (err) {
      log.error('Failed to load automation status', { error: String(err) });
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  async function setMode(mode: 'dry_run' | 'paper' | 'live') {
    if (mode === 'live') {
      const confirmed = window.confirm(
        'WARNING: You are about to enable LIVE trading. Real money will be at risk. Continue?'
      );
      if (!confirmed) return;
    }

    setActionLoading(true);
    try {
      await fetchWithAuth('/api/automation/mode', {
        method: 'POST',
        body: JSON.stringify({ mode, confirm: mode === 'live' }),
      });
      await loadStatus();
      log.action('trading_mode_changed', { mode });
    } catch (err) {
      log.error('Failed to change trading mode', { error: String(err) });
      setError(String(err));
    } finally {
      setActionLoading(false);
    }
  }

  async function togglePause() {
    setActionLoading(true);
    try {
      const endpoint = status?.is_paused ? '/api/automation/resume' : '/api/automation/pause';
      await fetchWithAuth(endpoint, { method: 'POST' });
      await loadStatus();
      log.action(status?.is_paused ? 'trading_resumed' : 'trading_paused');
    } catch (err) {
      log.error('Failed to toggle pause', { error: String(err) });
      setError(String(err));
    } finally {
      setActionLoading(false);
    }
  }

  async function resetCircuitBreaker() {
    const confirmed = window.confirm(
      'Are you sure you want to reset the circuit breaker? This will allow trading to resume.'
    );
    if (!confirmed) return;

    setActionLoading(true);
    try {
      await fetchWithAuth('/api/automation/circuit-breaker/reset', { method: 'POST' });
      await loadStatus();
      log.action('circuit_breaker_reset');
    } catch (err) {
      log.error('Failed to reset circuit breaker', { error: String(err) });
      setError(String(err));
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center gap-2">
            <RefreshCw className="h-4 w-4 animate-spin" />
            Loading trading controls...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error && !status) {
    return (
      <Card>
        <CardContent className="p-6 text-red-500">
          Failed to load status: {error}
          <Button type="button" variant="outline" size="sm" className="ml-2" onClick={loadStatus}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!status) {
    return (
      <Card>
        <CardContent className="p-6 text-muted-foreground">
          No automation status available
        </CardContent>
      </Card>
    );
  }

  const modeColors: Record<string, string> = {
    dry_run: 'bg-gray-500',
    paper: 'bg-yellow-500',
    live: 'bg-red-500',
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Trading Controls
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded text-sm">
            {error}
          </div>
        )}

        {/* Circuit Breaker Alert */}
        {status.circuit_breaker_triggered && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded flex items-center gap-2">
            <AlertTriangle className="h-5 w-5" />
            <div className="flex-1">
              <strong>Circuit Breaker Triggered</strong>
              <p className="text-sm">
                Trading halted at {status.circuit_breaker_triggered_at}
              </p>
            </div>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              onClick={resetCircuitBreaker}
              disabled={actionLoading}
            >
              Reset
            </Button>
          </div>
        )}

        {/* Trading Mode */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Trading Mode</label>
          <div className="flex gap-2">
            <Button
              type="button"
              variant={status.mode === 'dry_run' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('dry_run')}
              disabled={actionLoading}
            >
              Dry Run
            </Button>
            <Button
              type="button"
              variant={status.mode === 'paper' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('paper')}
              disabled={actionLoading}
              className={status.mode === 'paper' ? 'bg-yellow-500 hover:bg-yellow-600' : ''}
            >
              Paper
            </Button>
            <Button
              type="button"
              variant={status.mode === 'live' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setMode('live')}
              disabled={actionLoading}
              className={status.mode === 'live' ? 'bg-red-500 hover:bg-red-600' : ''}
            >
              Live
            </Button>
          </div>
        </div>

        {/* Status Badges */}
        <div className="flex gap-2 flex-wrap">
          <Badge className={modeColors[status.mode]}>
            Mode: {status.mode.replace('_', ' ').toUpperCase()}
          </Badge>
          <Badge variant={status.auto_execute ? 'default' : 'secondary'}>
            Auto-Execute: {status.auto_execute ? 'ON' : 'OFF'}
          </Badge>
          <Badge variant={status.is_paused ? 'destructive' : 'default'}>
            {status.is_paused ? 'PAUSED' : 'ACTIVE'}
          </Badge>
        </div>

        {/* Pause/Resume Button */}
        <Button
          type="button"
          variant={status.is_paused ? 'default' : 'secondary'}
          className="w-full"
          onClick={togglePause}
          disabled={actionLoading || status.circuit_breaker_triggered}
        >
          {status.is_paused ? (
            <>
              <Play className="h-4 w-4 mr-2" />
              Resume Trading
            </>
          ) : (
            <>
              <Pause className="h-4 w-4 mr-2" />
              Pause Trading
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
