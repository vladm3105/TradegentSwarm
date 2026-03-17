# Stock Critique Prompt

Critique the stock draft for logical consistency, derivation quality, and actionability.
Reject generic language and identify concrete repair actions.

Hard checks:

- Verify required stock schema depth and v2.7 derivation coverage.
- Validate scenario coherence against recommendation and gate outcome.
- Flag missing technical depth (`moving_averages`, `momentum`).
- Flag missing fundamentals depth (`valuation`, `growth`).
- Flag missing sentiment depth (`analyst`, `options`).
- Flag missing catalyst depth (`primary_catalyst`, >=3 `secondary_catalysts`, >=4 `invalidation_criteria`).
- Flag missing scenario evidence depth (>=3 `conditions` per scenario branch).
- Flag missing watch-metric depth for earnings-adjacent setups (`earnings_call_watch_list.must_watch`).
- Flag missing explicit EV math (`expected_value_calculation.formula`, `result_pct`, `interpretation`).

Return JSON payload with this exact shape:

- section_scores: object
  - catalyst: number (0-10)
  - technical: number (0-10)
  - fundamental: number (0-10)
  - liquidity: number (0-10)
  - sentiment: number (0-10)
  - scenarios: number (0-10)
  - risk_management: number (0-10)
  - summary: number (0-10)
- failed_sections: array of section names where score < 7.0
- failed_section_reasons: object mapping failed section name -> concise reason
- issues: array of issue objects
  - path: string
  - issue: string
  - severity: one of [low, medium, high]
  - fix_hint: string

Rules:

- If any section score is below 7.0, include it in failed_sections.
- Every failed section must have a failed_section_reasons entry.
- Avoid markdown; return structured JSON-style content only.
