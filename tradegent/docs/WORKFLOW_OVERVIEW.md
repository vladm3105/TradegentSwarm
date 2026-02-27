# Tradegent Workflow Overview

Complete documentation of the Tradegent trading workflow phases, skills, automation, and infrastructure.

---

## Master Workflow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              TRADEGENT WORKFLOW                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │  DISCOVERY  │───▶│  ANALYSIS   │───▶│ VALIDATION  │───▶│  WATCHLIST  │        │
│  │  Scanners   │    │  Deep Dive  │    │  Verify     │    │  Wait for   │        │
│  │  (7 daily)  │    │  (3 types)  │    │  Thesis     │    │  Trigger    │        │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘        │
│        │                  │                  │                  │                 │
│        │ Score ≥7.5      │                  │                  │ Trigger!        │
│        └──────────────────┘                  │                  │                 │
│                                              │                  ▼                 │
│                                              │            ┌─────────────┐         │
│                                              │            │    TRADE    │         │
│                                              │            │   Execute   │         │
│                                              │            │   Journal   │         │
│                                              │            └─────────────┘         │
│                                              │                  │                 │
│                                              │                  │ Closed          │
│                                              │                  ▼                 │
│                                              │            ┌─────────────┐         │
│                                              │            │   REVIEW    │         │
│                                              │            │ Post-Trade  │         │
│                                              │            │ Post-Earn   │         │
│                                              │            └─────────────┘         │
│                                              │                  │                 │
│                                              │                  │ Learnings       │
│                                              ▼                  ▼                 │
│                                        ┌───────────────────────────┐              │
│                                        │       MONITORING          │              │
│                                        │  Positions, Fills, Expiry │              │
│                                        │     (Background Daemon)   │              │
│                                        └───────────────────────────┘              │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Feedback Loops:**
- INVALIDATE result → removes watchlist entry, may trigger new analysis
- Post-trade review lessons → improve future analysis quality
- Confidence calibration → adjusts forecast confidence levels
- Monitoring alerts → may trigger manual re-analysis

---

## 1. Entry Points

Three mechanisms add stocks to the system for tracking and analysis.

### 1.1 Stock Table (`nexus.stocks`)

The master table for all tracked tickers with state machine.

| Column | Type | Purpose |
|--------|------|---------|
| `ticker` | VARCHAR(10) | Stock symbol (primary key) |
| `state` | ENUM | `analysis` → `paper` → `live` |
| `is_enabled` | BOOLEAN | Include in batch runs |
| `priority` | INTEGER | Processing order (10=highest) |
| `default_analysis_type` | VARCHAR | `earnings` or `stock` |
| `next_earnings_date` | DATE | Triggers pre-earnings analysis |
| `tags` | VARCHAR[] | Filterable categories |

**State Machine:**
```
analysis (observe only)
    │
    ▼ [user promotes]
paper (simulated orders via IB Gateway)
    │
    ▼ [BLOCKED - not implemented]
live (real money - future)
```

**CLI Commands:**
```bash
python tradegent.py stock add PLTR --priority 6 --tags ai defense
python tradegent.py stock enable NVDA
python tradegent.py stock disable TSLA
python tradegent.py stock set-state NVDA paper
python tradegent.py stock list
```

### 1.2 Scanner Results Routing

Scanners score candidates and route based on score:

| Score Range | Action | Destination |
|-------------|--------|-------------|
| ≥ 7.5 | High Priority | Trigger full analysis |
| 5.5 - 7.4 | Good | Add to watchlist |
| < 5.5 | Skip | No action |

### 1.3 Manual Additions

- Analysis WATCH recommendation → auto-add to watchlist
- User request: "add TICKER to watchlist"
- Direct database insert

---

## 2. Discovery Phase - Scanners

Systematic opportunity identification using rule-based scanners.

### 2.1 Scanner Types

| Type | Location | Run Frequency |
|------|----------|---------------|
| **Daily** | `scanners/daily/` | Once per day at scheduled time |
| **Intraday** | `scanners/intraday/` | Multiple times per day |
| **Weekly** | `scanners/weekly/` | Once per week |

### 2.2 Daily Schedule (ET)

