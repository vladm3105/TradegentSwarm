# TradegentSwarm - Copilot Instructions

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system. This is an **AI-first project** with agent automation.

## Project Structure

```
tradegent_swarm/
├── tradegent/               # Tradegent Platform (Python)
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

Skills live in `tradegent_knowledge/skills/{skill-name}/` with:
- `SKILL.md` — step-by-step workflow instructions
- `template.yaml` — output template structure

Claude Code skills in `.claude/skills/` integrate MCP tools:
1. **Pre-Analysis**: Get context via `rag_hybrid_context`, `graph_context`
2. **Real-Time Data**: Get prices via `mcp__ib-mcp__get_stock_price`, historical data
3. **Web Research**: Search via `mcp__brave-search__brave_web_search`, scrape via `fetch_protected_article`
4. **Post-Save Hooks**: Index via `graph_extract`, `rag_embed`, push via `mcp__github-vl__push_files`

### Workflow Chains

```text
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

### Scanner System

Scanners in `tradegent_knowledge/knowledge/scanners/` define systematic opportunity-finding rules:

| Type | Folder | Examples |
|------|--------|----------|
| Daily | `scanners/daily/` | premarket-gap, earnings-momentum, 52w-extremes |
| Intraday | `scanners/intraday/` | options-flow, unusual-volume |
| Weekly | `scanners/weekly/` | earnings-calendar, institutional-activity |

**Scoring**: Score ≥7.5 triggers analysis, 5.5-7.4 adds to watchlist, <5.5 skips.

**Execution**: Use `mcp__ib-mcp__run_scanner` for IB scanners, web search for catalysts.

### Watchlist Management

Watchlist entries in `tradegent_knowledge/knowledge/watchlist/` track potential trades waiting for triggers.

**Lifecycle**: `active` → `triggered` | `invalidated` | `expired`

| Action | Trigger |
|--------|---------|
| Add | Scanner score 5.5-7.4, analysis WATCH, user request |
| Remove (triggered) | Entry condition met → create trade journal |
| Remove (invalidated) | Thesis broken → archive |
| Remove (expired) | >30 days → archive |

**Daily review**: Check each active entry for trigger/invalidation/expiration.

## Tradegent Platform

### Running Commands
```bash
cd tradegent
python orchestrator.py --help     # CLI commands
python service.py                 # Start daemon
```

### Infrastructure
```bash
cd tradegent
docker compose up -d              # Start PostgreSQL, IB Gateway, Neo4j
```

### LLM Providers
```bash
# Current configuration (.env)
EMBED_PROVIDER=openai           # text-embedding-3-large (3072 dims)
EXTRACT_PROVIDER=openai         # gpt-4o-mini (12x faster than Ollama)
OPENAI_API_KEY=sk-proj-...      # ~$2/year total cost
```

| Task | Provider | Model | Speed | Cost |
|------|----------|-------|-------|------|
| RAG Embeddings | OpenAI | text-embedding-3-large | 0.1s/doc | $0.13/1M tokens |
| Graph Extraction | OpenAI | gpt-4o-mini | 8s/doc | $0.15/1M input |

### Database
- PostgreSQL stores all pipeline config, tickers, and results
- Schema in `tradegent/db/init.sql`
- All SQL queries go through `db_layer.py` (NexusDB class)
- Tables: `nexus.stocks`, `nexus.settings`, `nexus.schedules`, `nexus.run_history`, `nexus.analysis_results`, `nexus.ib_scanners`, `nexus.service_status`

### Watchlist Management
```bash
python orchestrator.py stock list                    # List all stocks
python orchestrator.py stock add PLTR --priority 6  # Add stock
python orchestrator.py stock enable NVDA            # Enable for automation
python orchestrator.py stock set-state NVDA paper   # Enable paper trading
python orchestrator.py watchlist                    # Analyze all enabled
```

### Two-Stage Pipeline
1. **Stage 1 (Analysis)**: Claude Code analyzes stock using IB data, web search, RAG+Graph context
2. **Gate**: Must pass EV >5%, confidence >60%, R:R >2:1
3. **Stage 2 (Execution)**: Places paper orders via IB Gateway (only if gate passes and stock state=paper)

### Trading Modes
| Mode | Settings | Stock State |
|------|----------|-------------|
| Analysis Only | `dry_run_mode=false`, `auto_execute_enabled=false` | `analysis` |
| Paper Trading | `dry_run_mode=false`, `auto_execute_enabled=true` | `paper` |
| Live Trading | — | 🚫 Blocked in code |

### Safety Mechanisms
- `dry_run_mode = true` (default) blocks all Claude Code calls
- `auto_execute_enabled = false` blocks Stage 2
- Stock state machine: `analysis` → `paper` → `live` (blocked)
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

## MCP Tools Reference

### RAG MCP (trading-rag)
| Tool | Purpose |
|------|---------|
| `rag_hybrid_context` | Get combined vector + graph context |
| `rag_search` | Semantic search |
| `rag_embed` | Embed document for search |
| `rag_status` | Get statistics |

### Graph MCP (trading-graph)
| Tool | Purpose |
|------|---------|
| `graph_extract` | Extract entities from document |
| `graph_context` | Get all ticker relationships |
| `graph_peers` | Get sector peers |
| `graph_risks` | Get known risks |
| `graph_biases` | Get bias history |

### IB MCP (ib-mcp)
| Tool | Purpose |
|------|---------|
| `get_stock_price` | Real-time quote |
| `get_historical_data` | OHLCV bars |
| `get_option_chain` | Options data |
| `run_scanner` | Market scanner |
| `get_positions` | Portfolio |

### GitHub MCP (github-vl)
| Tool | Purpose |
|------|---------|
| `push_files` | Push to TradegentSwarm repo |

## Important Notes

- Do not commit `.env` files (contains credentials)
- IB Gateway requires valid paper trading account
- RAG (pgvector) handles semantic search, Graph (Neo4j) handles entity relationships
- Scanner configs in `knowledge/scanners/` encode trading edge — treat as sensitive
- JSON schemas for all document types live in `workflows/schemas/`
- Skills auto-invoke based on conversation context
- All skills use post-save hooks to index in RAG+Graph
