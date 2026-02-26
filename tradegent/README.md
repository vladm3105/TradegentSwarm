# Tradegent Platform v2.3

A database-driven, uninterrupted trading orchestrator that uses Claude Code CLI as its AI engine, Interactive Brokers for market data and order execution, and a hybrid RAG+Graph knowledge system. Part of the **TradegentSwarm** multi-agent trading system. All configuration lives in PostgreSQL — no restarts needed to change behavior.

---

## Architecture

```
┌─ HOST MACHINE ────────────────────────────────────────────────────────┐
│                                                                       │
│  service.py (long-running daemon)                                     │
│    │                                                                  │
│    ├─ Tick loop: refresh cfg → due schedules → earnings → heartbeat   │
│    │                                                                  │
│    └─ tradegent.py (orchestrator)                                     │
│         │                                                             │
│         ├─ Stage 1: Analysis  ──→  subprocess: claude --print ...     │
│         │   prompt includes:          └─ uses MCP servers:            │
│         │   - skill framework             ├─ mcp__ib-gateway          │
│         │   - stock context from DB       ├─ mcp__trading-rag         │
│         │   - RAG+Graph history           ├─ mcp__trading-graph       │
│         │                                 └─ web_search               │
│         │                                                             │
│         ├─ Gate: Do Nothing? (EV >5%, confidence >60%, R:R >2:1)      │
│         │                                                             │
│         └─ Stage 2: Execution ──→  subprocess: claude --print ...     │
│              only if gate PASS          └─ mcp__ib-gateway            │
│              only if stock state=paper       (paper account)          │
│                                                                       │
│  tradegent.py CLI (separate terminal)                                 │
│    └─ manage stocks, settings, scanners, one-off analyses             │
│                                                                       │
│  MCP Servers (run on host via Claude Code):                           │
│    └─ python tradegent/rag/mcp_server.py   (trading-rag)              │
│    └─ python tradegent/graph/mcp_server.py (trading-graph)            │
│                                                                       │
└───────────────── connects via localhost ports ────────────────────────┘
                        │          │          │
                   :5433 PG   :4002 IB   :7688 Neo4j
                        │          │          │
┌─ DOCKER COMPOSE ──────┴──────────┴──────────┴─────────────────────────┐
│                                                                       │
│  postgres              ib-gateway              neo4j                  │
│  pgvector:pg16         gnzsnz/ib-gw           neo4j:5-community      │
│                                                                       │
│  nexus schema:         TWS API                 Knowledge Graph        │
│  - stocks              paper trading           Entity storage         │
│  - settings            VNC :5900               Cypher queries         │
│  - schedules                                                          │
│  - run_history         rag schema:                                    │
│  - ib_scanners         - documents             Relationships:         │
│  - service_status      - chunks                - Ticker peers         │
│  - analysis_results    - embeddings            - Risk factors         │
│                        (pgvector)              - Bias patterns        │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

**Why Tradegent runs on the host, not in Docker:** Claude Code CLI requires Node.js, the `~/.claude/` auth session, and MCP server configurations — all of which live on the host. Tradegent calls `claude` via subprocess, and Claude Code starts the MCP servers (IB Gateway, trading-rag, trading-graph) which connect to Docker services via localhost.

**CLI naming:** `tradegent.py` is the official CLI entry point. The legacy name `orchestrator.py` still works and contains the implementation.

---

## Files

```
tradegent/
├── tradegent.py            CLI entry point (equivalent to orchestrator.py)
├── service.py              Main entry point — long-running daemon
├── orchestrator.py         Pipeline engine + CLI implementation
├── db_layer.py             PostgreSQL access layer (NexusDB class)
│
├── # Monitoring Modules (v2.3)
├── ib_client.py            Direct IB MCP client (MCP protocol over streamable-http)
├── position_monitor.py     Detects IB position changes, triggers trade closes
├── order_reconciler.py     Polls IB for order status updates
├── watchlist_monitor.py    Evaluates watchlist trigger/invalidation conditions
├── expiration_monitor.py   Tracks options approaching expiration
├── notifications.py        Multi-channel alert system (Telegram, Webhook, Email)
├── skill_handlers.py       Skill invocation infrastructure (Python + Claude Code)
│
├── # Utilities
├── trading_calendar.py     Market hours detection, trading day checks
├── options_utils.py        OCC symbol parsing, ITM detection
├── preflight.py            Pre-analysis system health checks
├── utils.py                Shared utility functions
│
├── db/
│   ├── init.sql            Schema, seed data, views, functions
│   └── migrations/         Schema migrations (002-008)
│       ├── 003_trades_watchlist_taskqueue.sql
│       ├── 004_task_retry_columns.sql
│       ├── 005_position_detection.sql
│       ├── 006_options_trades.sql
│       ├── 007_notification_log.sql
│       └── 008_skill_settings.sql      # Skill integration (v2.3)
│
├── scripts/
│   ├── apply_migration.py      Apply database migrations
│   ├── ingest.py               Manual RAG+Graph ingestion
│   ├── visualize_analysis.py   Generate SVG from analysis YAML
│   └── verify_trading_schema.py
│
├── tests/                  Unit tests for all modules
├── rag/                    RAG module (embeddings, search)
├── graph/                  Graph module (Neo4j, extraction)
│
├── docker-compose.yml      Infrastructure: PG, IB Gateway, Neo4j
├── .env.template           Environment variables template
├── requirements.txt        Python dependencies
└── README.md               This file
```

**Runtime directories (created automatically):**

```
├── analyses/               Stage 1 outputs (NFLX_earnings_20260217_0630.md)
├── trades/                 Stage 2 outputs (NFLX_trade_20260217_0635.md)
└── logs/                   orchestrator.log, service.log
```

---

## Prerequisites

| Requirement | Purpose | Check |
|-------------|---------|-------|
| Docker + Docker Compose | Infrastructure services | `docker compose version` |
| Python 3.11+ | Orchestrator runtime | `python3 --version` |
| Node.js 20+ | Claude Code CLI dependency | `node --version` |
| Claude Code CLI | AI engine | `claude --version` |
| Anthropic API key | For automated Claude Code calls | console.anthropic.com |
| IB credentials | Paper trading account | interactivebrokers.com |

**Claude Code authentication:** The CLI must be authenticated before use. Run `claude` interactively once to sign in or set the `ANTHROPIC_API_KEY` environment variable. When using an API key, calls are billed per-token (separate from your Pro/Max subscription).

---

## Quick Start

```bash
# 1. Clone/copy the nexus-light directory
cd ~/nexus-light

# 2. Create environment file
cp .env.template .env
# Edit .env with your credentials (IB, Anthropic, OpenAI, PostgreSQL, Neo4j)

# 3. Run setup (starts Docker, initializes DB, verifies everything)
bash setup.sh

# 4. Verify
python3 tradegent.py status
python3 tradegent.py stock list
python3 tradegent.py settings list

# 5. Run a single analysis (dry run mode is ON by default)
python3 tradegent.py settings set dry_run_mode false
python3 tradegent.py analyze NFLX --type earnings

# 6. Start the service
python3 service.py
```

---

## Environment Variables (.env)

```bash
# Interactive Brokers
IB_USER=your_ib_username        # IBKR account username
IB_PASS=your_ib_password        # IBKR account password
IB_ACCOUNT=DU_PAPER             # Paper account ID (starts with DU)
VNC_PASS=nexus123               # VNC password for IB Gateway UI

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...    # API key from console.anthropic.com
                                # Separate from Pro/Max subscription
                                # Billed per-token when used by Claude Code

# PostgreSQL (shared instance)
PG_USER=lightrag
PG_PASS=changeme_pg_password    # Change this!
PG_DB=lightrag
PG_HOST=localhost               # Host connects to Docker via localhost
PG_PORT=5433                    # Remapped from 5432

# Neo4j (knowledge graph)
NEO4J_PASS=changeme_neo4j_password  # Change this!

