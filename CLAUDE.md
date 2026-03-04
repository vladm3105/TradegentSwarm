# TradegentSwarm - Claude Code Instructions

> **Skills**: v2.7 (stock-analysis), v2.6 (earnings-analysis), v2.1 (other)
> **Production Start**: 2026-02-23

**Tradegent** is an AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system.

## Quick Reference

| Topic | Rule File |
|-------|-----------|
| Project structure | `.claude/rules/01-project-overview.md` |
| Schema validation (v2.7) | `.claude/rules/02-schema-validation.md` |
| Skills system | `.claude/rules/03-skills-system.md` |
| Data architecture | `.claude/rules/04-data-architecture.md` |
| Database access | `.claude/rules/05-database-access.md` |
| MCP servers | `.claude/rules/06-mcp-servers.md` |
| IB Gateway | `.claude/rules/07-ib-gateway.md` |
| Observability | `.claude/rules/08-observability.md` |
| Git workflow | `.claude/rules/09-git-workflow.md` |
| File conventions | `.claude/rules/10-file-conventions.md` |
| Scanners | `.claude/rules/11-scanners.md` |
| Watchlist | `.claude/rules/12-watchlist.md` |
| Trading modes | `.claude/rules/13-trading-modes.md` |
| Auto-ingest | `.claude/rules/14-auto-ingest.md` |

## Critical Rules

### Database Access (psycopg3)

```python
from db_layer import NexusDB  # NOT TradingDB

db = NexusDB()
db.connect()
with db._conn.cursor() as cur:
    cur.execute("SELECT * FROM nexus.schedules")
    for row in cur.fetchall():
        print(row['name'])  # Dict access, NOT row[0]
```

### Common Mistakes

| Mistake | Correct |
|---------|---------|
| `from db_layer import TradingDB` | `from db_layer import NexusDB` |
| `row[0]` (tuple access) | `row['column_name']` (dict access) |
| `service_status.status` | `service_status.state` |
| `run_history.result_summary` | `run_history.raw_output` |

### Data Architecture

```
YAML Files (source of truth)
     │
     │ auto-ingest hook
     ▼
┌─────────────────────────────────────────────┐
│  [1] PostgreSQL kb_* tables ← UI queries    │
│  [2] pgvector RAG ← semantic search         │
│  [3] Neo4j Graph ← entity relationships     │
└─────────────────────────────────────────────┘
```

**SVG generation is DEPRECATED** - UI renders from database tables.

### Schema Validation (v2.7)

```bash
python scripts/validate_analysis.py <file.yaml>
```

Required: derivation objects, alert tags, 100+ char significance.

### Git Push (Conda Fix)

```bash
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

### Trading Modes

| Mode | dry_run | auto_execute | Behavior |
|------|---------|--------------|----------|
| Dry Run (default) | true | any | Logs only |
| Analysis Only | false | false | Reports, no orders |
| Paper Trading | false | true | Paper orders |

### Environment Variables

```bash
export PG_USER=tradegent PG_PASS=<pw> PG_DB=tradegent PG_HOST=localhost PG_PORT=5433
export NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASS=<pw>
export EMBED_PROVIDER=openai EXTRACT_PROVIDER=openai OPENAI_API_KEY=<key>
```

## Documentation

See `docs/` for full documentation:
- [Architecture Overview](docs/architecture/overview.md)
- [Skill-Database Mapping](docs/architecture/skill-database-mapping.md)
- [Database Schema](docs/architecture/database-schema.md)
