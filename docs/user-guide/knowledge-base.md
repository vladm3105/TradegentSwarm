# Knowledge Base Guide

The knowledge base stores all trading data, analyses, and learnings in structured YAML format.

---

## Overview

```
tradegent_knowledge/
├── skills/                  # Skill definitions
│   ├── stock-analysis/
│   ├── earnings-analysis/
│   └── ...
│
├── knowledge/               # Trading data
│   ├── analysis/
│   │   ├── stock/          # Stock analyses
│   │   ├── earnings/       # Earnings analyses
│   │   ├── research/       # Research reports
│   │   └── ticker-profiles/
│   ├── trades/             # Trade journal
│   ├── watchlist/          # Active watchlist
│   ├── reviews/            # Post-trade reviews
│   └── scanners/           # Scanner configs
│
└── examples/               # Sample files
```

---

## Three-Layer Model

```
Layer 1: FILES (Source of Truth)
─────────────────────────────────
Location: knowledge/**/*.yaml
Properties: Authoritative, portable, rebuildable

Layer 2: RAG (Semantic Search)
─────────────────────────────────
Storage: PostgreSQL pgvector
Rebuilds from: Layer 1 via embed_document()
Purpose: "Find similar analyses"

Layer 3: GRAPH (Entity Relations)
─────────────────────────────────
Storage: Neo4j
Rebuilds from: Layer 1 via extract_document()
Purpose: "What are NVDA's peers?"
```

**Conflict resolution:** Files always win. Re-index to fix discrepancies.

---

## File Naming

All files use ISO 8601 format:

```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```

Example: `NVDA_20250120T0900.yaml`

---

## Document Types

### Stock Analysis

**Location:** `knowledge/analysis/stock/`

```yaml
_meta:
  version: "2.4"
  doc_type: "stock-analysis"
  ticker: "NVDA"
  created: "2025-01-20T09:00:00-05:00"

data_quality:
  price_data_age_minutes: 5
  news_age_hours: 12

catalyst:
  primary: "..."
  strength: 8

technical:
  trend: "bullish"
  support: 140.00
  resistance: 150.00

fundamental:
  valuation: "..."
  growth: "..."

scenarios:
  bull: {probability: 0.20, target: 170}
  base: {probability: 0.45, target: 155}
  bear: {probability: 0.25, target: 130}
  disaster: {probability: 0.10, target: 110}

bias_countermeasures:
  - bias: "confirmation"
    rule: "..."
    checklist: ["...", "..."]

gate:
  ev_pct: 8.5
  confidence_pct: 65
  risk_reward: "3:1"
  passes: true

recommendation:
  action: "BUY"
  entry: 145.00
  stop: 138.00
  targets: [155, 165]
```

### Earnings Analysis

**Location:** `knowledge/analysis/earnings/`

Similar to stock analysis with additional:
- Consensus estimates
- IV analysis
- Earnings history
- Post-earnings drift

### Trade Journal

**Location:** `knowledge/trades/`

```yaml
_meta:
  version: "2.1"
  doc_type: "trade-journal"
  ticker: "NVDA"
  trade_id: "NVDA_20250120_001"

entry:
  date: "2025-01-20"
  price: 145.00
  size: 100
  direction: "long"
  thesis: "..."

risk:
  stop_loss: 138.00
  max_loss_pct: 5
  position_size_pct: 2

exit:
  date: "2025-01-25"
  price: 155.00
  reason: "target_hit"
  pnl: 1000.00
  pnl_pct: 6.9
```

### Watchlist

**Location:** `knowledge/watchlist/`

```yaml
_meta:
  version: "2.1"
  doc_type: "watchlist"
  ticker: "NVDA"
  created: "2025-01-15"
  expires: "2025-02-15"
  status: "active"

entry_trigger:
  type: "price"
  condition: "above"
  value: 145.00

invalidation:
  price_below: 135.00
  thesis_broken: "..."
  time_limit_days: 30

priority: "high"
notes: "..."
```

### Post-Trade Review

**Location:** `knowledge/reviews/`

```yaml
_meta:
  version: "2.1"
  doc_type: "post-trade-review"
  ticker: "NVDA"
  trade_id: "NVDA_20250120_001"

outcome:
  pnl: 1000.00
  pnl_pct: 6.9
  result: "win"

analysis:
  what_worked: ["..."]
  what_didnt: ["..."]

biases_detected:
  - bias: "anchoring"
    evidence: "..."

lessons:
  - lesson: "..."
    action: "..."

process_improvements:
  - improvement: "..."
    priority: "high"
```

---

## Indexing Documents

### Manual Indexing

```yaml
# Graph extraction (entities + relationships)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}

# RAG embedding (semantic search)
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA_20250120.yaml"}
```

### Batch Indexing

```bash
cd tradegent
python scripts/index_knowledge_base.py --force
```

### Verify Indexing

```bash
# Check RAG
python -c "
from rag.search import get_rag_stats
stats = get_rag_stats()
print(f'Documents: {stats.document_count}, Chunks: {stats.chunk_count}')
"

# Check Graph
python -c "
from graph.layer import TradingGraph
with TradingGraph() as g:
    stats = g.get_stats()
    print(f'Nodes: {sum(stats.node_counts.values())}')
"
```

---

## Searching Knowledge

### RAG Search (Semantic)

```yaml
# Basic search
Tool: rag_search
Input: {"query": "NVDA earnings surprise", "ticker": "NVDA", "top_k": 5}

# Reranked search (higher relevance)
Tool: rag_search_rerank
Input: {"query": "competitive position", "top_k": 5}

# Expanded search (better recall)
Tool: rag_search_expanded
Input: {"query": "AI chip demand", "n_expansions": 3}
```

### Graph Search (Relationships)

```yaml
# Ticker context
Tool: graph_context
Input: {"ticker": "NVDA"}

# Sector peers
Tool: graph_peers
Input: {"ticker": "NVDA"}

# Known risks
Tool: graph_risks
Input: {"ticker": "NVDA"}

# Trading biases
Tool: graph_biases
Input: {}
```

### Combined Search

```yaml
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings analysis"}
```

---

## Backup and Recovery

### Backup Files

```bash
# Full backup
tar -czf knowledge_backup_$(date +%Y%m%d).tar.gz \
  tradegent_knowledge/knowledge/
```

### Rebuild RAG/Graph

If indexes are corrupted or lost:

```bash
# 1. Clear existing
psql -c "TRUNCATE nexus.rag_documents CASCADE"
# Or Neo4j: MATCH (n) DETACH DELETE n

# 2. Re-index all
python scripts/index_knowledge_base.py --force
```

---

## Best Practices

1. **Never edit indexed files** without re-indexing
2. **Use consistent tickers** (NVDA not Nvidia)
3. **Include _meta** in all documents
4. **Set expires** on watchlist entries
5. **Link trades** to analyses via analysis_ref
6. **Review biases** regularly via graph_biases

---

## Related Documentation

- [RAG System](../architecture/rag-system.md)
- [Graph System](../architecture/graph-system.md)
- [Skills Guide](skills-guide.md)
