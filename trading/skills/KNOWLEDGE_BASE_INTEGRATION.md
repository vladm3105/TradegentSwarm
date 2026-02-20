# Knowledge Base Integration

This document describes how trading skills integrate with the RAG (pgvector) and Graph (Neo4j) systems via MCP tools.

## Skill Integration Pattern

Every skill follows this pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                         SKILL WORKFLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   PRE-      │    │   EXECUTE   │    │   POST-     │         │
│  │   ANALYSIS  │───▶│   SKILL     │───▶│   SAVE      │         │
│  │   CONTEXT   │    │   WORKFLOW  │    │   HOOKS     │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│        │                  │                  │                  │
│        ▼                  ▼                  ▼                  │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐           │
│  │ RAG+Graph │      │ IB MCP +  │      │ Graph +   │           │
│  │ Context   │      │ Web Data  │      │ RAG Index │           │
│  └───────────┘      └───────────┘      └───────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Pre-Analysis Context (Step 1)

Before starting any analysis, retrieve historical context:

```yaml
# Get hybrid context (vector + graph combined)
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings analysis", "analysis_type": "earnings-analysis"}

# Or use individual tools:

# Semantic search for similar analyses
Tool: rag_search
Input: {"query": "NVDA earnings surprise patterns", "ticker": "NVDA", "top_k": 5}

# Get all graph relationships
Tool: graph_context
Input: {"ticker": "NVDA"}

# Get sector peers
Tool: graph_peers
Input: {"ticker": "NVDA"}

# Get known risks
Tool: graph_risks
Input: {"ticker": "NVDA"}

# Check for trading biases
Tool: graph_biases
Input: {}
```

## Real-Time Data (Step 2)

Gather current market data via IB MCP:

```yaml
# Current price
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "NVDA"}

# Historical bars
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "NVDA", "duration": "3 M", "bar_size": "1 day"}

# Options data
Tool: mcp__ib-mcp__get_option_chain
Input: {"symbol": "NVDA", "include_greeks": true}

# Fundamentals
Tool: mcp__ib-mcp__get_fundamental_data
Input: {"symbol": "NVDA", "report_type": "ReportSnapshot"}

# News
Tool: mcp__ib-mcp__get_news_headlines
Input: {"symbol": "NVDA"}
```

## External Research (Step 3)

Gather web data via Brave Search and browser:

```yaml
# Web search
Tool: mcp__brave-search__brave_web_search
Input: {"query": "NVDA earnings preview analyst estimates"}

# Protected articles (Seeking Alpha, etc.)
Tool: fetch_protected_article
Input: {"url": "https://seekingalpha.com/article/...", "wait_for_selector": "article"}
```

## Post-Save Hooks (Final Step)

After saving any analysis file, index it in the knowledge base:

```yaml
# 1. Extract entities to Graph (Neo4j)
Tool: graph_extract
Input: {"file_path": "trading/knowledge/analysis/earnings/NVDA_20260220T0900.yaml"}

# 2. Embed for semantic search (pgvector)
Tool: rag_embed
Input: {"file_path": "trading/knowledge/analysis/earnings/NVDA_20260220T0900.yaml"}

# 3. Push to GitHub
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: TradegentSwarm
  branch: main
  files:
    - path: trading/knowledge/analysis/earnings/NVDA_20260220T0900.yaml
      content: [generated content]
  message: "Add earnings analysis for NVDA"
```

## Skill-Specific Entities

| Skill | Primary Entities Extracted |
|-------|---------------------------|
| `earnings-analysis` | Ticker, Company, EarningsEvent, Catalyst, Product, Executive, Sector, Industry |
| `stock-analysis` | Ticker, Catalyst, Sector, Industry, Pattern, Signal, Risk |
| `research-analysis` | Company, Product, MacroEvent, Risk, Industry |
| `trade-journal` | Trade, Ticker, Strategy, Structure, Bias, Pattern |
| `post-trade-review` | Learning, Bias, Strategy, Pattern |
| `ticker-profile` | Ticker, Company, Sector, Industry, Product, Risk, Pattern |
| `watchlist` | Ticker, Catalyst, Signal |
| `scan` | Ticker, Scanner, Signal |

## MCP Tools Reference

### RAG MCP (trading-rag)

| Tool | Purpose |
|------|---------|
| `rag_embed` | Embed a YAML document |
| `rag_embed_text` | Embed raw text |
| `rag_search` | Semantic search |
| `rag_similar` | Find similar analyses |
| `rag_hybrid_context` | Combined vector + graph context |
| `rag_status` | Get RAG statistics |

### Graph MCP (trading-graph)

| Tool | Purpose |
|------|---------|
| `graph_extract` | Extract entities from document |
| `graph_extract_text` | Extract from raw text |
| `graph_search` | Find connected nodes |
| `graph_peers` | Get sector peers |
| `graph_risks` | Get known risks |
| `graph_biases` | Get bias history |
| `graph_context` | Comprehensive context |
| `graph_query` | Raw Cypher query |
| `graph_status` | Get graph statistics |

### IB MCP (ib-mcp)

| Tool | Purpose |
|------|---------|
| `get_stock_price` | Real-time quote |
| `get_historical_data` | OHLCV bars |
| `get_option_chain` | Options data |
| `get_fundamental_data` | Fundamentals |
| `get_positions` | Portfolio positions |
| `get_pnl` | P&L summary |
| `run_scanner` | Market scanner |
| `get_news_headlines` | News |

### Brave Search MCP (brave-search)

| Tool | Purpose |
|------|---------|
| `brave_web_search` | Web search |

### Brave Browser MCP (brave-browser)

| Tool | Purpose |
|------|---------|
| `fetch_protected_article` | Scrape paywalled content |
| `take_screenshot` | Page screenshot |
| `extract_structured_data` | Extract with selectors |

### GitHub MCP (github-vl)

| Tool | Purpose |
|------|---------|
| `push_files` | Push multiple files |
| `create_or_update_file` | Single file |
| `get_file_contents` | Read file |
| `list_commits` | Commit history |

## Automatic Processing

When using the trading service daemon (`service.py`), new files in `trading/knowledge/`
are automatically detected and processed. Manual extraction is only needed for:
- Bulk imports
- Re-processing existing documents
- Testing

## Verification

Check indexing status:

```yaml
# RAG status
Tool: rag_status
Input: {}

# Graph status
Tool: graph_status
Input: {}
```