# LLM Providers (OpenAI recommended - ~$2/year total cost)
EMBED_PROVIDER=openai           # RAG embeddings (text-embedding-3-large, 3072 dims)
EXTRACT_PROVIDER=openai         # Graph extraction (gpt-4o-mini, 12x faster than Ollama)
OPENAI_API_KEY=sk-proj-...      # Get from platform.openai.com/api-keys

# Optional: Ollama fallback (local, free, slower)
# EMBED_PROVIDER=ollama
# EXTRACT_PROVIDER=ollama
# LLM_MODEL=qwen3:8b
# EMBED_MODEL=nomic-embed-text
```

**Note:** After setup, most configuration moves into the `nexus.settings` database table and is hot-reloadable. The `.env` file is only used for secrets and Docker container environment.

---

## Database Schema

All tables live in the `nexus` schema. RAG embeddings use the `rag` schema on the same PostgreSQL instance.

### nexus.stocks — Watchlist

Tracks which stocks the system monitors, analyzes, and trades.

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR(10) | Stock symbol (unique, primary key field) |
| name | VARCHAR(100) | Company name |
| sector | VARCHAR(50) | Sector classification |
| is_enabled | BOOLEAN | Include in automated batch runs (see note below) |
| state | ENUM | `analysis` (observe), `paper` (paper orders), `live` (future) |
| default_analysis_type | ENUM | `earnings` or `stock` |
| priority | INT 1-10 | Processing order (10 = highest) |
| next_earnings_date | DATE | Auto-triggers pre/post-earnings schedules |
| earnings_confirmed | BOOLEAN | Whether earnings date is confirmed |
| beat_history | VARCHAR(20) | e.g. "11/12" — recent beat track record |
| has_open_position | BOOLEAN | Whether there's a current position |
| position_state | VARCHAR(20) | pending, filled, partial, closed |
| max_position_pct | NUMERIC | Per-stock position limit (default 6%) |
| tags | TEXT[] | Filterable tags (mega_cap, scanner:HIGH_IV, etc.) |
| comments | TEXT | Free-form notes |

**Seed data:** NFLX, NVDA, AAPL, AMZN, MSFT, META, GOOGL, TSLA, AMD, CRM — all in `analysis` state.

**Enable/Disable behavior:**
- `is_enabled=true` → Stock included in `watchlist` and `run-due` batch commands
- `is_enabled=false` → Stock skipped in batch runs, but manual `analyze TICKER` still works
- Use case: Temporarily pause a stock (too volatile, no catalyst) without deleting it from the database

### nexus.ib_scanners — Market Scanners

IB market scanner configurations. Scanners discover opportunities and can auto-populate the watchlist.

| Column | Type | Description |
|--------|------|-------------|
| scanner_code | VARCHAR | IB scanner name (e.g. HIGH_OPT_IMP_VOLAT) |
| display_name | VARCHAR | Human-readable name |
| is_enabled | BOOLEAN | Include in scanner runs |
| instrument | VARCHAR | STK, OPT (default STK) |
| location | VARCHAR | STK.US.MAJOR, etc. |
| num_results | INT | Max results from IB (default 25) |
| filters | JSONB | Flexible filter parameters |
| auto_add_to_watchlist | BOOLEAN | Auto-add discoveries to stocks table |
| auto_analyze | BOOLEAN | Auto-run analysis on top results |
| analysis_type | VARCHAR | earnings or stock |
| max_candidates | INT | How many to auto-process |

**Filter JSONB example:**
```json
{
  "priceAbove": 10,
  "priceBelow": 500,
  "marketCapAbove": 1000000000,
  "avgOptVolumeAbove": 1000
}
```

**Seed scanners:** HIGH_OPT_IMP_VOLAT, HOT_BY_OPT_VOLUME, TOP_PERC_GAIN, TOP_PERC_LOSE, HIGH_OPT_IMP_VOLAT_OVER_HIST, MOST_ACTIVE.

### nexus.schedules — Task Scheduler

Cron-like task definitions. The service checks `v_due_schedules` view every tick and executes any that are due.

| Column | Type | Description |
|--------|------|-------------|
| name | VARCHAR | Human-readable name |
| task_type | VARCHAR | What to run (see task types below) |
| frequency | ENUM | once, daily, weekly, pre_earnings, post_earnings, interval |
| time_of_day | TIME | When (Eastern Time) |
| day_of_week | VARCHAR | For weekly: mon, tue, wed, ... |
| interval_minutes | INT | For interval frequency |
| days_before_earnings | INT | For pre_earnings frequency |
| days_after_earnings | INT | For post_earnings frequency |
| target_ticker | VARCHAR | For single-stock tasks |
| target_scanner_id | INT | For scanner tasks |
| target_tags | TEXT[] | Filter stocks by tags |
| analysis_type | VARCHAR | earnings, stock, postmortem, review |
| auto_execute | BOOLEAN | Enable Stage 2 (order placement) |
| custom_prompt | TEXT | For custom task type |
| market_hours_only | BOOLEAN | Only run during market hours |
| trading_days_only | BOOLEAN | Only run on weekdays |
| max_runs_per_day | INT | Cap on daily executions |
| priority | INT 1-10 | Execution order |
| next_run_at | TIMESTAMPTZ | Computed by scheduler |
| consecutive_fails | INT | Circuit breaker counter |
| max_consecutive_fails | INT | Auto-disable threshold (default 3) |

**Task types:**

| Type | Description |
|------|-------------|
| `analyze_stock` | Run analysis on a single ticker |
| `analyze_watchlist` | Analyze all enabled stocks |
| `pipeline` | Full Stage 1 → Stage 2 for a ticker |
| `run_scanner` | Execute a specific IB scanner |
| `run_all_scanners` | Execute all enabled scanners |
| `portfolio_review` | Weekly portfolio assessment |
| `postmortem` | Post-earnings review |
| `custom` | Execute custom_prompt via Claude Code |

**Seed schedules:**

| Schedule | Type | Frequency | Time |
|----------|------|-----------|------|
| Pre-Market Earnings Scan | run_all_scanners | daily | 6:30 AM ET |
| Morning Watchlist Analysis | analyze_watchlist | daily | 7:00 AM ET |
| Weekly Portfolio Review | portfolio_review | weekly (Sun) | 10:00 AM ET |
| Pre-Earnings Deep Dive | pipeline | pre_earnings T-7 | — |
| Pre-Earnings Update | pipeline | pre_earnings T-2 | — |
| Post-Earnings Review | postmortem | post_earnings T+1 | — |

### nexus.settings — Hot-Reloadable Configuration

Key-value pairs read by the service on every tick. Changes take effect immediately without restart.

| Category | Key | Default | Description |
|----------|-----|---------|-------------|
| rate_limits | max_daily_analyses | 15 | Max analysis runs per day |
| rate_limits | max_daily_executions | 5 | Max order executions per day |
| rate_limits | max_concurrent_runs | 2 | Max parallel Claude Code calls |
| claude | claude_cmd | "claude" | CLI command |
| claude | claude_timeout_seconds | 600 | Max seconds per call |
| claude | allowed_tools_analysis | "mcp__ib-gateway__*,..." | Stage 1 tools |
| claude | allowed_tools_execution | "mcp__ib-gateway__*,..." | Stage 2 tools |
| claude | allowed_tools_scanner | "mcp__ib-gateway__*" | Scanner tools |
| ib | ib_account | "DU_PAPER" | IB account for orders |
| ib | ib_trading_mode | "paper" | paper or live |
| knowledge | kb_ingest_enabled | true | Ingest analyses to RAG |
| knowledge | kb_query_enabled | true | Include RAG+Graph context |
| scheduler | scheduler_poll_seconds | 60 | Tick interval |
| scheduler | earnings_check_hours | [6, 7] | Hours for earnings triggers |
| scheduler | earnings_lookback_days | 21 | Days ahead to scan |
| feature_flags | **dry_run_mode** | **true** | **Blocks all Claude Code calls** |
| feature_flags | auto_execute_enabled | false | Global Stage 2 kill switch |
| feature_flags | scanners_enabled | true | Global scanner toggle |
| feature_flags | auto_viz_enabled | true | Auto-generate SVG after analysis |
| feature_flags | auto_watchlist_chain | true | Auto-add WATCH recommendations to watchlist |
| feature_flags | scanner_auto_route | true | Auto-route scanner results to analysis/watchlist |
| feature_flags | task_queue_enabled | true | Enable async task queue processing |
| rate_limits | analysis_cooldown_hours | 4 | Hours between re-analyzing same ticker |
| skills | skill_auto_invoke_enabled | true | Auto-process skill tasks from monitors |
| skills | skill_use_claude_code | false | Use Claude Code for complex skills (costs $) |
| skills | skill_daily_cost_limit | 5.00 | Max daily spend on Claude Code skills |
| skills | skill_cooldown_hours | 1 | Hours between same skill for same ticker |
| skills | detected_position_auto_create_trade | true | Auto-create trade for detected positions |
| skills | fill_analysis_enabled | true | Enable fill quality analysis |
| skills | position_close_review_enabled | true | Enable position close review |
| skills | expiration_review_enabled | true | Enable expiration review |

**Important:** `dry_run_mode` starts as `true`. The service will log what it *would* do but won't call Claude Code until you explicitly disable it.

### nexus.run_history — Audit Log

Every orchestrator run is tracked with full context.

| Column | Description |
|--------|-------------|
| schedule_id | Which schedule triggered this (nullable for manual runs) |
| task_type | analyze_stock, pipeline, etc. |
| ticker | Stock symbol |
| analysis_type | earnings, stock, etc. |
| status | started, completed, failed, timeout |
| stage | analysis, execution |
| gate_passed | Whether the "Do Nothing" gate passed |
| recommendation | BULLISH, NEUTRAL, BEARISH, etc. |
| confidence | 0-100 |
| expected_value | Expected value percentage |
| order_placed | Whether an order was placed |
| order_id | IB order ID (if placed) |
| order_details | JSONB with order specifics |
| analysis_file | Path to the analysis markdown |
| trade_file | Path to the trade log |
| started_at | When the run began |
| completed_at | When it finished |
| duration_seconds | How long it took |
| error_message | Error details (if failed) |

### nexus.analysis_results — Structured Outputs

Parsed JSON from each analysis for trend analysis and framework tracking.

| Column | Description |
|--------|-------------|
| gate_passed | Boolean |
| recommendation | BULLISH, NEUTRAL, etc. |
| confidence | 0-100 |
| expected_value_pct | EV as percentage |
| entry_price | Recommended entry |
| stop_loss | Stop loss level |
| target_price | Profit target |
| position_size_pct | Recommended allocation |
| structure | call_spread, put_spread, iron_condor, etc. |
| expiry_date | Options expiration |
| strikes | Array of strike prices |
| rationale | Summary text |
| price_at_analysis | Market price when analyzed |
| iv_at_analysis | Implied volatility at analysis time |

### nexus.service_status — Service Heartbeat

Singleton row (id=1) tracking the service health.

| Column | Description |
|--------|-------------|
| state | starting, running, paused, stopping, error |
| last_heartbeat | Updated every tick |
| last_tick_duration_ms | How long the last tick took |
| current_task | What's currently running |
| pid | Process ID |
| hostname | Machine name |
| ticks_total | Total ticks since last restart |
| today_analyses | Counter (resets at midnight) |
| today_executions | Counter (resets at midnight) |
| today_errors | Counter (resets at midnight) |

### nexus.trades — Trade Journal

Tracks executed positions for P&L and post-trade review.

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR(10) | Stock symbol |
| entry_date | TIMESTAMPTZ | When position was opened |
| entry_price | DECIMAL | Entry price |
| entry_size | DECIMAL | Number of shares/contracts |
| entry_type | VARCHAR | stock, call, put, spread |
| status | VARCHAR | open, closed, partial |
| exit_date | TIMESTAMPTZ | When position was closed |
| exit_price | DECIMAL | Exit price |
| exit_reason | VARCHAR | target, stop, manual, expiry |
| pnl_dollars | DECIMAL | P&L in dollars (auto-calculated) |
| pnl_pct | DECIMAL | P&L as percentage (auto-calculated) |
| thesis | TEXT | Trade thesis |
| source_analysis | VARCHAR | Path to source analysis file |
| review_status | VARCHAR | pending, completed |
| review_path | VARCHAR | Path to review file |

### nexus.watchlist — DB-Backed Watchlist

Persistent watchlist with entry triggers and expiration.

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR(10) | Stock symbol |
| entry_trigger | TEXT | Condition for entry (e.g., "Price below $150") |
| entry_price | DECIMAL | Target entry price |
| invalidation | TEXT | When to abandon the watch |
| invalidation_price | DECIMAL | Price that invalidates thesis |
| expires_at | TIMESTAMPTZ | Max time to hold watch |
| priority | VARCHAR | high, medium, low |
| status | VARCHAR | active, triggered, invalidated, expired |
| source | VARCHAR | analysis, scanner:name |
| source_analysis | VARCHAR | Path to source analysis |

### nexus.task_queue — Async Task Processing

Queue for background task processing with cooldown support.

| Column | Type | Description |
|--------|------|-------------|
| task_type | VARCHAR | See task types below |
| ticker | VARCHAR | Stock symbol |
| analysis_type | VARCHAR | stock, earnings |
| prompt | TEXT | Task prompt/instructions |
| priority | INT | Processing priority (1-10) |
| status | VARCHAR | pending, running, completed, failed |
| cooldown_key | VARCHAR | Prevents duplicate runs |
| cooldown_until | TIMESTAMPTZ | When cooldown expires |
| started_at | TIMESTAMPTZ | When task started |
| completed_at | TIMESTAMPTZ | When task finished |
| error_message | TEXT | Error details if failed |

**Task Types:**

| Type | Source | Handler | Skill |
|------|--------|---------|-------|
| `analysis` | CLI, scheduler | `_process_analysis_task` | stock-analysis, earnings-analysis |
| `post_trade_review` | position close | `_process_post_trade_review_task` | post-trade-review |
| `detected_position` | position_monitor | `_process_detected_position_task` | detected-position |
| `position_close_review` | position_monitor | `_process_position_close_review_task` | position-close-review |
| `fill_analysis` | order_reconciler | `_process_fill_analysis_task` | fill-analysis |
| `options_management` | expiration_monitor | `_process_options_management_task` | options-management |
| `expiration_review` | expiration_monitor | `_process_expiration_review_task` | expiration-review |

### nexus.skill_invocations — Skill Execution Tracking

Tracks all skill invocations for cost monitoring and debugging.

| Column | Type | Description |
|--------|------|-------------|
| skill_name | VARCHAR(50) | Skill name (detected_position, fill_analysis, etc.) |
| ticker | VARCHAR(20) | Stock symbol |
| invocation_type | VARCHAR(20) | `python` (free) or `claude_code` (paid) |
| cost_estimate | DECIMAL | Estimated cost for Claude Code invocations |
| status | VARCHAR(20) | started, completed, failed |
| started_at | TIMESTAMPTZ | When invocation started |
| completed_at | TIMESTAMPTZ | When invocation finished |
| error_message | TEXT | Error details if failed |
| output_path | VARCHAR(255) | Path to generated output file |
| trigger_source | VARCHAR(50) | What triggered the skill (position_monitor, etc.) |
| task_id | INTEGER | Link to task_queue entry |

**Views:**
- `v_skill_daily_costs` — Daily cost aggregation by skill and type

### Views

| View | Description |
|------|-------------|
| `v_due_schedules` | Enabled schedules where next_run_at ≤ now AND circuit breaker OK |
| `v_upcoming_earnings` | Enabled stocks with earnings in next 21 days, ordered by date |

---

## Stock State Machine

Every stock starts in `analysis` state. This is a safety mechanism — the system must prove its analysis quality before you allow it to place orders.

```
          stock add NFLX
               │
               ▼
        ┌────────────┐
        │  analysis   │  Observe: Claude analyzes, recommends, but places NO orders.
        └──────┬─────┘  Review analyses in analyses/ directory.
               │        Validate framework accuracy over 2-4 weeks.
  stock set-state NFLX --state paper
               │
               ▼
        ┌────────────┐
        │   paper     │  Paper orders: Full pipeline enabled.
        └──────┬─────┘  Claude places orders on IB paper account.
               │        Track P&L. Compare to analysis predictions.
  stock set-state NFLX --state live (future, not implemented)
               │
               ▼
        ┌────────────┐
        │    live     │  Real orders: Not yet implemented.
        └────────────┘  Requires additional safety gates.
