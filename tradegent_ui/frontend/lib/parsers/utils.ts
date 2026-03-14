/**
 * Shared utilities for all analysis version parsers.
 * No parser-specific logic here — only generic helpers.
 */

import type { AnalysisDetail } from '@/types/analysis';

// ── Safe accessor ──────────────────────────────────────────────────────────────

/** Safe nested property accessor with a typed default value */
export function get<T>(
  obj: Record<string, unknown> | undefined,
  path: string,
  defaultValue: T
): T {
  if (!obj) return defaultValue;
  const keys = path.split('.');
  let value: unknown = obj;
  for (const key of keys) {
    if (value === null || value === undefined || typeof value !== 'object') return defaultValue;
    value = (value as Record<string, unknown>)[key];
  }
  return (value ?? defaultValue) as T;
}

// ── Normalization ──────────────────────────────────────────────────────────────

/** Map any gate_result string → canonical PASS | MARGINAL | FAIL */
export function normalizeGateResult(raw: unknown): 'PASS' | 'MARGINAL' | 'FAIL' {
  if (!raw) return 'FAIL';
  const s = String(raw).toUpperCase();
  if (s === 'PASS') return 'PASS';
  if (s === 'MARGINAL') return 'MARGINAL';
  // v2.3 uses "proceed_with_caution" → MARGINAL
  if (s.includes('CAUTION') || s.includes('PROCEED')) return 'MARGINAL';
  return 'FAIL';
}

const VALID_RECOMMENDATIONS = new Set([
  'STRONG_BUY',
  'BUY',
  'WATCH',
  'NO_POSITION',
  'AVOID',
]);

/** Map any recommendation string → canonical union. Unknown values → NO_POSITION */
export function normalizeRecommendation(raw: unknown): AnalysisDetail['recommendation'] {
  const s = String(raw ?? '').toUpperCase().replace(/ /g, '_');
  if (VALID_RECOMMENDATIONS.has(s)) return s as AnalysisDetail['recommendation'];
  return 'NO_POSITION'; // NEUTRAL, etc.
}

// ── Sub-structure transformers ─────────────────────────────────────────────────

export function transformScenario(s: Record<string, unknown> | undefined) {
  return {
    probability: get(s, 'probability', 25),
    description: get(s, 'description', ''),
    target_price: get(s, 'target_price', 0),
    return_pct: get(s, 'return_pct', 0),
    timeline_days: get(s, 'timeline_days', 30),
    key_driver: get(s, 'key_driver', ''),
  };
}

export function transformArguments(
  args: unknown
): Array<{
  argument: string;
  score: number;
  evidence: string;
  counter: string;
  counter_strength: number;
}> {
  if (!Array.isArray(args)) return [];
  return args.map((a) => {
    const arg = a as Record<string, unknown>;
    return {
      argument: String(arg.argument || ''),
      score: Number(arg.score || 0),
      evidence: String(arg.evidence || ''),
      counter: String(arg.counter || ''),
      counter_strength: Number(arg.counter_strength || 0),
    };
  });
}

export function resolveCaseStrength(
  section: Record<string, unknown> | undefined,
  defaultValue = 5
): number {
  const clamp = (value: number): number => {
    const bounded = Math.max(1, Math.min(10, value));
    return Math.round(bounded * 10) / 10;
  };

  const args = Array.isArray(section?.arguments) ? section.arguments : [];
  const scores = args
    .map((item) => Number((item as Record<string, unknown>)?.score))
    .filter((score) => Number.isFinite(score) && score > 0);

  const averageScore = scores.length > 0
    ? scores.reduce((sum, score) => sum + score, 0) / scores.length
    : null;

  const rawStrength = section?.strength;
  if (rawStrength === undefined || rawStrength === null || rawStrength === '') {
    return averageScore !== null ? clamp(averageScore) : defaultValue;
  }

  const parsed = Number(rawStrength);
  if (!Number.isFinite(parsed)) {
    return averageScore !== null ? clamp(averageScore) : defaultValue;
  }

  if (parsed >= 1 && parsed <= 10) {
    return clamp(parsed);
  }

  if (averageScore !== null) {
    return clamp(averageScore);
  }

  return clamp(parsed);
}

export function transformPeers(
  peers: unknown
): Array<{
  ticker: string;
  name: string;
  pe_forward: number;
  ps_ratio: number;
  ev_ebitda: number;
  revenue_growth_pct: number;
  market_cap_b: number | null;
}> {
  if (!Array.isArray(peers)) return [];
  return peers.map((p) => {
    const peer = p as Record<string, unknown>;
    return {
      ticker: String(peer.ticker || ''),
      name: String(peer.name || ''),
      pe_forward: Number(peer.pe_forward || 0),
      ps_ratio: Number(peer.ps_ratio || 0),
      ev_ebitda: Number(peer.ev_ebitda || 0),
      revenue_growth_pct: Number(peer.revenue_growth_pct || 0),
      market_cap_b: peer.market_cap_b !== undefined ? Number(peer.market_cap_b) : null,
    };
  });
}

