# RAG System Architecture

The RAG (Retrieval-Augmented Generation) system provides semantic search over trading knowledge using PostgreSQL with pgvector.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline v2.0                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Document Input                                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────┐    ┌──────────────┐    ┌──────────┐    ┌───────────┐          │
│  │  Parse  │───▶│    Chunk     │───▶│  Embed   │───▶│   Store   │          │
│  │  YAML   │    │ (768 tokens) │    │ (OpenAI) │    │ (pgvector)│          │
│  └─────────┘    └──────────────┘    └──────────┘    └───────────┘          │
│                                                                             │
│  Query Input                                                                │
│       │                                                                     │
│       ▼                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────┐                      │
│  │ Classify │───▶│   Expand     │───▶│    Route     │                      │
│  │  Query   │    │   Query      │    │  (adaptive)  │                      │
│  └──────────┘    └──────────────┘    └──────────────┘                      │
│            │              │               │                                 │
│            └──────────────┴───────────────┘                                 │
│                           │                                                 │
│                           ▼                                                 │
│                    ┌──────────────┐    ┌──────────────┐                     │
│                    │   Rerank     │───▶│   Return     │                     │
│                    │ (CrossEnc)   │    │   Context    │                     │
│                    └──────────────┘    └──────────────┘                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### Core Modules

| Module | Purpose |
|--------|---------|
| `embed.py` | Document embedding pipeline |
| `search.py` | Semantic, hybrid, reranked search |
| `chunk.py` | Text chunking (768 tokens, 150 overlap) |
| `embedding_client.py` | OpenAI/Ollama embedding client |
| `mcp_server.py` | MCP server (12 tools) |

### v2.0 Modules

| Module | Purpose |
|--------|---------|
| `rerank.py` | Cross-encoder reranking |
| `query_classifier.py` | Query type classification |
| `query_expander.py` | LLM-based query expansion |
| `hybrid.py` | Combined vector + graph context |
| `evaluation.py` | RAGAS evaluation framework |

---

## Embedding Pipeline

### Document Processing

```python
from rag.embed import embed_document

result = embed_document("path/to/analysis.yaml")
# Returns: EmbedResult(doc_id, chunk_count, status)
```

**Steps:**
1. Parse YAML document
2. Flatten to text representation
3. Chunk into segments (768 tokens, 150 overlap)
4. Generate embeddings (OpenAI text-embedding-3-large)
5. Store in PostgreSQL with pgvector

### Embedding Configuration

| Setting | Value | Notes |
|---------|-------|-------|
| Provider | OpenAI | `EMBED_PROVIDER=openai` |
| Model | text-embedding-3-large | 1536 dimensions |
| Chunk size | 768 tokens | Research-backed optimal |
| Overlap | 150 tokens | Context preservation |
| Cost | ~$0.13/1M tokens | ~$2/year for 7,500 docs |

### Dimension Consistency

**Critical:** Once you embed documents with a provider, stay consistent.

| Provider | Dimensions | Switching |
|----------|------------|-----------|
| OpenAI | 1536 | Re-embed all documents |
| Ollama (nomic) | 768 | Re-embed all documents |

---

## Search Types

### Semantic Search

Basic vector similarity search.

```python
from rag.search import semantic_search

results = semantic_search(
    query="NVDA earnings catalyst",
    ticker="NVDA",
    top_k=5,
)
```

### Hybrid Search

Combined BM25 + vector search using Reciprocal Rank Fusion.

```python
from rag.search import hybrid_search

results = hybrid_search(
    query="earnings volatility",
    ticker="NVDA",
    vector_weight=0.7,
    bm25_weight=0.3,
)
```

### Reranked Search (v2.0)

Two-stage retrieve-then-rerank for higher relevance.

```python
from rag.search import search_with_rerank

results = search_with_rerank(
    query="competitive position",
    ticker="NVDA",
    top_k=5,           # Final results
    retrieval_k=50,    # Initial pool
)
```

### Expanded Search (v2.0)

LLM-generated query variations for better recall.

```python
from rag.search import search_with_expansion

results = search_with_expansion(
    query="AI chip demand",
    top_k=5,
    n_expansions=3,
)
# Searches: original + 3 semantic variations
```

---

## Query Classification (v2.0)

Automatic query routing based on query type.

```python
from rag.query_classifier import classify_query

analysis = classify_query("Compare NVDA vs AMD earnings")
# Returns: QueryType.COMPARISON, strategy="vector", tickers=["NVDA", "AMD"]
```

### Query Types

