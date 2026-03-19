# Tradegent Knowledge Base Handoff - 2026-03-19

## Scope

Knowledge repository in `tradegent_knowledge/`:
- Skill definitions (`skills/*/SKILL.md`, `template.yaml`)
- Source-of-truth data (`knowledge/**/*.yaml`)
- Workflows/schemas for validation and automation

## Current State

- Branch: `main`
- Commit: `9087607`
- Git status: `main...origin/main [ahead 1]`
- Action needed: decide whether to push the local ahead commit.

## Data Model (Operationally Important)

1. YAML files are source of truth.
2. Derived indexes:
- PostgreSQL `kb_*` tables (UI first-read path)
- RAG pgvector
- Neo4j graph
3. If conflict occurs, files win; re-ingest to reconcile derived stores.

## Key Directory Map

- Skills: `/opt/data/tradegent_swarm/tradegent_knowledge/skills`
- Knowledge docs: `/opt/data/tradegent_swarm/tradegent_knowledge/knowledge`
- Scanners: `/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/scanners`
- Reviews: `/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/reviews`

## Naming and Placement Rules

- File format: `{TICKER}_{YYYYMMDDTHHMM}.yaml`
- Stock analysis: `knowledge/analysis/stock/`
- Earnings analysis: `knowledge/analysis/earnings/`
- Watchlist: `knowledge/watchlist/`
- Trade journals: `knowledge/trades/{YYYY}/{MM}/`

## Validation Commands

From repository root:

```bash
cd /opt/data/tradegent_swarm/tradegent
python scripts/validate_analysis.py ../tradegent_knowledge/knowledge/analysis/stock/<FILE>.yaml
python scripts/validate_analysis.py --all
```

## Indexing Commands

Single file ingest:

```bash
cd /opt/data/tradegent_swarm/tradegent
python scripts/ingest.py ../tradegent_knowledge/knowledge/<PATH_TO_FILE>.yaml
```

Bulk ingest:

```bash
cd /opt/data/tradegent_swarm
python scripts/index_knowledge_base.py
```

## Operational Checks for New Owner

1. Validate at least one recent analysis YAML.
2. Run single-file ingest and confirm DB/RAG/Graph indexing succeeds.
3. Confirm UI can query newly indexed analysis from `kb_*` tables.
4. Review scanner run outputs under `knowledge/scanners/runs/` for expected shape.

## Risks / Attention Points

- The knowledge repo is one commit ahead of remote; unresolved if intentionally local-only.
- Scanner configs and trading knowledge are sensitive IP; preserve repository privacy and avoid exposure.
- Always save analyses regardless of PASS/MARGINAL/FAIL gate outcomes (required for learning loop and bot signaling).
