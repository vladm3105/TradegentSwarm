import { z } from 'zod';

// Recommendation types
export const RecommendationSchema = z.enum([
  'STRONG_BUY',
  'BUY',
  'WATCH',
  'NO_POSITION',
  'AVOID',
]);
export type Recommendation = z.infer<typeof RecommendationSchema>;

// Gate result types
export const GateResultSchema = z.enum(['PASS', 'MARGINAL', 'FAIL']);
export type GateResult = z.infer<typeof GateResultSchema>;

// Trade direction
export const DirectionSchema = z.enum(['LONG', 'SHORT']);
export type Direction = z.infer<typeof DirectionSchema>;

// Trade status
export const TradeStatusSchema = z.enum(['OPEN', 'CLOSED', 'PARTIAL']);
export type TradeStatus = z.infer<typeof TradeStatusSchema>;

// Trigger types
export const TriggerTypeSchema = z.enum([
  'PRICE_ABOVE',
  'PRICE_BELOW',
  'EVENT',
  'COMBINED',
]);
export type TriggerType = z.infer<typeof TriggerTypeSchema>;

// Priority levels
export const PrioritySchema = z.enum(['HIGH', 'MEDIUM', 'LOW']);
export type Priority = z.infer<typeof PrioritySchema>;

// Chart types
export const ChartTypeSchema = z.enum(['price', 'pnl', 'volume']);
export type ChartType = z.infer<typeof ChartTypeSchema>;

// Timeframe options
export const TimeframeSchema = z.enum(['1h', '6h', '24h', '7d', '30d']);
export type Timeframe = z.infer<typeof TimeframeSchema>;

// Component schemas
export const AnalysisCardPropsSchema = z.object({
  ticker: z.string(),
  recommendation: RecommendationSchema,
  confidence: z.number().min(0).max(100),
  expected_value: z.number(),
  gate_result: GateResultSchema,
  analysis_date: z.string(),
  forecast_valid_until: z.string().optional(),
});
export type AnalysisCardProps = z.infer<typeof AnalysisCardPropsSchema>;

export const PositionCardPropsSchema = z.object({
  ticker: z.string(),
  size: z.number(),
  avg_price: z.number(),
  current_price: z.number(),
  pnl: z.number(),
  pnl_pct: z.number(),
  market_value: z.number(),
});
export type PositionCardProps = z.infer<typeof PositionCardPropsSchema>;

export const TradeCardPropsSchema = z.object({
  ticker: z.string(),
  direction: DirectionSchema,
  entry_price: z.number(),
  current_price: z.number(),
  size: z.number(),
  pnl_pct: z.number(),
  status: TradeStatusSchema,
  entry_date: z.string(),
  exit_date: z.string().nullable().optional(),
});
export type TradeCardProps = z.infer<typeof TradeCardPropsSchema>;

export const WatchlistCardPropsSchema = z.object({
  ticker: z.string(),
  trigger_type: TriggerTypeSchema,
  trigger_value: z.number().nullable().optional(),
  priority: PrioritySchema,
  expires: z.string(),
  notes: z.string().optional(),
});
export type WatchlistCardProps = z.infer<typeof WatchlistCardPropsSchema>;

export const GateResultPropsSchema = z.object({
  ev: z.number(),
  ev_passed: z.boolean(),
  confidence: z.number(),
  confidence_passed: z.boolean(),
  risk_reward: z.number(),
  rr_passed: z.boolean(),
  edge_not_priced: z.boolean(),
  overall: GateResultSchema,
});
export type GateResultProps = z.infer<typeof GateResultPropsSchema>;

export const ScenarioSchema = z.object({
  name: z.string(),
  probability: z.number(),
  return_pct: z.number(),
  description: z.string().optional(),
});
export type Scenario = z.infer<typeof ScenarioSchema>;

export const ScenarioChartPropsSchema = z.object({
  scenarios: z.array(ScenarioSchema),
  weighted_ev: z.number(),
});
export type ScenarioChartProps = z.infer<typeof ScenarioChartPropsSchema>;

export const MetricSchema = z.object({
  label: z.string(),
  value: z.union([z.string(), z.number()]),
  change: z.number().optional(),
});
export type Metric = z.infer<typeof MetricSchema>;

