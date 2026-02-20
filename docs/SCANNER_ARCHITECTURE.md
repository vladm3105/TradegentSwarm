# Scanner System — Architecture

> **Status**: Active
> **Last updated**: 2026-02-20
> **Location**: `trading/knowledge/scanners/`
> **Companion**: [TRADING_RAG_ARCHITECTURE.md](TRADING_RAG_ARCHITECTURE.md), [TRADING_GRAPH_ARCHITECTURE.md](TRADING_GRAPH_ARCHITECTURE.md)

## Overview

The Scanner System is a YAML-configuration-based framework for systematically identifying trading opportunities. Scanners encode trading edge as repeatable, automated rules that integrate with IB MCP, RAG, and Graph systems.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SCANNER SYSTEM FLOW                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐        │
│  │   Schedule   │────▶│   Scanner    │────▶│   Scoring    │        │
│  │   Trigger    │     │   Execute    │     │   & Routing  │        │
│  └──────────────┘     └──────────────┘     └──────────────┘        │
│                              │                     │                 │
│                              ▼                     ▼                 │
│                       ┌────────────┐        ┌────────────┐          │
│                       │  IB MCP +  │        │  Skills    │          │
│                       │  Web Data  │        │  Chaining  │          │
│                       └────────────┘        └────────────┘          │
│                                                    │                 │
│                                                    ▼                 │
│                                    ┌───────────────────────────┐    │
│                                    │  Analysis / Watchlist     │    │
│                                    │  RAG + Graph Indexing     │    │
│                                    └───────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Configuration as knowledge** — Scanner YAML encodes trading edge, not just automation
2. **Weighted scoring** — Criteria weights sum to 1.0; consistent, reproducible ranking
3. **Automatic skill chaining** — High scores trigger analysis skills automatically
4. **Multi-source data** — Combines IB market data with web search for catalysts
5. **Strategy assignment** — Each scanner defines trade setups by score/criteria

---

## 1. Scanner Types

### 1.1 Classification

| Type | Folder | Frequency | Examples |
|------|--------|-----------|----------|
| **Daily** | `scanners/daily/` | Once per day at scheduled time | premarket-gap, earnings-momentum |
| **Intraday** | `scanners/intraday/` | Multiple times per day | unusual-volume, options-flow |
| **Weekly** | `scanners/weekly/` | Once per week | earnings-calendar, institutional-activity |

### 1.2 Available Scanners

| Scanner | Category | Key Criteria | Run Time (ET) |
|---------|----------|--------------|---------------|
| `premarket-gap` | Momentum | Gap >3%, catalyst, volume | 08:30 |
| `earnings-momentum` | Earnings | Beat history, IV, sentiment | 09:45 |
| `market-regime` | Context | Bull/bear/neutral classification | 09:35 |
| `news-catalyst` | Event | Material news, price impact | 07:00, 12:00, 18:00 |
| `52w-extremes` | Technical | Breakout/breakdown, volume | 15:45 |
| `oversold-bounce` | Mean Reversion | RSI, support levels | 15:50 |
| `sector-rotation` | Macro | Sector flows, relative strength | 16:15 |
| `options-flow` | Sentiment | Unusual options activity | 09:45, 11:00, 13:00, 15:00 |
| `unusual-volume` | Momentum | Volume spikes, news | 10:00, 11:30, 14:00, 15:30 |
| `earnings-calendar` | Weekly | Week ahead earnings | Sunday 07:00 |
| `institutional-activity` | Weekly | 13F filings, insider trades | Mon/Fri 18:00 |

---

## 2. Scanner YAML Structure

