/**
 * Earnings analysis parser — schema version 2.6
 *
 * Extends v2.5 flat structure with a `scoring` section.
 * Structure and decision/gate paths are identical to v2.5.
 *
 * Key YAML paths:
 *   recommendation  → decision.recommendation  (string e.g. "NEUTRAL" → NO_POSITION)
 *   confidence      → do_nothing_gate.confidence_actual  (number 0–100)
 *   gate_result     → do_nothing_gate.gate_result  (PASS|MARGINAL|FAIL)
 *   scoring         → scoring.{catalyst_score, fundamental_score, sentiment_score,
 *                              technical_score, weighted_total}
 *                     (note: fundamental_score maps to environment_score in AnalysisDetail)
 *
 * Absent sections compared to stock schema:
 *   setup, market_environment, comparable_companies, liquidity_analysis
 *   → filled with zero/empty defaults
 */

import type { AnalysisDetail } from '@/types/analysis';
import type { AnalysisDetailResponse } from '@/lib/api';
import {
  get,
  normalizeRecommendation,
  normalizeGateResult,
  transformScenario,
  transformArguments,
  resolveCaseStrength,
  transformPriceAlerts,
  transformEventAlerts,
  transformFalsificationCriteria,
  transformStrategies,
  transformPassReasons,
  transformNewsItems,
  EMPTY_COMPARABLE_COMPANIES,
  EMPTY_LIQUIDITY_ANALYSIS,
} from '../utils';