| Time | Scanner | Purpose |
|------|---------|---------|
| 07:00 | news-catalyst | Overnight news with price impact |
| 08:30 | premarket-gap | Gaps >3% with catalyst |
| 09:35 | market-regime | Classify bull/bear/neutral environment |
| 09:45 | earnings-momentum | Pre-earnings setups |
| 10:00+ | unusual-volume | Volume spikes (repeats intraday) |
| 15:45 | 52w-extremes | Breakouts/breakdowns |
| 15:50 | oversold-bounce | Mean reversion setups |
| 16:15 | sector-rotation | Money flow analysis |

### 2.3 Scoring System

Scanners use weighted criteria (weights sum to 1.0):

```
Score = Σ (Criterion × Weight)

Example earnings-momentum:
  Beat history (0.25) × 8 = 2.0
  IV percentile (0.20) × 7 = 1.4
  Sentiment (0.15) × 6 = 0.9
  Technical (0.20) × 7 = 1.4
  Liquidity (0.20) × 8 = 1.6
  ─────────────────────────
  Total = 7.3 → Watchlist
```

### 2.4 Scanner → Analysis Chaining

```
Scanner Result (Score ≥7.5)
        │
        ▼
[Has upcoming earnings?]
        │
    ┌───┴───┐
   Yes      No
    │        │
    ▼        ▼
earnings-  stock-
analysis   analysis
```

### 2.5 Key Files

- Scanner configs: `tradegent_knowledge/knowledge/scanners/`
- Scan skill: `.claude/skills/scan.md`

### 2.6 Scanner Output Logging

Scanner results are stored in two locations:

| Location | Content | Purpose |
|----------|---------|---------|
| **Database** (`nexus.run_history`) | Full candidates JSON in `raw_output` | Queryable history |
| **Files** (`tradegent/analyses/`) | Markdown with JSON block | Human-readable archive |

**Database `raw_output` format:**
```json
{
    "scanner": "HIGH_OPT_IMP_VOLAT",
    "scan_time": "2026-02-27T08:26:19-05:00",
    "candidates_found": 6,
    "candidates": [
        {"ticker": "MSTZ", "score": 8, "price": 13.06, "notes": "..."},
        {"ticker": "AGQ", "score": 7, "price": 186.43, "notes": "..."}
    ]
}
```

---

## 3. Analysis Phase

Deep-dive analysis for trading decisions.

### 3.1 Analysis Types

| Type | Skill | When to Use | Output |
|------|-------|-------------|--------|
| **Stock** | stock-analysis (v2.6) | General analysis, no imminent earnings | `analysis/stock/` |
| **Earnings** | earnings-analysis (v2.4) | 1-14 days before earnings | `analysis/earnings/` |
| **Research** | research-analysis (v2.1) | Macro, sector, thematic analysis | `analysis/research/` |

### 3.2 Stock Analysis (v2.6 Requirements)

| Section | Requirement |
|---------|-------------|
| comparable_companies | Min 3 peers with P/E, P/S, EV/EBITDA |
| liquidity_analysis | ADV, bid-ask spread, slippage estimates |
| insider_activity | Transaction details with Form 4 summary |
| bull_case / bear_case | Min 3 arguments each |
| do_nothing_gate | EV>5%, Confidence>60%, R:R>2:1 (normalized thresholds) |

**Gate Results:**
- **PASS** (4/4): All criteria met
- **MARGINAL** (3/4): Consider with caution
- **FAIL** (<3): Do not trade

### 3.3 Earnings Analysis (v2.4 Features)

- Phase 0: Time validation (system vs IB MCP sync)
- Steel-man bear case with scored arguments
- Bias countermeasures (rule + implementation + checklist + mantra)
- Pre-exit gate for loss aversion
- 4-scenario framework (bull, base, bear, disaster)
- Falsification criteria

### 3.4 Output Files

| Analysis | YAML | SVG |
|----------|------|-----|
| Stock | ✅ `analysis/stock/TICKER_DATE.yaml` | ✅ Auto-generated |
| Earnings | ✅ `analysis/earnings/TICKER_DATE.yaml` | ✅ Auto-generated |
| Research | ✅ `analysis/research/TICKER_DATE.yaml` | ❌ |

---

## 4. Validation Phase

Systematic verification of analysis chain integrity.

### 4.1 Report Validation Skill (v1.0)

**Triggers:**
- Auto: New analysis saved (if prior exists)
- Auto: `forecast_valid_until` expires
- Manual: `python tradegent.py validate-analysis run NVDA`

**Validation Results:**

