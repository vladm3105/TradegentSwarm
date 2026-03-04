# Data Architecture

## Files as Source of Truth

All skill outputs are stored as **YAML files first**, then indexed to databases.

```
┌─────────────────────────────────────────────────────────────────┐
│              YAML FILES = SOURCE OF TRUTH                       │
│                                                                 │
│  tradegent_knowledge/knowledge/                                 │
│  ├── analysis/stock/          ← Stock analyses                 │
│  ├── analysis/earnings/       ← Earnings analyses              │
│  ├── analysis/research/       ← Research analyses              │
│  ├── trades/{YYYY}/{MM}/      ← Trade journals                 │
│  ├── reviews/{YYYY}/{MM}/     ← Post-trade reviews             │
│  ├── watchlist/               ← Watchlist entries              │
│  └── ...                                                        │
│                                                                 │
│  Benefits: Git versioned, human readable, portable, recoverable │
└────────────────────────────┬────────────────────────────────────┘
                             │ auto-ingest hook (ingest.py)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│      DERIVED STORAGE (priority order for fast UI delivery)     │
├─────────────────────────────────────────────────────────────────┤
│  [1] PostgreSQL kb_* tables  ← FIRST (UI needs immediately)    │
│  [2] pgvector RAG chunks     ← Semantic search                 │
│  [3] Neo4j Knowledge Graph   ← Entity relationships            │
└─────────────────────────────────────────────────────────────────┘
```

## Why DB First?

The UI queries `kb_*` tables directly. Database insert is fastest, so UI can display new analysis immediately while RAG/Graph indexing continues.

## Why Not Direct-to-DB?

| Concern | File-Based Approach |
|---------|---------------------|
| Audit trail | Git history tracks all changes |
| Debugging | Read YAML files directly |
| Recovery | Re-ingest from files if DB lost |
| Sharing | Copy files to share analyses |
| Offline access | Files work without database |

## UI Visualization

> **Note**: SVG file generation is **DEPRECATED**.
> Settings: `svg_generation_enabled=false`, `auto_viz_enabled=false`

The UI renders visualizations dynamically from PostgreSQL `kb_*` tables:
- `kb_stock_analyses` → Stock analysis dashboard
- `kb_earnings_analyses` → Earnings analysis view
- `kb_trade_journals` → Trade history
- `kb_target_tracking` → Target verification

## Conflict Resolution

If derived storage conflicts with files, **files win**. Re-ingest to fix.