```yaml
# ═══════════════════════════════════════════════════════════════
# SCANNER TEMPLATE
# ═══════════════════════════════════════════════════════════════

_meta:
  id: SCANNER-{NAME}-001
  type: scanner-config
  version: 1
  created: "2025-01-25T09:00:00Z"
  updated: "2025-01-25T09:00:00Z"
  status: active
  run_frequency: daily | intraday | weekly
  last_run: null

scanner_config:
  name: "Scanner Display Name"
  description: "What this scanner finds"
  category: momentum | earnings | technical | macro
  priority: 1-10  # Execution order (1 = first)

  schedule:
    run_at: "08:30"  # ET
    run_days: [mon, tue, wed, thu, fri]
    skip_dates: []

  limits:
    max_results: 50
    max_api_calls: 10
    timeout_seconds: 30

# ═══════════════════════════════════════════════════════════════
# DATA SOURCES
# ═══════════════════════════════════════════════════════════════

scanner:
  source: multi  # ib_only | web_only | multi

  ib_scanner:
    scan_code: TOP_OPEN_PERC_GAIN  # IB scanner code
    instrument: STK
    location: STK.US.MAJOR
    filters:
      above_price: 10
      below_price: 500
      above_volume: 100000

  web_search:
    queries:
      - "{TICKER} catalyst news"
      - "{TICKER} analyst upgrade downgrade"
    sources:
      - benzinga.com
      - seekingalpha.com
    recency: "24h"

# ═══════════════════════════════════════════════════════════════
# QUALITY FILTERS
# ═══════════════════════════════════════════════════════════════

quality_filters:
  liquidity:
    min_avg_volume: 1000000
    min_dollar_volume_m: 10
    max_spread_pct: 0.3

  fundamentals:
    exclude_sectors: [Utilities]
    min_market_cap_m: 500

  technicals:
    require_above_200d_ma: false
    min_atr_pct: 1.0

  exclusions:
    exclude_tickers: [SPY, QQQ, IWM]  # ETFs
    exclude_if_held: false
    exclude_recent_trades_days: 14

# ═══════════════════════════════════════════════════════════════
# SCORING CRITERIA (weights sum to 1.0)
# ═══════════════════════════════════════════════════════════════

scoring:
  criteria:
    - name: criterion_1
      weight: 0.30
      calculation: |
        10: Best case description
        7: Good case description
        5: Average case description
        3: Below average description
        1: Poor case description

    - name: criterion_2
      weight: 0.25
      calculation: |
        10: ...
        5: ...
        1: ...

    # ... additional criteria

  min_total_score: 6.0      # Minimum to include in output
  auto_analyze_threshold: 7.5  # Trigger full analysis skill

# ═══════════════════════════════════════════════════════════════
# STRATEGY ASSIGNMENT
# ═══════════════════════════════════════════════════════════════

strategies:
  strategy_1:
    description: "Strategy description"
    criteria:
      - score >= 8
      - criterion_1 >= 7
    entry: "Entry trigger description"
    stop: "Stop loss description"
    target: "Profit target description"

  strategy_2:
    description: "Alternative strategy"
    criteria:
      - score <= 5
    entry: "..."
    stop: "..."
    target: "..."

# ═══════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════

output:
  format: watchlist

  capture_fields:
    - ticker
    - score
    - recommended_strategy
    # ... scanner-specific fields

  storage:
    watchlist_path: "watchlist/{YYYY}/{MM}/"
    log_path: "scanner-logs/{YYYY}/{MM}/{scanner_name}/"

  notifications:
    on_high_score: true
    on_unusual_volume: true

# ═══════════════════════════════════════════════════════════════
# AI AGENT INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════

agent_instructions:
  execution_steps:
    1: "Step 1 description"
    2: "Step 2 description"
    # ...

  decision_framework: |
    IF condition_1 → action_1
    IF condition_2 → action_2

  common_mistakes_to_avoid:
    - "Mistake 1"
    - "Mistake 2"

# ═══════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH HINTS
# ═══════════════════════════════════════════════════════════════

_graph:
  entities:
    - [scanner, SCANNER-{NAME}-001]
    - [category, {category}]
  relations:
    - [this, scans_for, {pattern_type}]

_links:
  skill_reference: "/path/to/skill/SKILL.md"
  output_template: "reference/templates/{template}.yaml"
```

---

## 3. Execution Flow

