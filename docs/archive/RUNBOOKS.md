# Operational Runbooks

Step-by-step procedures for common operational tasks in the Tradegent platform.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Service Health Recovery](#service-health-recovery)
3. [Disaster Recovery](#disaster-recovery)
4. [Knowledge Base Operations](#knowledge-base-operations)
5. [Performance Troubleshooting](#performance-troubleshooting)

---

## Daily Operations

### Morning Checklist (Pre-Market)

```bash
# 1. Verify all services running
docker compose ps

# Expected output:
# nexus-postgres    running  0.0.0.0:5433->5432/tcp
# nexus-neo4j       running  0.0.0.0:7474->7474/tcp, 0.0.0.0:7688->7687/tcp
# nexus-ib-gateway  running  0.0.0.0:4001-4002->4001-4002/tcp

# 2. Check IB Gateway connection
curl -s http://localhost:8100/health | jq .

# Expected: {"status": "healthy", "gateway_connected": true}

# 3. Verify RAG status
python -c "
from tradegent.rag.search import TradingRAGSearch
r = TradingRAGSearch()
print(r.get_stats())
"

# 4. Verify Graph status
python -c "
from tradegent.graph.layer import TradingGraph
with TradingGraph() as g:
    print(g.get_stats())
"
```

### End-of-Day Checklist

```bash
# 1. Check for failed analyses
grep -l "error" tradegent/logs/*.jsonl | tail -5

# 2. Verify day's analyses indexed
python -c "
from datetime import date
from tradegent.rag.search import TradingRAGSearch
r = TradingRAGSearch()
today = date.today().isoformat()
results = r.search(f'analysis {today}', top_k=10)
print(f'Today analyses: {len(results)}')
"

# 3. Run backup
./tradegent/scripts/backup.sh
```

---

## Service Health Recovery

### PostgreSQL Recovery

**Symptoms:** Connection refused, timeout errors, "database unavailable"

```bash
# Step 1: Check container status
docker compose ps postgres

# Step 2: Check logs
docker compose logs --tail=50 postgres

# Step 3: If container stopped, restart
docker compose restart postgres

# Step 4: Verify connection
docker exec nexus-postgres pg_isready -U lightrag

# Step 5: If corruption suspected, restore from backup
docker compose stop postgres
docker run --rm \
    -v trading_light_pilot_pg_data:/data \
    alpine rm -rf /data/*

docker exec -i nexus-postgres pg_restore -U lightrag -d lightrag \
    < /opt/data/tradegent_swarm/backups/postgres/lightrag_LATEST.dump

docker compose start postgres
```

### Neo4j Recovery

**Symptoms:** Connection refused, Cypher query errors, "graph unavailable"

```bash
# Step 1: Check container status
docker compose ps neo4j

# Step 2: Check logs
docker compose logs --tail=50 neo4j

# Step 3: Verify connectivity
curl -s http://localhost:7474/db/neo4j/tx/commit \
    -H "Content-Type: application/json" \
    -d '{"statements":[{"statement":"RETURN 1"}]}'

# Step 4: If unresponsive, restart
docker compose restart neo4j

# Step 5: If data corruption, restore from backup
docker compose stop neo4j
docker run --rm \
    -v trading_light_pilot_neo4j_data:/data \
    alpine rm -rf /data/*

docker run --rm \
    -v trading_light_pilot_neo4j_data:/data \
    -v /opt/data/tradegent_swarm/backups/neo4j:/backup \
    neo4j:5-community neo4j-admin database load neo4j --from-path=/backup/neo4j_LATEST.dump

docker compose start neo4j
```

### IB Gateway Recovery

**Symptoms:** Market data unavailable, order placement failing

```bash
# Step 1: Check container status
docker compose ps ib-gateway

# Step 2: Check health endpoint
curl -s http://localhost:8100/health

# Step 3: If disconnected, restart
docker compose restart ib-gateway

# Step 4: If 2FA required, connect via VNC
vncviewer localhost:5900
# Password: nexus123 (from VNC_PASS in .env)

# Step 5: Verify connection
curl -s http://localhost:8100/health | jq .gateway_connected
```

---

## Disaster Recovery

### Full System Recovery

**Scenario:** Complete data loss, starting from scratch

```bash
# Step 1: Clone repositories
git clone git@github.com:vladm3105/TradegentSwarm.git /opt/data/tradegent_swarm
cd /opt/data/tradegent_swarm
git clone git@github.com:vladm3105/tradegent-knowledge.git tradegent_knowledge

# Step 2: Start infrastructure
cd tradegent
docker compose up -d postgres neo4j

# Step 3: Initialize database schemas
docker exec -i nexus-postgres psql -U lightrag < db/init.sql

# Step 4: Apply migrations
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" \
    < graph/migrations/neo4j_schema.cypher

# Step 5: Re-index all knowledge documents
cd /opt/data/tradegent_swarm
python scripts/index_knowledge_base.py --force

# Step 6: Verify recovery
python -c "
from tradegent.rag.search import TradingRAGSearch
from tradegent.graph.layer import TradingGraph
r = TradingRAGSearch()
print('RAG:', r.get_stats())
with TradingGraph() as g:
    print('Graph:', g.get_stats())
"
```

### RAG-Only Recovery

**Scenario:** PostgreSQL data lost, need to rebuild RAG index

```bash
# Step 1: Clear RAG tables
docker exec nexus-postgres psql -U lightrag -c "
    TRUNCATE nexus.rag_documents, nexus.rag_chunks CASCADE;
"

# Step 2: Re-index all documents
python scripts/index_knowledge_base.py --rag-only --force

# Step 3: Verify
python -c "
from tradegent.rag.search import TradingRAGSearch
r = TradingRAGSearch()
print(r.get_stats())
"
```

### Graph-Only Recovery

**Scenario:** Neo4j data lost, need to rebuild graph

```bash
# Step 1: Clear all nodes
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" \
    "MATCH (n) DETACH DELETE n"

# Step 2: Re-apply schema
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" \
    < tradegent/graph/migrations/neo4j_schema.cypher

# Step 3: Re-extract all documents
python scripts/index_knowledge_base.py --graph-only --force

# Step 4: Verify
python -c "
from tradegent.graph.layer import TradingGraph
with TradingGraph() as g:
    print(g.get_stats())
"
```

---

## Knowledge Base Operations

### Index Single Document

```bash
# Index specific file to RAG + Graph
python -c "
from tradegent.rag.embed import embed_document
from tradegent.graph.extract import extract_document

file_path = 'tradegent_knowledge/knowledge/analysis/stock/NVDA_20260221T1145.yaml'

# RAG embedding
result = embed_document(file_path, force=True)
print(f'RAG: {result.chunk_count} chunks')

# Graph extraction
result = extract_document(file_path)
print(f'Graph: {len(result.entities)} entities')
"
```

### Search for Similar Analyses

```bash
python -c "
from tradegent.rag.search import TradingRAGSearch

r = TradingRAGSearch()
results = r.search('NVDA earnings data center growth', ticker='NVDA', top_k=5)

for res in results:
    print(f'{res[\"doc_id\"]}: {res[\"similarity\"]:.2f}')
"
```

### Get Ticker Context from Graph

```bash
python -c "
from tradegent.graph.layer import TradingGraph

with TradingGraph() as g:
    context = g.get_ticker_context('NVDA')
    print('Peers:', context.get('peers', []))
    print('Risks:', context.get('risks', []))
    print('Strategies:', context.get('strategies', []))
"
```

### Delete Document from Index

```bash
python -c "
from tradegent.rag.embed import delete_document

doc_id = 'NVDA_20260221T1145'
result = delete_document(doc_id)
print(f'Deleted: {result}')
"
```

---

## Performance Troubleshooting

### Slow RAG Searches

```bash
# Step 1: Check index statistics
docker exec nexus-postgres psql -U lightrag -c "
    SELECT relname, n_live_tup, pg_size_pretty(pg_relation_size(relid))
    FROM pg_stat_user_tables
    WHERE schemaname = 'nexus'
    ORDER BY n_live_tup DESC;
"

# Step 2: Check query plan
docker exec nexus-postgres psql -U lightrag -c "
    EXPLAIN ANALYZE
    SELECT * FROM nexus.rag_chunks
    ORDER BY embedding <-> '[0.1, 0.2, ...]'::vector
    LIMIT 10;
"

# Step 3: Rebuild HNSW index if needed
docker exec nexus-postgres psql -U lightrag -c "
    REINDEX INDEX CONCURRENTLY nexus.idx_rag_chunks_embedding;
"
```

### Slow Graph Queries

```bash
# Step 1: Check node counts
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" "
    MATCH (n) RETURN labels(n) AS label, count(*) AS count
    ORDER BY count DESC;
"

# Step 2: Check index usage
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" "
    SHOW INDEXES;
"

# Step 3: Profile slow query
docker exec nexus-neo4j cypher-shell -u neo4j -p "${NEO4J_PASS}" "
    PROFILE MATCH (t:Ticker {symbol: 'NVDA'})-[r]->(n)
    RETURN type(r), n LIMIT 100;
"
```

### High Memory Usage

```bash
# Step 1: Check container memory
docker stats --no-stream

# Step 2: Adjust PostgreSQL memory (in docker-compose.yml)
# services:
#   postgres:
#     command: postgres -c shared_buffers=512MB -c work_mem=64MB

# Step 3: Adjust Neo4j memory
# services:
#   neo4j:
#     environment:
#       - NEO4J_server_memory_heap_initial__size=512m
#       - NEO4J_server_memory_heap_max__size=1g
```

---

## Quick Reference

### Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| PostgreSQL | 5433 | TCP |
| Neo4j HTTP | 7474 | HTTP |
| Neo4j Bolt | 7688 | TCP |
| IB Gateway | 4002 | TCP (paper) |
| IB MCP Server | 8100 | SSE |

### Key Commands

| Task | Command |
|------|---------|
| Start services | `docker compose up -d` |
| Stop services | `docker compose down` |
| View logs | `docker compose logs -f [service]` |
| Run backup | `./tradegent/scripts/backup.sh` |
| Index documents | `python scripts/index_knowledge_base.py` |
| Check health | `docker compose ps` |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `PG_USER`, `PG_PASS` | PostgreSQL credentials |
| `NEO4J_USER`, `NEO4J_PASS` | Neo4j credentials |
| `EMBED_PROVIDER` | RAG embedding provider |
| `EXTRACT_PROVIDER` | Graph extraction provider |
| `OPENAI_API_KEY` | OpenAI API key |