| Result | Meaning | Action |
|--------|---------|--------|
| **CONFIRM** | New analysis confirms prior thesis | Status → 'confirmed' |
| **SUPERSEDE** | Thesis evolved, same direction | Link chain, status → 'superseded' |
| **INVALIDATE** | Thesis broken, direction changed | Alert, invalidate watchlist, status → 'invalidated' |

### 4.2 Output

| Output | Location |
|--------|----------|
| YAML | `knowledge/reviews/validation/TICKER_DATE.yaml` |
| SVG | ❌ Not generated |

### 4.3 CLI Commands

```bash
python tradegent.py validate-analysis run NVDA
python tradegent.py validate-analysis expired
python tradegent.py validate-analysis process-expired
python tradegent.py lineage show NVDA
python tradegent.py lineage active
python tradegent.py lineage invalidated
```

---

## 5. Watchlist Phase

Track potential trades waiting for specific entry conditions.

### 5.1 Watchlist Lifecycle

```
ENTRY SOURCES              ACTIVE                 RESOLUTION
─────────────────────────────────────────────────────────────
Scanner (5.5-7.4)    ─┐
Analysis (WATCH)     ─┼──▶ status: active ──┬──▶ triggered → trade-journal
User request         ─┘    Daily review     ├──▶ invalidated → archive
                                            └──▶ expired → archive
```

### 5.2 Required Fields

| Field | Description |
|-------|-------------|
| `entry_trigger` | Specific condition (price, event, combined) |
| `invalidation` | When to remove without triggering |
| `expires` | Max 30 days from creation |
| `priority` | high / medium / low |

### 5.3 Expiration Rules

| Setup Type | Recommended Expiration |
|------------|------------------------|
| Earnings play | Earnings date |
| Breakout watch | 7-14 days |
| Pullback entry | 5-10 days |
| General thesis | 30 days (max) |

### 5.4 Daily Review Process

```
FOR EACH active entry:
  1. Check expiration → expired? (cheapest check first)
  2. Check invalidation → invalidated?
  3. Check trigger → triggered?
  4. Check news → update or invalidate?
```

### 5.5 Trigger → Trade Journal Chain

When trigger fires:
1. Set status: "triggered"
2. Invoke trade-journal skill
3. Archive watchlist entry

### 5.6 Key Files

- Watchlist skill: `.claude/skills/watchlist.md`
- Active entries: `tradegent_knowledge/knowledge/watchlist/active/`

---

## 6. Trade Phase

Execute and document trades.

### 6.1 Trade Journal Skill (v2.1)

**Triggers:**
- "bought NVDA" or "sold NVDA"
- "entered position"
- "log trade"
- Watchlist trigger fired
- Position detected (via monitoring)

**Output:** `knowledge/trades/{YYYY}/{MM}/TICKER_YYYYMMDDTHHMM.yaml`

### 6.2 Trade Entry Sources

| Source | Detection | Thesis |
|--------|-----------|--------|
| Watchlist trigger | Auto | Use watchlist thesis |
| Manual entry | User statement | User-provided |
| External detection | position_monitor | Inferred from context |

---

## 7. Review Phase

Learn from outcomes to improve future performance.

### 7.1 Post-Trade Review (v2.1)

**Triggers:**
- Trade closed
- "review trade NVDA"
- "what did I learn"

**Output:** `knowledge/reviews/{YEAR}/{MM}/TICKER_DATE_review.yaml`

**Content:**
- Entry/exit analysis
- Thesis accuracy
- Execution quality
- Bias retrospective
- Lessons learned

### 7.2 Post-Earnings Review (v1.0)

**Triggers:**
- Auto: T+1 after earnings (4 hours after market open)
- Manual: `python tradegent.py review-earnings run NVDA`

**Output:** `knowledge/reviews/post-earnings/TICKER_DATE.yaml`

**Content:**
- Prior analysis reference
- Actual earnings results (from web search)
- Scenario outcome (which scenario occurred)
- Implied move vs actual move
- Data source effectiveness grades
- **Thesis accuracy grade (A-F)**
- Confidence calibration update
- Framework lessons

### 7.3 Confidence Calibration

Tracks prediction accuracy by confidence bucket:

| Bucket | Total | Correct | Accuracy |
|--------|-------|---------|----------|
| 50% | 23 | 11 | 48% |
| 60% | 45 | 29 | 64% |
| 70% | 31 | 24 | 77% |
| 80% | 18 | 16 | 89% |
| 90% | 8 | 8 | 100% |

