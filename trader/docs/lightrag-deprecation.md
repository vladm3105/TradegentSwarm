# LightRAG Deprecation Checklist

## Overview

Phased deprecation of LightRAG in favor of native pgvector + Neo4j hybrid system. LightRAG remains available as fallback during transition.

## Deprecation Phases

### Phase 1: Parallel Operation (Current)

Both systems run simultaneously. New system is primary, LightRAG is fallback.

- [x] Deploy pgvector embedding pipeline
- [x] Deploy Neo4j graph extraction
- [x] Implement hybrid context builder
- [x] Add fallback to LightRAG on errors
- [ ] Monitor error rates for 2 weeks
- [ ] Compare search quality (A/B testing)

**Acceptance Criteria:**
- New system handles > 95% of requests
- Search quality comparable or better
- No increase in skill failures

### Phase 2: Soft Deprecation

LightRAG available but not actively used.

- [ ] Remove LightRAG from default search path
- [ ] Keep LightRAG container running (standby)
- [ ] Log any fallback invocations
- [ ] Document remaining LightRAG dependencies

**Trigger**: Phase 1 acceptance met for 2 weeks

### Phase 3: Hard Deprecation

LightRAG disabled, resources freed.

- [ ] Stop LightRAG container
- [ ] Remove LightRAG from docker-compose.yml
- [ ] Archive LightRAG configuration
- [ ] Update documentation

**Trigger**: Phase 2 stable for 1 month

### Phase 4: Removal

Complete removal of LightRAG code and configuration.

- [ ] Delete LightRAG integration code
- [ ] Remove LightRAG environment variables
- [ ] Clean up LightRAG database tables
- [ ] Update CLAUDE.md and skill documentation

**Trigger**: Phase 3 stable for 3 months

## LightRAG Components Inventory

### Docker Services

| Component | Status | Deprecation Phase |
|-----------|--------|-------------------|
| `lightrag` container | Active | Phase 3 |

### Environment Variables

| Variable | Used By | Remove In |
|----------|---------|-----------|
| `LIGHTRAG_LLM_MODEL` | docker-compose.yml | Phase 3 |
| `LIGHTRAG_EMBED_MODEL` | docker-compose.yml | Phase 3 |

### Code References

```bash
# Find LightRAG references
grep -r "lightrag" /opt/data/trading_light_pilot/trader/ --include="*.py"
grep -r "9621" /opt/data/trading_light_pilot/trader/  # LightRAG port
```

| File | Function | Purpose | Replace With |
|------|----------|---------|--------------|
| docker-compose.yml | lightrag service | LightRAG API | Remove |
| hybrid.py | fallback search | Backup search | Native only |

### Database Objects

```sql
-- LightRAG native tables (in lightrag database)
-- These were created by LightRAG, not our schema

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'lightrag%';
```

### Network Dependencies

| Service | Port | Purpose | After Deprecation |
|---------|------|---------|-------------------|
| LightRAG API | 9621 | Document indexing, hybrid search | Not needed |

## Migration Verification

### Data Completeness

```bash
# Compare document counts
# LightRAG
curl -s http://localhost:9621/health | jq '.document_count'

# New system
docker exec nexus-postgres psql -U lightrag -d lightrag -t \
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
| `trader/README.md` | Update architecture diagram |
| `docs/monitoring.md` | Remove LightRAG metrics |
| `.claude/skills/*.md` | Remove LightRAG fallback notes |

## Rollback Capability

Until Phase 4 completion, maintain rollback capability:

```bash
# Re-enable LightRAG if needed
cd /opt/data/trading_light_pilot/trader

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
| Phase 1 (Parallel) | Current | In Progress |
| Phase 2 (Soft Deprecation) | +2 weeks | Pending |
| Phase 3 (Hard Deprecation) | +6 weeks | Pending |
| Phase 4 (Removal) | +18 weeks | Pending |
