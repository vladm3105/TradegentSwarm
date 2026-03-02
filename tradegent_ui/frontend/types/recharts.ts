/**
 * Recharts tooltip and callback types for proper TypeScript support.
 */

// Generic payload item from Recharts
export interface TooltipPayloadItem<T = Record<string, unknown>> {
  name: string;
  value: number | string;
  dataKey: string;
  payload: T;
  color?: string;
  fill?: string;
  stroke?: string;
}

// Custom tooltip props with proper typing
export interface CustomTooltipProps<T = Record<string, unknown>> {
  active?: boolean;
  payload?: TooltipPayloadItem<T>[];
  label?: string | number;
}

// P&L chart data point
export interface PnLDataPoint {
  date: string;
  pnl: number;
  cumulative?: number;
}

// Performance chart data point
export interface PerformanceDataPoint {
  ticker: string;
  pnl: number;
  pnl_pct: number;
  trades: number;
  win_rate: number;
}

// Scenario chart data point
export interface ScenarioDataPoint {
  name: string;
  probability: number;
  return_pct: number;
  description?: string;
}

// Win rate chart data point
export interface WinRateDataPoint {
  name: string;
  value: number;
}

// XAxis tick formatter callback
export type TickFormatterCallback = (value: string | number, index: number) => string;

// Label list formatter callback
export type LabelFormatterCallback = (value: number) => string;
