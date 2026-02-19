# Migration Rollback Procedures

## Overview

Procedures for rolling back from the new Trading Knowledge Base (Neo4j + pgvector) to the previous LightRAG-only system.

## Pre-Rollback Checklist

- [ ] Identify root cause of rollback decision
- [ ] Verify LightRAG backup exists and is recent
- [ ] Notify stakeholders of planned rollback
- [ ] Document current state (metrics, error logs)
- [ ] Estimate rollback duration

## Rollback Scenarios

### Scenario 1: Graph Layer Issues (Neo4j)

If Neo4j extraction or queries are failing, disable graph layer while keeping vector search.

```python
# Edit trader/config.py or set environment variable
GRAPH_ENABLED = False
# or
export GRAPH_ENABLED=false
```

**Code changes:**

```python
# In hybrid.py - add feature flag check
def get_hybrid_context(ticker: str, query: str, ...):
    # Vector search (always runs)
    vector_results = semantic_search(query, ticker=ticker)

    # Graph context (conditional)
    graph_context = {}
    if os.getenv("GRAPH_ENABLED", "true").lower() == "true":
        try:
            with TradingGraph() as graph:
                graph_context = graph.get_ticker_context(ticker)
        except Exception as e:
            log.warning(f"Graph unavailable: {e}")

    return HybridContext(...)
```

### Scenario 2: Embedding Issues (pgvector)

If embedding pipeline or vector search fails, fall back to LightRAG API.

```bash
# Re-enable LightRAG in docker-compose
docker compose up -d lightrag

# Update search to use LightRAG
export RAG_BACKEND=lightrag
```

**LightRAG fallback code:**

```python
# In search.py - add fallback
def semantic_search_with_fallback(query: str, **kwargs):
    backend = os.getenv("RAG_BACKEND", "pgvector")

    if backend == "pgvector":
        try:
            return semantic_search(query, **kwargs)
        except RAGUnavailableError:
            log.warning("pgvector unavailable, falling back to LightRAG")
            backend = "lightrag"

    if backend == "lightrag":
        return lightrag_search(query, **kwargs)

def lightrag_search(query: str, ticker: str = None, top_k: int = 5):
    """Fall back to LightRAG API."""
    import httpx
    response = httpx.post(
        "http://localhost:9621/query",
        json={"query": query, "mode": "hybrid"},
    )
    # Transform response to SearchResult format
    ...
```

### Scenario 3: Full Rollback to LightRAG

Complete rollback to pre-migration state.

#### Step 1: Stop New Services

```bash
cd /opt/data/trading_light_pilot/trader

# Keep LightRAG, stop graph-related
docker compose stop neo4j

# Verify LightRAG is running
docker compose ps lightrag
```

#### Step 2: Revert Code Changes

```bash
# Find last known good commit before migration
git log --oneline --all | grep -i "before knowledge base" || git log --oneline -20

# Create rollback branch
git checkout -b rollback/pre-knowledge-base <commit-hash>

# Or selectively revert
git revert --no-commit <migration-commits>
```

#### Step 3: Restore Database State

```bash
# Restore LightRAG's PostgreSQL tables only
docker exec -i nexus-postgres psql -U lightrag -d lightrag << 'EOF'
-- Drop new schemas
DROP SCHEMA IF EXISTS graph CASCADE;
DROP SCHEMA IF EXISTS rag CASCADE;

-- Keep LightRAG's native tables
-- (lightrag_* tables remain untouched)
EOF
```

#### Step 4: Update Configuration

```bash
# trader/.env
# Comment out new services
# NEO4J_PASS=...
# GRAPH_ENABLED=true

# Ensure LightRAG settings active
LIGHTRAG_LLM_MODEL=qwen3:8b
LIGHTRAG_EMBED_MODEL=nomic-embed-text
```

#### Step 5: Verify Rollback

```bash
# Test LightRAG query
curl -X POST http://localhost:9621/query \
    -H "Content-Type: application/json" \
    -d '{"query": "NVDA earnings thesis", "mode": "hybrid"}'

# Check LightRAG health
curl http://localhost:9621/health
```

## Rollback Verification Checklist

- [ ] LightRAG API responds to queries
- [ ] Skills can retrieve context (test with earnings-analysis)
- [ ] No errors in `docker compose logs lightrag`
- [ ] Previous analyses accessible
- [ ] New documents can be indexed

## Data Preservation During Rollback

### Export Graph Data Before Rollback

```bash
# Export Neo4j data for potential re-migration
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" \
    "CALL apoc.export.json.all('/data/backup/graph_export.json', {})"

docker cp nexus-neo4j:/data/backup/graph_export.json \
    /opt/data/trading_light_pilot/backups/rollback/
```

### Export Vector Embeddings

```sql
-- Export embeddings for re-use
COPY (
    SELECT doc_id, section_path, content, embedding::text
    FROM rag.chunks
) TO '/tmp/embeddings_export.csv' WITH CSV HEADER;
```

## Rollback Communication Template

```
Subject: Trading Knowledge Base Rollback - [DATE]

Status: Rolling back to LightRAG-only system

Reason: [Brief description]

Impact:
- Graph-based context temporarily unavailable
- Hybrid search reverted to LightRAG
- New entity extraction paused

Timeline:
- Rollback started: [TIME]
- Expected completion: [TIME]
- Post-rollback verification: [TIME]

Action Required:
- None for end users
- Skills will continue functioning with LightRAG backend

Next Steps:
- Investigate root cause
- Plan re-migration with fixes
```

## Re-Migration After Rollback

Once issues are resolved:

1. Review and fix root cause
2. Test fixes in isolation
3. Plan re-migration window
4. Follow original IPLAN-001 phases
5. Verify all metrics before full cutover

### Re-Migration Checklist

- [ ] Root cause documented and fixed
- [ ] Tests pass (unit + integration)
- [ ] Graph exports re-imported successfully
- [ ] Vector embeddings re-indexed
- [ ] Skills verified with hybrid context
- [ ] Monitoring alerts configured
- [ ] Stakeholders notified