/**
 * Transform price alert array.
 * Pass includeTag=true for versions that carry a `tag` field (v2.7 stock).
 */
export function transformPriceAlerts(
  alerts: unknown,
  includeTag: boolean
): Array<{
  price: number;
  direction: 'above' | 'below';
  significance: string;
  action_if_triggered: string;
  alert_active: boolean;
  tag?: string;
}> {
  if (!Array.isArray(alerts)) return [];
  return alerts.map((a) => {
    const alert = a as Record<string, unknown>;
    const entry: {
      price: number;
      direction: 'above' | 'below';
      significance: string;
      action_if_triggered: string;
      alert_active: boolean;
      tag?: string;
    } = {
      price: Number(alert.price || 0),
      direction: (alert.direction as 'above' | 'below') || 'above',
      significance: String(alert.significance || ''),
      action_if_triggered: String(alert.action_if_triggered || ''),
      alert_active: Boolean(alert.alert_active),
    };
    if (includeTag && alert.tag) entry.tag = String(alert.tag);
    return entry;
  });
}

export function transformEventAlerts(
  events: unknown
): Array<{ event: string; date: string; action: string }> {
  if (!Array.isArray(events)) return [];
  return events.map((e) => {
    const ev = e as Record<string, unknown>;
    return {
      event: String(ev.event || ''),
      date: String(ev.date || ''),
      action: String(ev.action || ''),
    };
  });
}

export function transformFalsificationCriteria(
  criteria: unknown
): Array<{ condition: string; current_value: string; threshold: string }> {
  if (!Array.isArray(criteria)) return [];
  return criteria.map((c) => {
    const crit = c as Record<string, unknown>;
    return {
      condition: String(crit.condition || ''),
      current_value: String(crit.current_value || ''),
      threshold: String(crit.threshold || ''),
    };
  });
}

export function transformStrategies(
  strats: unknown
): Array<{ strategy: string; trigger: string; entry_zone: string; rationale: string }> {
  if (!Array.isArray(strats)) return [];
  return strats.map((s) => {
    const strat = s as Record<string, unknown>;
    return {
      strategy: String(strat.strategy || ''),
      trigger: String(strat.trigger || ''),
      entry_zone: String(strat.entry_zone || ''),
      rationale: String(strat.rationale || ''),
    };
  });
}

export function transformPassReasons(
  reasons: unknown
): Array<{ reason: string; impact: 'H' | 'M' | 'L' }> {
  if (!Array.isArray(reasons)) return [];
  return reasons.map((r) => {
    const reason = r as Record<string, unknown>;
    return {
      reason: String(reason.reason || ''),
      impact: (reason.impact as 'H' | 'M' | 'L') || 'M',
    };
  });
}

export function transformNewsItems(
  items: unknown
): Array<{ news_item: string; date: string; age_weeks: number; priced_in: string }> {
  if (!Array.isArray(items)) return [];
  return items.map((i) => {
    const item = i as Record<string, unknown>;
    return {
      news_item: String(item.news_item || ''),
      date: String(item.date || ''),
      age_weeks: Number(item.age_weeks || 0),
      priced_in: String(item.priced_in || ''),
    };
  });
}

// ── Empty-section defaults ─────────────────────────────────────────────────────
// Earnings analyses omit many stock-specific sections. Parsers use these for
// required-but-absent fields so the AnalysisDetail type is always satisfied.

export const EMPTY_COMPARABLE_COMPANIES = {
  peers: [],
  sector_median_pe: null,
  sector_median_ps: null,
  sector_median_ev_ebitda: null,
  valuation_position: 'inline' as const,
  discount_premium_pct: 0,
  valuation_notes: '',
};

export const EMPTY_LIQUIDITY_ANALYSIS = {
  adv_shares: 0,
  adv_dollars: 0,
  adv_percentile: 0,
  bid_ask_spread_pct: 0,
  spread_environment: 'unknown',
  slippage_estimate_pct: 0,
  liquidity_score: 0,
  execution_notes: '',
};

export const EMPTY_SCORING = {
  catalyst_score: 0,
  environment_score: 0,
  technical_score: 0,
  risk_reward_score: 0,
  sentiment_score: 0,
  weighted_total: 0,
};

export const EMPTY_SCENARIOS = {
  strong_bull: transformScenario(undefined),
  base_bull: transformScenario(undefined),
  base_bear: transformScenario(undefined),
  strong_bear: transformScenario(undefined),
  expected_value: 0,
};
