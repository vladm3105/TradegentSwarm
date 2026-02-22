---
title: Stock Analysis
tags:
  - trading-skill
  - analysis
  - technical
  - ai-agent-primary
custom_fields:
  skill_category: analysis
  priority: primary
  development_status: active
  upstream_artifacts:
    - ticker-profile
    - scan
  downstream_artifacts:
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

# Stock Analysis Skill

Use this skill for non-earnings trading opportunities: technical breakouts, value plays, momentum trades, post-earnings drift. Auto-invokes when user requests stock analysis without earnings context.

## When to Use

- Technical breakout/breakdown setup identified
- Value opportunity analysis needed
- Momentum/trend following evaluation
- Post-earnings drift analysis
- Catalyst-driven opportunity (non-earnings)

## Workflow

### Step 1: Get Historical Context (RAG v2.0 + Graph)

Before starting analysis, retrieve relevant context using adaptive retrieval:

```yaml
# Primary: Adaptive hybrid context (auto-routes based on query type)
Tool: rag_hybrid_context
Input: {"ticker": "$TICKER", "query": "stock analysis technical patterns catalyst", "analysis_type": "stock-analysis"}

# Find similar past analyses for this ticker (direct lookup)
Tool: rag_similar
Input: {"ticker": "$TICKER", "analysis_type": "stock-analysis", "top_k": 3}

# Alternative: Reranked search for specific queries (higher relevance)
Tool: rag_search_rerank
Input: {"query": "$TICKER competitive position market share", "ticker": "$TICKER", "top_k": 5}
```

This returns:
- Similar past analyses for this ticker (direct similarity matching)
- Known technical patterns (with cross-encoder reranking for relevance)
- Previous trade outcomes
- Sector peer data
- Query is auto-classified (retrieval/relationship/comparison/trend) for optimal routing

### Step 2: Get Real-Time Market Data (IB MCP)

```yaml
# Current stock price
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Historical data for technical analysis
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "6 M", "bar_size": "1 day"}

# Intraday for entry timing
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "5 D", "bar_size": "15 mins"}

# Fundamentals
Tool: mcp__ib-mcp__get_fundamental_data
Input: {"symbol": "$TICKER", "report_type": "ReportSnapshot"}
```

### Step 3: Get Sector Context

```yaml
# Find sector peers from Graph
Tool: graph_peers
Input: {"ticker": "$TICKER"}

# Get known risks
Tool: graph_risks
Input: {"ticker": "$TICKER"}
```

### Step 4: Gather External Research

```yaml
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TICKER technical analysis catalyst news"}

# For analyst reports
Tool: fetch_protected_article
Input: {"url": "...", "wait_for_selector": "article"}
```

### Step 5: Read Skill Definition

Load `tradegent_knowledge/skills/stock-analysis/SKILL.md` and follow the 7-phase framework:

1. **Phase 1: Catalyst Identification** (no catalyst = no trade)
2. **Phase 2: Market Environment** (regime, sector, volatility)
3. **Phase 3: Technical Analysis** (trend, patterns, levels)
4. **Phase 4: Fundamental Check** (valuation, growth, red flags)
5. **Phase 5: Sentiment & Positioning**
6. **Phase 6: Scenario Analysis** (bull/base/bear with probabilities)
7. **Phase 7: Risk Management** (position sizing, R:R)

### Step 6: Calculate Setup Score

```
Catalyst Quality:     ___/10 × 0.25
Market Environment:   ___/10 × 0.15
Technical Setup:      ___/10 × 0.25
Risk/Reward:          ___/10 × 0.25
Sentiment Edge:       ___/10 × 0.10
─────────────────────────────────
TOTAL SCORE:                ___/10
```

- Score ≥ 7.5: STRONG_BUY or STRONG_SELL
- Score 6.5-7.4: BUY or SELL
- Score 5.5-6.4: WATCH
- Score < 5.5: AVOID

### Step 7: Generate Output

Use `tradegent_knowledge/skills/stock-analysis/template.yaml` structure.

**CRITICAL: End your analysis with a JSON block for machine parsing:**

```json
{
    "ticker": "SYMBOL",
    "gate_passed": true/false,
    "recommendation": "BULLISH/BEARISH/NEUTRAL/WAIT",
    "confidence": 0-100,
    "expected_value_pct": 0.0,
    "entry_price": null or price,
    "stop_loss": null or price,
    "target": null or price,
    "position_size_pct": 0.0,
    "structure": "shares/calls/puts/spread/none",
    "rationale_summary": "One sentence summary of recommendation"
}
```

This JSON block is REQUIRED for the orchestrator to parse your analysis. Without it, the analysis will show 0% confidence.

### Step 8: Save Analysis

Save to `tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 9: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 10: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/analysis/stock/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated analysis content]
  message: "Add stock analysis for {TICKER}"
```

## Chaining

After completion:
- If recommendation is WATCH → invoke **watchlist** skill
- If recommendation is BUY/SELL → prepare for **trade-journal** skill
- Update **ticker-profile** with new levels and observations

## Arguments

- `$ARGUMENTS`: Ticker symbol and optional catalyst description

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_hybrid_context` | Get historical context (v2.0: adaptive routing) |
| `rag_similar` | Find similar past analyses for ticker |
| `rag_search_rerank` | Higher relevance search (v2.0: cross-encoder) |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_historical_data` | Price history |
| `mcp__ib-mcp__get_fundamental_data` | Company fundamentals |
| `graph_peers` | Sector peer comparison |
| `graph_risks` | Known risk factors |
| `mcp__brave-search__brave_web_search` | Research |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Analyze $ARGUMENTS using the 7-phase stock analysis framework. Follow all steps: get context, gather data, execute phases, calculate score, save, index, and push to remote.
