# Schema Validation (v2.7)

All stock analyses MUST pass validation before commit:

```bash
python scripts/validate_analysis.py <file.yaml>
python scripts/validate_analysis.py --all  # Validate all
```

## v2.7 Requirements (stock-analysis)

- `alert_levels.price_alerts[]` must include:
  - `derivation` object with methodology, source_field, source_value, calculation
  - `tag` field (max 15 chars) for visualization (e.g., "20-day MA", "52-week Low")
- `summary.key_levels` must include `*_derivation` objects for entry, stop, target_1
- `significance` field minimum 100 characters
- Valid methodologies: support_resistance, moving_average, pivot_point, round_number, stop_buffer, scenario_target, peer_valuation

## v2.6 Requirements

- `comparable_companies` section (min 3 peers with P/E, P/S, EV/EBITDA)
- `liquidity_analysis` section (ADV, bid-ask spread, slippage estimates)
- Enhanced `insider_activity` with transaction details
- Minimum 3 arguments in bull/bear case analysis
- Do Nothing gate thresholds: EV>5%, Confidence>60%, R:R>2:1
- Gate result categories: PASS (4/4), MARGINAL (3/4), FAIL (<3)

## v2.6 Requirements (earnings-analysis)

- `scoring` section (catalyst, technical, fundamental, sentiment)
- ROOT-level `do_nothing_gate`
- Correct scenario names (`strong_beat`, etc.)
- IV data from `preparation.implied_move` section

**DEPRECATED**: Versions <2.6 are read-only. New analyses require v2.7.