### 3.1 Step-by-Step Process

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: SCHEDULE TRIGGER                                        │
│ • Cron-like schedule from scanner_config.schedule               │
│ • Example: premarket-gap runs at 08:30 ET                       │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: LOAD SCANNER CONFIG                                     │
│ • Read YAML from scanners/{type}/{name}.yaml                    │
│ • Parse all sections                                            │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: EXECUTE IB SCANNER                                      │
│ • Tool: mcp__ib-mcp__run_scanner                                │
│ • Parameters from scanner.ib_scanner                            │
│ • Get raw candidate list                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: GATHER ADDITIONAL DATA                                  │
│ • mcp__ib-mcp__get_quotes_batch (prices, volume, IV)           │
│ • mcp__brave-search__brave_web_search (catalysts, news)        │
│ • rag_search (prior context for tickers)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: APPLY QUALITY FILTERS                                   │
│ • Filter by liquidity (volume, dollar volume, spread)          │
│ • Filter by fundamentals (market cap, sector)                   │
│ • Apply exclusion lists                                         │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: SCORE CANDIDATES                                        │
│ • Calculate each criterion score (1-10)                         │
│ • Apply weights: Score = Σ(Criterion × Weight)                  │
│ • Rank by final score                                           │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: ROUTE BY SCORE                                          │
│ • ≥ 7.5: Trigger analysis skill (earnings or stock)            │
│ • 5.5-7.4: Add to watchlist                                     │
│ • < 5.5: Skip (log only)                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: OUTPUT & INDEX                                          │
│ • Save watchlist entries                                        │
│ • Index in Graph (graph_extract)                                │
│ • Embed for search (rag_embed)                                  │
│ • Push to GitHub (mcp__github-vl__push_files)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 MCP Tools Used

| Tool | Purpose | When Used |
|------|---------|-----------|
| `mcp__ib-mcp__run_scanner` | Execute IB market scanner | Step 3 |
| `mcp__ib-mcp__get_scanner_params` | Get available scanner types | Setup |
| `mcp__ib-mcp__get_quotes_batch` | Batch quotes for candidates | Step 4 |
| `mcp__ib-mcp__get_news_headlines` | News headlines per ticker | Step 4 |
| `mcp__ib-mcp__get_historical_data` | Price history for technicals | Step 4 |
| `mcp__brave-search__brave_web_search` | Catalyst and sentiment search | Step 4 |
| `rag_search` | Prior analyses and context | Step 4 |
| `graph_context` | Entity relationships | Step 4 |
| `graph_extract` | Index scan results | Step 8 |
| `rag_embed` | Embed for semantic search | Step 8 |
| `mcp__github-vl__push_files` | Push to remote | Step 8 |

---

## 4. Scoring System

### 4.1 Calculation

```
FINAL SCORE = Σ (Criterion_Score × Weight)

Where:
- Each Criterion_Score is 1-10
- All Weights sum to 1.0
- Final Score ranges 1-10
```

### 4.2 Score Interpretation

| Score Range | Classification | Action |
|-------------|----------------|--------|
| ≥ 7.5 | High Priority | Trigger full analysis skill |
| 6.5-7.4 | Good | Add to watchlist, monitor closely |
| 5.5-6.4 | Marginal | Add to watchlist, lower priority |
| < 5.5 | Skip | Log only, do not trade |

### 4.3 Example: Earnings Momentum Scoring

| Criterion | Weight | 10 Score | 5 Score | 1 Score |
|-----------|--------|----------|---------|---------|
| Beat History | 0.20 | 8/8 beats | 4-5/8 beats | <2/8 beats |
| Momentum | 0.25 | All signals bullish | Mixed signals | Bearish momentum |
| Sentiment | 0.20 | Bullish, whisper > consensus | Neutral | Bearish sentiment |
| IV Setup | 0.15 | IV 40-60 percentile | IV 30-40 or 75-85 | IV >85 (expensive) |
| Historical Reaction | 0.20 | Consistent 8%+ moves | 3-5% moves | <3% or erratic |

---

## 5. Skill Chaining

### 5.1 Automatic Triggers

```
SCANNER OUTPUT
      ↓
┌─────────────────────────────────────┐
│ Score ≥ 7.5?                        │
└──────────────┬──────────────────────┘
               ↓
        ┌──────┴──────┐
        │             │
       YES           NO
        │             │
        ▼             ▼
┌───────────────┐  ┌───────────────┐
│ Has earnings  │  │ Score 5.5-7.4?│
│ in 10 days?   │  └───────┬───────┘
└───────┬───────┘          │
        │                  ▼
   ┌────┴────┐      ┌─────────────┐
  YES       NO      │  watchlist  │
   │         │      │    skill    │
   ▼         ▼      └─────────────┘
┌────────┐ ┌────────┐
│earnings│ │ stock  │
│analysis│ │analysis│
│ skill  │ │ skill  │
└────────┘ └────────┘
```

### 5.2 Complete Workflow Chain

