# API Reference

Python API documentation for TradegentSwarm modules.

---

## RAG Module

### embed.py

```python
from rag.embed import embed_document, EmbedResult

result = embed_document(file_path: str) -> EmbedResult
```

**Parameters:**
- `file_path`: Path to YAML document

**Returns:** `EmbedResult`

| Attribute | Type | Description |
|-----------|------|-------------|
| `doc_id` | str | Document identifier |
| `file_path` | str | Source file path |
| `doc_type` | str | Document type |
| `ticker` | str | Associated ticker |
| `chunk_count` | int | Chunks created |
| `embed_model` | str | Model used |
| `error_message` | str | Error or "unchanged" |

### search.py

```python
from rag.search import semantic_search, hybrid_search, get_rag_stats

# Semantic search
results = semantic_search(
    query: str,
    ticker: str = None,
    top_k: int = 5,
    min_similarity: float = 0.5
) -> List[SearchResult]

# Hybrid search (vector + BM25)
results = hybrid_search(
    query: str,
    ticker: str = None,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> List[SearchResult]

# Statistics
stats = get_rag_stats() -> RAGStats
```

**SearchResult:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `doc_id` | str | Document ID |
| `content` | str | Chunk text |
| `score` | float | Similarity score |
| `ticker` | str | Ticker symbol |
| `section_label` | str | Section path |

**RAGStats:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `document_count` | int | Total documents |
| `chunk_count` | int | Total chunks |
| `tickers` | List[str] | Indexed tickers |
| `doc_types` | Dict[str, int] | Type counts |
| `last_embed` | datetime | Last embedding |

### rerank.py

```python
from rag.rerank import rerank_results

reranked = rerank_results(
    query: str,
    results: List[SearchResult],
    top_k: int = 5
) -> List[SearchResult]
```

### query_classifier.py

```python
from rag.query_classifier import classify_query, QueryType

analysis = classify_query(query: str) -> QueryAnalysis
```

**QueryType:**

| Type | Pattern | Strategy |
|------|---------|----------|
| RETRIEVAL | Standard query | vector |
| RELATIONSHIP | "related to" | graph |
| TREND | "recent", "last week" | vector + time |
| COMPARISON | "vs", "compare" | multi-ticker |
| GLOBAL | No ticker | hybrid |

---

## Graph Module

### layer.py

```python
from graph.layer import TradingGraph

with TradingGraph() as graph:
    # Health check
    healthy = graph.health_check() -> bool

    # Statistics
    stats = graph.get_stats() -> GraphStats

    # Ticker context
    ctx = graph.get_ticker_context(ticker: str) -> Dict

    # Sector peers
    peers = graph.get_sector_peers(ticker: str) -> List[Dict]

    # Competitors
    competitors = graph.get_competitors(ticker: str) -> List[Dict]

    # Risks
    risks = graph.get_risks(ticker: str) -> List[Dict]

    # Bias history
    biases = graph.get_bias_history(bias_name: str = None) -> List[Dict]

    # Related entities
    related = graph.find_related(ticker: str, depth: int = 2) -> List[Dict]

    # Custom Cypher
    results = graph.run_cypher(
        query: str,
        params: Dict = None,
        allow_writes: bool = False
    ) -> List[Dict]
```

**GraphStats:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `node_counts` | Dict[str, int] | Counts by label |
| `edge_counts` | Dict[str, int] | Counts by type |

### extract.py

```python
from graph.extract import extract_document, ExtractionResult

result = extract_document(
    file_path: str,
    extractor: str = "openai",
    commit: bool = True
) -> ExtractionResult
```

**ExtractionResult:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `entities` | List[EntityExtraction] | Extracted entities |
| `relations` | List[RelationExtraction] | Extracted relations |
| `source_doc_id` | str | Document ID |
| `source_doc_type` | str | Document type |
| `fields_processed` | List[str] | Fields extracted |
| `fields_failed` | List[str] | Failed fields |
| `committed` | bool | Stored in Neo4j |
| `extractor` | str | Provider used |