| Type | Pattern | Strategy |
|------|---------|----------|
| RETRIEVAL | Standard fact-seeking | vector |
| RELATIONSHIP | "related to", "connected" | graph |
| TREND | "recent", "last week" | vector + time filter |
| COMPARISON | "vs", "compare" | multi-ticker vector |
| GLOBAL | Broad, no ticker | hybrid |

---

## Adaptive Retrieval (v2.0)

`rag_hybrid_context` uses classification for optimal routing.

```python
from rag.hybrid import get_hybrid_context_adaptive

context = get_hybrid_context_adaptive(
    ticker="NVDA",
    query="How does NVDA relate to AMD?",
)
# Uses graph-first for RELATIONSHIP queries
```

**Routing Logic:**
- **RELATIONSHIP** → Graph peers + vector search
- **COMPARISON** → Multi-ticker vector search
- **TREND** → Time-filtered vector search
- **Default** → Reranked hybrid search

---

## MCP Tools

The RAG MCP server exposes 12 tools:

### Core Tools

| Tool | Description |
|------|-------------|
| `rag_embed` | Embed a YAML document |
| `rag_embed_text` | Embed raw text |
| `rag_search` | Semantic search |
| `rag_similar` | Find similar analyses for ticker |
| `rag_hybrid_context` | Combined vector + graph context |
| `rag_status` | RAG statistics |

### v2.0 Tools

| Tool | Description |
|------|-------------|
| `rag_search_rerank` | Search with cross-encoder reranking |
| `rag_search_expanded` | Search with query expansion |
| `rag_classify_query` | Classify query type |
| `rag_expand_query` | Generate query variations |
| `rag_evaluate` | RAGAS evaluation |
| `rag_metrics_summary` | Search metrics |

---

## Database Schema

```sql
-- Documents table
nexus.rag_documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE,
    file_path TEXT,
    doc_type VARCHAR(50),
    ticker VARCHAR(10),
    chunk_count INT,
    embed_model VARCHAR(100),
    embed_version VARCHAR(20)
)

-- Chunks table (with embeddings)
nexus.rag_chunks (
    id SERIAL PRIMARY KEY,
    doc_id INT REFERENCES rag_documents(id),
    section_path TEXT,
    content TEXT,
    content_tokens INT,
    embedding vector(1536),     -- OpenAI dimensions
    content_tsv tsvector,       -- BM25 full-text
    ticker VARCHAR(10),
    doc_type VARCHAR(50)
)
```

---

## Python API

### EmbedResult

```python
result = embed_document("path/to/file.yaml")

result.doc_id          # "MSFT_20260221T1715"
result.file_path       # "path/to/file.yaml"
result.doc_type        # "stock-analysis"
result.ticker          # "MSFT"
result.chunk_count     # 2
result.embed_model     # "text-embedding-3-large"
result.error_message   # None or "unchanged"
```

### RAGStats

```python
stats = get_rag_stats()

stats.document_count   # 22
stats.chunk_count      # 54
stats.tickers          # ["MSFT", "NVDA", ...]
stats.doc_types        # {"stock-analysis": 9, ...}
stats.last_embed       # datetime
```

### SearchResult

```python
results = semantic_search("query", top_k=5)

for r in results:
    r.doc_id           # Document ID
    r.content          # Chunk text
    r.score            # Similarity score
    r.ticker           # Ticker symbol
    r.section_label    # Section path
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBED_PROVIDER` | `openai` | Embedding provider |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `PG_HOST` | `localhost` | PostgreSQL host |
| `PG_PORT` | `5433` | PostgreSQL port |
| `CHUNK_MAX_TOKENS` | `768` | Max tokens per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap tokens |

### config.yaml

```yaml
features:
  reranking_enabled: true
  adaptive_retrieval: true
  query_expansion_enabled: true

chunking:
  max_tokens: 768
  min_tokens: 50
  overlap_tokens: 150
```

---

## Troubleshooting

### "Dimension mismatch"

Embedding provider changed. Options:
1. Re-embed all documents with new provider
2. Switch back to original provider

### Empty search results

- Check embeddings exist: `SELECT COUNT(*) FROM nexus.rag_chunks`
- Lower `min_similarity` threshold
- Try hybrid search with BM25

### Slow embedding

- Use `EMBED_PROVIDER=openai` (faster than Ollama)
- Check API key validity

---

## Related Documentation

- [Architecture Overview](overview.md)
- [Graph System](graph-system.md)
- [Database Schema](database-schema.md)
- Module: [`tradegent/rag/README.md`](../../tradegent/rag/README.md)
