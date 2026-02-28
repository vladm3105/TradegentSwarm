# LightRAG Deprecation Checklist

## Overview

Phased deprecation of LightRAG in favor of native pgvector + Neo4j hybrid system.

**Current Status: Phase 3 Complete (2025-02-19)**

## Deprecation Phases

### Phase 1: Parallel Operation (Complete)

Both systems run simultaneously. New system is primary, LightRAG is fallback.

- [x] Deploy pgvector embedding pipeline
- [x] Deploy Neo4j graph extraction
- [x] Implement hybrid context builder
- [x] Add fallback to LightRAG on errors
- [x] Monitor error rates for 2 weeks
- [x] Compare search quality (A/B testing)

**Acceptance Criteria:** Met
- New system handles > 95% of requests
- Search quality comparable or better
- No increase in skill failures

### Phase 2: Soft Deprecation (Complete)

LightRAG available but not actively used.

- [x] Remove LightRAG from default search path
- [x] Keep LightRAG container running (standby)
- [x] Log any fallback invocations
- [x] Document remaining LightRAG dependencies

**Completed**: No fallback invocations observed

### Phase 3: Hard Deprecation (Complete - 2025-02-19)

LightRAG disabled, resources freed.

- [x] Stop LightRAG container
- [x] Remove LightRAG from docker-compose.yml
- [x] Archive LightRAG configuration (removed)
- [x] Update documentation
- [x] Update orchestrator.py to use native RAG/Graph
- [x] Replace `ingest_to_lightrag()` with `kb_ingest_analysis()`
- [x] Update settings: `lightrag_*` → `kb_*`
- [x] Update MCP tools: `mcp__lightrag__*` → `mcp__trading-rag__*`, `mcp__trading-graph__*`

### Phase 4: Removal (In Progress)

Complete removal of LightRAG code and configuration.

- [x] Delete LightRAG integration code from orchestrator.py
- [x] Remove LightRAG environment variables from documentation
- [ ] Clean up LightRAG database tables (if any remain)
- [x] Update CLAUDE.md and skill documentation

**Target**: Complete after 1 month stability verification

## LightRAG Components Inventory

### Docker Services

| Component | Status | Deprecation Phase |
|-----------|--------|-------------------|
| `lightrag` container | **Removed** | Phase 3 Complete |

### Environment Variables

| Variable | Used By | Status |
|----------|---------|--------|
| `LIGHTRAG_LLM_MODEL` | docker-compose.yml | **Removed** |
| `LIGHTRAG_EMBED_MODEL` | docker-compose.yml | **Removed** |

### Code References

```bash
# Verify no LightRAG references remain
grep -r "lightrag" /opt/data/tradegent_swarm/tradegent/ --include="*.py"
# Should return no results (except this deprecation doc)
```

| File | Function | Status |
|------|----------|--------|
| docker-compose.yml | lightrag service | **Removed** |
| orchestrator.py | ingest_to_lightrag | **Replaced with kb_ingest_analysis** |
| orchestrator.py | lightrag_* settings | **Replaced with kb_* settings** |

### Database Objects

```sql
-- Check for any remaining LightRAG tables (should be empty)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'lightrag%';
```

### Network Dependencies

| Service | Port | Status |
|---------|------|--------|
| LightRAG API | 9621 | **Removed** - Port no longer in use |

## Migration Verification

### Data Completeness

```bash
# Compare document counts
# LightRAG
curl -s http://localhost:9621/health | jq '.document_count'

# New system
docker exec tradegent-postgres-1 psql -U tradegent -d tradegent -t \
    -c "SELECT COUNT(DISTINCT doc_id) FROM rag.documents;"
```

### Search Quality

```python
# Compare search results
from rag.search import semantic_search

def compare_search(query: str, ticker: str):
    # New system
    new_results = semantic_search(query, ticker=ticker, top_k=5)

    # LightRAG (if available)
    import httpx
    try:
        resp = httpx.post("http://localhost:9621/query", json={"query": query})
        lightrag_results = resp.json().get("results", [])
    except:
        lightrag_results = []

    print(f"Query: {query}")
    print(f"New system: {len(new_results)} results")
    print(f"LightRAG: {len(lightrag_results)} results")

    # Compare top result overlap
    new_ids = {r.doc_id for r in new_results[:3]}
    old_ids = {r.get('doc_id') for r in lightrag_results[:3]}
    overlap = new_ids & old_ids
    print(f"Top-3 overlap: {len(overlap)}/3")
```

### Performance Comparison

| Metric | LightRAG | New System | Target |
|--------|----------|------------|--------|
| Search latency (p50) | TBD | TBD | < 100ms |
| Search latency (p95) | TBD | TBD | < 500ms |
| Index latency | TBD | TBD | < 5s/doc |
| Memory usage | TBD | TBD | < 2GB |

## Fallback Code Removal

### Current Fallback Pattern

```python
# In hybrid.py (to be removed in Phase 4)
try:
    results = semantic_search(query, ticker=ticker)
except RAGUnavailableError:
    log.warning("Falling back to LightRAG")
    results = lightrag_fallback(query)
```

### Target Pattern (Phase 4)

```python
# Direct call, no fallback
results = semantic_search(query, ticker=ticker)
```

## Docker Compose Changes

### Phase 3: Comment Out

```yaml
# docker-compose.yml
services:
  # DEPRECATED: LightRAG replaced by native pgvector
  # lightrag:
  #   image: ghcr.io/hkuds/lightrag:latest
  #   ...
```

### Phase 4: Remove

Delete the entire `lightrag` service block.

## Documentation Updates

### Files to Update

| File | Update Required |
|------|-----------------|
| `CLAUDE.md` | Remove LightRAG references |
| `tradegent/README.md` | Update architecture diagram |
| `docs/monitoring.md` | Remove LightRAG metrics |
| `.claude/skills/*.md` | Remove LightRAG fallback notes |

## Rollback Capability

Until Phase 4 completion, maintain rollback capability:

```bash
# Re-enable LightRAG if needed
cd /opt/data/tradegent_swarm/tradegent

# Uncomment lightrag in docker-compose.yml
# Then:
docker compose up -d lightrag

# Set fallback mode
export RAG_BACKEND=lightrag
```

## Sign-Off Requirements

| Phase | Sign-Off By | Criteria |
|-------|-------------|----------|
| Phase 1 → 2 | System owner | 95% success rate, quality parity |
| Phase 2 → 3 | System owner | No fallback invocations for 1 month |
| Phase 3 → 4 | System owner | No issues for 3 months |

## Timeline

| Phase | Target Date | Status |
|-------|-------------|--------|
| Phase 1 (Parallel) | 2025-01 | Complete |
| Phase 2 (Soft Deprecation) | 2025-02 | Complete |
| Phase 3 (Hard Deprecation) | 2025-02-19 | **Complete** |
| Phase 4 (Removal) | 2025-03-19 | In Progress |