**EntityExtraction:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `type` | str | Entity type |
| `value` | str | Entity value |
| `confidence` | float | 0.0 - 1.0 |
| `evidence` | str | Source text |
| `needs_review` | bool | Low confidence flag |

---

## Orchestrator

### db_layer.py

```python
from db_layer import NexusDB

with NexusDB() as db:
    # Settings
    value = db.get_setting(key: str) -> str
    db.set_setting(key: str, value: str)

    # Stocks
    stocks = db.get_stocks(enabled_only: bool = False) -> List[Dict]
    db.add_stock(ticker: str, **kwargs)
    db.update_stock(ticker: str, **kwargs)
    db.set_stock_state(ticker: str, state: str)

    # Run history
    db.log_run(ticker: str, run_type: str, status: str, **kwargs)
    runs = db.get_runs(ticker: str = None, limit: int = 10) -> List[Dict]
```

---

## MCP Tools

### RAG MCP (trading-rag)

| Tool | Parameters | Returns |
|------|------------|---------|
| `rag_embed` | file_path | EmbedResult |
| `rag_embed_text` | text, doc_id, ticker | EmbedResult |
| `rag_search` | query, ticker, top_k | List[SearchResult] |
| `rag_search_rerank` | query, ticker, top_k, retrieval_k | List[SearchResult] |
| `rag_search_expanded` | query, top_k, n_expansions | List[SearchResult] |
| `rag_classify_query` | query | QueryAnalysis |
| `rag_expand_query` | query, n_expansions | List[str] |
| `rag_hybrid_context` | ticker, query | HybridContext |
| `rag_similar` | ticker, top_k | List[SearchResult] |
| `rag_status` | — | RAGStats |
| `rag_evaluate` | query, contexts, answer | RAGASMetrics |
| `rag_metrics_summary` | days | MetricsSummary |

### Graph MCP (trading-graph)

| Tool | Parameters | Returns |
|------|------------|---------|
| `graph_extract` | file_path | ExtractionResult |
| `graph_extract_text` | text, doc_id | ExtractionResult |
| `graph_search` | ticker, depth | List[Entity] |
| `graph_peers` | ticker | List[Peer] |
| `graph_risks` | ticker | List[Risk] |
| `graph_biases` | bias_name | List[BiasRecord] |
| `graph_context` | ticker | TickerContext |
| `graph_query` | cypher, params | List[Dict] |
| `graph_status` | — | GraphStats |

### IB MCP (ib-mcp)

| Tool | Parameters | Returns |
|------|------------|---------|
| `get_stock_price` | symbol | Quote |
| `get_quotes_batch` | symbols | List[Quote] |
| `get_historical_data` | symbol, duration, bar_size | List[Bar] |
| `get_option_chain` | symbol | OptionChain |
| `get_positions` | — | List[Position] |
| `get_portfolio` | — | Portfolio |
| `get_account_summary` | — | AccountSummary |
| `place_order` | symbol, action, quantity, order_type | OrderId |
| `run_scanner` | scan_code, max_results | List[ScanResult] |
| `health_check` | — | HealthStatus |

---

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `PG_HOST` | PostgreSQL host |
| `PG_PORT` | PostgreSQL port |
| `PG_USER` | Database user |
| `PG_PASS` | Database password |
| `PG_DB` | Database name |
| `NEO4J_URI` | Neo4j bolt URI |
| `NEO4J_USER` | Neo4j user |
| `NEO4J_PASS` | Neo4j password |
| `OPENAI_API_KEY` | OpenAI API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_PROVIDER` | openai | Embedding provider |
| `EXTRACT_PROVIDER` | openai | Extraction provider |
| `CHUNK_MAX_TOKENS` | 768 | Max chunk size |
| `CHUNK_OVERLAP` | 150 | Overlap tokens |

---

## Related Documentation

- [RAG System](../architecture/rag-system.md)
- [Graph System](../architecture/graph-system.md)
- [MCP Servers](../architecture/mcp-servers.md)
