# Trading RAG Module

Retrieval-Augmented Generation (RAG) system for trading knowledge. Embeds documents into PostgreSQL with pgvector for semantic search, then uses retrieved context to generate LLM answers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        RAG Pipeline                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Document Input                                                 │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  Parse  │───▶│  Chunk   │───▶│  Embed   │───▶│   Store   │  │
│  │  YAML   │    │  Text    │    │ (Ollama) │    │ (pgvector)│  │
│  └─────────┘    └──────────┘    └──────────┘    └───────────┘  │
│                                                                 │
│  Query Input                                                    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  Embed  │───▶│  Search  │───▶│ Retrieve │───▶│  Generate │  │
│  │  Query  │    │ (vector) │    │ Context  │    │   (LLM)   │  │
│  └─────────┘    └──────────┘    └──────────┘    └───────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```python
from rag.embed import embed_text, embed_document
from rag.search import semantic_search

# Embed text
result = embed_text(
    text="Your document content here...",
    doc_id="doc_001",
    doc_type="research",
    ticker="NVDA",
)
print(f"Stored {result.chunk_count} chunks")

# Search
results = semantic_search(
    query="What are the key risks?",
    ticker="NVDA",  # optional filter
    top_k=5,
)
for r in results:
    print(f"{r.similarity:.3f}: {r.content[:100]}...")
```

## Components

| File | Purpose |
|------|---------|
| `mcp_server.py` | **MCP server (primary interface)** |
| `embed.py` | Document embedding pipeline |
| `search.py` | Semantic and hybrid search |
| `chunk.py` | Text chunking with token limits |
| `embedding_client.py` | Ollama/OpenRouter embedding client |
| `schema.py` | PostgreSQL schema management |
| `models.py` | Data classes (EmbedResult, SearchResult) |
| `hybrid.py` | Combined vector + graph context |
| `config.yaml` | Configuration settings |
| `.env` | Environment variables (not committed) |
| `.env.template` | Environment template |

## Configuration

Settings are loaded from `.env` and `config.yaml` with environment variable overrides.

**Setup:**
```bash
cp .env.template .env
# Edit .env with your database credentials
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://lightrag:lightrag@localhost:5433/lightrag` | PostgreSQL connection |
| `RAG_SCHEMA` | `nexus` | Database schema name |
| `EMBED_PROVIDER` | `ollama` | Embedding provider (ollama, openrouter, openai) |
| `LLM_PROVIDER` | `ollama` | Fallback if EMBED_PROVIDER not set |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `LLM_API_KEY` | (none) | API key for OpenRouter/OpenAI |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `EMBED_DIMENSIONS` | `768` | Vector dimensions |
| `CHUNK_MAX_TOKENS` | `1500` | Max tokens per chunk |
| `CHUNK_MIN_TOKENS` | `50` | Min tokens (skip smaller) |

### Embedding Provider Options

| Provider | Model | Dimensions | Cost | Status |
|----------|-------|------------|------|--------|
| `ollama` | nomic-embed-text | 768 | Free (local) | Slower |
| `openai` | text-embedding-3-large | 1536* | $0.13/1M tokens | ✅ **Recommended** |
| `openai` | text-embedding-3-small | 768 | $0.02/1M tokens | Budget option |

*Uses API-level dimension truncation for pgvector HNSW index compatibility (max 2000 dims)

**Current config:** `EMBED_PROVIDER=openai` with `text-embedding-3-large` (1536 dimensions)

**Cost estimate:** ~$2/year for 7,500 documents (3-year projection)

**⚠️ WARNING:** Do NOT mix embedding providers! All documents must use the same embedding model for semantic search to work correctly. If switching providers, delete all embeddings and re-embed everything.

### Generation Settings (for RAG answer generation)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `llama3.2` | LLM model for generation |
| `LLM_TEMPERATURE` | `0.1` | Generation temperature |
| `LLM_NUM_PREDICT` | `200` | Max tokens to generate |
| `LLM_MAX_TOKENS` | `200` | Max tokens (cloud LLMs) |
| `LLM_TOP_P` | `0.9` | Top-p sampling |
| `LLM_TOP_K` | `40` | Top-k sampling |

## Database Schema

```sql
-- Documents table
nexus.rag_documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE,
    file_path TEXT,
    doc_type VARCHAR(50),
    ticker VARCHAR(10),
    doc_date DATE,
    chunk_count INT,
    embed_model VARCHAR(100),
    embed_version VARCHAR(20),
    tags TEXT[]
)

-- Chunks table (with embeddings)
nexus.rag_chunks (
    id SERIAL PRIMARY KEY,
    doc_id INT REFERENCES rag_documents(id),
    section_path TEXT,
    section_label VARCHAR(255),
    chunk_index INT,
    content TEXT,
    content_tokens INT,
    embedding vector(768),  -- pgvector
    content_tsv tsvector,   -- full-text search
    ticker VARCHAR(10),
    doc_type VARCHAR(50),
    doc_date DATE
)
```

## Embedding Functions

### embed_document(file_path, force=False)

Embed a YAML document file.

```python
from rag.embed import embed_document

result = embed_document("/path/to/analysis.yaml")
print(f"Doc ID: {result.doc_id}")
print(f"Chunks: {result.chunk_count}")
print(f"Duration: {result.duration_ms}ms")
```

### embed_text(text, doc_id, doc_type, ticker=None)

