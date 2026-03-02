/**
 * Type definitions for stock analysis data
 * Matches the v2.6+ YAML schema from tradegent_knowledge
 */

export interface Scenario {
  probability: number;
  description: string;
  target_price: number;
  return_pct: number;
  timeline_days: number;
  key_driver: string;
}

export interface ScenarioAnalysis {
  strong_bull: Scenario;
  base_bull: Scenario;
  base_bear: Scenario;
  strong_bear: Scenario;
  expected_value: number;
}

export interface CaseArgument {
  argument: string;
  score: number;
  evidence: string;
  counter: string;
  counter_strength: number;
}

export interface CaseAnalysis {
  strength: number;
  arguments: CaseArgument[];
  summary: string;
  strongest_argument: string;
}

export interface ComparablePeer {
  ticker: string;
  name: string;
  pe_forward: number;
  ps_ratio: number;
  ev_ebitda: number;
  revenue_growth_pct: number;
  market_cap_b: number | null;
}

export interface ComparableCompanies {
  peers: ComparablePeer[];
  sector_median_pe: number | null;
  sector_median_ps: number | null;
  sector_median_ev_ebitda: number | null;
  valuation_position: 'discount' | 'premium' | 'inline';
  discount_premium_pct: number;
  valuation_notes: string;
}

export interface LiquidityAnalysis {
  adv_shares: number;
  adv_dollars: number;
  adv_percentile: number;
  bid_ask_spread_pct: number;
  spread_environment: string;
  slippage_estimate_pct: number;
  liquidity_score: number;
  execution_notes: string;
}

export interface BiasCheck {
  recency_bias: { detected: boolean; severity: string };
  confirmation_bias: { detected: boolean; severity: string };
  anchoring: { detected: boolean; severity: string };
  fomo: { detected: boolean; severity: string };
  overconfidence: { detected: boolean; severity: string };
  bias_summary: string;
}

export interface DoNothingGate {
  ev_threshold: number;
  ev_actual: number;
  ev_passes: boolean;
  confidence_threshold: number;
  confidence_actual: number;
  confidence_passes: boolean;
  rr_threshold: number;
  rr_actual: number;
  rr_passes: boolean;
  edge_exists: boolean;
  edge_description: string;
  gates_passed: number;
  gate_result: 'PASS' | 'MARGINAL' | 'FAIL';
  gate_reasoning: string;
}

export interface PriceAlert {
  price: number;
  direction: 'above' | 'below';
  significance: string;
  action_if_triggered: string;
  alert_active: boolean;
  tag?: string;
}

export interface EventAlert {
  event: string;
  date: string;
  action: string;
}

export interface AlertLevels {
  price_alerts: PriceAlert[];
  event_alerts: EventAlert[];
  post_event_review: string;
}

export interface FalsificationCriteria {
  condition: string;
  current_value: string;
  threshold: string;
}

export interface Falsification {
  criteria: FalsificationCriteria[];
  thesis_invalid_if: string;
  review_triggers: string[];
}

export interface ThreatAssessment {
  primary_concern: string;
  structural_threat: { exists: boolean; description: string };
  cyclical_weakness: { exists: boolean };
  threat_summary: string;
}

export interface AlternativeStrategy {
  strategy: string;
  trigger: string;
  entry_zone: string;
  rationale: string;
}

export interface TradePlan {
  entry_criteria: {
    primary_trigger: string;
    alternative_trigger: string;
  };
  tranche_1?: {
    allocation_pct: number;
    entry_zone_low: number;
    entry_zone_high: number;
    trigger: string;
  };
  stop_loss?: number;
  target_1?: number;
  target_2?: number;
}

export interface Sentiment {
  analyst: {
    buy: number;
    hold: number;
    sell: number;
    avg_target: number;
    implied_upside_pct: number;
  };
  short_interest: {
    pct_float: number;
    days_to_cover: number;
    trend: string;
  };
  options: {
    put_call_ratio: number;
    iv_percentile: number;
    iv_rank: number;
    unusual_flow: string;
  };
}

export interface Fundamentals {
  valuation: {
    pe_ratio: number;
    pe_forward: number;
    ps_ratio: number;
    ev_ebitda: number;
  };
  growth: {
    revenue_growth_yoy: number;
    earnings_growth_yoy: number;
  };
  quality: {
    profit_margin: number;
    operating_margin: number;
    roe: number;
    debt_to_equity: number;
    cash_position_b: number;
  };
}