```bash
python tradegent.py calibration summary
python tradegent.py calibration ticker NVDA
```

---

## 8. Knowledge System & Learning Context

The knowledge system stores and retrieves learning content across RAG (semantic search) and Graph (relationships) to inform future analyses.

### 8.1 Learning Document Types

| Doc Type | Content | Indexing |
|----------|---------|----------|
| `post-earnings-review` | Forecast vs actual, thesis accuracy, framework lessons | RAG: 10 sections, Graph: 23 fields |
| `post-trade-review` | Trade outcome, bias analysis, lessons learned | RAG: section-based, Graph: entity extraction |
| `report-validation` | CONFIRM/SUPERSEDE/INVALIDATE decisions | RAG: 7 sections, Graph: 7 fields |
| `learning` | General trading rules and patterns | RAG + Graph |

### 8.2 Learning Context Retrieval

Every analysis automatically retrieves relevant learning context via `rag_hybrid_context`:

```
Pre-Analysis Context Retrieval
─────────────────────────────────────────────────────────────────
1. Past Analyses     │ Similar analyses for this ticker
2. Query Search      │ Relevant content matching analysis query
3. Learnings         │ Post-earnings, post-trade reviews
4. Framework Lessons │ Rules from "Framework Lesson" sections
5. Graph Context     │ Patterns, signals, risks, strategies
─────────────────────────────────────────────────────────────────
                              │
                              ▼
                    Formatted Context Block
                    ├── 📚 Learnings & Framework Lessons
                    ├── Knowledge Graph (patterns, signals, risks)
                    └── Past Analyses
```

### 8.3 Graph Learning Entities

The Graph extracts and stores learning-related entities:

| Entity Type | Relationship | Example |
|-------------|--------------|---------|
| **Pattern** | `OBSERVED_IN` → Ticker | sell-the-news-patterns, profit-taking |
| **Signal** | `INDICATES` → Ticker | Priced For Perfection, High Beat Probability |
| **Catalyst** | `AFFECTED_BY` ← Ticker | Strong Beat, Guidance Raises, Sell The News |
| **Risk** | `THREATENS` → Ticker | Negative Expected Value, Sell-The-News Risk |
| **Bias** | `DETECTED_IN` → Trade | Overconfidence, Recency Bias |
| **Strategy** | `WORKS_FOR` → Ticker | neutral-recommendation, earnings-momentum |

### 8.4 RAG Learning Sections

Learning content is chunked by section with context prefixes:

```yaml
# Example chunk prepared text
[post-earnings-review] [NVDA] [Framework Lesson]
When prediction markets show >90% beat probability AND beat streak
exceeds 6 quarters, EXPECT THE STOCK TO FALL even on a strong beat.
```

**Section mappings** (`rag/section_mappings.yaml`):
- `post-earnings-review`: actual_results, thesis_accuracy, framework_lesson, etc.
- `report-validation`: validation_result, validation_reasoning, prior_analysis_chain, etc.

### 8.5 Ingestion Pipeline

Documents are ingested to three systems in parallel:

```
Document Written → Auto-Ingest Hook (post-write-ingest.sh)
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    RAG Embedding   Graph Extraction   DB Storage
    (pgvector)      (Neo4j)            (PostgreSQL)
          │               │               │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │ Chunking  │   │ Entity    │   │ YAML      │
    │ Section-  │   │ Extraction│   │ Parsing   │
    │ based     │   │ LLM-based │   │           │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐
    │ Embedding │   │ Relation  │   │ Field     │
    │ OpenAI    │   │ Mapping   │   │ Extraction│
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          ▼               ▼               ▼
    rag_chunks      Neo4j nodes     nexus.kb_*
    table           /edges          tables
```

**Three Storage Systems:**

| System | Purpose | Query Method |
|--------|---------|--------------|
| **RAG (pgvector)** | Semantic search, similarity | `rag_search`, `rag_hybrid_context` |
| **Graph (Neo4j)** | Relationships, entity traversal | `graph_context`, `graph_peers` |
| **Database (PostgreSQL)** | SQL queries, reporting, analytics | Direct SQL, `db_layer.py` methods |

### 8.6 CLI Commands