```

---

## Two-Stage Pipeline

### Stage 1: Analysis

Claude Code is called with the analysis prompt, stock context from the database, and skill frameworks (earnings-analysis or stock-analysis). It uses MCP tools to:

- Fetch real-time prices, IV, options chains from IB Gateway
- Search the web for news, analyst estimates, earnings data
- Query RAG (pgvector) for similar prior analyses
- Query Graph (Neo4j) for ticker relationships, risks, and bias patterns

**Output:** A markdown file with an embedded JSON block containing the structured recommendation (gate_passed, confidence, expected_value, entry/stop/target, position structure).

### Gate: "Do Nothing" Check

The gate prevents low-conviction trades. It must pass ALL criteria:

| Criterion | Threshold |
|-----------|-----------|
| Expected Value | > 5% |
| Confidence | > 60% |
| Risk:Reward | > 2:1 |
| Edge not priced in | Yes |

If the gate fails, the pipeline stops. The analysis is still saved and ingested into RAG for future reference.

### Output File Types: MD vs YAML

The orchestrator generates different output formats based on the analysis outcome:

| Gate Result | Files Generated | Knowledge Indexed |
|-------------|-----------------|-------------------|
| **PASS** (4/4) | MD + YAML + SVG | RAG + Graph |
| **MARGINAL** (3/4) | MD + YAML | RAG + Graph |
| **FAIL** (<3) | **MD only** | RAG only |

**Why MD-only for failed gates:**

When the Do Nothing gate fails, there's no trade to structure — no entry price, stop loss, target, or position size to track. The MD summary captures the key takeaways (why to avoid the trade) without the overhead of full YAML schema compliance or SVG visualization.

**Example: Gate failures that produce MD-only output:**

| Ticker | Type | Gate | Recommendation | Reason |
|--------|------|------|----------------|--------|
| CWVX | Stock | 0/4 | AVOID | Leveraged ETF with structural decay |
| AMZN | Earnings | 0/4 | NEUTRAL | Negative EV, beat-and-drop pattern |
| AAPL | Earnings | 1.5/4 | NO POSITION | EV too low, 64 days out |

**Full YAML reports** are only generated when:
1. Gate passes (≥3/4 criteria met)
2. Recommendation is actionable (BUY, BULLISH, BEARISH)
3. Trade structure can be defined (entry, stop, target)

This is by design — the gate filters low-conviction setups before committing resources to full documentation and visualization.

### Stage 2: Execution

Only runs if:
1. Gate passed
2. Stock state is `paper` (or `live`)
3. `auto_execute_enabled` is true (global setting)

Claude Code reads the analysis, re-validates the trade plan, checks current prices and exposure, then places a LIMIT order on the IB paper account via the IB MCP server.

**Output:** A trade log in the trades/ directory with order details.

### Trading Modes

| Mode | `dry_run_mode` | `auto_execute_enabled` | Stock `state` | Behavior |
|------|----------------|------------------------|---------------|----------|
| **Analysis Only** | `false` | `false` | `analysis` | Reports only, no orders |
| **Paper Trading** | `false` | `true` | `paper` | Paper orders via IB Gateway (port 4002) |
| **Live Trading** | `false` | `true` | `live` | 🚫 **Blocked in code** — not implemented |

**Setup commands:**

```bash
# Analysis only (default safe mode)
python3 tradegent.py settings set dry_run_mode false
python3 tradegent.py settings set auto_execute_enabled false

