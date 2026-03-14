import { describe, expect, it } from 'vitest';

import type { AnalysisDetailResponse } from '@/lib/api';
import { stockParserV27 } from '@/lib/parsers/stock/v2.7';

function makeBaseResponse(yamlContent: Record<string, unknown>): AnalysisDetailResponse {
  return {
    id: 1,
    ticker: 'MSFT',
    analysis_date: '2026-03-14T13:43:34.659282',
    schema_version: '2.7',
    file_path: '/tmp/MSFT_20260314T1343.yaml',
    recommendation: 'WATCH',
    confidence: 0,
    gate_result: 'FAIL',
    expected_value: 2.15,
    current_price: 400.52,
    status: 'active',
    yaml_content: yamlContent,
  };
}

describe('stockParserV27 rationale fallback', () => {
  it('uses summary.narrative when top-level rationale is missing', () => {
    const response = makeBaseResponse({
      _meta: {
        id: 'MSFT_20260314T1343',
        type: 'stock-analysis',
        version: '2.7',
        created: '2026-03-14T13:43:34.659282',
      },
      analysis_type: 'stock',
      do_nothing_gate: {
        confidence_actual: 0,
        gate_result: 'FAIL',
      },
      catalyst: {
        catalyst_score: 7,
      },
      market_environment: {
        environment_score: 6,
      },
      technical: {
        technical_score: 5,
      },
      fundamentals: {
        fundamental_score: 7,
      },
      sentiment: {
        sentiment_score: 6,
      },
      summary: {
        narrative: 'Rationale from summary narrative.',
      },
      recommendation: {
        action: 'WATCH',
        confidence: 0,
      },
      scenarios: {},
      bull_case_analysis: { arguments: [] },
      base_case_analysis: { arguments: [] },
      bear_case_analysis: { arguments: [] },
      comparable_companies: { peers: [] },
      liquidity_analysis: {},
      bias_check: {},
      alert_levels: { price_alerts: [], event_alerts: [] },
      falsification: { criteria: [], review_triggers: [] },
      scoring: {},
    });

    const parsed = stockParserV27(response);

    expect(parsed.rationale).toBe('Rationale from summary narrative.');
    expect(parsed.confidence.rationale).toBe('Rationale from summary narrative.');
    expect(parsed.confidence.level).toBe(62);
  });
});
