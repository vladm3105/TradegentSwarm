/**
 * Earnings analysis parser — schema version 2.3
 *
 * Structure: phase1_preparation … phase7_decision … phase8_post_earnings
 * No flat recommendation or do_nothing_gate at root.
 *
 * Key YAML paths:
 *   recommendation  → derived from phase7_decision.recommendation.direction + gate result
 *   confidence      → phase7_decision.do_nothing_gate.confidence_above_60pct.actual  (0–100)
 *   gate_result     → normalizeGateResult(phase7_decision.do_nothing_gate.gate_result)
 *                     e.g. "proceed_with_caution" → MARGINAL
 *
 * Absent sections compared to stock schema:
 *   setup, catalyst, market_environment, comparable_companies,
 *   liquidity_analysis, scoring, alert_levels
 *   → all filled with zero/empty defaults
 */

import type { AnalysisDetail } from '@/types/analysis';
import type { AnalysisDetailResponse } from '@/lib/api';
import {
  get,
  normalizeGateResult,
  transformScenario,
  transformArguments,
  transformFalsificationCriteria,
  transformPassReasons,
  transformNewsItems,
  EMPTY_COMPARABLE_COMPANIES,
  EMPTY_LIQUIDITY_ANALYSIS,
  EMPTY_SCORING,
  EMPTY_SCENARIOS,
  resolveCaseStrength,
} from '../utils';

/** Map v2.3 direction string + gate result → canonical recommendation */
function mapV23Recommendation(
  direction: unknown,
  gateResult: 'PASS' | 'MARGINAL' | 'FAIL'
): AnalysisDetail['recommendation'] {
  const dir = String(direction || '').toLowerCase();
  if (!dir) return 'NO_POSITION';
  const isLong = dir === 'long';
  if (gateResult === 'PASS')    return isLong ? 'BUY'   : 'AVOID';
  if (gateResult === 'MARGINAL') return 'WATCH';
  return 'NO_POSITION';
}