# Enable paper trading for specific stocks
python3 tradegent.py settings set auto_execute_enabled true
python3 tradegent.py stock set-state NVDA paper
python3 tradegent.py stock set-state AAPL paper

# Live trading — NOT AVAILABLE
# Blocked in orchestrator.py for safety. Requires:
# - Extensive paper trading validation
# - Position/loss limits implementation
# - Manual review workflow
# - IB Gateway live mode (port 4001)
```

---

## CLI Commands

All commands connect to PostgreSQL and read settings from the database.

### Analysis

```bash
# Single stock analysis
python3 tradegent.py analyze NFLX --type earnings
python3 tradegent.py analyze NVDA --type stock

# Execute a previous analysis (Stage 2 only)
python3 tradegent.py execute analyses/NFLX_earnings_20260217_0630.md

# Full pipeline (Stage 1 → Gate → Stage 2)
python3 tradegent.py pipeline NFLX --type earnings
python3 tradegent.py pipeline NFLX --type earnings --no-execute  # Stage 1 only
```

### Bulk Operations

```bash
# Analyze all enabled stocks
python3 tradegent.py watchlist
python3 tradegent.py watchlist --auto-execute   # with Stage 2

# Run IB market scanners
python3 tradegent.py scan                       # all enabled scanners
python3 tradegent.py scan --scanner HIGH_OPT_IMP_VOLAT  # specific scanner

# Portfolio review
python3 tradegent.py review
```

### Stock Management

```bash
# List watchlist
python3 tradegent.py stock list

# Add a stock
python3 tradegent.py stock add DOCU --state paper --priority 7 \
    --tags earnings_play --earnings-date 2026-03-15 --comment "Cloud earnings play"

# Promote to paper trading
python3 tradegent.py stock set-state NFLX --state paper

# Enable/disable
python3 tradegent.py stock enable TSLA
python3 tradegent.py stock disable TSLA
```

### Settings Management

```bash
# View all settings
python3 tradegent.py settings list

# Get a single setting
python3 tradegent.py settings get dry_run_mode

# Change a setting (takes effect on next service tick)
python3 tradegent.py settings set dry_run_mode false
python3 tradegent.py settings set scheduler_poll_seconds 30
python3 tradegent.py settings set max_daily_analyses 20
```

### Scheduler

```bash
# Run all due schedules now
python3 tradegent.py run-due

# Check earnings triggers
python3 tradegent.py earnings-check
```

### Trade Management

```bash
# Add a new trade
python3 tradegent.py trade add NVDA --price 450.00 --size 100 --type stock \
    --thesis "AI momentum play" --analysis "analyses/NVDA_stock_20260224.md"

# Close a trade
python3 tradegent.py trade close 1 --price 475.00 --reason target
# Auto-chains to post-trade review task queue

# List trades
python3 tradegent.py trade list                    # Open trades (default)
python3 tradegent.py trade list --status closed    # Closed trades
python3 tradegent.py trade list --status all       # All trades

# View pending reviews
python3 tradegent.py trade pending-reviews
```

### Watchlist DB Commands

```bash
# List active watchlist entries
python3 tradegent.py watchlist-db list
python3 tradegent.py watchlist-db list --status all   # Include inactive

# Check for expirations and triggers
python3 tradegent.py watchlist-db check

# Process expired entries
python3 tradegent.py watchlist-db process-expired
```

### Task Queue

```bash
# Process pending tasks
python3 tradegent.py process-queue              # Up to 5 tasks (default)
python3 tradegent.py process-queue --max 10     # Up to 10 tasks

# View queue status
python3 tradegent.py queue-status
```

### System

```bash
# Status dashboard
python3 tradegent.py status

# Initialize database schema (first time or reset)
python3 tradegent.py db-init
```

### Service

```bash
# Run as long-running daemon
python3 service.py

# Single tick and exit (for cron)
python3 service.py once

