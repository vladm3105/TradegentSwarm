---
title: Stock Analysis v2.6
tags:
  - trading-skill
  - analysis
  - technical
  - ai-agent-primary
  - v2.6-required
custom_fields:
  skill_category: analysis
  priority: primary
  development_status: active
  version: "2.6"
  min_version: "2.6"
  upstream_artifacts:
    - ticker-profile
    - scan
  downstream_artifacts:
    - visualize-analysis
    - watchlist
    - trade-journal
  triggers:
    - "stock analysis"
    - "analyze stock"
    - "technical analysis"
    - "value analysis"
    - "momentum trade"
  auto_invoke: true
---

# Stock Analysis Skill v2.6

**ONLY v2.6 IS SUPPORTED. Older versions are deprecated.**

Use this skill for non-earnings trading opportunities: technical breakouts, value plays, momentum trades, post-earnings drift.

## v2.6 Requirements

| Section | Requirement |
|---------|-------------|
| `_meta.forecast_valid_until` | YYYY-MM-DD when analysis expires |
| `comparable_companies` | Min 3 peers with P/E, P/S, EV/EBITDA |
| `liquidity_analysis` | ADV, bid-ask spread, slippage estimates |
| `insider_activity` | Transaction details with Form 4 summary |
| `bull_case_analysis` | Min 3 scored arguments |
| `bear_case_analysis` | Min 3 scored arguments |
| `do_nothing_gate` | EV>5%, Confidence>60%, R:R>2:1 (fixed) |

## Forecast Validity

Every analysis MUST set `forecast_valid_until` in `_meta`:

| Scenario | Forecast Valid Until | Horizon Days |
|----------|---------------------|--------------|
| Has earnings date | Next earnings date | Days to earnings |
| No upcoming earnings | +30 calendar days | 30 |
| Major catalyst pending | Catalyst date | Days to catalyst |
| Macro/sector play | +14-21 days | 14-21 |

After `forecast_valid_until`, the analysis is **historical only** - used for learning/review, not trading decisions.

## Workflow

### Step 1: Time Validation (REQUIRED)

```bash
# Get system time
date '+%A %Y-%m-%d %H:%M:%S %Z'
```

```yaml
# Get IB time - verify sync
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "SPY"}
```

- If weekend: proceed with WARNING, use last close
- If time delta >1hr: ABORT

### Step 2: Get Historical Context (RAG + Graph)

```yaml
Tool: rag_hybrid_context
Input: {"ticker": "$TICKER", "query": "stock analysis", "analysis_type": "stock-analysis"}

Tool: rag_similar
Input: {"ticker": "$TICKER", "analysis_type": "stock-analysis", "top_k": 3}

Tool: graph_context
Input: {"ticker": "$TICKER"}
```

### Step 3: Get Real-Time Market Data (IB MCP)

```yaml
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "6 M", "bar_size": "1 day"}

Tool: mcp__ib-mcp__get_fundamental_data
Input: {"symbol": "$TICKER", "report_type": "ReportSnapshot"}
```

### Step 4: Get Comparable Companies (v2.6 REQUIRED)

```yaml
Tool: graph_peers
Input: {"ticker": "$TICKER"}

# For each peer, get fundamentals
Tool: mcp__ib-mcp__get_fundamental_data
Input: {"symbol": "$PEER", "report_type": "ReportSnapshot"}
```

Build peer table with minimum 3 peers:
| Ticker | P/E Fwd | P/S | EV/EBITDA | Rev Growth | Mkt Cap |

### Step 5: Get Liquidity Data (v2.6 REQUIRED)

From historical data, calculate:
- ADV (shares and dollars)
- Bid-ask spread %
- Slippage estimates for $10K/$50K/$100K positions
- Liquidity score 1-10

### Step 6: Research

```yaml
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TICKER analyst ratings insider transactions news"}
```

### Step 7: Execute 16-Phase Framework

Read `tradegent_knowledge/skills/stock-analysis/SKILL.md` and execute:

```
Phase 0:   Time Validation
Phase 0.5: Data Quality Check
Phase 1:   Catalyst Identification
Phase 1.5: News Age Check
Phase 2:   Market Environment
Phase 2.5: Threat Assessment
Phase 3:   Technical Analysis
Phase 4:   Fundamental Check
Phase 4.5: Comparable Companies (v2.6)
Phase 4.6: Liquidity Analysis (v2.6)
Phase 5:   Sentiment & Positioning
Phase 5.5: Expectations Assessment
Phase 6:   Scenario Analysis (4 scenarios)
Phase 7:   Steel-Man Cases (Bull/Base/Bear - min 3 args each)
Phase 8:   Bias Check
Phase 9:   Do Nothing Gate (NORMALIZED thresholds)
Phase 9.5: Pass Reasoning (if NO_POSITION)
Phase 10:  Alternative Strategies
Phase 11:  Trade Plan
Phase 12:  Summary & Action Items
```

