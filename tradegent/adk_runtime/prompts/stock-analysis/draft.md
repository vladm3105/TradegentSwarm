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
