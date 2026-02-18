# Trading Light Pilot

AI-driven trading platform that combines automated market analysis, trade execution, and a structured knowledge base. Uses Claude Code CLI as its AI engine, Interactive Brokers for market data/execution, and LightRAG for knowledge persistence.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRADING LIGHT PILOT                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   trader/                    trading/                                   │
│   ┌──────────────────┐       ┌──────────────────────────────────────┐  │
│   │  Nexus Light      │       │  skills/     (how-to guides)        │  │
│   │  Trading Platform │──────▶│  knowledge/  (data & docs)          │  │
│   │                   │       │  workflows/  (CI/CD & schemas)      │  │
│   │  • service.py     │       └──────────────────────────────────────┘  │
│   │  • orchestrator.py│                      │                         │
│   │  • db_layer.py    │                      ▼                         │
│   └────────┬─────────┘              ┌──────────────┐                   │
│            │                        │   LightRAG   │                   │
│            ▼                        └──────────────┘                   │
│   ┌─────────────────────────────────────────────┐                      │
│   │  Docker: PostgreSQL │ IB Gateway │ Neo4j    │                      │
│   └─────────────────────────────────────────────┘                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
trading_light_pilot/
├── trader/                         # Nexus Light Trading Platform
│   ├── service.py                  # Long-running daemon (tick loop)
│   ├── orchestrator.py             # Pipeline engine + CLI
│   ├── db_layer.py                 # PostgreSQL access layer
│   ├── db/init.sql                 # Schema, seed data, views
│   ├── docker-compose.yml          # PG, IB Gateway, LightRAG, Neo4j
│   ├── setup.sh                    # One-command setup
│   └── README.md                   # Platform documentation
│
└── trading/                        # Trading Knowledge System
    ├── knowledge/                  # Actual trading data & analyses
    │   ├── analysis/               # Earnings, stock, research, profiles
    │   ├── trades/                 # Executed trade journals
    │   ├── strategies/             # Strategy definitions
    │   ├── scanners/               # Scanner configs (daily/intraday/weekly)
    │   ├── learnings/              # Biases, patterns, rules
    │   ├── watchlist/              # Pending trade triggers
    │   └── reviews/                # Post-trade reviews
    │
    ├── skills/                     # Agent-agnostic skill definitions
    │   ├── earnings-analysis/      # 8-phase earnings framework
    │   ├── stock-analysis/         # 7-phase stock framework
    │   ├── research-analysis/      # Macro/sector/thematic research
    │   ├── trade-journal/          # Trade documentation
    │   ├── post-trade-review/      # Learning loop
    │   ├── watchlist/              # Trigger monitoring
    │   ├── ticker-profile/         # Persistent ticker knowledge
    │   └── market-scanning/        # Scanner execution
    │
    └── workflows/                  # CI/CD & validation
        ├── .github/                # Actions workflows & scripts
        └── .lightrag/              # Schemas & sync config
```

## Components

### Trader (`trader/`)

The Nexus Light Trading Platform — a database-driven orchestrator that runs analysis and execution pipelines via Claude Code CLI.

- **Two-stage pipeline**: Analysis (multi-source) → Gate check (EV, confidence, R:R) → Execution (paper trading)
- **Infrastructure**: PostgreSQL + IB Gateway + LightRAG + Neo4j via Docker Compose
- **Config in DB**: All settings live in PostgreSQL — no restarts to change behavior

See [trader/README.md](trader/README.md) for full setup and usage.

### Trading Knowledge (`trading/knowledge/`)

Structured YAML repository of trading data: analyses, trade journals, strategies, scanner configs, and learnings. All files follow the `{TICKER}_{YYYYMMDDTHHMM}.yaml` naming convention.

See [trading/knowledge/README.md](trading/knowledge/README.md) for details.

### Trading Skills (`trading/skills/`)

Agent-agnostic skill definitions with step-by-step frameworks and YAML templates. Works with any LLM — each skill is self-contained and single-purpose.

See [trading/skills/README.md](trading/skills/README.md) for the full skill index.

### Trading Workflows (`trading/workflows/`)

GitHub Actions CI/CD for validating documents against JSON schemas and syncing to LightRAG. Includes schemas for all document types.

## Prerequisites

| Requirement | Purpose |
|-------------|---------|
| Docker + Compose | Infrastructure services |
| Python 3.11+ | Orchestrator runtime |
| Node.js 20+ | Claude Code CLI dependency |
| Claude Code CLI | AI engine |
| Anthropic API key | Automated analysis |
| IB paper account | Market data & execution |

## Quick Start

```bash
cd trader
cp .env.template .env        # Fill in credentials
./setup.sh                   # Start infrastructure
python service.py            # Run the daemon
```

See [trader/README.md](trader/README.md) for detailed instructions.

## License

Private repository.
