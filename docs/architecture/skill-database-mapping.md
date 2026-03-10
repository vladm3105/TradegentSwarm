# Skill Output to Database Schema Mapping

Complete mapping of Claude Code skill outputs (YAML templates) to PostgreSQL database tables.

---

## Architecture: Files as Source of Truth

**YAML files are the source of truth.** Database storage is derived.

```
Skill Output (YAML)
       │
       │  1. Write to tradegent_knowledge/knowledge/
       ▼
┌──────────────────────────────────────────────────────┐
│  YAML FILES (source of truth)                        │
│  • Git version controlled                            │
│  • Human readable                                    │
│  • Portable and shareable                            │
│  • Disaster recovery source                          │
└──────────────────────────────────────────────────────┘
       │
       │  2. auto-ingest hook → ingest.py
       ▼
┌──────────────────────────────────────────────────────┐
│  DERIVED STORAGE (priority order for fast UI)        │
│  [1] PostgreSQL kb_* tables ← FIRST (UI needs this) │
│  [2] pgvector rag_chunks (semantic search)          │
│  [3] Neo4j graph (entity relationships)             │
└──────────────────────────────────────────────────────┘
```

**Ingestion Priority**: Database first for fastest UI delivery, then RAG, then Graph.

**Why files first?**
- Git history provides audit trail
- Files allow offline review and debugging
- Re-ingest from files if database is lost
- No vendor lock-in to specific database

**UI Visualization**: The tradegent_ui renders visualizations directly from PostgreSQL
`kb_*` tables. SVG file generation is **deprecated** (`svg_generation_enabled=false`).

---

## Overview

| Skill | Template Version | Output Directory | Database Table |
|-------|------------------|------------------|----------------|
| stock-analysis | v2.7 | `analysis/stock/` | `nexus.kb_stock_analyses` |
| earnings-analysis | v2.6 | `analysis/earnings/` | `nexus.kb_earnings_analyses` |

