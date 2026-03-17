# Stock Draft Prompt

Generate a structured stock analysis JSON object from available context and tool data.
Focus on realistic market data, explicit thesis, and required schema keys.
Do not use placeholders.

Required richness:

- Include `technical.moving_averages` and `technical.momentum` with concrete numeric values when context provides them.
- Include `fundamentals.valuation` and `fundamentals.growth` when context provides them.
- Include `sentiment.analyst` and `sentiment.options` when context provides them.
- Include four scenario branches: `strong_bull`, `base_bull`, `base_bear`, `strong_bear`.
- Include at least 3 arguments in both `bull_case_analysis.arguments` and `bear_case_analysis.arguments`.
- Include `summary.key_levels` and `alert_levels.price_alerts[0]` with derivation objects.
- Include `catalyst.primary_catalyst` plus at least 3 `catalyst.secondary_catalysts` with date, age, and priced-in status.
- Include at least 4 concrete `catalyst.invalidation_criteria` entries.
- Include at least 3 explicit `conditions` per scenario branch and compute `expected_value_calculation`.
- Include `sentiment.crowded_trade_assessment` and `technical.timing_conservatism_check` with concrete thresholds.
- If setup is earnings-adjacent, populate `earnings_call_watch_list` with at least 4 must-watch metrics and bull/bear thresholds.