Embed raw text content.

```python
from rag.embed import embed_text

result = embed_text(
    text="NVIDIA reported strong Q4 earnings...",
    doc_id="nvda_q4_2024",
    doc_type="earnings",
    ticker="NVDA",
)
```

## Search Functions

### semantic_search(query, ...)

Vector similarity search.

```python
from rag.search import semantic_search

results = semantic_search(
    query="semiconductor supply chain risks",
    ticker="NVDA",           # optional
    doc_type="research",     # optional
    top_k=5,
    min_similarity=0.3,
)
```

**Similarity interpretation:**
- `> 0.8`: Near-identical (dedup candidate)
- `0.6 - 0.8`: Highly relevant (primary context)
- `0.4 - 0.6`: Somewhat relevant (supporting)
- `0.3 - 0.4`: Loosely related
- `< 0.3`: Irrelevant (excluded)

### hybrid_search(query, ...)

Combined BM25 + vector search using Reciprocal Rank Fusion.

```python
from rag.search import hybrid_search

results = hybrid_search(
    query="earnings volatility play",
    ticker="NVDA",
    vector_weight=0.7,
    bm25_weight=0.3,
    top_k=5,
)
```

### get_similar_analyses(ticker, analysis_type=None, top_k=3)

Find similar past analyses for a ticker.

```python
from rag.search import get_similar_analyses

results = get_similar_analyses("NVDA", analysis_type="earnings")
```

## Schema Management

```python
from rag.schema import init_schema, verify_schema, health_check

# Initialize tables and indexes
init_schema()

# Verify setup
status = verify_schema()
print(f"pgvector: {status['pgvector_enabled']}")
print(f"Tables: {status['tables']}")

# Health check
if health_check():
    print("Database connected")
```

## Testing

```bash
cd trader

# Run RAG tests
pytest rag/tests/ -v

# Run with coverage
pytest rag/tests/ --cov=rag --cov-report=term-missing

# Integration test (requires PostgreSQL)
pytest rag/tests/test_integration.py --run-integration
```

### Full RAG Test

```bash
# Ensure .env is configured
cp tradegent/rag/.env.template tradegent/rag/.env
# Edit tradegent/rag/.env with your database credentials

# Run full pipeline test (embeds story, searches, generates answers)
python tmp/test_rag.py
```

**Expected output:**
```
======================================================================
Full RAG Test: Store → Retrieve → Generate
======================================================================

[1] Embedding story (~200 tokens)...
    Stored 1 chunk(s)
    Document ID: test_story_marcus_chen

[2] RAG Question-Answering
----------------------------------------------------------------------

Q1: What is Marcus Chen's risk management rule?
    Retrieved context (similarity: 0.562)
    Answer: Marcus Chen's risk management rule is the "5-3-2 Rule"...

Q2: Where did Marcus Chen start his trading career?
    Retrieved context (similarity: 0.727)
    Answer: Marcus Chen started his trading career at Goldman Sachs in 2008.

Q3: What was Marcus Chen's most profitable trade?
    Retrieved context (similarity: 0.696)
    Answer: Marcus Chen's most profitable trade was accumulating NVIDIA shares...
```

## MCP Server (Primary Interface)

The RAG module is exposed via MCP server at `mcp_server.py`. **Use MCP tools as the primary interface** for all RAG operations.

**Server name:** `trading-rag`

| Tool | Description |
|------|-------------|
| `rag_embed` | Embed a YAML document |
| `rag_embed_text` | Embed raw text |
| `rag_search` | Semantic search |
| `rag_similar` | Find similar analyses |
| `rag_hybrid_context` | Combined vector + graph context |
| `rag_status` | Get RAG statistics |

### MCP Usage Examples

```yaml
# Embed a document
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/earnings/NVDA_20250120T0900.yaml"}

# Search for context
Tool: rag_search
Input: {"query": "NVDA earnings surprise", "ticker": "NVDA", "top_k": 5}

# Get hybrid context (vector + graph)
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings catalyst analysis"}

# Check RAG status
Tool: rag_status
Input: {}
```

### Running the MCP Server

```bash
# Direct execution
python tradegent/rag/mcp_server.py

# Or import and run
python -c "from rag.mcp_server import server; print(server.name)"
```

## Index Tuning

The default HNSW index works well for any dataset size:

```sql
-- Current (HNSW - recommended)
CREATE INDEX idx_rag_chunks_embedding
    ON nexus.rag_chunks USING hnsw (embedding vector_cosine_ops);

-- Alternative: IVFFlat for very large datasets (>100K chunks)
-- Requires reindexing after bulk inserts
CREATE INDEX idx_rag_chunks_embedding
    ON nexus.rag_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

## Troubleshooting

**"connection failed: password authentication failed"**
- Check `tradegent/rag/.env` has correct `DATABASE_URL`
- Verify password matches `PG_PASS` in `tradegent/.env`
- Verify PostgreSQL is running: `docker compose ps`

**"relation nexus.rag_documents does not exist"**
- Initialize schema: `python -c "from rag.schema import init_schema; init_schema()"`

**Empty search results**
- Verify embeddings stored: `SELECT COUNT(*) FROM nexus.rag_chunks`
- Check index type (HNSW works better for small datasets)
- Lower `min_similarity` threshold

**Slow embedding**
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Verify model is loaded: `ollama list`