> **Schema version history:** Multiple historical versions coexist in the database. The frontend parser registry handles all versions — see [UI_FEATURES — Analysis Display System](../../tradegent_ui/docs/UI_FEATURES.md#8-analysis-display-system).
>
> | Type | Versions in DB | Notes |
> |------|---------------|-------|
> | stock-analysis | 2.6 (40 rows), 2.7 (18 rows) | v2.7 adds alert `tag` + `derivation` |
> | earnings-analysis | 2.3 (2 rows), 2.5 (14 rows), 2.6 (1 row) | v2.3 uses phase1-7 structure; v2.5+ uses flat `decision.*` structure |
| research | v2.1 | `analysis/research/` | `nexus.kb_research_analyses` |
| ticker-profile | v2.1 | `analysis/ticker-profiles/` | `nexus.kb_ticker_profiles` |
| trade-journal | v2.1 | `trades/{YYYY}/{MM}/` | `nexus.kb_trade_journals` |
| watchlist | v2.1 | `watchlist/` | `nexus.kb_watchlist_entries` |
| post-trade-review | v2.1 | `reviews/{YYYY}/{MM}/` | `nexus.kb_reviews` |
| post-earnings-review | v1.0 | `reviews/post-earnings/` | `nexus.kb_reviews` + `nexus.kb_earnings_results` |
| report-validation | v1.0 | `reviews/validation/` | `nexus.kb_reviews` |

---

## Stock Analysis (v2.7)

**Template**: `skills/stock-analysis/template.yaml`
**Table**: `nexus.kb_stock_analyses`
**Extraction**: `db_layer.py:upsert_kb_stock_analysis()`

### Field Mapping

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `ticker` | `ticker` | VARCHAR(10) | Required |
| `_meta.created` | `analysis_date` | TIMESTAMPTZ | ISO datetime |
| `_meta.version` | `schema_version` | VARCHAR(10) | e.g., "2.7" |
| `current_price` | `current_price` | DECIMAL(12,4) | |
| `recommendation` | `recommendation` | VARCHAR(20) | STRONG_BUY, BUY, WATCH, etc. |
| `confidence.level` | `confidence` | INTEGER | 0-100 |
| `do_nothing_gate.ev_actual` | `expected_value_pct` | DECIMAL(8,4) | |
| `do_nothing_gate.gate_result` | `gate_result` | VARCHAR(20) | PASS, MARGINAL, FAIL |
| `do_nothing_gate.gates_passed` | `gate_criteria_met` | INTEGER | 0-4 |
| `do_nothing_gate.rr_actual` | `risk_reward_ratio` | DECIMAL(5,2) | Fallback |
| `scenarios.strong_bull.probability` | `bull_probability` | DECIMAL(5,2) | |
| `scenarios.base_bull.probability` | `base_probability` | DECIMAL(5,2) | |
| `scenarios.base_bear.probability` | `bear_probability` | DECIMAL(5,2) | |
| `summary.key_levels.entry` | `entry_price` | DECIMAL(12,4) | |
| `summary.key_levels.stop` | `stop_price` | DECIMAL(12,4) | |
| `summary.key_levels.target_1` | `target_1_price` | DECIMAL(12,4) | |
| `summary.key_levels.target_2` | `target_2_price` | DECIMAL(12,4) | |
| `scoring.catalyst_score` | `catalyst_score` | INTEGER | 0-10 |
| `scoring.technical_score` | `technical_score` | INTEGER | 0-10 |
| `scoring.fundamental_score` | `fundamental_score` | INTEGER | 0-10, fallback to environment_score |
| `scoring.sentiment_score` | `sentiment_score` | INTEGER | 0-10 |
| `threat_assessment.total_threat_level` | `total_threat_level` | VARCHAR(20) | low, medium, high, critical |
| `bull_case_analysis.strength` | `bull_case_strength` | INTEGER | 0-100 |
| `bear_case_analysis.strength` | `bear_case_strength` | INTEGER | 0-100 |
| `catalyst.type` | `catalyst_type` | VARCHAR(50) | technical, fundamental, event, etc. |
| `catalyst.date` | `catalyst_date` | TIMESTAMPTZ | |
| `catalyst.days_until` | `days_to_catalyst` | INTEGER | |
| `trade_plan.position_sizing.max_portfolio_pct` | `position_size_pct` | DECIMAL(5,2) | |
| *(full document)* | `yaml_content` | JSONB | Complete YAML as JSON |

### JSONB-Only Fields (Query via yaml_content)

These fields are stored but NOT extracted to columns:

| Template Path | Query Example |
|---------------|---------------|
| `comparable_companies` | `yaml_content->'comparable_companies'->0->>'ticker'` |
| `liquidity_analysis` | `yaml_content->'liquidity_analysis'->>'adv'` |
| `insider_activity` | `yaml_content->'insider_activity'->>'summary'` |
| `alert_levels.price_alerts[]` | `yaml_content->'alert_levels'->'price_alerts'` |
| `summary.key_levels.*_derivation` | `yaml_content->'summary'->'key_levels'->'entry_derivation'` |
| `falsification.criteria[]` | `yaml_content->'falsification'->'criteria'` |
| `thesis_reversal.conditions_to_flip[]` | `yaml_content->'thesis_reversal'->'conditions_to_flip'` |
| `meta_learning.new_rule` | `yaml_content->'meta_learning'->'new_rule'` |
| `bias_check.*` | `yaml_content->'bias_check'` |

---

## Earnings Analysis (v2.6)

**Template**: `skills/earnings-analysis/template.yaml`
**Table**: `nexus.kb_earnings_analyses`
**Extraction**: `db_layer.py:upsert_kb_earnings_analysis()`

### Field Mapping

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `ticker` | `ticker` | VARCHAR(10) | Required |
| `_meta.created` | `analysis_date` | TIMESTAMPTZ | |
| `_meta.version` | `schema_version` | VARCHAR(10) | e.g., "2.6" |
| `earnings_date` | `earnings_date` | DATE | Required |
| `earnings_time` | `earnings_time` | VARCHAR(10) | BMO, AMC |
| `days_to_earnings` | `days_to_earnings` | INTEGER | |
| `current_price` | `current_price` | DECIMAL(12,4) | |
| `decision.recommendation` | `recommendation` | VARCHAR(20) | BULLISH, NEUTRAL, etc. |
| `decision.confidence_pct` | `confidence` | INTEGER | 0-100 |
| `probability.final_probability.p_beat` | `p_beat` | DECIMAL(5,2) | |
| `scenarios.expected_value` | `expected_value_pct` | DECIMAL(8,4) | Fallback |
| `do_nothing_gate.gate_result` | `gate_result` | VARCHAR(20) | ROOT level in v2.6 |
| `do_nothing_gate.gates_passed` | `gate_criteria_met` | INTEGER | |
| `do_nothing_gate.rr_actual` | `risk_reward_ratio` | DECIMAL(5,2) | |
| `bull_case_analysis.strength` | `bull_case_strength` | INTEGER | ROOT level |
| `bear_case_analysis.strength` | `bear_case_strength` | INTEGER | ROOT level |
| `trade_plan.entry.price` | `entry_price` | DECIMAL(12,4) | Fallback to summary.key_levels |
| `trade_plan.stop_loss.price` | `stop_price` | DECIMAL(12,4) | |
| `trade_plan.targets.target_1` | `target_1_price` | DECIMAL(12,4) | |
| `trade_plan.targets.target_2` | `target_2_price` | DECIMAL(12,4) | |
| `scenarios.strong_beat.probability` | `bull_probability` | DECIMAL(5,2) | v2.6 scenario names |
| `scenarios.modest_beat.probability` | `base_probability` | DECIMAL(5,2) | |
| `scenarios.modest_miss.probability` | `bear_probability` | DECIMAL(5,2) | |
| `scenarios.strong_miss.probability` | `disaster_probability` | DECIMAL(5,2) | |
| `scoring.catalyst_score` | `catalyst_score` | INTEGER | v2.6 added |
| `scoring.technical_score` | `technical_score` | INTEGER | v2.6 added |
| `scoring.fundamental_score` | `fundamental_score` | INTEGER | v2.6 added |
| `scoring.sentiment_score` | `sentiment_score` | INTEGER | v2.6 added |
| `threat_assessment.total_threat_level` | `total_threat_level` | VARCHAR(20) | |
| `preparation.implied_move.iv_rank` | `iv_rank` | DECIMAL(5,2) | |
| `preparation.implied_move.percentage` | `expected_move_pct` | DECIMAL(5,2) | |
| *(full document)* | `yaml_content` | JSONB | |

### JSONB-Only Fields

| Template Path | Description |
|---------------|-------------|
| `historical_moves.quarters[]` | Past earnings reactions |
| `customer_demand.signals[]` | Demand indicators |
| `news_age_check.items[]` | News priced-in assessment |
| `falsification.beat_thesis_wrong_if[]` | Invalidation criteria |
| `alternative_strategies.strategies[]` | Other approaches |

---

## Earnings Results (Post-Earnings Review Output)

**Table**: `nexus.kb_earnings_results`
**Extraction**: `db_layer.py:upsert_kb_earnings_result()`

| Source Field | DB Column | Type | Notes |
|--------------|-----------|------|-------|
| `ticker` | `ticker` | VARCHAR(20) | |
| `earnings_date` | `earnings_date` | DATE | Unique with ticker |
| `earnings_time` | `earnings_time` | VARCHAR(10) | |
| `actual_results.eps.actual` | `eps_actual` | DECIMAL(10,4) | |
| `actual_results.eps.consensus` | `eps_consensus` | DECIMAL(10,4) | |
| `actual_results.eps.surprise_pct` | `eps_surprise_pct` | DECIMAL(8,4) | |
| *(computed)* | `eps_beat` | BOOLEAN | GENERATED: actual > consensus |
| `actual_results.revenue.actual_b` | `revenue_actual` | DECIMAL(16,2) | In millions |
| `actual_results.revenue.consensus_b` | `revenue_consensus` | DECIMAL(16,2) | |
| `actual_results.revenue.surprise_pct` | `revenue_surprise_pct` | DECIMAL(8,4) | |
| *(computed)* | `revenue_beat` | BOOLEAN | GENERATED |
| `actual_results.guidance` | `guidance` | VARCHAR(20) | raised, maintained, lowered |
| `actual_results.guidance_details` | `guidance_details` | TEXT | |
| `actual_results.stock_reaction.gap_pct` | `gap_pct` | DECIMAL(8,4) | |
| `actual_results.stock_reaction.day1_move_pct` | `day1_move_pct` | DECIMAL(8,4) | |
| `actual_results.stock_reaction.gap_direction` | `gap_direction` | VARCHAR(10) | up, down, flat |

---

## Trade Journal

**Template**: `skills/trade-journal/template.yaml`
**Table**: `nexus.kb_trade_journals`
**Extraction**: `db_layer.py:upsert_kb_trade_journal()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `trade_id` | VARCHAR(50) | Unique |
| `ticker` | `ticker` | VARCHAR(10) | |
| `direction` | `direction` | VARCHAR(10) | long, short |
| `entry.date` | `entry_date` | TIMESTAMPTZ | |
| `entry.price` | `entry_price` | DECIMAL(12,4) | |
| `exit.date` | `exit_date` | TIMESTAMPTZ | Nullable |
| `exit.price` | `exit_price` | DECIMAL(12,4) | Nullable |
| `outcome` | `outcome` | VARCHAR(20) | win, loss, breakeven |
| `return_pct` | `return_pct` | DECIMAL(8,4) | |
| `pnl_dollars` | `pnl_dollars` | DECIMAL(12,2) | |
| `holding_days` | `holding_days` | INTEGER | |
| `grades.entry` | `entry_grade` | VARCHAR(1) | A-F |
| `grades.exit` | `exit_grade` | VARCHAR(1) | |
| `grades.overall` | `overall_grade` | VARCHAR(1) | |
| `biases_detected[]` | `biases_detected` | TEXT[] | Array |
| `primary_lesson` | `primary_lesson` | TEXT | |
| *(source reference)* | `source_stock_analysis_id` | INTEGER | FK to kb_stock_analyses |
| *(source reference)* | `source_earnings_analysis_id` | INTEGER | FK to kb_earnings_analyses |

---

## Watchlist Entry

**Template**: `skills/watchlist/template.yaml`
**Table**: `nexus.kb_watchlist_entries`
**Extraction**: `db_layer.py:upsert_kb_watchlist_entry()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `watchlist_id` | VARCHAR(50) | Unique |
| `ticker` | `ticker` | VARCHAR(10) | |
| `entry_trigger` | `entry_trigger` | TEXT | Condition description |
| `entry.price` | `entry_price` | DECIMAL(12,4) | |
| `status` | `status` | VARCHAR(20) | active, triggered, expired |
| `priority` | `priority` | VARCHAR(10) | high, medium, low |
| `conviction_level` | `conviction_level` | INTEGER | 0-100 |
| `_meta.expires` | `expires_at` | TIMESTAMPTZ | |
| *(on trigger)* | `triggered_at` | TIMESTAMPTZ | |
| *(on invalidate)* | `invalidated_at` | TIMESTAMPTZ | |
| `source_analysis` | `source_analysis` | VARCHAR(500) | File path |
| `source_score` | `source_score` | DECIMAL(5,2) | Scanner score |
| *(link)* | `source_stock_analysis_id` | INTEGER | FK |
| *(link)* | `source_earnings_analysis_id` | INTEGER | FK |
| *(link)* | `source_scanner_id` | INTEGER | FK to kb_scanner_configs |
| *(on trigger)* | `triggered_price` | DECIMAL(12,4) | |
| *(on trade)* | `resulting_trade_id` | INTEGER | FK to kb_trade_journals |

---

## Reviews (All Types)

**Template**: `skills/post-trade-review/template.yaml`, `skills/post-earnings-review/template.yaml`
**Table**: `nexus.kb_reviews`
**Extraction**: `db_layer.py:upsert_kb_review()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `review_id` | VARCHAR(50) | Unique |
| `_meta.type` | `review_type` | VARCHAR(30) | post-trade-review, post-earnings-review, validation |
| `ticker` | `ticker` | VARCHAR(10) | |
| `grades.overall` | `overall_grade` | VARCHAR(1) | A-F |
| `return_pct` | `return_pct` | DECIMAL(8,4) | |
| `outcome` | `outcome` | VARCHAR(20) | |
| `validation_result` | `validation_result` | VARCHAR(20) | CONFIRM, SUPERSEDE, INVALIDATE |
| `primary_lesson` | `primary_lesson` | TEXT | |
| `biases_detected[]` | `biases_detected` | TEXT[] | |
| `bias_cost_estimate` | `bias_cost_estimate` | DECIMAL(12,2) | |
| *(link)* | `source_analysis_id` | INTEGER | Polymorphic |
| *(link)* | `source_trade_id` | INTEGER | FK to kb_trade_journals |
| *(link)* | `lineage_id` | INTEGER | FK to analysis_lineage |

---

## Ticker Profile

**Template**: `skills/ticker-profile/template.yaml`
**Table**: `nexus.kb_ticker_profiles`
**Extraction**: `db_layer.py:upsert_kb_ticker_profile()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `ticker` | `ticker` | VARCHAR(10) | Unique |
| `company.name` | `company_name` | VARCHAR(200) | |
| `company.sector` | `sector` | VARCHAR(50) | |
| `company.industry` | `industry` | VARCHAR(100) | |
| `company.market_cap_category` | `market_cap_category` | VARCHAR(20) | mega, large, mid, small |
| `trading_characteristics.typical_iv` | `typical_iv` | DECIMAL(5,2) | |
| `trading_characteristics.avg_daily_volume` | `avg_daily_volume` | BIGINT | |
| `trading_characteristics.options_liquidity` | `options_liquidity` | VARCHAR(20) | |
| `performance.total_trades` | `total_trades` | INTEGER | |
| `performance.win_rate` | `win_rate` | DECIMAL(5,2) | |
| `performance.avg_return` | `avg_return` | DECIMAL(8,4) | |
| `performance.total_pnl` | `total_pnl` | DECIMAL(12,2) | |
| `lessons.common_biases[]` | `common_biases` | TEXT[] | |
| `lessons.learned[]` | `lessons_learned` | TEXT[] | |

---

## Research Analysis

**Template**: `skills/research/template.yaml`
**Table**: `nexus.kb_research_analyses`
**Extraction**: `db_layer.py:upsert_kb_research_analysis()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `research_id` | VARCHAR(50) | Unique |
| `_meta.type` | `research_type` | VARCHAR(30) | macro, sector, thematic |
| `title` | `title` | VARCHAR(200) | |
| `_meta.created` | `analysis_date` | TIMESTAMPTZ | |
| `tickers[]` | `tickers` | TEXT[] | Related tickers |
| `sectors[]` | `sectors` | TEXT[] | Related sectors |
| `themes[]` | `themes` | TEXT[] | Investment themes |
| `outlook` | `outlook` | VARCHAR(20) | bullish, neutral, bearish |
| `confidence` | `confidence` | INTEGER | 0-100 |
| `time_horizon` | `time_horizon` | VARCHAR(20) | short, medium, long |

---

## Scanner Config

**Template**: `scanners/{type}/*.yaml`
**Table**: `nexus.kb_scanner_configs`
**Extraction**: `db_layer.py:upsert_kb_scanner_config()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `scanner_code` | VARCHAR(100) | Unique |
| `scanner_config.name` | `scanner_name` | VARCHAR(200) | |
| `_meta.type` | `scanner_type` | VARCHAR(30) | daily, intraday, weekly |
| `scanner_config.category` | `category` | VARCHAR(50) | momentum, earnings, etc. |
| `scanner_config.schedule_time` | `schedule_time` | TIME | |
| `scanner_config.schedule_days[]` | `schedule_days` | TEXT[] | |
| `scanner_config.is_enabled` | `is_enabled` | BOOLEAN | |
| `scanner.sources[]` | `data_sources` | TEXT[] | |
| `output.max_candidates` | `max_candidates` | INTEGER | |
| `scoring.min_score` | `min_score` | DECIMAL(4,2) | |
| `scoring.criteria` | `scoring_criteria` | JSONB | Weights and rules |

---

## Learnings

**Template**: `learnings/{category}/*.yaml`
**Table**: `nexus.kb_learnings`
**Extraction**: `db_layer.py:upsert_kb_learning()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `learning_id` | VARCHAR(50) | Unique |
| `category` | `category` | VARCHAR(30) | bias, pattern, rule |
| `subcategory` | `subcategory` | VARCHAR(50) | |
| `title` | `title` | VARCHAR(200) | |
| `description` | `description` | TEXT | |
| `rule` | `rule_statement` | TEXT | |
| `countermeasure` | `countermeasure` | TEXT | |
| `confidence` | `confidence` | VARCHAR(20) | high, medium, low |
| `validation_status` | `validation_status` | VARCHAR(20) | pending, validated, rejected |
| `evidence_count` | `evidence_count` | INTEGER | |
| `estimated_cost` | `estimated_cost` | DECIMAL(12,2) | |
| `related_tickers[]` | `related_tickers` | TEXT[] | |
| `related_trades[]` | `related_trades` | TEXT[] | Trade IDs |

---

## Strategies

**Template**: `strategies/*.yaml`
**Table**: `nexus.kb_strategies`
**Extraction**: `db_layer.py:upsert_kb_strategy()`

| Template Path | DB Column | Type | Notes |
|---------------|-----------|------|-------|
| `_meta.id` | `strategy_id` | VARCHAR(50) | Unique |
| `name` | `strategy_name` | VARCHAR(200) | |
| `type` | `strategy_type` | VARCHAR(30) | momentum, mean_reversion, etc. |
| `asset_class` | `asset_class` | VARCHAR(20) | equity, options |
| `time_horizon` | `time_horizon` | VARCHAR(20) | |
| `performance.total_trades` | `total_trades` | INTEGER | |
| `performance.win_rate` | `win_rate` | DECIMAL(5,2) | |
| `performance.avg_return` | `avg_return` | DECIMAL(8,4) | |
| `performance.max_drawdown` | `max_drawdown` | DECIMAL(8,4) | |
| `performance.sharpe_ratio` | `sharpe_ratio` | DECIMAL(6,3) | |
| `performance.total_pnl` | `total_pnl` | DECIMAL(12,2) | |
| `status` | `status` | VARCHAR(20) | active, paused, deprecated |
| `confidence_level` | `confidence_level` | VARCHAR(20) | |
| `entry_conditions[]` | `entry_conditions` | TEXT[] | |
| `exit_conditions[]` | `exit_conditions` | TEXT[] | |
| `known_weaknesses[]` | `known_weaknesses` | TEXT[] | |

---

## Supporting Tables

### Alert Tracking

**Table**: `nexus.kb_alert_tracking`

Tracks price alerts from analyses.

| Column | Source | Notes |
|--------|--------|-------|
| `ticker` | Analysis ticker | |
| `source_stock_analysis_id` | FK | |
| `source_earnings_analysis_id` | FK | |
| `alert_type` | `alert_levels.price_alerts[].direction` | price_above, price_below |
| `alert_level` | `alert_levels.price_alerts[].price` | |
| `alert_tag` | `alert_levels.price_alerts[].tag` | v2.7 |
| `status` | System | active, triggered, expired |
| `triggered_at` | System | When alert fired |

### Target Tracking

**Table**: `nexus.kb_target_tracking`

Tracks whether analysis targets were hit.

| Column | Source | Notes |
|--------|--------|-------|
| `ticker` | Analysis | |
| `source_stock_analysis_id` | FK | |
| `price_at_analysis` | `current_price` | |
| `entry_price` | `summary.key_levels.entry` | |
| `stop_price` | `summary.key_levels.stop` | |
| `target_1_price` | `summary.key_levels.target_1` | |
| `entry_hit` | System | Computed from price history |
| `target_1_hit` | System | |
| `stop_hit` | System | |
| `outcome` | System | target_1_hit, stopped_out, etc. |

### Scanner Runs

**Table**: `nexus.kb_scanner_runs`

Scanner execution results with candidates.

| Column | Source | Notes |
|--------|--------|-------|
| `run_id` | Generated | `{scanner_name}_{timestamp}` |
| `scanner_name` | `scanner_config.name` | |
| `scanner_config_id` | FK | Link to kb_scanner_configs |
| `run_timestamp` | System | When scan executed |
| `schedule_type` | Config | daily, intraday, weekly |
| `market_phase` | System | premarket, open, close |
| `market_regime` | IB MCP | bull, bear, neutral |
| `vix_level` | IB MCP | Current VIX |
| `spy_change_pct` | IB MCP | SPY % change |
| `universe_size` | Scan | Total stocks scanned |
| `scored_candidates` | Scan | Candidates scored |
| `high_score_count` | Scan | Score >= 7.5 |
| `watchlist_count` | Scan | Score 5.5-7.4 |
| `top_candidate_ticker` | Scan | Best candidate |
| `top_candidate_score` | Scan | Best score |
| `yaml_content` | Full YAML | Complete scan results |

### Price History

**Table**: `nexus.kb_price_history`

Historical OHLCV for backtesting.

| Column | Source | Notes |
|--------|--------|-------|
| `ticker` | | |
| `price_date` | | |
| `open_price`, `high_price`, `low_price`, `close_price` | IB MCP | |
| `volume` | IB MCP | |
| `sma_20`, `sma_50`, `sma_200` | Computed | |
| `rsi_14`, `atr_14` | Computed | |

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SKILL EXECUTION                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Claude Code executes skill                                      │
│  2. Generates YAML from template                                    │
│  3. Saves to tradegent_knowledge/knowledge/                         │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       AUTO-INGEST HOOK                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  scripts/ingest.py detects doc_type and routes:                     │
│                                                                     │
│  stock-analysis    → upsert_kb_stock_analysis()                     │
│  earnings-analysis → upsert_kb_earnings_analysis()                  │
│  research          → upsert_kb_research_analysis()                  │
│  ticker-profile    → upsert_kb_ticker_profile()                     │
│  trade-journal     → upsert_kb_trade_journal()                      │
│  watchlist         → upsert_kb_watchlist_entry()                    │
│  *-review          → upsert_kb_review()                             │
│  scanner-run       → upsert_kb_scanner_run()                        │
│                                                                     │
│  Post-processing (automatic):                                       │
│  - post-earnings-review → extracts to kb_earnings_results           │
│  - stock/earnings analysis → triggers extract alerts (DB trigger)   │
│  - stock/earnings analysis → triggers create target tracking        │
│                                                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│   PostgreSQL    │ │  pgvector   │ │     Neo4j       │
│   kb_* tables   │ │ rag_chunks  │ │  Knowledge      │
│                 │ │             │ │  Graph          │
│ - Extracted     │ │ - Semantic  │ │ - Entities      │
│   columns       │ │   search    │ │ - Relations     │
│ - yaml_content  │ │ - Similar   │ │ - Patterns      │
│   JSONB         │ │   analyses  │ │                 │
└─────────────────┘ └─────────────┘ └─────────────────┘
```

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-02 | 1.0 | Initial mapping document |
| 2026-03-02 | 1.1 | Added earnings-analysis v2.6 scoring section |
| 2026-03-02 | 1.2 | Added scanner_run, price_history, auto-extraction triggers |
| 2026-03-02 | 1.3 | Documented file-first architecture, deprecated SVG generation |
