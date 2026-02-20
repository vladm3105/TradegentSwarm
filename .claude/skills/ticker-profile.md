---
title: Ticker Profile
tags:
  - trading-skill
  - knowledge-base
  - ticker
  - ai-agent-primary
custom_fields:
  skill_category: knowledge-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - post-trade-review
  downstream_artifacts:
    - earnings-analysis
    - stock-analysis
  triggers:
    - "ticker profile"
    - "stock profile"
    - "what do I know about"
    - "historical data for"
    - "update profile"
  auto_invoke: true
---

# Ticker Profile Skill

Use this skill to maintain persistent knowledge about frequently traded stocks. Auto-invokes when user asks about historical patterns, ticker knowledge, or before first trade in a new ticker.

## When to Use

- First trade in a new ticker (create profile)
- After earnings report (update profile)
- Building knowledge on focus stocks
- User asks "what do I know about TICKER?"
- Before analysis to load context

## Workflow

### Step 1: Check Existing Profile (RAG + Graph)

```yaml
# Search for existing profile
Tool: rag_search
Input: {"query": "$TICKER profile", "ticker": "$TICKER", "top_k": 5}

# Get all graph relationships for ticker
Tool: graph_context
Input: {"ticker": "$TICKER"}

# Check for known risks
Tool: graph_risks
Input: {"ticker": "$TICKER"}

# Get sector peers
Tool: graph_peers
Input: {"ticker": "$TICKER"}

# Check trading biases
Tool: graph_biases
Input: {}
```

### Step 2: Get Current Market Data (IB MCP)

```yaml
# Current price and volume
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Historical data for levels
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "1 Y", "bar_size": "1 day"}

# Fundamentals
Tool: mcp__ib-mcp__get_fundamental_data
Input: {"symbol": "$TICKER", "report_type": "ReportSnapshot"}

# Contract details (sector, industry)
Tool: mcp__ib-mcp__get_contract_details
Input: {"symbol": "$TICKER"}
```

### Step 3: Gather Company Information

```yaml
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TICKER company business model products"}

# For detailed profiles
Tool: fetch_protected_article
Input: {"url": "https://seekingalpha.com/symbol/$TICKER", "wait_for_selector": "article"}
```

### Step 4: Read Skill Definition

Load `trading/skills/ticker-profile/SKILL.md` and gather/update:

- **Company Basics** (sector, market cap, business model)
- **Earnings Patterns** (8 quarters: beats, reactions, guidance)
- **Technical Levels** (ATH, 52-week range, support/resistance, MAs)
- **Your Edge** (patterns you've observed, reliable signals)
- **Trading History** (your trades, win rate, lessons)
- **Key Dates** (earnings schedule, dividends, conferences)

### Step 5: Generate Output

Use `trading/skills/ticker-profile/template.yaml` structure.

### Step 6: Save Profile

Save to `trading/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 7: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph
Tool: graph_extract
Input: {"file_path": "trading/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "trading/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 8: Push to Remote

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: TradegentSwarm
  branch: main
  files:
    - path: trading/knowledge/analysis/ticker-profiles/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated profile content]
  message: "Update ticker profile for {TICKER}"
```

## Profile Maintenance

Update after:
- Each earnings report
- Each trade you make (via post-trade-review)
- Significant price moves (>10%)
- Major news events

Quarterly refresh:
- All technical levels
- Earnings history
- Edge section review

## Chaining

- Called by **earnings-analysis** and **stock-analysis** for context
- Updated by **post-trade-review** with new lessons
- Informs **watchlist** entry quality assessment

## Arguments

- `$ARGUMENTS`: Ticker symbol

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search` | Find existing profile |
| `graph_context` | All ticker relationships |
| `graph_risks` | Known risk factors |
| `graph_peers` | Sector peers |
| `graph_biases` | Trading biases |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_historical_data` | Price history |
| `mcp__ib-mcp__get_fundamental_data` | Fundamentals |
| `mcp__ib-mcp__get_contract_details` | Sector/industry |
| `mcp__brave-search__brave_web_search` | Company research |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to remote |

## Execution

Create or update the ticker profile for $ARGUMENTS. Check for existing profile first, gather current data, and save updated profile. Follow all steps: get context, gather data, save, index, and push to remote.
