# Migration Testing Checklist

## Overview

Comprehensive testing checklist for Trading Knowledge Base migration validation.

## Pre-Migration Tests

### Infrastructure Readiness

- [ ] Docker services start without errors
  ```bash
  cd /opt/data/trading_light_pilot/trader
  docker compose up -d
  docker compose ps  # All services healthy
  ```

- [ ] Neo4j accessible on ports 7475 (HTTP) and 7688 (Bolt)
  ```bash
  curl -f http://localhost:7475 && echo "Neo4j HTTP OK"
  nc -z localhost 7688 && echo "Neo4j Bolt OK"
  ```

- [ ] PostgreSQL accessible on port 5433
  ```bash
  docker exec nexus-postgres pg_isready -U lightrag
  ```

- [ ] Ollama running and models available
  ```bash
  curl http://localhost:11434/api/tags | jq '.models[].name'
  ```

### Schema Validation

- [ ] PostgreSQL schemas created
  ```sql
  SELECT schema_name FROM information_schema.schemata
  WHERE schema_name IN ('rag', 'graph');
  ```

- [ ] Required tables exist
  ```sql
  SELECT table_schema, table_name
  FROM information_schema.tables
  WHERE table_schema IN ('rag', 'graph')
  ORDER BY table_schema, table_name;
  ```

- [ ] Neo4j constraints applied
  ```cypher
  SHOW CONSTRAINTS;
  ```

## Unit Tests

### Graph Layer

- [ ] `test_layer.py` passes
  ```bash
  pytest trader/graph/tests/test_layer.py -v
  ```

- [ ] `test_extract.py` passes
  ```bash
  pytest trader/graph/tests/test_extract.py -v
  ```

- [ ] `test_normalize.py` passes
  ```bash
  pytest trader/graph/tests/test_normalize.py -v
  ```

- [ ] `test_query.py` passes
  ```bash
  pytest trader/graph/tests/test_query.py -v
  ```

### RAG Layer

- [ ] `test_chunk.py` passes
  ```bash
  pytest trader/rag/tests/test_chunk.py -v
  ```

- [ ] `test_embedding.py` passes
  ```bash
  pytest trader/rag/tests/test_embedding.py -v
  ```

- [ ] `test_embed.py` passes
  ```bash
  pytest trader/rag/tests/test_embed.py -v
  ```

- [ ] `test_search.py` passes
  ```bash
  pytest trader/rag/tests/test_search.py -v
  ```

- [ ] `test_hybrid.py` passes
  ```bash
  pytest trader/rag/tests/test_hybrid.py -v
  ```

### Full Suite

- [ ] All unit tests pass
  ```bash
  pytest trader/ -v --ignore=trader/graph/tests/test_integration.py --ignore=trader/rag/tests/test_integration.py
  ```

## Integration Tests

### Graph Integration

- [ ] Neo4j connection test
  ```python
  from graph.layer import TradingGraph
  with TradingGraph() as g:
      assert g.health_check()
  ```

- [ ] Node creation round-trip
  ```python
  with TradingGraph() as g:
      g.merge_node("Ticker", {"symbol": "TEST"})
      result = g.run_cypher("MATCH (t:Ticker {symbol: 'TEST'}) RETURN t")
      assert len(result) == 1
      g.run_cypher("MATCH (t:Ticker {symbol: 'TEST'}) DELETE t")
  ```

- [ ] Relationship creation
  ```python
  with TradingGraph() as g:
      g.merge_node("Ticker", {"symbol": "A"})
      g.merge_node("Ticker", {"symbol": "B"})
      g.merge_relation(
          "Ticker", {"symbol": "A"},
          "COMPETES_WITH",
          "Ticker", {"symbol": "B"},
          {}
      )
  ```

### RAG Integration

- [ ] Embedding generation
  ```python
  from rag.embedding import EmbeddingClient
  client = EmbeddingClient()
  embedding = client.embed("Test query")
  assert len(embedding) == 768
  ```

- [ ] Document embedding round-trip
  ```python
  from rag.embed import embed_document
  chunks = embed_document("/path/to/test.yaml")
  assert len(chunks) > 0
  ```

