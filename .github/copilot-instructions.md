# Trading Light Pilot - Copilot Instructions

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system. This is an **AI-first project** with agent automation.

## Project Structure

```
trading_light_pilot/
├── trader/                  # Nexus Light Trading Platform (Python)
│   ├── service.py           # Long-running daemon
│   ├── orchestrator.py      # Pipeline engine + CLI
│   ├── db_layer.py          # PostgreSQL access layer
│   └── docker-compose.yml   # Infrastructure services
│
└── trading/                 # Trading Knowledge System
    ├── skills/              # Agent skill definitions (SKILL.md + template.yaml)
    ├── knowledge/           # Trading data & analyses (YAML documents)
    └── workflows/           # CI/CD & validation schemas
```

## Key Conventions

### File Naming
All trading documents use ISO 8601 format:
```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```
Example: `NVDA_20250120T0900.yaml`

### Skill → Knowledge Mapping

| Skill | Output Location |
|-------|-----------------|
| earnings-analysis | `knowledge/analysis/earnings/` |
| stock-analysis | `knowledge/analysis/stock/` |
| research-analysis | `knowledge/analysis/research/` |
| ticker-profile | `knowledge/analysis/ticker-profiles/` |
| trade-journal | `knowledge/trades/` |
| watchlist | `knowledge/watchlist/` |
| post-trade-review | `knowledge/reviews/` |
| market-scanning | Uses `knowledge/scanners/`, outputs to `watchlist/` |

### Trading Skills

Skills live in `trading/skills/{skill-name}/` with:
- `SKILL.md` — step-by-step workflow instructions
- `template.yaml` — output template structure

### Workflow Chains

```text
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

## Trader Platform

### Running Commands
```bash
cd trader
python orchestrator.py --help     # CLI commands
python service.py                 # Start daemon
```

### Infrastructure
```bash
cd trader
docker compose up -d              # Start PostgreSQL, IB Gateway, Neo4j
```

### Database
- PostgreSQL stores all pipeline config, tickers, and results
- Schema in `trader/db/init.sql`
- All SQL queries go through `db_layer.py` (NexusDB class)
- Tables: `nexus.stocks`, `nexus.settings`, `nexus.schedules`, `nexus.run_history`, `nexus.analysis_results`, `nexus.ib_scanners`, `nexus.service_status`

### Two-Stage Pipeline
1. **Stage 1 (Analysis)**: Claude Code analyzes stock using IB data, web search, RAG+Graph context
2. **Gate**: Must pass EV >5%, confidence >60%, R:R >2:1
3. **Stage 2 (Execution)**: Places paper orders via IB Gateway (only if gate passes and stock state=paper)

### Safety Mechanisms
- `dry_run_mode = true` (default) blocks all Claude Code calls
- `auto_execute_enabled = false` blocks Stage 2
- Stock state machine: `analysis` → `paper` → `live` (future)
- Circuit breaker: schedules auto-disable after 3 consecutive failures

## Code Standards

- Python 3.11+ with type hints
- Follow PEP 8 conventions
- Use existing patterns in `orchestrator.py` and `db_layer.py`
- All SQL queries go through `db_layer.py`

## Git Workflow

SSH authentication with conda/OpenSSL workaround:

```bash
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

## Important Notes

- Do not commit `.env` files (contains credentials)
- IB Gateway requires valid paper trading account
- RAG (pgvector) handles semantic search, Graph (Neo4j) handles entity relationships
- Scanner configs in `knowledge/scanners/` encode trading edge — treat as sensitive
- JSON schemas for all document types live in `workflows/schemas/`
