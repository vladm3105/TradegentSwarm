# Nexus Light Trading Platform v2.1

A database-driven, uninterrupted trading orchestrator that uses Claude Code CLI as its AI engine, Interactive Brokers for market data and order execution, and LightRAG for knowledge persistence. All configuration lives in PostgreSQL — no restarts needed to change behavior.

---

## Architecture

```
┌─ HOST MACHINE ────────────────────────────────────────────────────────┐
│                                                                       │
│  service.py (long-running daemon)                                     │
│    │                                                                  │
│    ├─ Tick loop: refresh cfg → due schedules → earnings → heartbeat   │
│    │                                                                  │
│    └─ orchestrator.py                                                 │
│         │                                                             │
│         ├─ Stage 1: Analysis  ──→  subprocess: claude --print ...     │
│         │   prompt includes:          └─ uses MCP servers:            │
│         │   - skill framework             ├─ mcp__ib-gateway          │
│         │   - stock context from DB       ├─ mcp__lightrag            │
│         │   - LightRAG history            └─ web_search               │
│         │                                                             │
│         ├─ Gate: Do Nothing? (EV >5%, confidence >60%, R:R >2:1)      │
│         │                                                             │
│         └─ Stage 2: Execution ──→  subprocess: claude --print ...     │
│              only if gate PASS          └─ mcp__ib-gateway            │
│              only if stock state=paper       (paper account)          │
│                                                                       │
│  orchestrator.py CLI (separate terminal)                              │
│    └─ manage stocks, settings, scanners, one-off analyses             │
│                                                                       │
└───────────────── connects via localhost ports ────────────────────────┘
                        │          │          │          │
                   :5432 PG   :4002 IB   :9621 RAG  :7687 Neo4j
                        │          │          │          │
┌─ DOCKER COMPOSE ──────┴──────────┴──────────┴──────────┴──────────────┐
│                                                                       │
│  postgres        ib-gateway        lightrag          neo4j            │
│  pgvector:pg16   gnzsnz/ib-gw     lightrag:latest   neo4j:5          │
│                                                                       │
│  nexus schema:   TWS API           REST + MCP        Graph storage    │
│  - stocks        paper trading     Anthropic LLM     for LightRAG    │
│  - settings      VNC :5900         OpenAI embed                      │
│  - schedules                       PG + Neo4j                        │
│  - run_history                     backends                          │
│  - ib_scanners                                                       │
│  - service_status                                                    │
│  - analysis_results                                                  │
│                                                                       │
│  LightRAG uses public schema on same PG instance                     │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

**Why the orchestrator runs on the host, not in Docker:** Claude Code CLI requires Node.js, the `~/.claude/` auth session, and MCP server configurations — all of which live on the host. The orchestrator calls `claude` via subprocess, and Claude Code starts the MCP servers (IB, LightRAG) which connect to Docker services via localhost.

---

## Files

```
nexus-light/
├── service.py              Main entry point — long-running daemon
├── orchestrator.py         Pipeline engine + CLI commands
├── db_layer.py             PostgreSQL access layer (NexusDB class)
├── db/
│   └── init.sql            Schema, seed data, views, functions
├── docker-compose.yml      Infrastructure: PG, IB, LightRAG, Neo4j
├── nexus-light.service     systemd unit (optional)
├── setup.sh                One-command setup
├── .env.template           Environment variables template
├── requirements.txt        Python dependencies
├── Dockerfile              For future GCP Cloud Run deployment
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
python3 orchestrator.py status
python3 orchestrator.py stock list
python3 orchestrator.py settings list

# 5. Run a single analysis (dry run mode is ON by default)
python3 orchestrator.py settings set dry_run_mode false
python3 orchestrator.py analyze NFLX --type earnings

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

# OpenAI (embeddings for LightRAG)
OPENAI_API_KEY=sk-...           # For text-embedding-3-small model

# PostgreSQL (shared instance)
PG_USER=lightrag
PG_PASS=changeme_pg_password    # Change this!
PG_DB=lightrag
PG_HOST=localhost               # Host connects to Docker via localhost
PG_PORT=5432

