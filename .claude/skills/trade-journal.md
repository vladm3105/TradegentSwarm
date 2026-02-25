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

### Step 1: Get Context (RAG v2.0 + Graph)

```yaml
# Find the analysis that triggered this trade (v2.0: reranked for relevance)
Tool: rag_search_rerank
Input: {"query": "$TICKER analysis recommendation", "ticker": "$TICKER", "top_k": 5}

# Find similar past trades for this ticker (reference for sizing, lessons)
Tool: rag_similar
Input: {"ticker": "$TICKER", "analysis_type": "trade-journal", "top_k": 3}

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

Load `tradegent_knowledge/skills/trade-journal/SKILL.md`.

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

Use `tradegent_knowledge/skills/trade-journal/template.yaml` structure.

### Step 7: Save Trade Journal

Save to `tradegent_knowledge/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 8: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph (captures trade, strategy, biases)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 9: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/trades/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated trade journal content]
  message: "Add trade journal: {TICKER} {entry|exit|update}"
```

## Chaining

- Entry triggered by **earnings-analysis** or **stock-analysis** recommendation
- Entry may come from **watchlist** trigger firing
- Exit automatically triggers **post-trade-review** skill
- Results update **ticker-profile** trading history

## Workflow Automation (Database-Backed)

Trades can be tracked in the `nexus.trades` database table for automated workflow:

**Database CLI Commands:**
```bash
# Add a trade to database
python orchestrator.py trade add NVDA --entry-price 145.00 --thesis "Earnings momentum"

# Close a trade (auto-queues post-trade review)
python orchestrator.py trade close NVDA --price 158.00 --reason target_hit

# List trades
python orchestrator.py trade list --status open
```

**Auto-Review Chaining:**
When a trade is closed via CLI, the system automatically:
1. Updates `nexus.trades` with exit details and P&L
2. Queues a `post_trade_review` task in `nexus.task_queue`
3. `python orchestrator.py process-queue` executes the review

**Trade Table Fields:**
| Field | Purpose |
|-------|---------|
| `status` | open, closed |
| `review_status` | pending, completed |
| `review_path` | Path to completed review file |

## Arguments

- `$ARGUMENTS`: Ticker symbol and action (entry/exit/update)

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search_rerank` | Find triggering analysis (v2.0: cross-encoder) |
| `rag_similar` | Find similar past trades for reference |
| `graph_context` | Ticker relationships |
| `graph_biases` | Document active biases |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_positions` | Portfolio positions |
| `mcp__ib-mcp__get_executions` | Actual fill prices |
| `mcp__ib-mcp__get_pnl` | P&L calculation |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Document the trade for $ARGUMENTS. Use actual fill prices from IB, not intended prices. Follow all steps: get context, gather data, record details, save, index, and push to remote. For exits, trigger post-trade-review.
