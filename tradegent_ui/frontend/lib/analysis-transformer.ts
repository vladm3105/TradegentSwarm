/**
 * Transform API response (yaml_content) to AnalysisDetail type
 * Handles missing/incomplete data gracefully
 */

import type { AnalysisDetail } from '@/types/analysis';
import type { AnalysisDetailResponse } from './api';

/**
 * Safe accessor with default value
 */
function get<T>(obj: Record<string, unknown> | undefined, path: string, defaultValue: T): T {
  if (!obj) return defaultValue;

  const keys = path.split('.');
  let value: unknown = obj;

  for (const key of keys) {
    if (value === null || value === undefined || typeof value !== 'object') {
      return defaultValue;
    }
    value = (value as Record<string, unknown>)[key];
  }

  return (value ?? defaultValue) as T;
}

/**
 * Transform API response to AnalysisDetail
 */
export function transformToAnalysisDetail(response: AnalysisDetailResponse): AnalysisDetail {
  const yaml = response.yaml_content as Record<string, unknown>;

  // Extract nested objects with type casting
  const setup = yaml.setup as Record<string, unknown> || {};
  const catalyst = yaml.catalyst as Record<string, unknown> || {};
  const market = yaml.market_environment as Record<string, unknown> || {};
  const threat = yaml.threat_assessment as Record<string, unknown> || {};
  const scenarios = yaml.scenarios as Record<string, unknown> || {};
  const bullCase = yaml.bull_case_analysis as Record<string, unknown> || {};
  const baseCase = yaml.base_case_analysis as Record<string, unknown> || {};
  const bearCase = yaml.bear_case_analysis as Record<string, unknown> || {};
  const comparable = yaml.comparable_companies as Record<string, unknown> || {};
  const liquidity = yaml.liquidity_analysis as Record<string, unknown> || {};
  const sentiment = yaml.sentiment as Record<string, unknown> || {};
  const fundamentals = yaml.fundamentals as Record<string, unknown> || {};
  const biasCheck = yaml.bias_check as Record<string, unknown> || {};
  const gate = yaml.do_nothing_gate as Record<string, unknown> || {};
  const alerts = yaml.alert_levels as Record<string, unknown> || {};
  const falsification = yaml.falsification as Record<string, unknown> || {};
  const scoring = yaml.scoring as Record<string, unknown> || {};
  const confidence = yaml.confidence as Record<string, unknown> || {};
  const passReasoning = yaml.pass_reasoning as Record<string, unknown> || {};
  const altStrategies = yaml.alternative_strategies as Record<string, unknown> || {};
  const metaLearning = yaml.meta_learning as Record<string, unknown> || {};
  const newsCheck = yaml.news_age_check as Record<string, unknown> || {};
  const meta = yaml._meta as Record<string, unknown> || {};

  // Transform scenarios
  const transformScenario = (s: Record<string, unknown> | undefined) => ({
    probability: get(s, 'probability', 25),
    description: get(s, 'description', ''),
    target_price: get(s, 'target_price', 0),
    return_pct: get(s, 'return_pct', 0),
    timeline_days: get(s, 'timeline_days', 30),
    key_driver: get(s, 'key_driver', ''),
  });

  // Transform case arguments
  const transformArguments = (args: unknown[]): Array<{argument: string; score: number; evidence: string; counter: string; counter_strength: number}> => {
    if (!Array.isArray(args)) return [];
    return args.map((arg: unknown) => {
      const a = arg as Record<string, unknown>;
      return {
        argument: String(a.argument || ''),
        score: Number(a.score || 0),
        evidence: String(a.evidence || ''),
        counter: String(a.counter || ''),
        counter_strength: Number(a.counter_strength || 0),
      };
    });
  };

  // Transform peers
  const transformPeers = (peers: unknown[]): Array<{ticker: string; name: string; pe_forward: number; ps_ratio: number; ev_ebitda: number; revenue_growth_pct: number; market_cap_b: number | null}> => {
    if (!Array.isArray(peers)) return [];
    return peers.map((p: unknown) => {
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
  };

  // Transform price alerts
  const transformPriceAlerts = (alerts: unknown[]): Array<{price: number; direction: 'above' | 'below'; significance: string; action_if_triggered: string; alert_active: boolean; tag?: string}> => {
    if (!Array.isArray(alerts)) return [];
    return alerts.map((a: unknown) => {
      const alert = a as Record<string, unknown>;
      return {
        price: Number(alert.price || 0),
        direction: (alert.direction as 'above' | 'below') || 'above',
        significance: String(alert.significance || ''),
        action_if_triggered: String(alert.action_if_triggered || ''),
        alert_active: Boolean(alert.alert_active),
        tag: alert.tag ? String(alert.tag) : undefined,
      };
    });
  };

  // Transform event alerts
  const transformEventAlerts = (events: unknown[]): Array<{event: string; date: string; action: string}> => {
    if (!Array.isArray(events)) return [];
    return events.map((e: unknown) => {
      const event = e as Record<string, unknown>;
      return {
        event: String(event.event || ''),
        date: String(event.date || ''),
        action: String(event.action || ''),
      };
    });
  };

  // Transform falsification criteria
  const transformFalsificationCriteria = (criteria: unknown[]): Array<{condition: string; current_value: string; threshold: string}> => {
    if (!Array.isArray(criteria)) return [];
    return criteria.map((c: unknown) => {
      const crit = c as Record<string, unknown>;
      return {
        condition: String(crit.condition || ''),
        current_value: String(crit.current_value || ''),
        threshold: String(crit.threshold || ''),
      };
    });
  };

  // Transform alternative strategies
  const transformStrategies = (strats: unknown[]): Array<{strategy: string; trigger: string; entry_zone: string; rationale: string}> => {
    if (!Array.isArray(strats)) return [];
    return strats.map((s: unknown) => {
      const strat = s as Record<string, unknown>;
      return {
        strategy: String(strat.strategy || ''),
        trigger: String(strat.trigger || ''),
        entry_zone: String(strat.entry_zone || ''),
        rationale: String(strat.rationale || ''),
      };
    });
  };

  // Transform pass reasons
  const transformPassReasons = (reasons: unknown[]): Array<{reason: string; impact: 'H' | 'M' | 'L'}> => {
    if (!Array.isArray(reasons)) return [];
    return reasons.map((r: unknown) => {
      const reason = r as Record<string, unknown>;
      return {
        reason: String(reason.reason || ''),
        impact: (reason.impact as 'H' | 'M' | 'L') || 'M',
      };
    });
  };

  // Transform news items
  const transformNewsItems = (items: unknown[]): Array<{news_item: string; date: string; age_weeks: number; priced_in: string}> => {
    if (!Array.isArray(items)) return [];
    return items.map((i: unknown) => {
      const item = i as Record<string, unknown>;
      return {
        news_item: String(item.news_item || ''),
        date: String(item.date || ''),
        age_weeks: Number(item.age_weeks || 0),
        priced_in: String(item.priced_in || ''),
      };
    });
  };

  // Build the AnalysisDetail object
  const analysisDetail: AnalysisDetail = {
    _meta: {
      id: get(meta, 'id', response.ticker + '_' + response.analysis_date.split('T')[0]),
      type: get(meta, 'type', 'stock-analysis'),
      version: response.schema_version || get(meta, 'version', '2.6'),
      created: get(meta, 'created', response.analysis_date),
      status: get(meta, 'status', 'active'),
    },
    ticker: response.ticker,
    current_price: response.current_price || Number(yaml.current_price) || 0,
    analysis_date: response.analysis_date.split('T')[0],
    analysis_type: String(yaml.analysis_type || 'stock'),

    setup: {
      fifty_two_week_high: get(setup, 'fifty_two_week_high', 0),
      fifty_two_week_low: get(setup, 'fifty_two_week_low', 0),
      distance_from_ath_pct: get(setup, 'distance_from_ath_pct', 0),
      distance_from_52w_low_pct: get(setup, 'distance_from_52w_low_pct', 0),
      market_cap_b: get(setup, 'market_cap_b', 0),
      pe_ttm: get(setup, 'pe_ttm', 0),
      pe_forward: get(setup, 'pe_forward', 0),
      next_earnings_date: get(setup, 'next_earnings_date', ''),
      days_to_earnings: get(setup, 'days_to_earnings', 0),
      ytd_return_pct: get(setup, 'ytd_return_pct', 0),
    },

    catalyst: {
      type: get(catalyst, 'type', 'none'),
      description: get(catalyst, 'description', ''),
      specificity: get(catalyst, 'specificity', 'low'),
      timing: get(catalyst, 'timing', 'none'),
      catalyst_score: get(catalyst, 'catalyst_score', 0),
      reasoning: get(catalyst, 'reasoning', ''),
    },

    market_environment: {
      regime: get(market, 'regime', 'neutral'),
      sector: get(market, 'sector', ''),
      sector_trend: get(market, 'sector_trend', 'neutral'),
      vix_level: get(market, 'vix_level', 15),
      vix_environment: get(market, 'vix_environment', 'normal'),
      environment_score: get(market, 'environment_score', 5),
    },

    threat_assessment: {
      primary_concern: get(threat, 'primary_concern', 'none'),
      structural_threat: {
        exists: get(threat, 'structural_threat.exists', false),
        description: get(threat, 'structural_threat.description', ''),
      },
      cyclical_weakness: {
        exists: get(threat, 'cyclical_weakness.exists', false),
      },
      threat_summary: get(threat, 'threat_summary', ''),
    },

    scenarios: {
      strong_bull: transformScenario(scenarios.strong_bull as Record<string, unknown>),
      base_bull: transformScenario(scenarios.base_bull as Record<string, unknown>),
      base_bear: transformScenario(scenarios.base_bear as Record<string, unknown>),
      strong_bear: transformScenario(scenarios.strong_bear as Record<string, unknown>),
      expected_value: get(scenarios, 'expected_value', response.expected_value || 0),
    },

    bull_case_analysis: {
      strength: get(bullCase, 'strength', 5),
      arguments: transformArguments(bullCase.arguments as unknown[]),
      summary: get(bullCase, 'summary', ''),
      strongest_argument: get(bullCase, 'strongest_argument', ''),
    },

    base_case_analysis: {
      strength: get(baseCase, 'strength', 5),
      arguments: transformArguments(baseCase.arguments as unknown[]),
      summary: get(baseCase, 'summary', ''),
      strongest_argument: get(baseCase, 'strongest_argument', ''),
    },

    bear_case_analysis: {
      strength: get(bearCase, 'strength', 5),
      arguments: transformArguments(bearCase.arguments as unknown[]),
      summary: get(bearCase, 'summary', ''),
      strongest_argument: get(bearCase, 'strongest_argument', ''),
    },

    comparable_companies: {
      peers: transformPeers(comparable.peers as unknown[]),
      sector_median_pe: get(comparable, 'sector_median_pe', null),
      sector_median_ps: get(comparable, 'sector_median_ps', null),
      sector_median_ev_ebitda: get(comparable, 'sector_median_ev_ebitda', null),
      valuation_position: get(comparable, 'valuation_position', 'inline'),
      discount_premium_pct: get(comparable, 'discount_premium_pct', 0),
      valuation_notes: get(comparable, 'valuation_notes', ''),
    },

    liquidity_analysis: {
      adv_shares: get(liquidity, 'adv_shares', 0),
      adv_dollars: get(liquidity, 'adv_dollars', 0),
      adv_percentile: get(liquidity, 'adv_percentile', 0),
      bid_ask_spread_pct: get(liquidity, 'bid_ask_spread_pct', 0),
      spread_environment: get(liquidity, 'spread_environment', 'normal'),
      slippage_estimate_pct: get(liquidity, 'slippage_estimate_pct', 0),
      liquidity_score: get(liquidity, 'liquidity_score', 5),
      execution_notes: get(liquidity, 'execution_notes', ''),
    },

    sentiment: {
      analyst: {
        buy: get(sentiment, 'analyst.buy', 0),
        hold: get(sentiment, 'analyst.hold', 0),
        sell: get(sentiment, 'analyst.sell', 0),
        avg_target: get(sentiment, 'analyst.avg_target', 0),
        implied_upside_pct: get(sentiment, 'analyst.implied_upside_pct', 0),
      },
      short_interest: {
        pct_float: get(sentiment, 'short_interest.pct_float', 0),
        days_to_cover: get(sentiment, 'short_interest.days_to_cover', 0),
        trend: get(sentiment, 'short_interest.trend', 'stable'),
      },
      options: {
        put_call_ratio: get(sentiment, 'options.put_call_ratio', 1),
        iv_percentile: get(sentiment, 'options.iv_percentile', 50),
        iv_rank: get(sentiment, 'options.iv_rank', 50),
        unusual_flow: get(sentiment, 'options.unusual_flow', 'none'),
      },
    },

    fundamentals: {
      valuation: {
        pe_ratio: get(fundamentals, 'valuation.pe_ratio', 0),
        pe_forward: get(fundamentals, 'valuation.pe_forward', 0) || get(setup, 'pe_forward', 0),
        ps_ratio: get(fundamentals, 'valuation.ps_ratio', 0),
        ev_ebitda: get(fundamentals, 'valuation.ev_ebitda', 0),
      },
      growth: {
        revenue_growth_yoy: get(fundamentals, 'growth.revenue_growth_yoy', 0),
        earnings_growth_yoy: get(fundamentals, 'growth.earnings_growth_yoy', 0),
      },
      quality: {
        profit_margin: get(fundamentals, 'quality.profit_margin', 0),
        operating_margin: get(fundamentals, 'quality.operating_margin', 0),
        roe: get(fundamentals, 'quality.roe', 0),
        debt_to_equity: get(fundamentals, 'quality.debt_to_equity', 0),
        cash_position_b: get(fundamentals, 'quality.cash_position_b', 0),
      },
    },

    bias_check: {
      recency_bias: {
        detected: get(biasCheck, 'recency_bias.detected', false),
        severity: get(biasCheck, 'recency_bias.severity', 'none'),
      },
      confirmation_bias: {
        detected: get(biasCheck, 'confirmation_bias.detected', false),
        severity: get(biasCheck, 'confirmation_bias.severity', 'none'),
      },
      anchoring: {
        detected: get(biasCheck, 'anchoring.detected', false),
        severity: get(biasCheck, 'anchoring.severity', 'none'),
      },
      fomo: {
        detected: get(biasCheck, 'fomo.detected', false),
        severity: get(biasCheck, 'fomo.severity', 'none'),
      },
      overconfidence: {
        detected: get(biasCheck, 'overconfidence.detected', false),
        severity: get(biasCheck, 'overconfidence.severity', 'none'),
      },
      bias_summary: get(biasCheck, 'bias_summary', ''),
    },

    do_nothing_gate: {
      ev_threshold: get(gate, 'ev_threshold', 5),
      ev_actual: get(gate, 'ev_actual', response.expected_value || 0),
      ev_passes: get(gate, 'ev_passes', false),
      confidence_threshold: get(gate, 'confidence_threshold', 60),
      confidence_actual: get(gate, 'confidence_actual', response.confidence || 0),
      confidence_passes: get(gate, 'confidence_passes', false),
      rr_threshold: get(gate, 'rr_threshold', 2),
      rr_actual: get(gate, 'rr_actual', 0),
      rr_passes: get(gate, 'rr_passes', false),
      edge_exists: get(gate, 'edge_exists', false),
      edge_description: get(gate, 'edge_description', ''),
      gates_passed: get(gate, 'gates_passed', 0),
      gate_result: (response.gate_result as 'PASS' | 'MARGINAL' | 'FAIL') || get(gate, 'gate_result', 'FAIL'),
      gate_reasoning: get(gate, 'gate_reasoning', ''),
    },

    alert_levels: {
      price_alerts: transformPriceAlerts(alerts.price_alerts as unknown[]),
      event_alerts: transformEventAlerts(alerts.event_alerts as unknown[]),
      post_event_review: get(alerts, 'post_event_review', ''),
    },

    falsification: {
      criteria: transformFalsificationCriteria(falsification.criteria as unknown[]),
      thesis_invalid_if: get(falsification, 'thesis_invalid_if', ''),
      review_triggers: Array.isArray(falsification.review_triggers)
        ? (falsification.review_triggers as string[])
        : [],
    },

    scoring: {
      catalyst_score: get(scoring, 'catalyst_score', 0),
      environment_score: get(scoring, 'environment_score', 0),
      technical_score: get(scoring, 'technical_score', 0),
      risk_reward_score: get(scoring, 'risk_reward_score', 0),
      sentiment_score: get(scoring, 'sentiment_score', 0),
      weighted_total: get(scoring, 'weighted_total', 0),
    },

    confidence: {
      level: get(confidence, 'level', response.confidence || 0),
      rationale: get(confidence, 'rationale', ''),
    },

    recommendation: (response.recommendation as 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NO_POSITION' | 'AVOID') ||
      (yaml.recommendation as 'STRONG_BUY' | 'BUY' | 'WATCH' | 'NO_POSITION' | 'AVOID') ||
      'NO_POSITION',

    rationale: String(yaml.rationale || ''),

    pass_reasoning: passReasoning.applicable ? {
      applicable: true,
      primary_reason: get(passReasoning, 'primary_reason', ''),
      reasons: transformPassReasons(passReasoning.reasons as unknown[]),
      summary: get(passReasoning, 'summary', ''),
    } : undefined,

    alternative_strategies: (altStrategies.applicable || (altStrategies.strategies as unknown[])?.length > 0) ? {
      applicable: Boolean(altStrategies.applicable),
      strategies: transformStrategies(altStrategies.strategies as unknown[]),
      best_alternative: get(altStrategies, 'best_alternative', ''),
      best_alternative_rationale: get(altStrategies, 'best_alternative_rationale', ''),
    } : undefined,

    meta_learning: metaLearning.pattern_identified ? {
      pattern_identified: get(metaLearning, 'pattern_identified', ''),
      similar_setup: get(metaLearning, 'similar_setup', ''),
    } : undefined,

    news_age_check: (newsCheck.items as unknown[])?.length > 0 ? {
      items: transformNewsItems(newsCheck.items as unknown[]),
      stale_news_risk: get(newsCheck, 'stale_news_risk', false),
      fresh_catalyst_exists: get(newsCheck, 'fresh_catalyst_exists', false),
    } : undefined,
  };

  return analysisDetail;
}

/**
 * Check if analysis has sufficient data for full visualization
 */
export function hasFullAnalysisData(response: AnalysisDetailResponse): boolean {
  const yaml = response.yaml_content as Record<string, unknown>;

  // Check for essential fields that indicate a complete analysis
  return Boolean(
    response.recommendation &&
    response.confidence &&
    response.gate_result &&
    yaml.scenarios &&
    yaml.do_nothing_gate
  );
}