# Neo4j (graph storage for LightRAG)
NEO4J_PASS=changeme_neo4j_password  # Change this!
```

**Note:** After setup, most configuration moves into the `nexus.settings` database table and is hot-reloadable. The `.env` file is only used for secrets and Docker container environment.

---

## Database Schema

All tables live in the `nexus` schema. LightRAG uses the `public` schema on the same PostgreSQL instance.

### nexus.stocks — Watchlist

Tracks which stocks the system monitors, analyzes, and trades.

| Column | Type | Description |
|--------|------|-------------|
| ticker | VARCHAR(10) | Stock symbol (unique, primary key field) |
| name | VARCHAR(100) | Company name |
| sector | VARCHAR(50) | Sector classification |
| is_enabled | BOOLEAN | Include in automated runs |
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
| lightrag | lightrag_url | "http://localhost:9621" | LightRAG endpoint |
| lightrag | lightrag_ingest_enabled | true | Ingest analyses |
| scheduler | scheduler_poll_seconds | 60 | Tick interval |
| scheduler | earnings_check_hours | [6, 7] | Hours for earnings triggers |
| scheduler | earnings_lookback_days | 21 | Days ahead to scan |
| feature_flags | **dry_run_mode** | **true** | **Blocks all Claude Code calls** |
| feature_flags | auto_execute_enabled | false | Global Stage 2 kill switch |
| feature_flags | scanners_enabled | true | Global scanner toggle |
| feature_flags | lightrag_query_enabled | true | Include LightRAG context |

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
- Query LightRAG for prior analyses and trading patterns

**Output:** A markdown file with an embedded JSON block containing the structured recommendation (gate_passed, confidence, expected_value, entry/stop/target, position structure).

### Gate: "Do Nothing" Check

The gate prevents low-conviction trades. It must pass ALL criteria:

| Criterion | Threshold |
|-----------|-----------|
| Expected Value | > 5% |
| Confidence | > 60% |
| Risk:Reward | > 2:1 |
| Edge not priced in | Yes |

If the gate fails, the pipeline stops. The analysis is still saved and ingested into LightRAG for future reference.

### Stage 2: Execution

Only runs if:
1. Gate passed
2. Stock state is `paper` (or `live`)
3. `auto_execute_enabled` is true (global setting)

Claude Code reads the analysis, re-validates the trade plan, checks current prices and exposure, then places a LIMIT order on the IB paper account via the IB MCP server.

**Output:** A trade log in the trades/ directory with order details.

---

## CLI Commands

All commands connect to PostgreSQL and read settings from the database.

### Analysis

```bash
# Single stock analysis
python3 orchestrator.py analyze NFLX --type earnings
python3 orchestrator.py analyze NVDA --type stock

# Execute a previous analysis (Stage 2 only)
python3 orchestrator.py execute analyses/NFLX_earnings_20260217_0630.md

# Full pipeline (Stage 1 → Gate → Stage 2)
python3 orchestrator.py pipeline NFLX --type earnings
python3 orchestrator.py pipeline NFLX --type earnings --no-execute  # Stage 1 only
```

### Bulk Operations

```bash
# Analyze all enabled stocks
python3 orchestrator.py watchlist
python3 orchestrator.py watchlist --auto-execute   # with Stage 2

# Run IB market scanners
python3 orchestrator.py scan                       # all enabled scanners
python3 orchestrator.py scan --scanner HIGH_OPT_IMP_VOLAT  # specific scanner

# Portfolio review
python3 orchestrator.py review
```

### Stock Management

```bash
# List watchlist
python3 orchestrator.py stock list

# Add a stock
python3 orchestrator.py stock add DOCU --state paper --priority 7 \
    --tags earnings_play --earnings-date 2026-03-15 --comment "Cloud earnings play"

# Promote to paper trading
python3 orchestrator.py stock set-state NFLX --state paper