export function earningsParserV26(response: AnalysisDetailResponse): AnalysisDetail {
  const yaml = response.yaml_content as Record<string, unknown>;
  const meta = (yaml._meta as Record<string, unknown>) ?? {};

  const decision     = (yaml.decision          as Record<string, unknown>) ?? {};
  const preparation  = (yaml.preparation       as Record<string, unknown>) ?? {};
  const probability  = (yaml.probability       as Record<string, unknown>) ?? {};
  const scenarios    = (yaml.scenarios         as Record<string, unknown>) ?? {};
  const threat       = (yaml.threat_assessment as Record<string, unknown>) ?? {};
  const bullCase     = (yaml.bull_case_analysis   as Record<string, unknown>) ?? {};
  const baseCase     = (yaml.base_case_analysis   as Record<string, unknown>) ?? {};
  const bearCase     = (yaml.bear_case_analysis   as Record<string, unknown>) ?? {};
  const sentiment    = (yaml.sentiment         as Record<string, unknown>) ?? {};
  const biasCheck    = (yaml.bias_check        as Record<string, unknown>) ?? {};
  const gate         = (yaml.do_nothing_gate   as Record<string, unknown>) ?? {};
  const alerts       = (yaml.alert_levels      as Record<string, unknown>) ?? {};
  const falsification  = (yaml.falsification     as Record<string, unknown>) ?? {};
  const scoring        = (yaml.scoring           as Record<string, unknown>) ?? {};
  const passReasoning  = (yaml.pass_reasoning   as Record<string, unknown>) ?? {};
  const altStrategies  = (yaml.alternative_strategies as Record<string, unknown>) ?? {};
  const metaLearning   = (yaml.meta_learning    as Record<string, unknown>) ?? {};
  const newsCheck      = (yaml.news_age_check   as Record<string, unknown>) ?? {};

  // confidence: prefer gate column, fall back to decision or probability block
  const confidenceActual =
    response.confidence ??
    get(gate, 'confidence_actual', get(decision, 'confidence_pct', get(probability, 'confidence_pct', 0)));

  const gateResult = normalizeGateResult(response.gate_result ?? get(gate, 'gate_result', 'FAIL'));

  // recommendation is in decision block, not at root
  const rawRec = response.recommendation ?? get(decision, 'recommendation', '');

  return {
    _meta: {
      id:      get(meta, 'id', `${response.ticker}_${response.analysis_date.split('T')[0]}`),
      type:    get(meta, 'type', 'earnings-analysis'),
      version: response.schema_version || get(meta, 'version', '2.6'),
      created: get(meta, 'created', response.analysis_date),
      status:  get(meta, 'status', 'active'),
    },

    ticker:        response.ticker,
    current_price: response.current_price ?? Number(yaml.current_price) ?? 0,
    analysis_date: response.analysis_date.split('T')[0],
    analysis_type: 'earnings',

    setup: {
      fifty_two_week_high:       0,
      fifty_two_week_low:        0,
      distance_from_ath_pct:     0,
      distance_from_52w_low_pct: 0,
      market_cap_b:              0,
      pe_ttm:                    0,
      pe_forward:                0,
      next_earnings_date:        String(yaml.earnings_date || ''),
      days_to_earnings:          Number(yaml.days_to_earnings || 0),
      ytd_return_pct:            0,
    },

    catalyst: {
      type:           'earnings',
      description:    get(preparation, 'key_metric', get(preparation, 'key_catalyst', '')),
      specificity:    'high',
      timing:         String(yaml.earnings_date || yaml.earnings_time || 'upcoming'),
      catalyst_score: get(scoring, 'catalyst_score', 0),
      reasoning:      get(decision, 'key_insight', get(preparation, 'thesis', '')),
    },

    market_environment: {
      regime:            'neutral',
      sector:            '',
      sector_trend:      'neutral',
      vix_level:         15,
      vix_environment:   'normal',
      environment_score: 5,
    },

    threat_assessment: {
      primary_concern:   get(threat, 'primary_concern', 'none'),
      structural_threat: {
        exists:      get(threat, 'structural_threat.exists', false),
        description: get(threat, 'structural_threat.description', ''),
      },
      cyclical_weakness: { exists: get(threat, 'cyclical_weakness.exists', false) },
      threat_summary:    get(threat, 'threat_summary', ''),
    },

    scenarios: {
      strong_bull:    transformScenario(scenarios.strong_bull as Record<string, unknown>),
      base_bull:      transformScenario(scenarios.base_bull   as Record<string, unknown>),
      base_bear:      transformScenario(scenarios.base_bear   as Record<string, unknown>),
      strong_bear:    transformScenario(scenarios.strong_bear as Record<string, unknown>),
      expected_value: get(gate, 'ev_actual', response.expected_value ?? 0),
    },

    bull_case_analysis: {
      strength:           resolveCaseStrength(bullCase),
      arguments:          transformArguments(bullCase.arguments),
      summary:            get(bullCase, 'summary', ''),
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
      summary:            get(bearCase, 'summary', ''),
      strongest_argument: get(bearCase, 'strongest_argument', ''),
    },

    comparable_companies: EMPTY_COMPARABLE_COMPANIES,
    liquidity_analysis:   EMPTY_LIQUIDITY_ANALYSIS,

    sentiment: {
      analyst: {
        buy:              get(sentiment, 'analyst.buy', 0),
        hold:             get(sentiment, 'analyst.hold', 0),
        sell:             get(sentiment, 'analyst.sell', 0),
        avg_target:       get(sentiment, 'analyst.avg_target', 0),
        implied_upside_pct: get(sentiment, 'analyst.implied_upside_pct', 0),
      },
      short_interest: {
        pct_float:    get(sentiment, 'short_interest.pct_float', 0),
        days_to_cover: get(sentiment, 'short_interest.days_to_cover', 0),
        trend:        get(sentiment, 'short_interest.trend', 'stable'),
      },
      options: {
        put_call_ratio: get(sentiment, 'options.put_call_ratio', 1),
        iv_percentile:  get(sentiment, 'options.iv_percentile', 50),
        iv_rank:        get(sentiment, 'options.iv_rank', 50),
        unusual_flow:   get(sentiment, 'options.unusual_flow', 'none'),
      },
    },

    fundamentals: {
      valuation: { pe_ratio: 0, pe_forward: 0, ps_ratio: 0, ev_ebitda: 0 },
      growth:    { revenue_growth_yoy: 0, earnings_growth_yoy: 0 },
      quality:   { profit_margin: 0, operating_margin: 0, roe: 0, debt_to_equity: 0, cash_position_b: 0 },
    },

    bias_check: {
      recency_bias:      { detected: get(biasCheck, 'recency_bias.detected', false),      severity: get(biasCheck, 'recency_bias.severity', 'none') },
      confirmation_bias: { detected: get(biasCheck, 'confirmation_bias.detected', false), severity: get(biasCheck, 'confirmation_bias.severity', 'none') },
      anchoring:         { detected: get(biasCheck, 'anchoring.detected', false),         severity: get(biasCheck, 'anchoring.severity', 'none') },
      fomo:              { detected: get(biasCheck, 'fomo.detected', false),              severity: get(biasCheck, 'fomo.severity', 'none') },
      overconfidence:    { detected: get(biasCheck, 'overconfidence.detected', false),    severity: get(biasCheck, 'overconfidence.severity', 'none') },
      bias_summary: get(biasCheck, 'bias_summary', ''),
    },

    do_nothing_gate: {
      ev_threshold:        get(gate, 'ev_threshold', 5),
      ev_actual:           get(gate, 'ev_actual', response.expected_value ?? 0),
      ev_passes:           get(gate, 'ev_passes', false),
      confidence_threshold: get(gate, 'confidence_threshold', 60),
      confidence_actual:   confidenceActual,
      confidence_passes:   get(gate, 'confidence_passes', false),
      rr_threshold:        get(gate, 'rr_threshold', 2),
      rr_actual:           get(gate, 'rr_actual', 0),
      rr_passes:           get(gate, 'rr_passes', false),
      edge_exists:         get(gate, 'edge_exists', false),
      edge_description:    get(gate, 'edge_description', ''),
      gates_passed:        get(gate, 'gates_passed', 0),
      gate_result:         gateResult,
      gate_reasoning:      get(gate, 'gate_reasoning', ''),
    },

    alert_levels: {
      price_alerts:     transformPriceAlerts(alerts.price_alerts, false),
      event_alerts:     transformEventAlerts(alerts.event_alerts),
      post_event_review: get(alerts, 'post_event_review', ''),
    },

    falsification: {
      criteria:          transformFalsificationCriteria(falsification.criteria),
      thesis_invalid_if: get(falsification, 'thesis_invalid_if', ''),
      review_triggers:   Array.isArray(falsification.review_triggers)
        ? (falsification.review_triggers as string[])
        : [],
    },

    // v2.6 adds scoring; fundamental_score maps to environment_score slot in AnalysisDetail
    scoring: {
      catalyst_score:    get(scoring, 'catalyst_score', 0),
      environment_score: get(scoring, 'fundamental_score', 0),   // earnings v2.6 uses fundamental_score
      technical_score:   get(scoring, 'technical_score', 0),
      risk_reward_score: 0,                                        // not in earnings scoring
      sentiment_score:   get(scoring, 'sentiment_score', 0),
      weighted_total:    get(scoring, 'weighted_total', 0),
    },

    confidence: {
      level:    confidenceActual,
      rationale: get(decision, 'rationale', ''),
    },

    recommendation: normalizeRecommendation(rawRec),
    rationale: get(decision, 'rationale', get(decision, 'key_insight', '')),

    pass_reasoning: passReasoning.applicable
      ? {
          applicable:     true,
          primary_reason: get(passReasoning, 'primary_reason', ''),
          reasons:        transformPassReasons(passReasoning.reasons),
          summary:        get(passReasoning, 'summary', ''),
        }
      : undefined,

    alternative_strategies:
      altStrategies.applicable || Array.isArray(altStrategies.strategies)
        ? {
            applicable:                 Boolean(altStrategies.applicable),
            strategies:                 transformStrategies(altStrategies.strategies),
            best_alternative:           get(altStrategies, 'best_alternative', ''),
            best_alternative_rationale: get(altStrategies, 'best_alternative_rationale', ''),
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
