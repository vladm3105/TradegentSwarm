# Trading Light Pilot - Claude Code Instructions

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and LightRAG.

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
    └── workflows/           # CI/CD & LightRAG schemas
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

## Trading Skills

When executing trading skills:

1. Read the `SKILL.md` file from `trading/skills/{skill-name}/`
2. Follow the workflow steps exactly
3. Use the `template.yaml` structure for output
4. Save output to corresponding `trading/knowledge/` folder

### Available Skills

- **earnings-analysis**: 8-phase pre-earnings analysis (3-10 days before earnings)
- **stock-analysis**: 7-phase non-earnings analysis (technical, value, momentum)
- **research-analysis**: Macro/sector/thematic research
- **ticker-profile**: Persistent ticker knowledge
- **trade-journal**: Document executed trades
- **watchlist**: Track potential trades waiting for trigger
- **post-trade-review**: Analyze completed trades for lessons
- **market-scanning**: Find trading opportunities using scanner configs

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
docker compose up -d              # Start PostgreSQL, IB Gateway, Neo4j, LightRAG
docker compose logs -f            # View logs
```

### Database
- PostgreSQL stores all pipeline config, tickers, and results
- Schema in `trader/db/init.sql`
- Use `db_layer.py` for all database operations

## Code Standards

- Python 3.11+ with type hints
- Follow PEP 8 conventions
- Use existing patterns in `orchestrator.py` and `db_layer.py`
- All SQL queries go through `db_layer.py`

## Important Notes

- Do not commit `.env` files (contains credentials)
- IB Gateway requires valid paper trading account
- LightRAG syncs trading knowledge for semantic search
- Scanner configs in `knowledge/scanners/` encode trading edge - treat as sensitive