export interface Setup {
  fifty_two_week_high: number;
  fifty_two_week_low: number;
  distance_from_ath_pct: number;
  distance_from_52w_low_pct: number;
  market_cap_b: number;
  pe_ttm: number;
  pe_forward: number;
  next_earnings_date: string;
  days_to_earnings: number;
  ytd_return_pct: number;
}

export interface MetaLearning {
  pattern_identified?: string;
  similar_setup?: string;
  new_rule?: {
    rule: string;
    validation_status: string;
  };
}

export interface PassReasoning {
  applicable: boolean;
  primary_reason: string;
  reasons: Array<{ reason: string; impact: 'H' | 'M' | 'L' }>;
  summary: string;
}

export interface AnalysisDetail {
  // Meta
  _meta: {
    id: string;
    type: string;
    version: string;
    created: string;
    status: string;
  };

  // Core identification
  ticker: string;
  current_price: number;
  analysis_date: string;
  analysis_type: string;

  // Setup data
  setup: Setup;

  // Catalyst
  catalyst: {
    type: string;
    description: string;
    specificity: string;
    timing: string;
    catalyst_score: number;
    reasoning: string;
  };

  // Market environment
  market_environment: {
    regime: string;
    sector: string;
    sector_trend: string;
    vix_level: number;
    vix_environment: string;
    environment_score: number;
  };

  // Threat assessment
  threat_assessment: ThreatAssessment;

  // Scenarios
  scenarios: ScenarioAnalysis;

  // Case analyses
  bull_case_analysis: CaseAnalysis;
  base_case_analysis: CaseAnalysis;
  bear_case_analysis: CaseAnalysis;

  // Comparable companies
  comparable_companies: ComparableCompanies;

  // Liquidity
  liquidity_analysis: LiquidityAnalysis;

  // Sentiment
  sentiment: Sentiment;

  // Fundamentals
  fundamentals: Fundamentals;

  // Bias check
  bias_check: BiasCheck;

  // Gate
  do_nothing_gate: DoNothingGate;

  // Alerts & falsification
  alert_levels: AlertLevels;
  falsification: Falsification;

  // Scoring & recommendation
  scoring: {
    catalyst_score: number;
    environment_score: number;
    technical_score: number;
    risk_reward_score: number;
    sentiment_score: number;
    weighted_total: number;
  };

  confidence: {
    level: number;
    rationale: string;
  };

  recommendation: 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NO_POSITION' | 'AVOID';

  // Rationale
  rationale: string;

  // Pass reasoning (when recommendation is not BUY)
  pass_reasoning?: PassReasoning;

  // Alternative strategies
  alternative_strategies?: {
    applicable: boolean;
    strategies: AlternativeStrategy[];
    best_alternative: string;
    best_alternative_rationale: string;
  };

  // Trade plan
  trade_plan?: TradePlan;

  // Meta learning
  meta_learning?: MetaLearning;

  // News age check
  news_age_check?: {
    items: Array<{
      news_item: string;
      date: string;
      age_weeks: number;
      priced_in: string;
    }>;
    stale_news_risk: boolean;
    fresh_catalyst_exists: boolean;
  };
}

// Helper function to get gate result color
export function getGateResultColor(result: 'PASS' | 'MARGINAL' | 'FAIL'): string {
  switch (result) {
    case 'PASS':
      return 'bg-green-500';
    case 'MARGINAL':
      return 'bg-yellow-500';
    case 'FAIL':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

// Helper to get recommendation color
export function getRecommendationColor(rec: string): string {
  switch (rec) {
    case 'STRONG_BUY':
    case 'BUY':
      return 'bg-green-500 text-white';
    case 'WATCH':
      return 'bg-yellow-500 text-black';
    case 'NO_POSITION':
      return 'bg-gray-400 text-white';
    case 'AVOID':
      return 'bg-red-500 text-white';
    default:
      return 'bg-gray-500 text-white';
  }
}

// Helper to get threat level color
export function getThreatLevelColor(concern: string): string {
  const level = concern?.toLowerCase() || 'none';
  if (level === 'none' || level === 'low') return 'bg-green-500';
  if (level === 'moderate' || level === 'medium') return 'bg-yellow-500';
  return 'bg-red-500';
}

// Helper to calculate price position in range
export function getPricePositionPct(current: number, low: number, high: number): number {
  if (high === low) return 50;
  return Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100));
}

// Helper to format market cap
export function formatMarketCap(capB: number | null | undefined): string {
  if (capB === null || capB === undefined) return 'N/A';
  if (capB >= 1) return `$${capB.toFixed(2)}B`;
  return `$${(capB * 1000).toFixed(0)}M`;
}

// Helper to format percentage with sign
export function formatPctWithSign(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return 'N/A';
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}
