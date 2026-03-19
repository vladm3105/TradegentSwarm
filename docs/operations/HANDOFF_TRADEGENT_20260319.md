# Tradegent Platform Handoff - 2026-03-19

## Scope

Core platform in `tradegent/`:
- CLI + orchestrator (`orchestrator.py`)
- daemon (`service.py`)
- RAG module (`rag/`)
- Graph module (`graph/`)
- DB layer (`db_layer.py`)

## Current State

- Branch: `main`
- Commit: `991a787`
- Git status: clean and synced with `origin/main`
- Recent test remediation completed and pushed.

## What Changed Recently

- Fixed RAG chunk config parsing for `${VAR:-default}` templates.
- Fixed token chunk splitting loop edge case when overlap approaches max tokens.
- Updated/rewritten failing tests across RAG + IB client + side effects.
- Inlined runtime engine guard logic into `orchestrator.py` and removed deprecated `cli_runtime` package files.

## Start/Run

From repository root:

```bash
cd /opt/data/tradegent_swarm/tradegent

# Bring up infra
docker compose up -d

# Optional full preflight
python preflight.py --full

# Initialize DB if needed
python orchestrator.py db-init

# Run service daemon
python service.py
```

Quick CLI examples:

```bash
cd /opt/data/tradegent_swarm/tradegent
python tradegent.py --help
python tradegent.py settings set dry_run_mode false
python tradegent.py pipeline NVDA --type stock --no-execute
```

## Health/Validation Checklist

1. Infra containers healthy (`docker compose ps`).
2. PostgreSQL reachable on `5433`.
3. Neo4j reachable on `7688`.
4. IB Gateway paper mode reachable on `4002`.
5. IB MCP service reachable on `8100`.
6. Quick analysis run completes without pipeline exceptions.

## Operational Risks

- Production safety relies on mode settings; keep `dry_run_mode=true` unless intentionally testing analysis/trading flow.
- Some tests and schedulers are time-sensitive; weekend and timezone behavior can affect expectations.
- `psql` may fail in this environment due to `libpq` mismatch; prefer Python `psycopg` checks via project venv.

## Useful Paths

- Main code: `/opt/data/tradegent_swarm/tradegent`
- Logs: `/opt/data/tradegent_swarm/tradegent/logs`
- Rules: `/opt/data/tradegent_swarm/.claude/rules`

## Recommended First Task for New Owner

Run `preflight.py --full`, then execute one dry-run stock pipeline and verify output persistence + indexing behavior end-to-end.
