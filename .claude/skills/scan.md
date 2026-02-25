---
title: Market Scanning
tags:
  - trading-skill
  - scanning
  - opportunity-finding
  - ai-agent-primary
custom_fields:
  skill_category: scanning
  priority: primary
  development_status: active
  upstream_artifacts: []
  downstream_artifacts:
    - earnings-analysis
    - stock-analysis
    - watchlist
  triggers:
    - "scan"
    - "market scan"
    - "find opportunities"
    - "run scanner"
    - "daily scan"
    - "what should I trade"
  auto_invoke: true
---

# Market Scanning Skill

Use this skill to systematically identify trading opportunities using scanner configurations. Auto-invokes for daily trading routine or when user asks for opportunities.

## When to Use

- Daily market routine (pre-market, open, close)
- Finding new trade candidates
- User asks "what should I trade?" or "find opportunities"
- Running specific scanner by name

## Available Scanners

### Daily Scanners (`tradegent_knowledge/knowledge/scanners/daily/`)
| Scanner | Time | Purpose |
|---------|------|---------|
| market-regime | 09:35 | Classify market environment |
| premarket-gap | 08:30 | Gaps with catalysts |
| news-catalyst | 07:00/12:00/18:00 | Material news |
| earnings-momentum | 09:45 | Pre-earnings setups |
| 52w-extremes | 15:45 | Breakouts/breakdowns |
| sector-rotation | 16:15 | Sector flows |
| oversold-bounce | 15:50 | Mean reversion |

### Intraday Scanners (`tradegent_knowledge/knowledge/scanners/intraday/`)
| Scanner | Purpose |
|---------|---------|
| options-flow | Unusual options activity |
| unusual-volume | Volume spikes |

### Weekly Scanners (`tradegent_knowledge/knowledge/scanners/weekly/`)
| Scanner | Time | Purpose |
|---------|------|---------|
| earnings-calendar | Sun 07:00 | Week ahead earnings |
| institutional-activity | Mon/Fri 18:00 | 13F filings, insiders |

## Workflow

### Step 1: Load Scanner Config

Read scanner configuration from `tradegent_knowledge/knowledge/scanners/{daily|intraday|weekly}/`

### Step 2: Get Market Context (RAG v2.0 + Graph)

```yaml
# Get current market regime (v2.0: reranked for relevance)
Tool: rag_search_rerank
Input: {"query": "market regime volatility sector rotation", "top_k": 5}

# Get recent scan results for comparison
Tool: rag_search_rerank
Input: {"query": "scanner results opportunities", "top_k": 10}

# Discover sector relationships for context (optional per-ticker)
Tool: graph_search
Input: {"ticker": "$SECTOR_LEADER", "depth": 2}
```

### Step 3: Execute Scanner via IB MCP

```yaml
# Run IB scanner
Tool: mcp__ib-mcp__run_scanner
Input: {"scan_code": "$SCANNER_CODE", "instrument": "STK", "location": "STK.US.MAJOR", "max_results": 50}

# Get scanner parameters (for custom scans)
Tool: mcp__ib-mcp__get_scanner_params
Input: {}

# Get quotes for scanner results
Tool: mcp__ib-mcp__get_quotes_batch
Input: {"symbols": ["TICKER1", "TICKER2", "..."]}

# Get news for top candidates
Tool: mcp__ib-mcp__get_news_headlines
Input: {"symbol": "$TICKER"}
```

### Step 4: Gather Additional Data

```yaml
# Web search for catalysts
Tool: mcp__brave-search__brave_web_search
Input: {"query": "$TICKER catalyst news today"}

# For earnings scanner - get earnings dates
Tool: mcp__brave-search__brave_web_search
Input: {"query": "earnings calendar this week $SECTOR"}
```

### Step 5: Apply Quality Filters

From scanner config:
- Liquidity filters (volume, avg volume)
- Price filters (min/max price)
- Exclusion lists (penny stocks, ADRs, etc.)

### Step 6: Score Candidates

```
SCORE CALCULATION:
Score = Σ (Criterion Score × Weight)
Where weights sum to 1.0

INTERPRETATION:
≥ 7.5: High priority → trigger analysis
6.5-7.4: Good → add to watchlist
5.5-6.4: Marginal → monitor only
< 5.5: Skip
```