```bash
# Manual ingestion (all three systems)
python scripts/ingest.py ../tradegent_knowledge/knowledge/analysis/stock/NVDA_20260223T1100.yaml

# Backfill all YAML files to database
python scripts/backfill_kb_database.py --all

# Check RAG stats
python -c "from rag.search import get_rag_stats; print(get_rag_stats())"

# Check Graph stats
python -c "from graph.layer import TradingGraph; g=TradingGraph(); g.connect(); print(g.get_stats())"

# Check DB stats (via docker)
docker exec tradegent-postgres-1 psql -U tradegent -d tradegent -c "
SELECT 'kb_stock_analyses', COUNT(*) FROM nexus.kb_stock_analyses
UNION ALL SELECT 'kb_earnings_analyses', COUNT(*) FROM nexus.kb_earnings_analyses;"

# Search for learnings
python -c "from rag.search import get_learnings_for_topic; print(get_learnings_for_topic('priced for perfection'))"

# Get ticker context with learnings
python -c "from graph.layer import TradingGraph; g=TradingGraph(); g.connect(); print(g.get_ticker_context('NVDA'))"

# Query KB database directly
docker exec tradegent-postgres-1 psql -U tradegent -d tradegent -c "
SELECT ticker, recommendation, confidence FROM nexus.kb_stock_analyses
WHERE gate_result = 'PASS' ORDER BY analysis_date DESC LIMIT 5;"
```

### 8.7 Learning Feedback Loop

```
Analysis Created
      │
      ▼
[New Analysis] ──────────────────────────────────────┐
      │                                               │
      │ Triggers validation                           │
      ▼                                               │
Report Validation ──▶ CONFIRM/SUPERSEDE/INVALIDATE   │
      │                                               │
      │ After earnings                                │
      ▼                                               │
Post-Earnings Review ──▶ Framework Lesson            │
      │                                               │
      │ Ingest to knowledge base                      │
      ▼                                               │
RAG + Graph ◀─────────────────────────────────────────┘
      │
      │ Pre-analysis context retrieval
      ▼
[Next Analysis for Same Ticker]
      │
      ▼
"📚 Learnings & Framework Lessons" section
appears in context, informing the new analysis
```

---

## 9. Monitoring Phase

Background automation for position tracking and alerts.

### 8.1 Monitoring Skills (5 total)

| Skill | Implementation | Cost | Trigger |
|-------|----------------|------|---------|
| **detected-position** | Python/Claude | Free/$0.25-0.40 | Position increase detected |
| **options-management** | Python/Claude | Free/$0.30-0.50 | Expiring options (7 days) |
| **fill-analysis** | Python only | Free | Order filled |
| **position-close-review** | Python only | Free | Position closed |
| **expiration-review** | Python/Claude | Free/$0.20 | Option expired |

### 8.2 Background Monitors

| Module | Purpose | Detection |
|--------|---------|-----------|
| `position_monitor.py` | Position changes | Compares IB positions vs `nexus.trades` |
| `order_reconciler.py` | Order lifecycle | Fills, cancels, modifications |
| `expiration_monitor.py` | Options expiry | 7-day warnings, day-of decisions |
| `watchlist_monitor.py` | Trigger checking | Price/condition triggers |

### 8.3 Task Queue Flow

```
position_monitor   ──▶ detected_position task  ──▶ skill_handler ──▶ trade entry
order_reconciler   ──▶ fill_analysis task      ──▶ skill_handler ──▶ fill grade
expiration_monitor ──▶ options_management task ──▶ skill_handler ──▶ roll advice
service (earnings) ──▶ post_earnings_review    ──▶ skill_handler ──▶ review + grade
service (expiry)   ──▶ report_validation       ──▶ skill_handler ──▶ CONFIRM/SUPERSEDE/INVALIDATE
```

### 8.4 CLI Commands

```bash
# Enable Claude Code mode (costs money)
python tradegent.py settings set skill_use_claude_code true

# Set daily cost limit
python tradegent.py settings set skill_daily_cost_limit 10.00

# Process pending skill tasks manually
python tradegent.py process-queue --max 5

# View queue status
python tradegent.py queue-status

# View skill invocation history
psql -d tradegent -c "SELECT skill_name, ticker, status, cost_estimate FROM nexus.skill_invocations ORDER BY started_at DESC LIMIT 10;"
```

---

## Service Daemon

Long-running orchestrator service (`service.py`).

### Architecture

