---
title: Watchlist
tags:
  - trading-skill
  - trade-management
  - monitoring
  - ai-agent-primary
custom_fields:
  skill_category: trade-management
  priority: primary
  development_status: active
  upstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - scan
  downstream_artifacts:
    - trade-journal
  triggers:
    - "watchlist"
    - "add to watchlist"
    - "watch this"
    - "monitor"
    - "waiting for trigger"
    - "review watchlist"
  auto_invoke: true
---

# Watchlist Skill

Use this skill to track potential trades waiting for trigger conditions. Auto-invokes when analysis recommends WATCH or user wants to monitor a setup.

## When to Use

- Analysis score 5.5-6.4 (WATCH recommendation)
- Good setup but waiting for specific trigger
- Scanner candidate needs confirmation
- Quality stock at wrong price
- User says "add to watchlist" or "watch this"

## Workflow

### Step 1: Get Context (RAG v2.0 + Graph)

```yaml
# Check for existing watchlist entries (v2.0: reranked for relevance)
Tool: rag_search_rerank
Input: {"query": "$TICKER watchlist trigger", "ticker": "$TICKER", "top_k": 5}

# Get ticker context
Tool: graph_context
Input: {"ticker": "$TICKER"}

# Check known risks before adding to watchlist
Tool: graph_risks
Input: {"ticker": "$TICKER"}
```

### Step 2: Get Current Market Data (IB MCP)

```yaml
# Current price to set trigger levels
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "$TICKER"}

# Historical data for support/resistance
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "$TICKER", "duration": "3 M", "bar_size": "1 day"}

# Options activity for sentiment
Tool: mcp__ib-mcp__get_option_chain
Input: {"symbol": "$TICKER", "include_greeks": false}
```

### Step 3: Determine Action

- **add**: Create new watchlist entry
- **review**: Check all entries against current prices
- **remove**: Remove triggered/invalidated/expired entries

### Step 4: Read Skill Definition

Load `tradegent_knowledge/skills/watchlist/SKILL.md`.

**For adding**, specify:
- Entry trigger (specific, measurable)
- Invalidation criteria
- Expiration date (max 30 days)
- Priority (high/medium/low)
- Source (which analysis or scanner)

**For review**, check each entry:
- Did trigger fire? → Execute analysis or trade
- Did invalidation occur? → Remove
- News affecting thesis? → Update or remove
- Stale (>30 days)? → Remove

### Step 5: Entry Trigger Types

```
PRICE TRIGGERS:
- Breakout above $X
- Pullback to $X
- Break below $X (shorts)

CONDITION TRIGGERS:
- Earnings report
- FDA decision
- Pattern completion
- Volume confirmation

COMBINED TRIGGERS:
- Price above $X WITH volume > Y
- Break resistance AND sector confirming
```

### Step 6: Generate Output

Use `tradegent_knowledge/skills/watchlist/template.yaml` structure.

### Step 7: Save Watchlist Entry

Save to `tradegent_knowledge/knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml`

### Step 8: Index in Knowledge Base (Post-Save Hooks)

```yaml
# Extract entities to Graph
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml"}

# Embed for semantic search
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 9: Push to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/watchlist/{TICKER}_{YYYYMMDDTHHMM}.yaml
      content: [generated watchlist content]
  message: "Update watchlist: {TICKER} {add|update|remove}"
```

## Daily Review Routine

```
EVERY TRADING DAY:
□ Check each entry vs current price
□ Triggers fired? → Execute
□ Invalidations? → Remove
□ News impact? → Update/remove

WEEKLY:
□ Remove stale entries (>30 days)
□ Reprioritize by likelihood
□ Check for new scanner candidates
```

## Chaining

- Receives WATCH recommendations from **earnings-analysis** and **stock-analysis**
- Receives candidates from **scan** skill
- Triggers fire → invoke **trade-journal** for entry
- May trigger new **stock-analysis** when conditions met

## Database-Backed Watchlist (Workflow Automation)

The `nexus.watchlist` table provides database-backed watchlist management:

**Auto-Chaining:**
When an analysis recommends WATCH and `auto_watchlist_chain=true`:
```
Analysis YAML → extract_chain_data() → nexus.watchlist table
```

**Database CLI Commands:**
```bash
# List active watchlist entries
python orchestrator.py watchlist-db list

# Check for triggered/expired entries
python orchestrator.py watchlist-db check

# Process expired entries (archive them)
python orchestrator.py watchlist-db process-expired
```

**Table Fields:**
| Field | Purpose |
|-------|---------|
| `entry_trigger` | Condition to fire (price, event) |
| `invalidation` | Condition to remove |
| `expires_at` | Max 30-day expiration |
| `status` | active, triggered, invalidated, expired |
| `source_analysis` | Link to triggering analysis |

**Two-Layer Approach:**
1. **YAML files** in `knowledge/watchlist/` - Source of truth
2. **Database table** `nexus.watchlist` - For automated daily checks

Both are valid; use database for automation, YAML for full context.

## Arguments

- `$ARGUMENTS`: Ticker symbol and action (add/review/remove), or "review all"

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search_rerank` | Find existing entries (v2.0: cross-encoder) |
| `graph_context` | Ticker relationships |
| `graph_risks` | Known risk factors |
| `mcp__ib-mcp__get_stock_price` | Current price |
| `mcp__ib-mcp__get_historical_data` | Support/resistance levels |
| `mcp__ib-mcp__get_option_chain` | Options sentiment |
| `graph_extract` | Index entities |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Manage watchlist for $ARGUMENTS. Follow all steps: get context, gather data, create/update/remove entry, save, index, and push to remote.
