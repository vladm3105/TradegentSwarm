'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  TrendingUp,
  TrendingDown,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  ExternalLink,
  BarChart3,
} from 'lucide-react';
import {
  cn,
  formatCurrency,
  formatPercent,
  formatDate,
  getRecommendationClass,
  getGateClass,
  getPnlColor,
} from '@/lib/utils';
import type {
  AnalysisCardProps,
  PositionCardProps,
  TradeCardProps,
  WatchlistCardProps,
  GateResultProps,
  ScenarioChartProps,
  MetricsRowProps,
  ChartCardProps,
  ErrorCardProps,
  LoadingCardProps,
  TextCardProps,
  TableCardProps,
  GrafanaPanelProps,
} from '@/types/a2ui';

// ============================================================================
// AnalysisCard - Stock analysis with recommendation
// ============================================================================
export function AnalysisCard({
  ticker,
  recommendation,
  confidence,
  expected_value,
  gate_result,
  analysis_date,
  forecast_valid_until,
}: AnalysisCardProps) {
  const recClass = getRecommendationClass(recommendation);
  const gateClass = getGateClass(gate_result);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold">{ticker}</CardTitle>
          <Badge className={recClass}>{recommendation.replace('_', ' ')}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Confidence</p>
            <p className="font-semibold">{confidence}%</p>
          </div>
          <div>
            <p className="text-muted-foreground">Expected Value</p>
            <p className={cn('font-semibold', getPnlColor(expected_value))}>
              {formatPercent(expected_value)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Gate Result</p>
            <Badge variant="outline" className={gateClass}>
              {gate_result}
            </Badge>
          </div>
        </div>
        <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
          <span>Analyzed: {formatDate(analysis_date)}</span>
          {forecast_valid_until && (
            <span>Valid until: {formatDate(forecast_valid_until)}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// PositionCard - Portfolio position with P&L
// ============================================================================
export function PositionCard({
  ticker,
  size,
  avg_price,
  current_price,
  pnl,
  pnl_pct,
  market_value,
}: PositionCardProps) {
  const isPositive = pnl >= 0;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold">{ticker}</CardTitle>
          <div className={cn('flex items-center gap-1', getPnlColor(pnl))}>
            {isPositive ? (
              <TrendingUp className="h-4 w-4" />
            ) : (
              <TrendingDown className="h-4 w-4" />
            )}
            <span className="font-semibold">{formatPercent(pnl_pct)}</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Position</p>
            <p className="font-semibold">
              {size} shares @ {formatCurrency(avg_price)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Current Price</p>
            <p className="font-semibold">{formatCurrency(current_price)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">P&L</p>
            <p className={cn('font-semibold', getPnlColor(pnl))}>
              {formatCurrency(pnl, { showSign: true })}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Market Value</p>
            <p className="font-semibold">{formatCurrency(market_value)}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// TradeCard - Trade journal entry
// ============================================================================
export function TradeCard({
  ticker,
  direction,
  entry_price,
  current_price,
  size,
  pnl_pct,
  status,
  entry_date,
  exit_date,
}: TradeCardProps) {
  const statusColors = {
    OPEN: 'bg-blue-500/20 text-blue-500',
    CLOSED: 'bg-gray-500/20 text-gray-500',
    PARTIAL: 'bg-yellow-500/20 text-yellow-500',
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg font-bold">{ticker}</CardTitle>
            <Badge variant="outline" className={direction === 'LONG' ? 'text-gain' : 'text-loss'}>
              {direction}
            </Badge>
          </div>
          <Badge className={statusColors[status]}>{status}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Entry</p>
            <p className="font-semibold">
              {size} @ {formatCurrency(entry_price)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Current/Exit</p>
            <p className="font-semibold">{formatCurrency(current_price)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">P&L</p>
            <p className={cn('font-semibold', getPnlColor(pnl_pct))}>
              {formatPercent(pnl_pct)}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Duration</p>
            <p className="font-semibold text-xs">
              {formatDate(entry_date)} - {exit_date ? formatDate(exit_date) : 'Open'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// WatchlistCard - Watchlist entry with trigger
// ============================================================================
export function WatchlistCard({
  ticker,
  trigger_type,
  trigger_value,
  priority,
  expires,
  notes,
}: WatchlistCardProps) {
  const priorityColors = {
    HIGH: 'bg-loss/20 text-loss',
    MEDIUM: 'bg-yellow-500/20 text-yellow-500',
    LOW: 'bg-muted text-muted-foreground',
  };

  const triggerLabels = {
    PRICE_ABOVE: `Above ${trigger_value ? formatCurrency(trigger_value) : '—'}`,
    PRICE_BELOW: `Below ${trigger_value ? formatCurrency(trigger_value) : '—'}`,
    EVENT: 'Event-based',
    COMBINED: 'Multiple triggers',
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-bold">{ticker}</CardTitle>
          <Badge className={priorityColors[priority]}>{priority}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">Trigger:</span>
          <span className="font-medium">{triggerLabels[trigger_type]}</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <AlertCircle className="h-4 w-4 text-muted-foreground" />
          <span className="text-muted-foreground">Expires:</span>
          <span className="font-medium">{formatDate(expires)}</span>
        </div>
        {notes && (
          <p className="text-sm text-muted-foreground pt-2 border-t">{notes}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// GateResult - Do Nothing Gate with 4 criteria
// ============================================================================
export function GateResult({
  ev,
  ev_passed,
  confidence,
  confidence_passed,
  risk_reward,
  rr_passed,
  edge_not_priced,
  overall,
}: GateResultProps) {
  const gateClass = getGateClass(overall);
  const criteria = [
    { label: 'EV > 5%', value: formatPercent(ev), passed: ev_passed },
    { label: 'Confidence > 60%', value: `${confidence}%`, passed: confidence_passed },
    { label: 'R:R > 2:1', value: `${risk_reward.toFixed(1)}:1`, passed: rr_passed },
    { label: 'Edge Not Priced', value: edge_not_priced ? 'Yes' : 'No', passed: edge_not_priced },
  ];

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Do Nothing Gate</CardTitle>
          <Badge className={gateClass}>{overall}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-3">
          {criteria.map((c) => (
            <div
              key={c.label}
              className={cn(
                'flex items-center gap-2 p-2 rounded-md border',
                c.passed ? 'border-gain/30 bg-gain/5' : 'border-loss/30 bg-loss/5'
              )}
            >
              {c.passed ? (
                <CheckCircle2 className="h-4 w-4 text-gain" />
              ) : (
                <XCircle className="h-4 w-4 text-loss" />
              )}
              <div className="flex-1">
                <p className="text-xs text-muted-foreground">{c.label}</p>
                <p className="text-sm font-medium">{c.value}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// ScenarioChart - Scenario probability bars
// ============================================================================
export function ScenarioChart({ scenarios, weighted_ev }: ScenarioChartProps) {
  const maxProbability = Math.max(...scenarios.map((s) => s.probability));

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">Scenarios</CardTitle>
          <span className={cn('font-semibold', getPnlColor(weighted_ev))}>
            EV: {formatPercent(weighted_ev)}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {scenarios.map((scenario) => (
          <div key={scenario.name} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{scenario.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  {scenario.probability}%
                </span>
                <span className={cn('font-medium', getPnlColor(scenario.return_pct))}>
                  {formatPercent(scenario.return_pct)}
                </span>
              </div>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  scenario.return_pct >= 0 ? 'bg-gain' : 'bg-loss'
                )}
                style={{ width: `${(scenario.probability / maxProbability) * 100}%` }}
              />
            </div>
            {scenario.description && (
              <p className="text-xs text-muted-foreground">{scenario.description}</p>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// MetricsRow - Key-value metrics with change indicators
// ============================================================================
export function MetricsRow({ metrics }: MetricsRowProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {metrics.map((metric) => (
        <Card key={metric.label}>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">{metric.label}</p>
              {metric.change !== undefined && (
                <span className={cn('text-xs font-medium', getPnlColor(metric.change))}>
                  {formatPercent(metric.change)}
                </span>
              )}
            </div>
            <p className="text-2xl font-bold tabular-nums">
              {typeof metric.value === 'number'
                ? metric.value.toLocaleString()
                : metric.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// ChartCard - Price/PnL/volume chart placeholder
// ============================================================================
export function ChartCard({
  ticker,
  chart_type,
  data,
  timeframe,
}: ChartCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            {ticker} - {chart_type.charAt(0).toUpperCase() + chart_type.slice(1)}
          </CardTitle>
          {timeframe && (
            <Badge variant="outline">{timeframe}</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[200px] flex items-center justify-center bg-muted/50 rounded-lg">
          <p className="text-muted-foreground text-sm">
            Chart visualization ({data.length} data points)
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// ErrorCard - Error display with retry action
// ============================================================================
export function ErrorCard({
  code,
  message,
  recoverable,
  retry_action,
}: ErrorCardProps) {
  return (
    <Card className="border-loss/30 bg-loss/5">
      <CardContent className="pt-6">
        <div className="flex items-start gap-4">
          <div className="p-2 rounded-full bg-loss/20">
            <XCircle className="h-5 w-5 text-loss" />
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold">Error</span>
              <Badge variant="outline" className="text-loss border-loss/30">
                {code}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">{message}</p>
            {recoverable && retry_action && (
              <Button variant="outline" size="sm" className="mt-2">
                <RefreshCw className="h-4 w-4 mr-2" />
                {retry_action}
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// LoadingCard - Loading state with progress
// ============================================================================
export function LoadingCard({
  message,
  progress,
  task_id,
}: LoadingCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-primary border-t-transparent" />
            <p className="font-medium">{message}</p>
          </div>
          {progress !== null && progress !== undefined && (
            <div className="space-y-1">
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="text-xs text-muted-foreground text-right">{progress}%</p>
            </div>
          )}
          {task_id && (
            <p className="text-xs text-muted-foreground font-mono">Task: {task_id}</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// TextCard - Markdown content display
// ============================================================================
export function TextCard({ content, title }: TextCardProps) {
  return (
    <Card>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className={title ? '' : 'pt-6'}>
        <div className="prose prose-sm dark:prose-invert max-w-none">
          {/* Simple markdown rendering - can be enhanced with react-markdown */}
          <p className="whitespace-pre-wrap">{content}</p>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// TableCard - Data table with headers
// ============================================================================
export function TableCard({ headers, rows, title }: TableCardProps) {
  return (
    <Card>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className={title ? '' : 'pt-6'}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                {headers.map((header, i) => (
                  <th
                    key={i}
                    className="text-left font-medium text-muted-foreground p-2"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-b last:border-0">
                  {row.map((cell, j) => (
                    <td key={j} className="p-2">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// GrafanaPanel - Embedded Grafana dashboard panel
// ============================================================================
export function GrafanaPanel({
  dashboard_uid,
  panel_id,
  title,
  timeframe = '24h',
  height = 300,
  theme = 'dark',
}: GrafanaPanelProps) {
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || 'http://localhost:3000';

  const timeRanges: Record<string, { from: string; to: string }> = {
    '1h': { from: 'now-1h', to: 'now' },
    '6h': { from: 'now-6h', to: 'now' },
    '24h': { from: 'now-24h', to: 'now' },
    '7d': { from: 'now-7d', to: 'now' },
    '30d': { from: 'now-30d', to: 'now' },
  };

  const range = timeRanges[timeframe] || timeRanges['24h'];
  const embedUrl = `${grafanaUrl}/d-solo/${dashboard_uid}?orgId=1&panelId=${panel_id}&from=${range.from}&to=${range.to}&theme=${theme}`;

  return (
    <Card>
      {title && (
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">{title}</CardTitle>
            <a
              href={`${grafanaUrl}/d/${dashboard_uid}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
            >
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </CardHeader>
      )}
      <CardContent className={title ? '' : 'pt-6'}>
        <iframe
          src={embedUrl}
          width="100%"
          height={height}
          frameBorder="0"
          className="rounded-lg"
          title={title || `Grafana Panel ${panel_id}`}
        />
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Component Registry - Maps type strings to components
// ============================================================================
export const componentRegistry: Record<
  string,
  React.ComponentType<Record<string, unknown>>
> = {
  AnalysisCard: AnalysisCard as React.ComponentType<Record<string, unknown>>,
  PositionCard: PositionCard as React.ComponentType<Record<string, unknown>>,
  TradeCard: TradeCard as React.ComponentType<Record<string, unknown>>,
  WatchlistCard: WatchlistCard as React.ComponentType<Record<string, unknown>>,
  GateResult: GateResult as React.ComponentType<Record<string, unknown>>,
  ScenarioChart: ScenarioChart as React.ComponentType<Record<string, unknown>>,
  MetricsRow: MetricsRow as React.ComponentType<Record<string, unknown>>,
  ChartCard: ChartCard as React.ComponentType<Record<string, unknown>>,
  ErrorCard: ErrorCard as React.ComponentType<Record<string, unknown>>,
  LoadingCard: LoadingCard as React.ComponentType<Record<string, unknown>>,
  TextCard: TextCard as React.ComponentType<Record<string, unknown>>,
  TableCard: TableCard as React.ComponentType<Record<string, unknown>>,
  GrafanaPanel: GrafanaPanel as React.ComponentType<Record<string, unknown>>,
};