### Step 7: Route Results by Score

```yaml
# Score ≥ 7.5: Trigger full analysis
→ Invoke earnings-analysis or stock-analysis skill

# Score 5.5-7.4: Add to watchlist
→ Invoke watchlist skill

# Score < 5.5: Skip
→ Log and continue
```

### Step 8: Generate Scan Summary

Output summary of:
- Scanner run metadata (time, scanner name)
- Candidates found
- Actions taken (analyses triggered, watchlist adds)
- Market regime context

### Step 9: Index Results (Post-Save Hooks)

If saving scan results:

```yaml
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/scans/{SCANNER}_{YYYYMMDDTHHMM}.yaml"}

Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/scans/{SCANNER}_{YYYYMMDDTHHMM}.yaml"}
```

### Step 10: Push Watchlist Candidates to Remote (Private Knowledge Repo)

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge    # Private knowledge repository
  branch: main
  files:
    - path: knowledge/watchlist/{TICKER1}_{YYYYMMDDTHHMM}.yaml
      content: [watchlist entry content]
    - path: knowledge/watchlist/{TICKER2}_{YYYYMMDDTHHMM}.yaml
      content: [watchlist entry content]
  message: "Scanner results: {scanner_name} - {count} candidates"
```

## Daily Routine

```
PRE-MARKET (07:00-09:30):
□ News Catalyst scanner
□ Pre-Market Gap scanner
□ Note high-priority candidates

MARKET OPEN (09:35-10:00):
□ Market Regime classifier
□ Earnings Momentum scanner
□ First Unusual Volume check

MID-DAY (11:00-14:00):
□ Options Flow checks
□ Unusual Volume updates

CLOSE (15:30-16:15):
□ 52-Week Extremes
□ Oversold Bounce
□ Sector Rotation
□ Daily summary
```

## Chaining

- High scores → invoke **earnings-analysis** or **stock-analysis**
- Medium scores → invoke **watchlist** skill
- Updates market regime context for all other skills
- Weekly earnings-calendar informs **earnings-analysis** pipeline

## Workflow Automation (Auto-Routing)

Scanner results are automatically routed via database when `scanner_auto_route=true`:

```
Scanner Results → _route_scanner_results() → Task Queue or Watchlist DB
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       ≥ 7.5         5.5-7.4         < 5.5
          │              │              │
          ▼              ▼              ▼
   nexus.task_queue  nexus.watchlist   Skip
   (analyze task)    (with priority)
```

**Cooldown Mechanism:**
- Same ticker won't be re-analyzed within `analysis_cooldown_hours` (default: 4)
- Checked via `cooldown_key` in `nexus.task_queue`

**CLI Commands:**
```bash
# Process queued analyses from scanner
python orchestrator.py process-queue

# Check what's queued
python orchestrator.py queue-status

# Run analyses for due stocks
python orchestrator.py run-due
```

**Settings:**
| Setting | Default | Purpose |
|---------|---------|---------|
| `scanner_auto_route` | true | Enable auto-routing |
| `analysis_cooldown_hours` | 4 | Min hours between re-analysis |

## Arguments

- `$ARGUMENTS`: Scanner name (optional), or "daily", "weekly", "all"

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `rag_search_rerank` | Market context (v2.0: cross-encoder) |
| `graph_search` | Discover sector relationships |
| `mcp__ib-mcp__run_scanner` | Execute IB scanner |
| `mcp__ib-mcp__get_scanner_params` | Scanner options |
| `mcp__ib-mcp__get_quotes_batch` | Candidate prices |
| `mcp__ib-mcp__get_news_headlines` | News for candidates |
| `mcp__brave-search__brave_web_search` | Catalyst research |
| `graph_extract` | Index results |
| `rag_embed` | Embed for search |
| `mcp__github-vl__push_files` | Push to private knowledge repo |

## Execution

Run market scanning for $ARGUMENTS. Load scanner configs, execute via IB MCP, score candidates, and route to appropriate skills. Follow all steps: get context, run scanner, score, route, and push results.
