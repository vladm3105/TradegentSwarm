---
title: Trade Journal
tags:
  - trading-skill
  - trade-management
  - execution
  - ai-agent-primary
custom_fields:
  skill_category: trade-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - watchlist
  downstream_artifacts:
    - post-trade-review
    - ticker-profile
  triggers:
    - "trade journal"
    - "log trade"
    - "record trade"
    - "entered position"
    - "exited position"
    - "bought"
    - "sold"
  auto_invoke: true
---

# Trade Journal Skill

Use this skill to document executed trades with entry/exit details, rationale, and outcomes. Auto-invokes when user mentions entering or exiting a position.

## When to Use

- Immediately after entering a position
- Immediately after exiting a position
- To update notes during an open trade
- User says "I bought/sold TICKER"

## Workflow

### Step 1: Get Context (RAG + Graph)

```yaml
# Find the analysis that triggered this trade
Tool: rag_search
Input: {"query": "$TICKER analysis recommendation", "ticker": "$TICKER", "top_k": 5}

# Get ticker context
Tool: graph_context
Input: {"ticker": "$TICKER"}

# Check for known biases (to document in journal)
Tool: graph_biases
Input: {}
```

### Step 2: Get Current Market Data (IB MCP)

```yaml
# Current price for entry/exit
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Check portfolio position (for exits)
Tool: mcp__ib-mcp__get_positions
Input: {}

# Get recent executions (for fill prices)
Tool: mcp__ib-mcp__get_executions
Input: {}

# Get P&L (for exit calculations)
Tool: mcp__ib-mcp__get_pnl
Input: {}
```

### Step 3: Determine Action Type

- **entry**: Record new position
- **exit**: Close position, calculate P&L
- **update**: Add notes during trade

### Step 4: Read Skill Definition

Load `trading/skills/trade-journal/SKILL.md`.

**For entry**, record:
- Entry details (actual fill price, date, size, order type)
- Risk management (stop loss level, targets)
- Link to triggering analysis
- Entry notes (why now, concerns, emotional state)

**For exit**, record:
- Exit details (actual fill price, date, reason)
- Calculate: Gross P&L, Net P&L, Return %
- Classify outcome (big win/small win/breakeven/small loss/big loss)
- **Trigger post-trade-review**

### Step 5: Position Sizing Verification (Entry Only)

Before entry, verify:
```
1. Stop Distance % = (Entry - Stop) / Entry
2. Dollar Risk = Portfolio × Risk % (1-2% max)
3. Shares = Dollar Risk / (Entry × Stop Distance %)
4. Position % = (Shares × Entry) / Portfolio
5. MAX POSITION: 20% of portfolio
6. Portfolio Heat: Sum of all position risks < 15%
```

### Step 6: Generate Output

Use `trading/skills/trade-journal/template.yaml` structure.

### Step 7: Save Trade Journal

Save to `trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 8: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph (captures trade, strategy, biases)
Tool: graph_extract
Input: {"file_path": "trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 9: Push to Remote

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: TradegentSwarm
  branch: main
  files:
    - path: trading/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated trade journal content]
  message: "Add trade journal: {TICKER} {entry|exit|update}"
```

## Chaining

- Entry triggered by **earnings-analysis** or **stock-analysis** recommendation
- Entry may come from **watchlist** trigger firing
- Exit automatically triggers **post-trade-review** skill
- Results update **ticker-profile** trading history

## Arguments

- `$ARGUMENTS`: Ticker symbol and action (entry/exit/update)

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search` | Find triggering analysis |
| `graph_context` | Ticker relationships |
| `graph_biases` | Document active biases |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_positions` | Portfolio positions |
| `mcp__ib-mcp__get_executions` | Actual fill prices |
| `mcp__ib-mcp__get_pnl` | P&L calculation |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to remote |

## Execution

Document the trade for $ARGUMENTS. Use actual fill prices from IB, not intended prices. Follow all steps: get context, gather data, record details, save, index, and push to remote. For exits, trigger post-trade-review.