export const MetricsRowPropsSchema = z.object({
  metrics: z.array(MetricSchema),
});
export type MetricsRowProps = z.infer<typeof MetricsRowPropsSchema>;

export const ChartDataPointSchema = z.object({
  date: z.string().optional(),
  time: z.string().optional(),
  value: z.number(),
  label: z.string().optional(),
});
export type ChartDataPoint = z.infer<typeof ChartDataPointSchema>;

export const ChartCardPropsSchema = z.object({
  ticker: z.string(),
  chart_type: ChartTypeSchema,
  data: z.array(ChartDataPointSchema),
  timeframe: z.string().optional(),
});
export type ChartCardProps = z.infer<typeof ChartCardPropsSchema>;

export const ErrorCardPropsSchema = z.object({
  code: z.string(),
  message: z.string(),
  recoverable: z.boolean(),
  retry_action: z.string().nullable().optional(),
});
export type ErrorCardProps = z.infer<typeof ErrorCardPropsSchema>;

export const LoadingCardPropsSchema = z.object({
  message: z.string(),
  progress: z.number().nullable().optional(),
  task_id: z.string().nullable().optional(),
});
export type LoadingCardProps = z.infer<typeof LoadingCardPropsSchema>;

export const TextCardPropsSchema = z.object({
  content: z.string(),
  title: z.string().nullable().optional(),
});
export type TextCardProps = z.infer<typeof TextCardPropsSchema>;

export const TableCardPropsSchema = z.object({
  headers: z.array(z.string()),
  rows: z.array(z.array(z.string())),
  title: z.string().nullable().optional(),
});
export type TableCardProps = z.infer<typeof TableCardPropsSchema>;

export const GrafanaPanelPropsSchema = z.object({
  dashboard_uid: z.string(),
  panel_id: z.number(),
  title: z.string().nullable().optional(),
  timeframe: TimeframeSchema.optional().default('24h'),
  height: z.number().min(200).max(600).optional().default(300),
  theme: z.enum(['light', 'dark']).optional().default('dark'),
});
export type GrafanaPanelProps = z.infer<typeof GrafanaPanelPropsSchema>;

// Component union type
export const A2UIComponentSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('AnalysisCard'), props: AnalysisCardPropsSchema }),
  z.object({ type: z.literal('PositionCard'), props: PositionCardPropsSchema }),
  z.object({ type: z.literal('TradeCard'), props: TradeCardPropsSchema }),
  z.object({ type: z.literal('WatchlistCard'), props: WatchlistCardPropsSchema }),
  z.object({ type: z.literal('GateResult'), props: GateResultPropsSchema }),
  z.object({ type: z.literal('ScenarioChart'), props: ScenarioChartPropsSchema }),
  z.object({ type: z.literal('MetricsRow'), props: MetricsRowPropsSchema }),
  z.object({ type: z.literal('ChartCard'), props: ChartCardPropsSchema }),
  z.object({ type: z.literal('ErrorCard'), props: ErrorCardPropsSchema }),
  z.object({ type: z.literal('LoadingCard'), props: LoadingCardPropsSchema }),
  z.object({ type: z.literal('TextCard'), props: TextCardPropsSchema }),
  z.object({ type: z.literal('TableCard'), props: TableCardPropsSchema }),
  z.object({ type: z.literal('GrafanaPanel'), props: GrafanaPanelPropsSchema }),
]);
export type A2UIComponent = z.infer<typeof A2UIComponentSchema>;

// Full A2UI response schema
export const A2UIResponseSchema = z.object({
  type: z.literal('a2ui'),
  text: z.string(),
  components: z.array(A2UIComponentSchema),
});
export type A2UIResponse = z.infer<typeof A2UIResponseSchema>;

// Validation helper
export function validateA2UIResponse(data: unknown): A2UIResponse | null {
  const result = A2UIResponseSchema.safeParse(data);
  if (result.success) {
    return result.data;
  }
  console.error('A2UI validation error:', result.error);
  return null;
}

// Component type guard
export function isA2UIComponent(data: unknown): data is A2UIComponent {
  return A2UIComponentSchema.safeParse(data).success;
}