# Initialize schedule next_run_at times
python3 service.py init

# Show health status
python3 service.py health
```

---

## Workflow Automation

The platform automates common trading workflows through automatic chaining and task queuing.

### Post-Analysis Workflow

After each analysis completes, the following steps run automatically:

1. **Auto-Visualization** — Generates an SVG dashboard from the analysis YAML
2. **Chain Data Extraction** — Extracts recommendation, EV, entry price from the analysis
3. **Watchlist Chaining** — If recommendation is WATCH, adds to DB watchlist
4. **Gate Logging** — Logs whether the Do Nothing gate passed

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Analysis   │────▶│  Generate   │────▶│  Extract    │────▶│  Chain to   │
│  Completes  │     │  SVG        │     │  Chain Data │     │  Watchlist  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Scanner Routing

Scanner results are automatically routed based on score thresholds:

| Score | Action |
|-------|--------|
| ≥ 7.5 | Queue full analysis (high priority) |
| 5.5 - 7.4 | Add to watchlist (14-day expiration) |
| < 5.5 | Skip |

```bash
# Scanner routing is automatic when scanner_auto_route=true
python3 tradegent.py scan
# High-scoring results appear in: python3 tradegent.py queue-status
```

### Trade → Review Chain

When a trade is closed, a post-trade review is automatically queued:

```bash
python3 tradegent.py trade close 1 --price 475.00 --reason target
# → Queues post-trade review task
# → Process with: python3 tradegent.py process-queue
```

### T-7/T-2/T+1 Earnings Schedules

Pre-configured earnings analysis schedules:

| Schedule | Timing | Analysis Type |
|----------|--------|---------------|
| T-7 | 7 days before earnings | Full earnings analysis |
| T-2 | 2 days before earnings | Updated analysis |
| T+1 | 1 day after earnings | Post-earnings review |

```bash
# Setup earnings schedules for all stocks with earnings dates
psql -d lightrag -f scripts/setup_earnings_schedules.sql
```

### Controlling Automation

| Setting | Default | Description |
|---------|---------|-------------|
| `auto_viz_enabled` | true | Auto-generate SVG visualizations |
| `auto_watchlist_chain` | true | Auto-add WATCH recommendations |
| `scanner_auto_route` | true | Auto-route scanner results |
| `task_queue_enabled` | true | Enable background task processing |
| `analysis_cooldown_hours` | 4 | Prevent re-analyzing same ticker |

```bash
# Disable all automation
python3 tradegent.py settings set auto_viz_enabled false
python3 tradegent.py settings set auto_watchlist_chain false
python3 tradegent.py settings set scanner_auto_route false
```

---

## Running the Service

### Option 1: screen/tmux (simplest)

```bash
screen -S tradegent
cd ~/tradegent
python3 service.py
# Ctrl+A, D to detach
# screen -r tradegent to reattach
```

### Option 2: systemd (production)

Edit `tradegent.service` — replace `YOUR_USER` with your Linux username (4 places). If using nvm, uncomment the PATH line.

```bash
sudo cp tradegent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tradegent

# Verify
sudo systemctl status tradegent
journalctl -u tradegent -f
```

The nvm/PATH issue: systemd doesn't source `~/.bashrc`. If `claude` is installed via nvm's Node.js, you must set the full PATH in the service file. Run `which node` and `which claude` to find the correct paths.

### Option 3: cron (one-shot)

```bash
# Check every minute for due schedules
* * * * * cd /home/your_user/nexus-light && /usr/bin/python3 service.py once >> logs/cron.log 2>&1
```

---

## Service Tick Lifecycle

Every N seconds (configurable via `scheduler_poll_seconds`):

1. **Reconnect** — `db.ensure_connection()` checks if the PostgreSQL connection is alive, reconnects if not.
2. **Refresh settings** — `cfg.refresh()` reads ALL settings from `nexus.settings` table into memory. Any changes you made since the last tick take effect now.
3. **Check due schedules** — Queries `v_due_schedules` view. Executes each due schedule through the task dispatch map.
4. **Earnings check** — During configured hours (default 6-7 AM ET on trading days), checks for stocks with upcoming earnings and triggers pre/post-earnings schedules.
5. **Position monitoring** (v2.3) — Every 5 minutes during market hours, compares IB positions vs DB trades to detect closes, partial closes, and external position increases.
6. **Order reconciliation** (v2.3) — Every 2 minutes when orders are pending, polls IB for order status updates and handles fills/cancels.
7. **Watchlist monitoring** (v2.3) — Every 5 minutes during market hours, evaluates trigger/invalidation conditions on active watchlist entries.
8. **Task queue processing** (v2.3) — Processes queued tasks (post-trade reviews, detected position reviews) with retry logic.
9. **Expiration check** (v2.3) — Once daily, checks for options expiring soon and auto-closes expired worthless options.
10. **Heartbeat** — Writes state, tick duration, and task info to `nexus.service_status`.

The sleep between ticks is interruptible — SIGTERM/SIGINT breaks the sleep immediately for graceful shutdown.

---

## Monitoring Modules (v2.3)

### Position Monitor

Detects IB position changes and triggers trade closes. Compares IB positions vs `nexus.trades` to detect:

- **Full closes** — Position gone from IB, trade marked closed with P&L
- **Partial closes** — Position reduced, trade size updated
- **External increases** — New shares/contracts added outside orchestrator

```python
# Runs every 5 minutes during market hours
deltas = position_monitor.check_positions()
results = position_monitor.process_deltas(deltas)
# results: {closed: 2, partial: 0, increase: 1, errors: 0}
```

**Settings:**
| Key | Default | Description |
|-----|---------|-------------|
| `position_monitor_enabled` | true | Enable/disable position monitoring |
| `position_monitor_interval_seconds` | 300 | Check interval (5 min) |
| `auto_track_position_increases` | true | Auto-create trades for detected positions |
| `position_detect_min_value` | 100 | Minimum $ value to track |

### Order Reconciler

Polls IB for order status updates on pending orders:

- **Filled** — Updates trade with fill price, triggers notifications
- **Cancelled** — Closes trade with P&L=0
- **Partial** — Updates trade with partial fill info

```python
# Runs every 2 minutes when orders pending
results = order_reconciler.reconcile_pending_orders()
# results: {filled: 1, partial: 0, cancelled: 0, pending: 2, errors: 0}
```

### Watchlist Monitor

Evaluates trigger/invalidation conditions on active watchlist entries:

**Supported conditions:**
| Type | Example | Auto-evaluated |
|------|---------|----------------|
| `PRICE_ABOVE` | "breaks above $150" | Yes |
| `PRICE_BELOW` | "drops below $140" | Yes |
| `SUPPORT_HOLD` | "holds $145 support" | Yes (requires 3 consecutive checks) |
| `RESISTANCE_BREAK` | "breaks $160 resistance" | Yes |
| `DATE_BEFORE` | "before 2026-03-15" | Yes |
| `CUSTOM` | Complex conditions | No (manual review) |

```python
# Runs every 5 minutes during market hours
results = watchlist_monitor.check_entries()
# results: {checked: 10, triggered: 1, invalidated: 0, expired: 2, errors: 0}
```

**Settings:**
| Key | Default | Description |
|-----|---------|-------------|
| `watchlist_monitor_enabled` | true | Enable/disable watchlist monitoring |
| `watchlist_check_interval_seconds` | 300 | Check interval (5 min) |
| `watchlist_price_threshold_pct` | 0.5 | Price tolerance for trigger evaluation |

### Expiration Monitor

Tracks options approaching expiration:

- **Warning** — Options expiring within 7 days
- **Critical** — Options expiring within 3 days
- **Expired** — Auto-close as worthless (unless ITM)

```python
# Runs once daily
results = expiration_monitor.process_expirations()
# results: {expired_worthless: 1, needs_review: 0, errors: 0}
```

**Settings:**
| Key | Default | Description |
|-----|---------|-------------|
| `options_expiry_warning_days` | 7 | Warning threshold |
| `options_expiry_critical_days` | 3 | Critical threshold |
| `auto_close_expired_options` | true | Auto-close expired worthless |

### Skill Handlers

The `skill_handlers.py` module bridges monitoring modules with Claude Code skills. It implements a **hybrid model**: Python handlers (free) for routine tasks, with optional Claude Code enhancement (paid) for complex analysis.

**Invocation flow:**
```
Monitor detects event → queue_task() → process_task_queue() → skill_handler()
                                                                    │
                                              ┌─────────────────────┴─────────────────────┐
                                              │                                           │
                                    skill_use_claude_code=false           skill_use_claude_code=true
                                              │                                           │
                                    invoke_skill_python()                   invoke_skill_claude()
                                              │                                           │
                                    Python handler (free)                Claude Code CLI ($0.20-0.50)