# Enable/disable
python3 orchestrator.py stock enable TSLA
python3 orchestrator.py stock disable TSLA
```

### Settings Management

```bash
# View all settings
python3 orchestrator.py settings list

# Get a single setting
python3 orchestrator.py settings get dry_run_mode

# Change a setting (takes effect on next service tick)
python3 orchestrator.py settings set dry_run_mode false
python3 orchestrator.py settings set scheduler_poll_seconds 30
python3 orchestrator.py settings set max_daily_analyses 20
```

### Scheduler

```bash
# Run all due schedules now
python3 orchestrator.py run-due

# Check earnings triggers
python3 orchestrator.py earnings-check
```

### System

```bash
# Status dashboard
python3 orchestrator.py status

# Initialize database schema (first time or reset)
python3 orchestrator.py db-init
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

## Running the Service

### Option 1: screen/tmux (simplest)

```bash
screen -S nexus
cd ~/nexus-light
python3 service.py
# Ctrl+A, D to detach
# screen -r nexus to reattach
```

### Option 2: systemd (production)

Edit `nexus-light.service` — replace `YOUR_USER` with your Linux username (4 places). If using nvm, uncomment the PATH line.

```bash
sudo cp nexus-light.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-light

# Verify
sudo systemctl status nexus-light
journalctl -u nexus-light -f
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
5. **Heartbeat** — Writes state, tick duration, and task info to `nexus.service_status`.

The sleep between ticks is interruptible — SIGTERM/SIGINT breaks the sleep immediately for graceful shutdown.

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
| postgres | pgvector/pgvector:pg16 | 5432 | Shared DB for Nexus + LightRAG |
| ib-gateway | ghcr.io/gnzsnz/ib-gateway:stable | 4002, 5900 | Paper trading API + VNC |
| lightrag | lightrag/lightrag:latest | 9621 | Knowledge base API |
| neo4j | neo4j:5-community | 7474, 7687 | Graph storage for LightRAG |

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

## MCP Server Configuration

Claude Code's MCP servers are configured in `~/.claude/` on the host. The orchestrator relies on these being set up correctly.

Required MCP servers:
- **ib-gateway** — connects to localhost:4002 for market data and order execution
- **lightrag** — connects to localhost:9621 for knowledge retrieval

Configure by editing `~/.claude/settings.json` or using `claude mcp add`. The exact configuration depends on which IB MCP server implementation you're using.

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
   gcloud run jobs create nexus-scheduler \
       --image gcr.io/PROJECT/nexus-orchestrator \
       --args="service.py,once" \
       --set-env-vars="PG_HOST=/cloudsql/..." \
       --add-cloudsql-instances=PROJECT:REGION:INSTANCE

   # Schedule via Cloud Scheduler
   gcloud scheduler jobs create http nexus-premarket \
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
If analyses aren't running, check: `python3 orchestrator.py settings get dry_run_mode`. Disable with: `python3 orchestrator.py settings set dry_run_mode false`.

**Schedule not firing:**
Check next_run_at: `SELECT name, next_run_at FROM nexus.schedules WHERE is_enabled`. Re-initialize: `python3 service.py init`. Check circuit breaker: `SELECT name, consecutive_fails FROM nexus.schedules`.

**High API costs:**
Reduce `max_daily_analyses`. Use `dry_run_mode = true` when not actively monitoring. Set a spending cap in the Anthropic Console.

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
git remote set-url origin git@github.com:vladm3105/trading_light_pilot.git
```

Requires `~/.ssh/config` entry:
```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/github-vladm3105
    IdentitiesOnly yes
```

---

## Testing

The platform includes comprehensive test coverage for the graph and RAG layers.

### Running Tests

```bash
cd trader

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
trader/
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
git clone git@github.com:vladm3105/trading_light_pilot.git
cd trading_light_pilot

# Setup
cp .env.template .env
# Edit .env with your credentials
bash setup.sh

# Run tests before committing
cd trader && pytest --no-cov -q

# After making changes
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

---

*Nexus Light Trading Platform v2.1 — Database-driven. Uninterrupted. Hot-reloadable.*