```
┌─────────────────────────────────────────────┐
│                SERVICE LOOP                  │
│                                              │
│   ┌─────────┐   ┌──────────┐   ┌────────┐  │
│   │ Refresh  │──▶│ Check    │──▶│Execute │  │
│   │ Settings │   │ Due      │   │ Tasks  │  │
│   │ from DB  │   │ Schedules│   │        │  │
│   └─────────┘   └──────────┘   └────────┘  │
│         │              │             │       │
│   ┌─────▼──────────────▼─────────────▼──┐   │
│   │           Heartbeat + Metrics        │   │
│   └──────────────────────────────────────┘   │
│                                              │
│   sleep(scheduler_poll_seconds from DB)       │
└─────────────────────────────────────────────┘
```

### Auto-Trigger Mechanisms

| Event | Trigger Time | Action |
|-------|--------------|--------|
| Earnings date passed | T+1, 4hrs after open | Queue post-earnings review |
| Forecast expired | Daily check | Queue report validation |
| Position change | Every tick | Queue detected-position |
| Watchlist trigger | Every tick | Check price/condition |
| Options expiring | 7 days before | Queue options-management |

### Running Modes

```bash
python service.py              # Long-running service (default)
python service.py once         # Single tick, then exit (cron)
python service.py init         # Initialize schedule times
python service.py health       # Print health status
```

---

## Trading Modes

Safety-first design with progressive enablement.

### Mode Configuration

| Mode | Settings | Stock State | Behavior |
|------|----------|-------------|----------|
| **Dry Run** (default) | `dry_run_mode=true` | any | Logs only, no execution |
| **Analysis Only** | `dry_run_mode=false`, `auto_execute_enabled=false` | `analysis` | Reports, no orders |
| **Paper Trading** | `dry_run_mode=false`, `auto_execute_enabled=true` | `paper` | Simulated orders |
| **Live Trading** | — | `live` | 🚫 **BLOCKED in code** |

### Configuration

```bash
# Step 1: Disable dry run mode (required for any operation)
python tradegent.py settings set dry_run_mode false

# Step 2a: Analysis only (default)
python tradegent.py settings set auto_execute_enabled false

# Step 2b: Enable paper trading
python tradegent.py settings set auto_execute_enabled true
python tradegent.py stock set-state NVDA paper
```

### IB Gateway Ports

| Mode | Port | Container |
|------|------|-----------|
| Paper | 4002 | paper-ib-gateway |
| Live | 4001 | live-ib-gateway |

---

## Preflight Checks

System verification before analysis.

### Check Types

| Type | Services | When to Run |
|------|----------|-------------|
| **Full** | Docker containers (PostgreSQL, Neo4j, IB Gateway), RAG, Graph, IB MCP (port 8100), IB Gateway port, Market Status | Start of trading session |
| **Quick** | RAG, IB MCP, Market Status | Before each analysis |

### Services Checked (Full)

| Service | Check | Description |
|---------|-------|-------------|
| `postgres_container` | Docker | tradegent-postgres-1 container running |
| `neo4j_container` | Docker | tradegent-neo4j-1 container running |
| `ib_gateway` | Docker | paper-ib-gateway container healthy |
| `rag` | Python | pgvector connectivity (doc/chunk counts) |
| `graph` | Python | Neo4j connectivity (node/edge counts) |
| `ib_mcp` | HTTP | IB MCP server on port 8100 |
| `ib_gateway_port` | TCP | IB Gateway API port (4002 paper, 4001 live) |
| `market` | Time | Market hours status (ET timezone) |

### Status Meanings

| Status | Meaning |
|--------|---------|
| `healthy` | Service fully operational |
| `degraded` | Available with limitations (weekend, after-hours) |
| `unhealthy` | Service unavailable |
| `unknown` | Could not determine status |
| `READY` | Minimum requirements met (RAG working) |
| `NOT READY` | Cannot proceed, RAG unavailable |

### Usage

```bash
# Full check (first run of session)
cd tradegent && python preflight.py --full

# Quick check (before each analysis)
cd tradegent && python preflight.py
```

### Sample Output

```
============================================================
  📋 PAPER TRADING (Simulated)
  Account: DUK291525
  Port: 4002 | Container: paper-ib-gateway
============================================================

Preflight Check (full) - 2026-02-26 17:37:56
------------------------------------------------------------
  ✓ postgres_container: healthy - Container running (tradegent-postgres-1)
  ✓ neo4j_container: healthy - Container running (tradegent-neo4j-1)
  ✓ ib_gateway: healthy - PAPER container healthy (paper-ib-gateway)
  ✓ rag: healthy - 59 docs, 86 chunks
  ✓ graph: healthy - 211 nodes, 256 edges
  ✓ ib_mcp: healthy - Server responding on port 8100
  ✓ ib_gateway_port: healthy - PAPER: IB Gateway port 4002 accessible
  ✓ market: degraded - After-hours (17:37 ET)
------------------------------------------------------------
Status: READY
```