### Step 8: Do Nothing Gate (v2.6 NORMALIZED)

**FIXED THRESHOLDS - DO NOT MODIFY:**

| Criteria | Threshold |
|----------|-----------|
| Expected Value | >5% |
| Confidence | >60% |
| Risk:Reward | >2:1 |
| Edge Not Priced | Yes |

**Gate Results:**
- PASS (4/4): Full position eligible
- MARGINAL (3/4): Reduced position or WATCH
- FAIL (<3): NO_POSITION or AVOID

### Step 9: Generate Output

Use `tradegent_knowledge/skills/stock-analysis/template.yaml` (v2.6).

**REQUIRED: End with JSON block:**

```json
{
    "ticker": "SYMBOL",
    "gate_passed": true,
    "gate_result": "PASS|MARGINAL|FAIL",
    "recommendation": "STRONG_BUY|BUY|WATCH|NO_POSITION|AVOID",
    "confidence": 0-100,
    "expected_value_pct": 0.0,
    "entry_price": null,
    "stop_loss": null,
    "target": null,
    "position_size_pct": 0.0,
    "structure": "shares|calls|puts|spread|none",
    "forecast_valid_until": "YYYY-MM-DD",
    "rationale_summary": "One sentence summary"
}
```

### Step 10: Validate & Save

```bash
# REQUIRED: Validate before saving
python scripts/validate_analysis.py <file.yaml>
```

Save to: `tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 11: Index & Push

```yaml
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge
  branch: main
  files:
    - path: knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [analysis content]
  message: "Add stock analysis v2.6 for {TICKER}"
```

### Step 12: Generate Visualization (v2.6)

Generate SVG dashboard for human review:

```bash
cd /opt/data/tradegent_swarm/tradegent && python scripts/visualize_analysis.py ../tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml
```

Output: `{TICKER}_{YYYYMMDDTHHMM}.svg` (same directory as YAML)

The SVG dashboard displays:
- Recommendation badge with confidence
- Price range visualization
- Do Nothing Gate results (4 criteria)
- Scenario analysis with probability bars
- Comparable companies table
- Bull/Bear strength indicators
- Trade structure summary

## Scoring

```
Catalyst Quality:     ___/10 × 0.25
Market Environment:   ___/10 × 0.15
Technical Setup:      ___/10 × 0.25
Risk/Reward:          ___/10 × 0.25
Sentiment Edge:       ___/10 × 0.10
─────────────────────────────────
TOTAL SCORE:                ___/10
```

| Score | Gate | Recommendation |
|-------|------|----------------|
| ≥7.5 | PASS | STRONG_BUY/SELL |
| 6.5-7.4 | PASS | BUY/SELL |
| 5.5-6.4 | MARGINAL | WATCH |
| <5.5 | FAIL | NO_POSITION/AVOID |

## Chaining

- **Always** → generate **visualize-analysis** SVG
- WATCH → invoke **watchlist** skill
- BUY/SELL → prepare for **trade-journal** skill

## Workflow Automation

Post-analysis workflow runs automatically when `auto_viz_enabled` and `auto_watchlist_chain` settings are enabled:

```
Analysis Saved → Auto-Viz SVG → Extract Chain Data → Auto-Chain
                     │                  │                │
                     ▼                  ▼                ▼
               SVG dashboard    recommendation     WATCH → nexus.watchlist
                                  + EV/conf       BUY/SELL → ready for trade
```

**Database Settings:**
- `auto_viz_enabled`: Auto-generate SVG after save (default: true)
- `auto_watchlist_chain`: Auto-add WATCH to database watchlist (default: true)

The orchestrator handles this automatically via `_post_analysis_workflow()` function.

## MCP Tools

| Tool | Purpose |
|------|---------|
| `rag_hybrid_context` | Historical context |
| `rag_similar` | Similar past analyses |
| `graph_context` | Full ticker context |
| `graph_peers` | Comparable companies |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_historical_data` | Price/volume history |
| `mcp__ib-mcp__get_fundamental_data` | Fundamentals |
| `mcp__brave-search__brave_web_search` | Research |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to repo |

## Execution

Analyze $ARGUMENTS using v2.6 framework. All 16 phases required. Validate before save.