```
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

---

## 6. Strategy Assignment

### 6.1 Strategy Matrix

Each scanner defines strategies based on score and criteria:

**Pre-Market Gap Scanner:**

| Strategy | Score | Criteria | Entry | Stop | Target |
|----------|-------|----------|-------|------|--------|
| Gap & Go | ≥8 | Strong catalyst, volume | First 5-min high break | Below pre-market low | 1.5-2x risk |
| Gap Fade | ≤5 | Weak/no catalyst | After failed push | Above pre-market high | 50% gap fill |
| Gap Pullback | ≥7 | Gap holding | VWAP test | Below VWAP by 1 ATR | Pre-market high |

**Earnings Momentum Scanner:**

| Conviction | Price Action | Position Recommendation |
|------------|--------------|-------------------------|
| High (>70%) | Rising | Full size, enter now |
| High | Flat | Full size, enter now |
| High | Declining | Wait for stabilization, reduced size |
| Medium (55-70%) | Rising/Flat | Reduced size or spreads |
| Medium | Declining | Pass or small contrarian |
| Low (<55%) | Any | Pass - insufficient edge |

---

## 7. Daily Trading Routine

### 7.1 Schedule (ET)

| Time | Scanner | Purpose | Action on High Score |
|------|---------|---------|----------------------|
| 07:00 | news-catalyst | Overnight news | Trigger stock-analysis |
| 08:30 | premarket-gap | Gaps with catalysts | Trigger stock-analysis |
| 09:35 | market-regime | Market classification | Context for all scans |
| 09:45 | earnings-momentum | Pre-earnings setups | Trigger earnings-analysis |
| 10:00+ | unusual-volume | Volume spikes | Trigger stock-analysis |
| 15:45 | 52w-extremes | Breakouts/breakdowns | Trigger stock-analysis |
| 15:50 | oversold-bounce | Mean reversion | Add to watchlist |
| 16:15 | sector-rotation | Money flows | Inform next day |

### 7.2 Weekly Schedule

| Day | Time | Scanner | Purpose |
|-----|------|---------|---------|
| Sunday | 07:00 | earnings-calendar | Plan week ahead |
| Monday | 18:00 | institutional-activity | 13F filings review |
| Friday | 18:00 | institutional-activity | Week's insider activity |

---

## 8. Integration with RAG + Graph

### 8.1 Pre-Scan Context

Before scoring, scanners can retrieve prior knowledge:

```yaml
# Get ticker context from Graph
Tool: graph_context
Input: {"ticker": "NVDA"}
# Returns: peers, risks, strategies, biases

# Get similar past analyses from RAG
Tool: rag_similar
Input: {"ticker": "NVDA", "analysis_type": "earnings"}
# Returns: prior earnings analyses for comparison
```

### 8.2 Post-Scan Indexing

After generating output, results are indexed:

```yaml
# Extract entities for Graph
Tool: graph_extract
Input: {"file_path": "trading/knowledge/scans/earnings-momentum_20250220T0945.yaml"}

# Embed for RAG search
Tool: rag_embed
Input: {"file_path": "trading/knowledge/scans/earnings-momentum_20250220T0945.yaml"}
```

---

## 9. Performance Tracking

### 9.1 Metrics Per Scanner

| Metric | Definition | Target |
|--------|------------|--------|
| Hit Rate | % of high-score candidates that move as expected | >60% |
| Win Rate | % of traded candidates that were profitable | >55% |
| Avg Return | Mean return per traded signal | >1.5x risk |
| False Positive Rate | % of high scores that failed | <30% |
| Time-to-Move | Days from signal to target move | <5 days |

### 9.2 Optimization

- Track metrics per scanner over 30-day rolling window
- Adjust scoring weights based on performance
- Refine quality filters to reduce false positives
- Update strategy parameters based on actual results

---

## 10. Security

Scanner configurations encode trading edge. Security considerations:

1. **Do not share** scoring weights or quality filter thresholds
2. **Version control** scanner changes (git history)
3. **Review changes** before committing scanner modifications
4. **Backup** scanner configs separately from public documentation

---

## Related Documentation

- [TRADING_RAG_ARCHITECTURE.md](TRADING_RAG_ARCHITECTURE.md) — Semantic search system
- [TRADING_GRAPH_ARCHITECTURE.md](TRADING_GRAPH_ARCHITECTURE.md) — Knowledge graph system
- [trading/knowledge/scanners/README.md](../trading/knowledge/scanners/README.md) — Scanner folder documentation
- [.claude/skills/scan.md](../.claude/skills/scan.md) — Scan skill definition