### Programmatic Usage

```python
from tradegent.preflight import run_full_preflight, run_quick_preflight

status = run_full_preflight()
if not status.can_analyze:
    print("Cannot proceed:", status.errors)
```

---

## Complete Skill Index

All 16 skills organized by workflow phase.

| Skill | Version | Phase | Auto-Trigger | Output Location |
|-------|---------|-------|--------------|-----------------|
| **scan** | v1.0 | Discovery | Scheduled | Uses scanners/, outputs to watchlist |
| **stock-analysis** | v2.6 | Analysis | Scanner ≥7.5 | `analysis/stock/` |
| **earnings-analysis** | v2.4 | Analysis | Scanner + earnings | `analysis/earnings/` |
| **research-analysis** | v2.1 | Analysis | Manual | `analysis/research/` |
| **report-validation** | v1.0 | Validation | New analysis saved | `reviews/validation/` |
| **watchlist** | v2.1 | Watchlist | Scanner 5.5-7.4, WATCH | `watchlist/` |
| **ticker-profile** | v2.1 | Knowledge | Post-trade update | `analysis/ticker-profiles/` |
| **trade-journal** | v2.1 | Trade | Trigger fired | `trades/` |
| **post-trade-review** | v2.1 | Review | Trade closed | `reviews/{year}/{month}/` |
| **post-earnings-review** | v1.0 | Review | T+1 after earnings | `reviews/post-earnings/` |
| **detected-position** | v1.0 | Monitoring | Position increase | `trades/` |
| **options-management** | v1.0 | Monitoring | Expiring options | — |
| **fill-analysis** | v1.0 | Monitoring | Order filled | — |
| **position-close-review** | v1.0 | Monitoring | Position closed | — |
| **expiration-review** | v1.0 | Monitoring | Option expired | — |
| **visualize-analysis** | v1.0 | Utility | After analysis | SVG in same folder |

---

## Database Tables

### Core Tables

| Table | Purpose |
|-------|---------|
| `nexus.stocks` | Ticker master with state machine |
| `nexus.ib_scanners` | IB scanner configurations |
| `nexus.schedules` | Analysis scheduling |
| `nexus.run_history` | Execution audit log (scanner candidates in `raw_output` JSON) |
| `nexus.analysis_results` | Analysis outputs |
| `nexus.settings` | System configuration |
| `nexus.service_status` | Daemon heartbeat |
| `nexus.audit_log` | Action audit trail |
| `nexus.trades` | Trade journal entries |
| `nexus.watchlist` | Pending trade triggers |
| `nexus.task_queue` | Async work queue |
| `nexus.analysis_lineage` | Analysis chain tracking |
| `nexus.confidence_calibration` | Prediction accuracy tracking |

### Knowledge Base Tables (Migration 009)

Full YAML content storage for queryable indexing alongside files.

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `nexus.kb_stock_analyses` | Stock analysis YAML storage | ticker, recommendation, confidence, yaml_content |
| `nexus.kb_earnings_analyses` | Earnings analysis storage | ticker, earnings_date, p_beat, yaml_content |
| `nexus.kb_research_analyses` | Research analysis storage | tickers[], sectors[], themes[], yaml_content |
| `nexus.kb_ticker_profiles` | Ticker profile storage | ticker, win_rate, total_pnl, yaml_content |
| `nexus.kb_trade_journals` | Trade journal storage | ticker, outcome, return_pct, biases_detected[] |
| `nexus.kb_watchlist_entries` | Watchlist YAML storage | ticker, status, entry_trigger, yaml_content |
| `nexus.kb_reviews` | All review types | ticker, review_type, overall_grade, yaml_content |
| `nexus.kb_learnings` | Bias/pattern/rule storage | category, description, validation_status |
| `nexus.kb_strategies` | Strategy storage | strategy_id, win_rate, entry_conditions[] |
| `nexus.kb_scanner_configs` | Scanner config storage | scanner_code, scanner_type, scoring_criteria |