export function earningsParserV23(response: AnalysisDetailResponse): AnalysisDetail {
  const yaml = response.yaml_content as Record<string, unknown>;
  const meta = (yaml._meta as Record<string, unknown>) ?? {};

  // ── Phase sections ──────────────────────────────────────────────────────────
  const p1  = (yaml.phase1_preparation  as Record<string, unknown>) ?? {};
  const p2  = (yaml.phase2_fundamentals as Record<string, unknown>) ?? {};
  const p3  = (yaml.phase3_technical    as Record<string, unknown>) ?? {};
  const p4  = (yaml.phase4_sentiment    as Record<string, unknown>) ?? {};
  const p5  = (yaml.phase5_probability  as Record<string, unknown>) ?? {};
  const p6  = (yaml.phase6_risk_and_bias as Record<string, unknown>) ?? {};
  const p7  = (yaml.phase7_decision     as Record<string, unknown>) ?? {};

  // ── Gate lives inside phase7_decision ──────────────────────────────────────
  const p7Gate = (p7.do_nothing_gate  as Record<string, unknown>) ?? {};
  const p7Rec  = (p7.recommendation   as Record<string, unknown>) ?? {};

  // Root-level recommendation object (abbreviated version of p7Rec)
  const rootRec = (yaml.recommendation as Record<string, unknown>) ?? {};

  const rawGateResult = get(p7Gate, 'gate_result', '');
  const gateResult    = normalizeGateResult(response.gate_result ?? rawGateResult);

  // direction from either p7 or root recommendation
  const direction = get(p7Rec, 'direction', get(rootRec, 'direction', ''));

  // confidence: phase7 gate stores it as a nested object { actual: N, threshold: N, status }
  const confidenceObj = (p7Gate.confidence_above_60pct as Record<string, unknown>) ?? {};
  const confidenceActual = get(confidenceObj, 'actual', response.confidence ?? 0);

  // EV actual
  const evObj    = (p7Gate.expected_value_above_5pct as Record<string, unknown>) ?? {};
  const evActual = get(evObj, 'actual', response.expected_value ?? 0);

  // R:R actual
  const rrObj    = (p7Gate.risk_reward_above_2to1 as Record<string, unknown>) ?? {};
  const rrActual = get(rrObj, 'ratio', 0);

  // ── Sections present at root in v2.3 ───────────────────────────────────────
  const biasCheck     = (yaml.bias_check    as Record<string, unknown>) ?? {};
  const falsification = (yaml.falsification as Record<string, unknown>) ?? {};
  const metaLearning  = (yaml.meta_learning as Record<string, unknown>) ?? {};
  const newsCheck     = (yaml.news_age_check as Record<string, unknown>) ?? {};
  const passReasoning = (yaml.pass_reasoning as Record<string, unknown>) ?? {};
  const bullCase      = (yaml.bull_case_analysis as Record<string, unknown>) ?? {};
  const baseCase      = (yaml.base_case_analysis as Record<string, unknown>) ?? {};
  const bearCase      = (yaml.bear_case_analysis as Record<string, unknown>) ?? {};

  // Sentiment from phase4
  const sentimentData  = (p4.sentiment_indicators as Record<string, unknown>) ?? {};
  const analystData    = (p4.analyst_consensus    as Record<string, unknown>) ?? {};

  // Fundamentals from phase2
  const fundValuation  = (p2.valuation_metrics  as Record<string, unknown>) ?? {};
  const fundGrowth     = (p2.growth_metrics     as Record<string, unknown>) ?? {};
  const fundQuality    = (p2.quality_metrics    as Record<string, unknown>) ?? {};

  return {
    _meta: {
      id:      get(meta, 'id', `${response.ticker}_${response.analysis_date.split('T')[0]}`),
      type:    get(meta, 'type', 'earnings-analysis'),
      version: response.schema_version || get(meta, 'version', '2.3'),
      created: get(meta, 'created', response.analysis_date),
      status:  get(meta, 'status', 'active'),
    },

    ticker:        response.ticker,
    current_price: response.current_price ?? Number(yaml.current_price) ?? 0,
    analysis_date: response.analysis_date.split('T')[0],
    analysis_type: 'earnings',

    // setup: not present in v2.3 — use what we have at root
    setup: {
      fifty_two_week_high:       get(p1, 'fifty_two_week_high', 0),
      fifty_two_week_low:        get(p1, 'fifty_two_week_low', 0),
      distance_from_ath_pct:     0,
      distance_from_52w_low_pct: 0,
      market_cap_b:              get(p2, 'market_cap_b', 0),
      pe_ttm:                    get(p2, 'pe_ttm', 0) || get(fundValuation, 'pe_ttm', 0),
      pe_forward:                get(p2, 'pe_forward', 0) || get(fundValuation, 'pe_forward', 0),
      next_earnings_date:        String(yaml.earnings_date || ''),
      days_to_earnings:          Number(yaml.days_to_earnings || 0),
      ytd_return_pct:            0,
    },

    // catalyst: not a dedicated section — derive from preparation
    catalyst: {
      type:           'earnings',
      description:    get(p1, 'key_metric', get(p1, 'thesis', '')),
      specificity:    'high',
      timing:         String(yaml.earnings_date || 'upcoming'),
      catalyst_score: 0,
      reasoning:      get(p1, 'setup_rationale', get(p1, 'key_catalyst', '')),
    },

    // market_environment: pull whatever technical section has
    market_environment: {
      regime:            get(p3, 'market_regime', 'neutral'),
      sector:            get(p3, 'sector', get(p1, 'sector', '')),
      sector_trend:      get(p3, 'sector_trend', 'neutral'),
      vix_level:         get(p3, 'vix_level', 15),
      vix_environment:   get(p3, 'vix_environment', 'normal'),
      environment_score: get(p3, 'environment_score', 5),
    },

    // threat_assessment: not present — use phase6 risk data
    threat_assessment: {
      primary_concern:   get(p6, 'primary_risk', get(p6, 'key_risk', 'none')),
      structural_threat: {
        exists:      false,
        description: get(p6, 'structural_concern', ''),
      },
      cyclical_weakness: { exists: false },
      threat_summary:    get(p6, 'risk_summary', ''),
    },

    // scenarios: phase5 has probability, use bull/base/bear if present at root
    scenarios: bullCase.strong_bull
      ? {
          strong_bull:    transformScenario(bullCase.strong_bull as Record<string, unknown>),
          base_bull:      transformScenario(bullCase.base_bull   as Record<string, unknown>),
          base_bear:      transformScenario(bearCase.base_bear   as Record<string, unknown>),
          strong_bear:    transformScenario(bearCase.strong_bear as Record<string, unknown>),
          expected_value: evActual,
        }
      : { ...EMPTY_SCENARIOS, expected_value: evActual },

    bull_case_analysis: {
      strength:           resolveCaseStrength(bullCase),
      arguments:          transformArguments(bullCase.arguments),
      summary:            get(bullCase, 'summary', get(p5, 'bull_case', '')),
      strongest_argument: get(bullCase, 'strongest_argument', ''),
    },

    base_case_analysis: {
      strength:           resolveCaseStrength(baseCase),
      arguments:          transformArguments(baseCase.arguments),
      summary:            get(baseCase, 'summary', ''),
      strongest_argument: get(baseCase, 'strongest_argument', ''),
    },

    bear_case_analysis: {
      strength:           resolveCaseStrength(bearCase),
      arguments:          transformArguments(bearCase.arguments),
      summary:            get(bearCase, 'summary', get(p5, 'bear_case', '')),
      strongest_argument: get(bearCase, 'strongest_argument', ''),
    },

    // Not present in v2.3
    comparable_companies: EMPTY_COMPARABLE_COMPANIES,
    liquidity_analysis:   EMPTY_LIQUIDITY_ANALYSIS,

    sentiment: {
      analyst: {
        buy:              get(analystData, 'buy', get(p4, 'analyst_buy', 0)),
        hold:             get(analystData, 'hold', get(p4, 'analyst_hold', 0)),
        sell:             get(analystData, 'sell', get(p4, 'analyst_sell', 0)),
        avg_target:       get(analystData, 'avg_target', 0),
        implied_upside_pct: get(analystData, 'implied_upside_pct', 0),
      },
      short_interest: {
        pct_float:    get(sentimentData, 'short_interest_pct', 0),
        days_to_cover: get(sentimentData, 'days_to_cover', 0),
        trend:        'stable',
      },
      options: {
        put_call_ratio: get(sentimentData, 'put_call_ratio', 1),
        iv_percentile:  get(sentimentData, 'iv_percentile', 50),
        iv_rank:        get(sentimentData, 'iv_rank', 50),
        unusual_flow:   'none',
      },
    },

    fundamentals: {
      valuation: {
        pe_ratio:   get(fundValuation, 'pe_ttm', 0),
        pe_forward: get(fundValuation, 'pe_forward', 0),
        ps_ratio:   get(fundValuation, 'ps_ratio', 0),
        ev_ebitda:  get(fundValuation, 'ev_ebitda', 0),
      },
      growth: {
        revenue_growth_yoy:  get(fundGrowth, 'revenue_growth_yoy', 0),
        earnings_growth_yoy: get(fundGrowth, 'earnings_growth_yoy', 0),
      },
      quality: {
        profit_margin:   get(fundQuality, 'profit_margin', 0),
        operating_margin: get(fundQuality, 'operating_margin', 0),
        roe:             get(fundQuality, 'roe', 0),
        debt_to_equity:  get(fundQuality, 'debt_to_equity', 0),
        cash_position_b: get(fundQuality, 'cash_position_b', 0),
      },
    },

    bias_check: {
      recency_bias:      { detected: get(biasCheck, 'recency_bias.detected', false),      severity: get(biasCheck, 'recency_bias.severity', 'none') },
      confirmation_bias: { detected: get(biasCheck, 'confirmation_bias.detected', false), severity: get(biasCheck, 'confirmation_bias.severity', 'none') },
      anchoring:         { detected: get(biasCheck, 'anchoring.detected', false),         severity: get(biasCheck, 'anchoring.severity', 'none') },
      fomo:              { detected: get(biasCheck, 'fomo.detected', false),              severity: get(biasCheck, 'fomo.severity', 'none') },
      overconfidence:    { detected: get(biasCheck, 'overconfidence.detected', false),    severity: get(biasCheck, 'overconfidence.severity', 'none') },
      bias_summary: get(biasCheck, 'bias_summary', get(p6, 'bias_summary', '')),
    },

    // Gate reconstructed from phase7_decision.do_nothing_gate
    do_nothing_gate: {
      ev_threshold:        get(evObj,          'threshold', 5),
      ev_actual:           evActual,
      ev_passes:           (get(evObj,          'status', '') as string) === 'pass',
      confidence_threshold: get(confidenceObj, 'threshold', 60),
      confidence_actual:   confidenceActual,
      confidence_passes:   (get(confidenceObj,  'status', '') as string) === 'pass',
      rr_threshold:        2,
      rr_actual:           rrActual,
      rr_passes:           (get(rrObj,          'status', '') as string) === 'pass',
      edge_exists:         (get(p7Gate, 'edge_not_priced_in.status', '') as string) === 'pass',
      edge_description:    get(p7Gate, 'gate_notes', ''),
      gates_passed:        0,
      gate_result:         gateResult,
      gate_reasoning:      get(p7Gate, 'gate_notes', ''),
    },

    // Not present in v2.3
    alert_levels: {
      price_alerts:     [],
      event_alerts:     [],
      post_event_review: '',
    },

    falsification: {
      criteria:          transformFalsificationCriteria(falsification.criteria),
      thesis_invalid_if: get(falsification, 'thesis_invalid_if', ''),
      review_triggers:   Array.isArray(falsification.review_triggers)
        ? (falsification.review_triggers as string[])
        : [],
    },

    // Not present in v2.3
    scoring: EMPTY_SCORING,

    confidence: {
      level:    confidenceActual,
      rationale: get(p7, 'decision_rationale', ''),
    },

    recommendation: mapV23Recommendation(direction, gateResult),
    rationale: get(p7, 'decision_rationale', get(yaml, 'summary', '')),

    pass_reasoning: passReasoning.applicable
      ? {
          applicable:     true,
          primary_reason: get(passReasoning, 'primary_reason', ''),
          reasons:        transformPassReasons(passReasoning.reasons),
          summary:        get(passReasoning, 'summary', ''),
        }
      : undefined,

    meta_learning: metaLearning.pattern_identified
      ? {
          pattern_identified: get(metaLearning, 'pattern_identified', ''),
          similar_setup:      get(metaLearning, 'similar_setup', ''),
        }
      : undefined,

    news_age_check:
      Array.isArray(newsCheck.items) && (newsCheck.items as unknown[]).length > 0
        ? {
            items:                transformNewsItems(newsCheck.items),
            stale_news_risk:      get(newsCheck, 'stale_news_risk', false),
            fresh_catalyst_exists: get(newsCheck, 'fresh_catalyst_exists', false),
          }
        : undefined,
  };
}