```

**Python handlers:**
| Handler | Purpose |
|---------|---------|
| `python_fill_analysis` | Calculates slippage, grades fill quality |
| `python_position_close_review` | Calculates P&L, queues full review |
| `python_detected_position_basic` | Creates basic trade entry |
| `python_options_summary` | Lists expiring positions with Greeks |
| `python_expiration_review` | Updates trade status, calculates final P&L |

**Enable Claude Code mode:**
```bash
# Enable for higher quality analysis (costs money)
python tradegent.py settings set skill_use_claude_code true

# Set daily cost limit
python tradegent.py settings set skill_daily_cost_limit 10.00
```

**Cost tracking:**
```sql
-- Today's skill costs
SELECT skill_name, invocation_type, SUM(cost_estimate) as total_cost
FROM nexus.skill_invocations
WHERE started_at >= CURRENT_DATE
GROUP BY skill_name, invocation_type;

-- Daily cost summary
SELECT * FROM nexus.v_skill_daily_costs ORDER BY date DESC LIMIT 7;
```

### Notifications

Multi-channel alert system for trading events:

**Channels:**
| Channel | Configuration | Use Case |
|---------|---------------|----------|
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` env vars | Mobile alerts |
| Webhook | `webhook_url` setting | Integration with other systems |
| Email | `EMAIL_*` env vars | Formal notifications |
| Console | Always available | Development/testing |

**Events:**
| Event | Priority | Trigger |
|-------|----------|---------|
| `position_closed` | HIGH | Position closed (stop hit, manual close) |
| `order_filled` | HIGH | Order completely filled |
| `watchlist_triggered` | HIGH | Watchlist entry trigger condition met |
| `options_expiring` | MEDIUM/HIGH | Options expiring within 3 days |
| `position_detected` | MEDIUM | New position detected externally |

**Settings:**
| Key | Default | Description |
|-----|---------|-------------|
| `notifications_enabled` | false | Master enable/disable |
| `notification_min_priority` | MEDIUM | Minimum priority to send |
| `notification_rate_limit` | 1.0 | Notifications per second |

```bash
# Enable notifications
python tradegent.py settings set notifications_enabled true

# Set Telegram credentials (in .env or export)
export TELEGRAM_BOT_TOKEN=123456789:ABCdefGHI...
export TELEGRAM_CHAT_ID=-1001234567890
```

---

## IB MCP Client

The `ib_client.py` module provides direct access to IB Gateway via MCP protocol:

```python
from ib_client import IBClient

client = IBClient()
print(client.health_check())  # True
print(client.get_stock_price("NVDA"))  # {bid, ask, last, volume, ...}
```

**Transport:** Uses `streamable-http` (not SSE) because:
- Service makes independent, short-lived calls on a polling schedule
- Each call is a complete HTTP round-trip (no persistent connection needed)
- Better fit for periodic polling vs real-time streaming

**Server URL:** `http://localhost:8100/mcp`

**Start IB MCP server:**
```bash
cd /opt/data/trading/mcp_ib
PYTHONPATH=src python -m ibmcp --transport streamable-http --host 0.0.0.0 --port 8100
```

---

## Safety Mechanisms

| Mechanism | Purpose |
|-----------|---------|
| `dry_run_mode = true` | Default ON. Blocks all Claude Code calls. |
| `auto_execute_enabled = false` | Global Stage 2 kill switch. |
| Stock state = analysis | Per-stock gate. No orders until promoted to paper. |
| "Do Nothing" gate | EV/confidence/R:R thresholds block low-conviction trades. |
| `max_daily_analyses = 15` | Cost circuit breaker. |
| `max_daily_executions = 5` | Order count limit. |
| Circuit breaker | Schedules auto-disable after 3 consecutive failures. |
| SIGTERM handling | Graceful shutdown completes current tick. |
| Paper trading only | IB account configured for paper mode. |

**First-run safety sequence:**
1. `dry_run_mode = true` — Service runs but makes no Claude Code calls.
2. Flip `dry_run_mode = false` — Analyses run, but all stocks are in `analysis` state, so no orders.
3. Review analyses for 2-4 weeks.
4. Promote a stock to `paper` — Orders go to paper account.
5. After paper validation, consider `live` (future feature).

---

## Cost Management

When the `ANTHROPIC_API_KEY` environment variable is set, Claude Code bills per-token through the Anthropic Console (separate from your Pro/Max subscription).

**Estimated costs per Claude Code call:**
- Input: ~20-50K tokens (prompt + tool calls) → $0.06-0.15
- Output: ~10-20K tokens (analysis + tool responses) → $0.15-0.30
- **Total per analysis: ~$0.20-0.45**

**Daily estimates:**
- Light usage (5 analyses): ~$1-2/day
- Default limit (15 analyses): ~$3-7/day
- Heavy day (15 analyses + 5 executions): ~$5-10/day

**Monthly estimate: $50-150** depending on usage patterns.