**Design Principles:**
- Dual storage: YAML files remain source of truth; database provides queryable index
- Full content: Complete YAML stored as JSONB plus extracted key fields for indexing
- Auto-sync: Database updated via `ingest.py` hook when YAML files are saved

### Views

| View | Purpose |
|------|---------|
| `nexus.v_due_schedules` | Schedules ready to run |
| `nexus.v_upcoming_earnings` | Stocks with near-term earnings |
| `nexus.v_pending_post_earnings_reviews` | Reviews needing processing |
| `nexus.v_expired_forecasts` | Forecasts past valid_until date |

---

## Automatic Triggers

```
┌────────────────────────┬────────────────────────────────────────────────────┐
│ Event                  │ What Gets Triggered                                │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Scanner score ≥7.5     │ → Full analysis (earnings or stock)               │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Scanner score 5.5-7.4  │ → Watchlist entry                                  │
├────────────────────────┼────────────────────────────────────────────────────┤
│ New analysis saved     │ → Report validation (if prior exists)             │
│                        │ → RAG embed + Graph extract (always)               │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Earnings date passes   │ → Post-earnings review (T+1, 4hrs after open)      │
├────────────────────────┼────────────────────────────────────────────────────┤
│ forecast_valid_until   │ → Report validation (check if still valid)         │
│ expires                │                                                    │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Watchlist trigger fires│ → Trade journal                                    │
│                        │ → Archive watchlist entry                          │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Trade closed           │ → Post-trade review                                │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Position detected      │ → detected-position skill                          │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Order filled           │ → fill-analysis skill                              │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Option expiring (7d)   │ → options-management skill                         │
├────────────────────────┼────────────────────────────────────────────────────┤
│ Option expired         │ → expiration-review skill                          │
├────────────────────────┼────────────────────────────────────────────────────┤
│ INVALIDATE result      │ → Watchlist entry invalidated                      │
│                        │ → Alert logged                                     │
└────────────────────────┴────────────────────────────────────────────────────┘
```

---

## CLI Commands Quick Reference

### Analysis
```bash
python tradegent.py analyze NVDA --type stock
python tradegent.py analyze NVDA --type earnings
python tradegent.py watchlist              # Analyze all enabled stocks
python tradegent.py run-due                # Run due schedules
```

### Stock Management
```bash
python tradegent.py stock list
python tradegent.py stock add PLTR --priority 6 --tags ai defense
python tradegent.py stock enable NVDA
python tradegent.py stock disable TSLA
python tradegent.py stock set-state NVDA paper
```

### Validation & Review
```bash
python tradegent.py validate-analysis run NVDA
python tradegent.py validate-analysis expired
python tradegent.py validate-analysis process-expired
python tradegent.py review-earnings run NVDA
python tradegent.py review-earnings pending
python tradegent.py review-earnings backfill --limit 10
```

### Lineage & Calibration
```bash
python tradegent.py lineage show NVDA
python tradegent.py lineage active
python tradegent.py lineage invalidated
python tradegent.py calibration summary
python tradegent.py calibration ticker NVDA
```

### Queue & Skills
```bash
python tradegent.py process-queue --max 5
python tradegent.py queue-status
python tradegent.py settings set skill_use_claude_code true
python tradegent.py settings set skill_daily_cost_limit 10.00
```

### Service
```bash
python service.py              # Long-running
python service.py once         # Single tick
python service.py health       # Health check
```

### Preflight
```bash
python preflight.py --full     # Full check
python preflight.py            # Quick check
```

---

## Settings

### Core Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `dry_run_mode` | true | Block all execution (safety default) |
| `auto_execute_enabled` | false | Allow paper/live order placement |

### Review & Validation Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `auto_post_earnings_review` | true | Auto-queue review T+1 after earnings |
| `auto_report_validation` | true | Auto-validate when new analysis saved |
| `validation_on_expiry` | true | Auto-validate when forecast expires |
| `post_earnings_delay_hours` | 4 | Hours after market open to queue review |
| `invalidation_alerts_enabled` | true | Log alerts on INVALIDATE |

### Skill Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `skill_use_claude_code` | false | Use Claude Code for full analysis (costs money) |
| `skill_daily_cost_limit` | 10.00 | Daily Claude Code cost cap |
| `skill_cooldown_hours` | 1 | Hours between same skill for same ticker |

---

*Last updated: 2026-02-27 (KB tables added)*
