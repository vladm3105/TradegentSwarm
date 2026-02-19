# Trading Knowledge Base Monitoring

## Overview

Metrics for graph extraction, embedding pipeline, and hybrid search operations.

## Extraction Metrics

### Success Rate

Track via JSONL logs in `trader/logs/`:

```bash
# Count successful extractions (last 24h)
grep '"status": "success"' logs/extract_*.jsonl | wc -l

# Count failures
grep '"status": "error"' logs/extract_*.jsonl | wc -l

# Success rate calculation
success=$(grep -c '"status": "success"' logs/extract_*.jsonl 2>/dev/null || echo 0)
total=$(wc -l < logs/extract_*.jsonl 2>/dev/null || echo 1)
echo "Scale: $((success * 100 / total))%"
```

### Confidence Distribution

```sql
-- PostgreSQL: Check confidence levels for pending commits
SELECT
    confidence_bucket,
    COUNT(*) as count
FROM (
    SELECT
        CASE
            WHEN confidence >= 0.7 THEN 'auto_commit'
            WHEN confidence >= 0.5 THEN 'flagged'
            ELSE 'skipped'
        END as confidence_bucket
    FROM graph.pending_commits
    WHERE created_at > NOW() - INTERVAL '7 days'
) sub
GROUP BY confidence_bucket;
```

### Entity Extraction Stats

```python
from graph.layer import TradingGraph

with TradingGraph() as graph:
    stats = graph.get_stats()
    print(f"Total nodes: {stats['node_count']}")
    print(f"Total relationships: {stats['relationship_count']}")
    print(f"Labels: {stats['labels']}")
```

## Embedding Pipeline Metrics

### Embedding Throughput

```sql
-- Chunks embedded per hour
SELECT
    DATE_TRUNC('hour', embedded_at) as hour,
    COUNT(*) as chunks_embedded
FROM rag.chunks
WHERE embedded_at > NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', embedded_at)
ORDER BY hour DESC;
```

### Token Usage

```sql
-- Average tokens per chunk by doc type
SELECT
    doc_type,
    AVG(content_tokens) as avg_tokens,
    MAX(content_tokens) as max_tokens,
    COUNT(*) as chunk_count
FROM rag.chunks
GROUP BY doc_type;
```

### Embedding Model Status

```python
from rag.embedding import EmbeddingClient

client = EmbeddingClient()
status = client.health_check()
print(f"Primary (Ollama): {status.get('ollama', 'unavailable')}")
print(f"Fallback chain: {client.fallback_chain}")
```

## Search Performance

### Query Latency

```python
import time
from rag.search import semantic_search

start = time.time()
results = semantic_search("NVDA earnings thesis", top_k=5)
latency_ms = (time.time() - start) * 1000
print(f"Search latency: {latency_ms:.1f}ms")
print(f"Results returned: {len(results)}")
```

### Similarity Score Distribution

```sql
-- Check similarity scores from recent searches (if logged)
SELECT
    AVG(similarity) as avg_similarity,
    MIN(similarity) as min_similarity,
    MAX(similarity) as max_similarity
FROM rag.search_log
WHERE searched_at > NOW() - INTERVAL '24 hours';
```

## Pending Commits Queue

### Queue Depth

```sql
-- Pending commits awaiting review
SELECT
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM graph.pending_commits
GROUP BY status;
```

### Retry Status

```sql
-- Failed commits with retry counts
SELECT
    doc_id,
    entity_type,
    retry_count,
    last_error,
    created_at
FROM graph.pending_commits
WHERE status = 'failed'
ORDER BY retry_count DESC
LIMIT 10;
```

## Health Checks

### Service Health

```bash
# Check all services
cd /opt/data/trading_light_pilot/trader
python -c "
from graph.layer import TradingGraph
from rag.embedding import EmbeddingClient
import psycopg

# Neo4j
with TradingGraph() as g:
    print(f'Neo4j: {\"OK\" if g.health_check() else \"FAIL\"}')

# Embedding
client = EmbeddingClient()
print(f'Embedding: {\"OK\" if client.health_check() else \"FAIL\"}')

# PostgreSQL
try:
    import os
    conn_str = os.getenv('DATABASE_URL', 'postgresql://lightrag:lightrag@localhost:5433/lightrag')
    with psycopg.connect(conn_str) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            print('PostgreSQL: OK')
except Exception as e:
    print(f'PostgreSQL: FAIL ({e})')
"
```

### Docker Health

```bash
cd /opt/data/trading_light_pilot/trader
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"
```

## Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Extraction success rate | < 90% | < 80% |
| Pending queue depth | > 50 | > 100 |
| Average confidence | < 0.6 | < 0.5 |
| Search latency (p95) | > 500ms | > 1000ms |
| Embedding failures | > 5/hour | > 20/hour |

## Log Locations

| Component | Log Path | Format |
|-----------|----------|--------|
| Extraction | `logs/extract_YYYYMMDD.jsonl` | JSONL |
| Embedding | `logs/embed_YYYYMMDD.jsonl` | JSONL |
| MCP Servers | `logs/mcp_graph.log`, `logs/mcp_rag.log` | Text |
| Docker | `docker compose logs <service>` | Text |
