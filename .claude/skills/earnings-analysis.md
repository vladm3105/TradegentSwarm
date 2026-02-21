---
title: Earnings Analysis
tags:
  - trading-skill
  - analysis
  - earnings
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
    - "earnings analysis"
    - "analyze earnings"
    - "pre-earnings"
    - "before earnings"
  auto_invoke: true
---

# Earnings Analysis Skill

Use this skill when analyzing stocks 3-10 days before earnings announcements. Auto-invokes when user mentions earnings analysis, pre-earnings setup, or requests analysis before an earnings date.

## When to Use

- User asks for earnings analysis on a ticker
- Scanner identifies high-potential earnings setup
- User mentions upcoming earnings for a stock
- Pre-earnings trade evaluation needed

## Workflow

### Step 1: Get Historical Context (RAG v2.0 + Graph)

Before starting analysis, retrieve relevant context using adaptive retrieval:

```yaml
# Primary: Adaptive hybrid context (auto-routes based on query type)
Tool: rag_hybrid_context
Input: {"ticker": "$TICKER", "query": "earnings analysis historical patterns", "analysis_type": "earnings-analysis"}

# Find similar past earnings analyses for this ticker (direct lookup)
Tool: rag_similar
Input: {"ticker": "$TICKER", "analysis_type": "earnings-analysis", "top_k": 3}

# Alternative: Reranked search for specific earnings patterns (higher relevance)
Tool: rag_search_rerank
Input: {"query": "$TICKER earnings surprise reaction IV crush", "ticker": "$TICKER", "top_k": 5}
```

This returns:
- Similar past earnings analyses for this ticker (direct similarity matching)
- Historical beat/miss patterns (with cross-encoder reranking)
- Known biases from previous trades
- Peer comparison data
- Query auto-classified for optimal retrieval strategy

### Step 2: Get Real-Time Market Data (IB MCP)

```yaml
# Current stock price and volume
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Historical price action (for technical setup)
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "3 M", "bar_size": "1 day"}

# Options implied move (ATM straddle)
Tool: mcp__ib-mcp__get_option_chain
Input: {"symbol": "$TICKER", "include_greeks": true}
```

### Step 3: Gather External Research

For paywalled content (Seeking Alpha, analyst reports):

```yaml
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TICKER earnings preview analyst estimates"}

# For protected articles
Tool: fetch_protected_article
Input: {"url": "https://seekingalpha.com/...", "wait_for_selector": "article"}
```

### Step 4: Read Skill Definition

Load `tradegent_knowledge/skills/earnings-analysis/SKILL.md` and follow the 8-phase framework:

1. **Phase 1: Preparation** - Historical earnings data (8 quarters)
2. **Phase 2: Customer Demand Signals** (50% weight - critical)
3. **Phase 3: Technical Setup**
4. **Phase 4: Sentiment Analysis**
5. **Phase 5: Probability Assessment**
6. **Phase 6: Bias Check**
7. **Phase 7: Decision Framework**
8. **Phase 8: Execution Plan**

### Step 5: Generate Output

Use `tradegent_knowledge/skills/earnings-analysis/template.yaml` structure.

### Step 6: Save Analysis

Save to `tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 7: Index in Knowledge Base (Post-Save Hooks)

After saving, extract entities and embed for future retrieval:

```yaml
# Extract entities to Graph (Neo4j)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search (pgvector)
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 8: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/analysis/earnings/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated analysis content]
  message: "Add earnings analysis for {TICKER}"
```

## Chaining

After completion:
- If recommendation is WATCH → invoke **watchlist** skill
- If recommendation is BULLISH/BEARISH with trade → prepare for **trade-journal** skill
- Update **ticker-profile** if significant new patterns observed

## Arguments

- `$ARGUMENTS`: Ticker symbol (e.g., NVDA, AAPL, MSFT)

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_hybrid_context` | Get historical context (v2.0: adaptive routing) |
| `rag_similar` | Find similar past earnings analyses |
| `rag_search_rerank` | Higher relevance search (v2.0: cross-encoder) |
| `mcp__ib-mcp__get_stock_price` | Current price and volume |
| `mcp__ib-mcp__get_historical_data` | Price history for technicals |
| `mcp__ib-mcp__get_option_chain` | Options IV and implied move |
| `mcp__brave-search__brave_web_search` | Search for analyst reports |
| `fetch_protected_article` | Scrape paywalled content |
| `graph_extract` | Index entities after save |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Analyze $ARGUMENTS for upcoming earnings using the 8-phase framework. Follow all steps: get context, gather data, execute phases, save, index, and push to remote.
