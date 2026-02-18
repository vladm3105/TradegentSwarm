# Trading Light Pilot - Claude Code Instructions

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and LightRAG. This is an **AI-first project** with agent automation.

## Project Structure

```
trading_light_pilot/
├── .claude/skills/          # Claude Code skills (auto-invoke enabled)
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

## Claude Code Skills

Skills in `.claude/skills/` auto-invoke based on context. Each skill has:
- YAML frontmatter with metadata and triggers
- Workflow steps referencing `trading/skills/`
- Chaining to related skills

### Skill Index

| Skill                 | Triggers                                                 | Category   |
| --------------------- | -------------------------------------------------------- | ---------- |
| **earnings-analysis** | "earnings analysis", "pre-earnings", "before earnings"   | Analysis   |
| **stock-analysis**    | "stock analysis", "technical analysis", "value analysis" | Analysis   |
| **research**          | "research", "macro analysis", "sector analysis"          | Research   |
| **ticker-profile**    | "ticker profile", "what do I know about"                 | Knowledge  |
| **trade-journal**     | "log trade", "bought", "sold", "entered position"        | Trade Mgmt |
| **watchlist**         | "watchlist", "add to watchlist", "watch this"            | Trade Mgmt |
| **post-trade-review** | "review trade", "closed trade", "what did I learn"       | Learning   |
| **scan**              | "scan", "find opportunities", "what should I trade"      | Scanning   |

### Workflow Chains

```text
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

**Automatic chaining:**

- Analysis recommends WATCH → triggers watchlist skill
- Trade journal exit → triggers post-trade-review skill
- Scanner high score → triggers appropriate analysis skill
- Post-trade review → updates ticker-profile

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

## Executing Skills

When a skill is invoked (auto or manual):

1. Read the `SKILL.md` file from `trading/skills/{skill-name}/`
2. Follow the workflow steps exactly
3. Use the `template.yaml` structure for output
4. Save output to corresponding `trading/knowledge/` folder
5. Check for chaining actions (WATCH → watchlist, exit → review)

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
- Skills auto-invoke based on conversation context - no manual `/command` needed