- [ ] Semantic search
  ```python
  from rag.search import semantic_search
  results = semantic_search("NVDA earnings", top_k=3)
  # Results may be empty if no docs indexed yet
  ```

### Hybrid Context

- [ ] Combined context retrieval
  ```python
  from rag.hybrid import get_hybrid_context
  ctx = get_hybrid_context("NVDA", "earnings thesis")
  assert ctx.ticker == "NVDA"
  assert ctx.formatted != ""
  ```

## End-to-End Tests

### CLI Commands

- [ ] `graph index` works
  ```bash
  python orchestrator.py graph index /path/to/test.yaml
  ```

- [ ] `graph query` works
  ```bash
  python orchestrator.py graph query "MATCH (t:Ticker) RETURN t.symbol LIMIT 5"
  ```

- [ ] `graph stats` works
  ```bash
  python orchestrator.py graph stats
  ```

- [ ] `rag embed` works
  ```bash
  python orchestrator.py rag embed /path/to/test.yaml
  ```

- [ ] `rag search` works
  ```bash
  python orchestrator.py rag search "earnings thesis" --ticker NVDA
  ```

- [ ] `rag stats` works
  ```bash
  python orchestrator.py rag stats
  ```

### Skill Integration

- [ ] earnings-analysis retrieves context
  ```
  # Invoke skill, verify context section appears
  ```

- [ ] stock-analysis retrieves context
  ```
  # Invoke skill, verify context section appears
  ```

- [ ] trade-journal saves and can be retrieved
  ```
  # Log trade, then search for it
  ```

## Data Migration Tests

### Document Indexing

- [ ] Index sample earnings analysis
  ```bash
  python orchestrator.py rag embed trading/knowledge/analysis/earnings/NVDA_*.yaml
  python orchestrator.py graph index trading/knowledge/analysis/earnings/NVDA_*.yaml
  ```

- [ ] Index sample trade journal
  ```bash
  python orchestrator.py rag embed trading/knowledge/trades/*.yaml
  python orchestrator.py graph index trading/knowledge/trades/*.yaml
  ```

- [ ] Verify chunks created
  ```sql
  SELECT doc_id, COUNT(*) as chunks
  FROM rag.chunks
  GROUP BY doc_id;
  ```

- [ ] Verify entities extracted
  ```cypher
  MATCH (n) RETURN labels(n) as label, COUNT(*) as count;
  ```

### Search Quality

- [ ] Top result relevance
  ```python
  results = semantic_search("NVDA data center revenue", ticker="NVDA", top_k=1)
  assert results[0].similarity > 0.7
  ```

- [ ] Section filtering works
  ```python
  results = semantic_search("thesis", ticker="NVDA", section="thesis")
  assert all("thesis" in r.section_label.lower() for r in results)
  ```

## Performance Tests

### Latency

- [ ] Search latency < 500ms
  ```python
  import time
  start = time.time()
  results = semantic_search("test query", top_k=5)
  latency = (time.time() - start) * 1000
  assert latency < 500, f"Search latency {latency}ms exceeds 500ms"
  ```

- [ ] Embedding latency < 2s
  ```python
  import time
  from rag.embedding import EmbeddingClient
  client = EmbeddingClient()
  start = time.time()
  embedding = client.embed("Test document content " * 100)
  latency = (time.time() - start) * 1000
  assert latency < 2000, f"Embedding latency {latency}ms exceeds 2000ms"
  ```

### Throughput

- [ ] Batch embedding > 10 docs/minute
  ```bash
  time python orchestrator.py rag embed trading/knowledge/analysis/earnings/*.yaml
  ```

## Rollback Tests

- [ ] Rollback procedure documented
- [ ] Rollback tested in non-production
- [ ] Recovery time < 15 minutes

## Sign-Off

| Test Category | Passed | Tester | Date |
|---------------|--------|--------|------|
| Infrastructure | [ ] | | |
| Unit Tests | [ ] | | |
| Integration Tests | [ ] | | |
| End-to-End Tests | [ ] | | |
| Data Migration | [ ] | | |
| Performance | [ ] | | |
| Rollback | [ ] | | |

**Final Approval:** _______________  Date: _______________