**Cost controls:**
- `max_daily_analyses` caps the number of Claude Code calls per day.
- `dry_run_mode` blocks all calls.
- Set a spending limit in the Anthropic Console (console.anthropic.com).
- Monitor with: `python3 service.py health` (shows today's analysis count).

---

## Docker Services

The `docker-compose.yml` runs infrastructure only:

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| postgres | pgvector/pgvector:pg16 | 5433 | Shared DB (Nexus + RAG schemas) |
| ib-gateway | ghcr.io/gnzsnz/ib-gateway:stable | 4002, 5900 | Paper trading API + VNC |
| neo4j | neo4j:5-community | 7475, 7688 | Knowledge graph storage |

```bash
# Start all infrastructure
docker compose up -d

# Check status
docker compose ps

# View IB Gateway (VNC)
# Connect to localhost:5900 with password from VNC_PASS

# View Neo4j Browser
# Open localhost:7474 in browser

# Stop everything
docker compose down

# Stop and delete volumes (full reset)
docker compose down -v
```

The `init.sql` file is mounted into PostgreSQL's `docker-entrypoint-initdb.d/` directory and runs automatically on first boot.

---

## Knowledge Base Integration

The platform integrates with the `tradegent_knowledge/` directory for trading data, skills, and analyses.

> **Note:** `tradegent_knowledge/` is cloned from a separate private repository (`vladm3105/tradegent-knowledge`) to keep trading data, scanner configs, and analyses confidential.

### Three-Layer Data Model

```
Layer 1: FILES (Source of Truth)
  Location: tradegent_knowledge/knowledge/**/*.yaml
  Properties: Authoritative, portable, rebuildable

Layer 2: RAG (Semantic Search)
  Storage: PostgreSQL with pgvector (rag schema)
  Rebuilds from: Layer 1 files

Layer 3: GRAPH (Entity Relations)
  Storage: Neo4j
  Rebuilds from: Layer 1 files
```

**Key principle:** Files are authoritative. If RAG/Graph conflict with files, files win.

### Skill System

Skills in `tradegent_knowledge/skills/` provide agent-agnostic frameworks for trading tasks:

| Skill | Version | Phases | Purpose |
|-------|---------|--------|---------|
| `earnings-analysis` | v2.4 | 14 | Pre-earnings systematic analysis |
| `stock-analysis` | v2.4 | 13 | Technical/value/catalyst analysis |
| `research-analysis` | v2.1 | 8 | Macro/sector/thematic research |
| `ticker-profile` | v2.1 | 10 | Persistent ticker knowledge |
| `trade-journal` | v2.1 | 7 | Record executed trades |
| `watchlist` | v2.1 | 8 | Track potential trades |
| `post-trade-review` | v2.1 | 10 | Analyze completed trades |
| `market-scanning` | v1.0 | — | Find trading opportunities |

### v2.4 Features (Analysis Skills)

- **Phase 0: Time Validation** - Validates system/IB MCP time sync (ERROR if >1hr discrepancy)
- **Market status awareness** - Detects weekend/holiday/pre-market/after-hours conditions
- Steel-man bear case with scored arguments
- Bias countermeasures (rule + implementation + checklist + mantra)
- Pre-exit gate for loss aversion prevention
- Do Nothing gate (EV >5%, Confidence >60%, R:R >2:1)
- 4-scenario framework (bull, base, bear, disaster)
- Meta-learning with validation tracking
- Data quality and news age checks
- Post-save indexing to RAG + Graph

### Post-Save Indexing

Every skill includes a post-save phase that indexes documents:

```yaml
# 1. Extract entities to Graph (Neo4j)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/..."}

# 2. Embed for semantic search (pgvector)
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/..."}

# 3. Push to private Knowledge Repo
Tool: mcp__github-vl__push_files
```

### Knowledge Base Structure

```
tradegent_knowledge/
├── knowledge/                  # Trading data & analyses
│   ├── analysis/               # Earnings, stock, research, profiles
│   ├── trades/                 # Executed trade journals
│   ├── strategies/             # Strategy definitions
│   ├── scanners/               # Scanner configs (daily/intraday/weekly)
│   ├── learnings/              # Biases, patterns, rules
│   ├── watchlist/              # Pending trade triggers
│   └── reviews/                # Post-trade reviews
│
├── skills/                     # Agent-agnostic skill definitions
│   ├── earnings-analysis/      # SKILL.md + template.yaml
│   ├── stock-analysis/
│   └── ...
│
└── workflows/                  # CI/CD & validation schemas
```

### Bulk Indexing

To rebuild RAG and Graph from files:

```bash
# Index all knowledge documents
python scripts/index_knowledge_base.py

# RAG only
python scripts/index_knowledge_base.py --rag-only

# Graph only
python scripts/index_knowledge_base.py --graph-only

# Force re-index (even if already indexed)
python scripts/index_knowledge_base.py --force
```

### Related Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| Knowledge Base README | `tradegent_knowledge/knowledge/README.md` | Data structure and naming conventions |
| Skills README | `tradegent_knowledge/skills/README.md` | Full skill index and workflows |
| MCP Integration | `tradegent_knowledge/skills/KNOWLEDGE_BASE_INTEGRATION.md` | MCP tool reference |
| Risk Management | `docs/RISK_MANAGEMENT.md` | Position sizing, stops, gates |
| Runbooks | `docs/RUNBOOKS.md` | Operational procedures and disaster recovery |
| Scanner Architecture | `docs/SCANNER_ARCHITECTURE.md` | Scanner system design |

---

## MCP Server Configuration

Claude Code's MCP servers are configured in `~/.claude/` on the host. The orchestrator relies on these being set up correctly.

Required MCP servers:
- **ib-gateway** — connects to localhost:4002 for market data and order execution
- **trading-rag** — runs `tradegent/rag/mcp_server.py` for semantic search
- **trading-graph** — runs `tradegent/graph/mcp_server.py` for knowledge graph queries

Configure by editing `~/.claude/mcp.json` or using `claude mcp add`. Example configuration:

```json
{
  "mcpServers": {
    "trading-rag": {
      "command": "python",
      "args": ["/opt/data/tradegent_swarm/tradegent/rag/mcp_server.py"]
    },
    "trading-graph": {
      "command": "python",
      "args": ["/opt/data/tradegent_swarm/tradegent/graph/mcp_server.py"]
    }
  }
}
```

---

## Useful SQL Queries

```sql
-- What's running today?
SELECT ticker, analysis_type, status, gate_passed, confidence, duration_seconds
FROM nexus.run_history
WHERE started_at::date = CURRENT_DATE
ORDER BY started_at DESC;

-- Gate pass rate by stock
SELECT ticker, COUNT(*) as runs,
       SUM(CASE WHEN gate_passed THEN 1 ELSE 0 END) as passes,
       ROUND(AVG(confidence)) as avg_confidence
FROM nexus.analysis_results
GROUP BY ticker ORDER BY runs DESC;

-- Average analysis duration
SELECT analysis_type, ROUND(AVG(duration_seconds)) as avg_sec,
       COUNT(*) as total
FROM nexus.run_history
WHERE status = 'completed'
GROUP BY analysis_type;

-- Upcoming earnings
SELECT * FROM nexus.v_upcoming_earnings;

-- Service health
SELECT state, last_heartbeat, ticks_total,
       today_analyses, today_executions, today_errors
FROM nexus.service_status;

-- Change poll interval (takes effect next tick)
UPDATE nexus.settings SET value = '30' WHERE key = 'scheduler_poll_seconds';

-- Disable dry run
UPDATE nexus.settings SET value = 'false' WHERE key = 'dry_run_mode';

-- Failed schedules (check circuit breakers)
SELECT name, consecutive_fails, max_consecutive_fails, last_run_status
FROM nexus.schedules
WHERE consecutive_fails > 0;
```

---

## Production Path (GCP)

The orchestrator is designed to be stateless — all state lives in PostgreSQL. For production:

1. **Replace Docker Compose with managed services:**
   - Cloud SQL for PostgreSQL
   - GKE or Compute Engine for IB Gateway (needs persistent connection)
   - Cloud Run for LightRAG

2. **Replace Claude Code CLI with Anthropic API SDK:**
   - Swap `call_claude_code()` with direct API calls
   - Implement MCP tool routing as API tool definitions
   - This removes the Node.js / `~/.claude/` dependency

3. **Deploy orchestrator as Cloud Run Job:**
   ```bash
   gcloud run jobs create tradegent-scheduler \
       --image gcr.io/PROJECT/tradegent \
       --args="service.py,once" \
       --set-env-vars="PG_HOST=/cloudsql/..." \
       --add-cloudsql-instances=PROJECT:REGION:INSTANCE

   # Schedule via Cloud Scheduler
   gcloud scheduler jobs create http tradegent-premarket \
       --schedule="30 6 * * 1-5" \
       --time-zone="America/New_York" \
       --uri="https://..."
   ```

The `Dockerfile` in the repo is a starting point for this migration.

---

## Troubleshooting

**"claude" not found:**
The Claude Code CLI isn't on PATH. If using nvm: `export PATH="$HOME/.nvm/versions/node/v20.x.x/bin:$PATH"`. For systemd, set this in the service file.

**Database connection failed:**
Check Docker is running: `docker compose ps`. Verify PG_HOST=localhost and credentials in .env match docker-compose.yml.

**IB Gateway not connecting:**
Connect via VNC (localhost:5900) to check the login screen. Paper account credentials must be correct. The gateway may need manual 2FA approval on first connect.

**Dry run mode:**
If analyses aren't running, check: `python3 tradegent.py settings get dry_run_mode`. Disable with: `python3 tradegent.py settings set dry_run_mode false`.

**Schedule not firing:**
Check next_run_at: `SELECT name, next_run_at FROM nexus.schedules WHERE is_enabled`. Re-initialize: `python3 service.py init`. Check circuit breaker: `SELECT name, consecutive_fails FROM nexus.schedules`.

**High API costs:**
Reduce `max_daily_analyses`. Use `dry_run_mode = true` when not actively monitoring. Set a spending cap in the Anthropic Console.

**"Dimension mismatch: got 768, expected 1536"**
This happens when switching embedding providers (e.g., from Ollama to OpenAI). Each provider uses different embedding dimensions:
- OpenAI text-embedding-3-large: 1536 dimensions
- Ollama nomic-embed-text: 768 dimensions

**Solution:** Stay consistent with one provider. If you need to switch:
1. Re-embed ALL documents with the new provider, OR
2. Reset the RAG database and re-index

Check your provider setting: `echo $EMBED_PROVIDER` should match what was used to create existing embeddings.

**Git push fails with `OpenSSL version mismatch`:**
If you use conda, its `LD_LIBRARY_PATH` loads a newer OpenSSL that conflicts with system SSH. Fix:

```bash
# Option 1: Clear LD_LIBRARY_PATH for SSH during git operations
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push

# Option 2: Add a git alias (one-time setup)
git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
# Then use: git pushs

# Option 3: Deactivate conda before git operations
conda deactivate
git push
```

**Git authentication fails (HTTPS):**
This project uses SSH authentication. Ensure your remote is set to SSH:

```bash
git remote set-url origin git@github.com:vladm3105/TradegentSwarm.git
```

Requires `~/.ssh/config` entry:
```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/your-github-key
    IdentitiesOnly yes
```

---

## Quick Verification: RAG + Graph

After setup, verify the RAG and Graph modules are working:

```bash
cd tradegent

# Set environment variables (or source .env)
export PG_USER=lightrag
export PG_PASS='<your-password>'
export PG_DB=lightrag
export PG_HOST=localhost
export PG_PORT=5433
export EMBED_PROVIDER=openai
export OPENAI_API_KEY='<your-key>'
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASS='<your-password>'

# 1. Test RAG embedding
python -c "
from rag.embed import embed_document
result = embed_document('../tradegent_knowledge/knowledge/analysis/stock/MSFT_20260221T1715.yaml')
print(f'Embedded: {result.doc_id}, Chunks: {result.chunk_count}, Status: {result.error_message or \"success\"}')
"

# 2. Test RAG search
python -c "
from rag.search import semantic_search, get_rag_stats
stats = get_rag_stats()
print(f'RAG Stats: {stats.document_count} docs, {stats.chunk_count} chunks')
results = semantic_search('Microsoft Azure growth', ticker='MSFT', top_k=3)
print(f'Search found {len(results)} results')
for r in results:
    print(f'  - {r.doc_id}: {r.content[:60]}...')
"

# 3. Test Graph extraction
python -c "
from graph.extract import extract_document
result = extract_document('../tradegent_knowledge/knowledge/analysis/stock/MSFT_20260221T1715.yaml')
print(f'Extracted: {len(result.entities)} entities, {len(result.relations)} relations')
print(f'Committed: {result.committed}')
"

# 4. Test Graph queries
python -c "
from graph.layer import TradingGraph
graph = TradingGraph()
graph.connect()
ctx = graph.get_ticker_context('MSFT')
print(f'MSFT context: {ctx}')
stats = graph.get_stats()
print(f'Graph: {sum(stats.node_counts.values())} nodes, {sum(stats.edge_counts.values())} edges')
graph.close()
"
```

**Expected output:**
- RAG: Documents embedded, search returns results
- Graph: Entities extracted, context queries return data

---

## Testing

The platform includes comprehensive test coverage for the graph and RAG layers.

### Running Tests

```bash
cd tradegent

# Run all tests with coverage
pytest

# Run specific test modules
pytest graph/tests/test_webhook.py -v      # Webhook endpoint tests
pytest graph/tests/test_rate_limit.py -v   # Rate limiting tests
pytest graph/tests/ -v                      # All graph tests
pytest rag/tests/ -v                        # All RAG tests

# Run without coverage (faster)
pytest --no-cov

# Run only unit tests (no external dependencies)
pytest -m unit

# Run integration tests (requires Neo4j, PostgreSQL)
pytest --run-integration -m integration
```

### Test Coverage

Coverage reports are generated automatically with pytest. Configuration in `.coveragerc`.

```bash
# Generate HTML coverage report
pytest --cov-report=html

# View report
open coverage_report/index.html
```

### Test Structure

```
tradegent/
├── tests/                    # Core platform tests
│   ├── conftest.py           # Shared fixtures (DB mocks, settings)
│   ├── test_orchestrator.py  # Pipeline, CLI, gate checks
│   └── test_db_layer.py      # Database operations, CRUD
│
├── graph/tests/
│   ├── conftest.py           # Shared fixtures (Neo4j mocks, test client)
│   ├── test_webhook.py       # FastAPI endpoint tests (12 endpoints)
│   ├── test_rate_limit.py    # Rate limiting and retry decorator tests
│   ├── test_layer.py         # Neo4j layer operations
│   ├── test_extract.py       # Entity extraction pipeline
│   ├── test_normalize.py     # Entity normalization
│   ├── test_query.py         # Cypher query catalog
│   ├── test_integration.py   # End-to-end tests (conditional)
│   └── fixtures/             # YAML test fixtures
│
├── rag/tests/
│   ├── conftest.py           # Shared fixtures (PostgreSQL mocks)
│   ├── test_chunk.py         # Document chunking
│   ├── test_embed.py         # Embedding generation
│   ├── test_search.py        # Search implementation
│   └── ...
│
├── pytest.ini                # Pytest configuration with markers
└── .coveragerc               # Coverage configuration
```

### Test Markers

| Marker | Description |
|--------|-------------|
| `@unit` | Unit tests (no external dependencies) |
| `@integration` | Integration tests (requires Neo4j, PostgreSQL) |
| `@slow` | Slow tests (embedding, extraction) |
| `@phase11` | Phase 11 Graph Trading Intelligence tests |
| `@phase12` | Phase 12 Graph-RAG Hybrid tests |

---

## Development Workflow

```bash
# Clone
git clone git@github.com:vladm3105/TradegentSwarm.git
cd TradegentSwarm

# Setup
cp tradegent/.env.template tradegent/.env
# Edit .env with your credentials
cd tradegent && bash setup.sh

# Install pre-commit hooks (required)
pip install pre-commit
pre-commit install

# Run tests before committing
pytest --no-cov -q

# After making changes
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

### Pre-commit Hooks

Pre-commit hooks run automatically on every commit:
- **Gitleaks** — Scans for secrets (API keys, passwords)
- **detect-secrets** — Additional secret detection
- **ruff** — Python linting and formatting
- **bandit** — Security scanning

If a secret is detected, the commit is blocked. Remove the secret and try again.

### CI/CD Pipeline

GitHub Actions runs on all PRs and pushes:

1. **secrets-scan** — Blocks if secrets detected (runs first)
2. **lint** — ruff, black, mypy
3. **test** — pytest with coverage
4. **integration** — Full integration tests (main branch only)
5. **security** — bandit, safety, detect-secrets

---

## Security

### Audit Logging

All significant actions are logged to `nexus.audit_log`:

```sql
-- View recent audit events
SELECT timestamp, action, actor, resource_type, resource_id, result
FROM nexus.audit_log
ORDER BY timestamp DESC
LIMIT 20;

-- Log an event programmatically
SELECT nexus.audit_log_event(
    'stock_add',           -- action
    'stock',               -- resource_type
    'NVDA',                -- resource_id
    'success',             -- result
    '{"priority": 9}'::jsonb  -- details
);
```

### Health Endpoint Security

The health endpoint binds to localhost by default:

| Variable | Default | Description |
|----------|---------|-------------|
| `HEALTH_BIND_ADDR` | `127.0.0.1` | Bind address (use `0.0.0.0` for containers) |
| `HEALTH_CHECK_TOKEN` | (none) | Bearer token for authenticated access |

Without a token, only basic status is exposed. With a token, detailed metrics are available.

```bash
# Basic health check
curl http://localhost:8080/health

# Authenticated (detailed metrics)
curl -H "Authorization: Bearer $HEALTH_CHECK_TOKEN" http://localhost:8080/health
```

---

*Tradegent Platform v2.3 — Database-driven. Uninterrupted. Hot-reloadable.*
