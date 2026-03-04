# Trading Modes & Configuration

## Safety Default

The system starts with `dry_run_mode=true`, which blocks ALL Claude Code calls.

## Trading Modes

| Mode | dry_run | auto_execute | stock.state | Behavior |
|------|---------|--------------|-------------|----------|
| **Dry Run** (default) | true | any | any | Logs only, no calls |
| **Analysis Only** | false | false | analysis | Reports, no orders |
| **Paper Trading** | false | true | paper | Paper orders |
| **Live Trading** | — | — | live | **Blocked in code** |

## Enabling Trading

```bash
# Step 1: Disable dry run mode
python tradegent.py settings set dry_run_mode false

# Step 2a: Analysis only
python tradegent.py settings set auto_execute_enabled false

# Step 2b: Enable paper trading
python tradegent.py settings set auto_execute_enabled true
python tradegent.py stock set-state NVDA paper
```

## Environment Variables

**PostgreSQL:**
```bash
export PG_USER=tradegent
export PG_PASS=<password>
export PG_DB=tradegent
export PG_HOST=localhost
export PG_PORT=5433
```

**Neo4j:**
```bash
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASS=<password>
```

**LLM Providers:**
```bash
export EMBED_PROVIDER=openai    # RAG embeddings (keep consistent!)
export EXTRACT_PROVIDER=openai  # Graph extraction
export OPENAI_API_KEY=<key>
```

## Parallel Execution

| Setting | Default | Description |
|---------|---------|-------------|
| `parallel_execution_enabled` | true | Enable parallel execution |
| `parallel_fallback_to_sequential` | true | Fall back on failure |
| `max_concurrent_runs` | 2 | Max parallel processes |
| `max_daily_analyses` | 15 | Daily analysis cap |

## Key Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `dry_run_mode` | true | Block all Claude Code calls |
| `auto_execute_enabled` | false | Enable order placement |
| `svg_generation_enabled` | false | DEPRECATED |
| `auto_viz_enabled` | false | DEPRECATED |
| `skill_use_claude_code` | false | Enable Claude for skills |
| `skill_daily_cost_limit` | 10.00 | Max daily skill cost |

## CLI Commands

```bash
python tradegent.py --help
python tradegent.py analyze NVDA --type stock
python tradegent.py watchlist
python tradegent.py run-scanners
python service.py  # Start daemon
```

## Infrastructure

```bash
cd tradegent
docker compose up -d  # Start PostgreSQL, IB Gateway, Neo4j
docker compose logs -f
```
