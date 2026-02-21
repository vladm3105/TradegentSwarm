# Trading RAG (Retrieval-Augmented Generation) — Architecture Plan

> **Status**: Implemented
> **Last updated**: 2026-02-21
> **Skills Version**: v2.3 (stock-analysis, earnings-analysis), v2.1 (other skills)
> **Replaces**: LightRAG vector search component
> **Companions**: [TRADING_GRAPH_ARCHITECTURE.md](TRADING_GRAPH_ARCHITECTURE.md) (knowledge graph), [SCANNER_ARCHITECTURE.md](SCANNER_ARCHITECTURE.md) (opportunity finding)

## Overview

Domain-specific vector search system using **pgvector** in the existing PostgreSQL
instance. Enables semantic retrieval of past analyses, trade journals, learnings,
and strategies to provide context for new trading decisions.

Together with the Neo4j knowledge graph, this forms a **hybrid RAG** system:
- **pgvector** — "find me similar analyses" (semantic similarity)
- **Neo4j** — "show me connected knowledge" (structural relationships)
- **Combined** — rich context for Claude when analyzing new positions

### Design Principles

1. **Section-level chunking** — YAML documents are split by semantic section (thesis, risks, catalysts), not by token count
2. **Metadata-first filtering** — filter by ticker, doc type, date range *before* vector search (fast + precise)
3. **Same PostgreSQL instance** — no new infrastructure; pgvector is already available in `nexus-postgres`
4. **OpenAI embeddings** — `text-embedding-3-large` (1536 dims via API truncation) for best quality at ~$2/year; Ollama fallback available
5. **Incremental indexing** — embed documents as skills produce them, no batch backfill of templates

### Key Decision: Why Not LightRAG?

| Factor | LightRAG | Custom pgvector RAG |
|--------|----------|---------------------|
| Embedding model | Cloud API ($) | OpenAI text-embedding-3-large (~$2/year) |
| Chunking | Generic text splitting | YAML-section-aware |
| Metadata filtering | Limited | Full SQL (ticker, type, date, tags) |
| Infrastructure | Separate container + API | Existing PostgreSQL instance |
| Hybrid search | Built-in but opaque | Explicit: pgvector + Neo4j graph |
| Operational complexity | High (separate process) | Low (SQL queries via db_layer.py) |
| Timeout risk | Critical (extraction + embedding) | None (embedding is fast: ~100ms/doc) |

---

## 1. Database Schema

### 1.1 Enable pgvector Extension

```sql
-- Run once in nexus-postgres
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.2 Documents Table

Tracks every document that has been embedded.

```sql
CREATE TABLE IF NOT EXISTS nexus.rag_documents (
    id              SERIAL PRIMARY KEY,
    doc_id          VARCHAR(100) NOT NULL UNIQUE,    -- _meta.id (e.g., "EA-NVDA-Q4-2024")
    file_path       VARCHAR(500) NOT NULL,           -- Relative path from project root
    doc_type        VARCHAR(50) NOT NULL,            -- earnings-analysis, stock-analysis, trade-journal, etc.
    ticker          VARCHAR(10),                     -- Primary ticker (NULL for research/macro docs)
    
    -- Temporal
    doc_date        DATE,                            -- Analysis/trade date
    quarter         VARCHAR(20),                     -- Q4-FY2025 (for earnings)
    
    -- Processing state
    chunk_count     INTEGER DEFAULT 0,
    embed_version   VARCHAR(20) NOT NULL DEFAULT '1.0.0',  -- Prompt/chunking version
    embed_model     VARCHAR(50) NOT NULL DEFAULT 'nomic-embed-text',
    
    -- Source tracking
    file_hash       VARCHAR(64),                     -- SHA-256 of source file (detect changes)
    
    tags            TEXT[],                           -- From _meta or inferred
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rag_docs_type ON nexus.rag_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_docs_ticker ON nexus.rag_documents(ticker);
CREATE INDEX IF NOT EXISTS idx_rag_docs_date ON nexus.rag_documents(doc_date);
CREATE INDEX IF NOT EXISTS idx_rag_docs_tags ON nexus.rag_documents USING gin(tags);
```

### 1.3 Chunks Table

Individual sections of documents with their embeddings.

```sql
CREATE TABLE IF NOT EXISTS nexus.rag_chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          INTEGER NOT NULL REFERENCES nexus.rag_documents(id) ON DELETE CASCADE,
    
    -- Chunk identity
    section_path    VARCHAR(200) NOT NULL,            -- YAML key path: "phase2_fundamentals.competitive_context"
    section_label   VARCHAR(100) NOT NULL,            -- Human-readable: "Competitive Context"
    chunk_index     SMALLINT NOT NULL DEFAULT 0,      -- For sections split into multiple chunks
    
    -- Content
    content         TEXT NOT NULL,                    -- Flattened text of this section
    content_tokens  INTEGER,                         -- Approximate token count
    
    -- Embedding
    embedding       vector(1536) NOT NULL,             -- nomic-embed-text output
    
    -- Denormalized metadata for filtered search (avoids JOINs)
    doc_type        VARCHAR(50) NOT NULL,
    ticker          VARCHAR(10),
    doc_date        DATE,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vector similarity index (IVFFlat for <100K chunks, switch to HNSW if needed)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding 
    ON nexus.rag_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- Filtered search indexes
CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON nexus.rag_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_ticker ON nexus.rag_chunks(ticker);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_type ON nexus.rag_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_section ON nexus.rag_chunks(section_label);

-- Unique constraint: one chunk per section per document
CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_chunks_unique 
    ON nexus.rag_chunks(doc_id, section_path, chunk_index);
```

### 1.4 Embedding Log

Audit trail for embedding operations.

```sql
CREATE TABLE IF NOT EXISTS nexus.rag_embed_log (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          INTEGER REFERENCES nexus.rag_documents(id),
    file_path       VARCHAR(500),
    action          VARCHAR(20) NOT NULL,             -- 'embed', 'reembed', 'delete'
    chunks_created  INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    embed_model     VARCHAR(50),
    embed_version   VARCHAR(20),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 1.5 Index Tuning Notes

| Chunk Count | Index Type | Config |
|-------------|-----------|--------|
| < 10,000 | IVFFlat | `lists = 50` |
| 10,000 – 100,000 | IVFFlat | `lists = 100` |
| > 100,000 | HNSW | `m = 16, ef_construction = 64` |

To switch index type:

```sql
-- Drop IVFFlat, create HNSW
DROP INDEX IF EXISTS nexus.idx_rag_chunks_embedding;
CREATE INDEX idx_rag_chunks_embedding 
    ON nexus.rag_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

---

## 2. Embedding Pipeline

### 2.1 Embedding Providers

Embeddings use a configurable provider (default Ollama, recommended OpenAI) with fallback chain support.

| Provider | Model | Dimensions | Context | Cost | Speed | Use Case |
|----------|-------|-----------|---------|------|-------|----------|
| **OpenAI** (recommended) | `text-embedding-3-large` | 1536* | 8191 tokens | ~$0.00013/1K tokens | ~80ms/chunk | Best quality, API truncation to 1536 |
| **Ollama** (free) | `nomic-embed-text` | 768 | 2048 tokens | $0 | ~50ms/chunk | Local, free, but lower quality |
| **OpenRouter** | `openai/text-embedding-3-small` | 1536* | 8191 tokens | ~$0.00002/chunk | ~100ms/chunk | Pay-per-use cloud fallback |

\* OpenAI text-embedding-3-large outputs 3072 dims by default; we use API-level truncation to 1536 dims because pgvector's HNSW index has a 2000 dimension limit.

> **Important**: All providers in the fallback chain MUST output the same dimensionality. Mixing dimensions corrupts vector search.

### 2.2 Fallback Chain

Configured in `tradegent/rag/config.yaml`:

```yaml
embedding:
  # EMBED_PROVIDER env var selects default (recommended: openai)
  default_provider: "${EMBED_PROVIDER:-ollama}"
  fallback_chain:
    - ollama           # Try local first ($0)
    - openrouter       # Fallback to cloud if Ollama fails/unavailable
  timeout_seconds: 30
  dimensions: "${EMBED_DIMENSIONS:-1536}"   # All providers must match

  ollama:
    base_url: "${LLM_BASE_URL:-http://localhost:11434}"
    model: "${EMBED_MODEL:-nomic-embed-text}"

  openrouter:
    api_key: "${LLM_API_KEY}"
    model: "${EMBED_MODEL:-openai/text-embedding-3-small}"
    dimensions: "${EMBED_DIMENSIONS:-1536}"

  # Direct OpenAI (recommended for best quality)
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "${EMBED_MODEL:-text-embedding-3-large}"
    dimensions: "${EMBED_DIMENSIONS:-1536}"   # API truncates from 3072 to 1536
```

**LiteLLM Benefits**:

- **Unified API** for 100+ embedding providers (OpenAI, Cohere, Voyage, etc.)
- **Automatic retries** with exponential backoff on transient failures
- **Cost tracking** and rate limiting built-in
- **OpenRouter integration** for pay-per-use without separate API keys per provider
- **Dimension normalization** — request specific output dimensions for compatibility

**Shared Config Note**: The `OPENROUTER_API_KEY` environment variable is shared with
the Graph extraction system (see [TRADING_GRAPH_ARCHITECTURE.md](TRADING_GRAPH_ARCHITECTURE.md)).
Both systems use LiteLLM with the same fallback chain pattern.

### 2.3 Unified Embedding Client

```python
from litellm import embedding as litellm_embedding
import requests

class EmbeddingClient:
    """Embedding with Ollama-first, LiteLLM/OpenRouter fallback."""
    
    def __init__(self, config: dict):
        self.config = config
        self.fallback_chain = config.get("fallback_chain", ["ollama"])
    
    def get_embedding(self, text: str) -> list[float]:
        for provider in self.fallback_chain:
            try:
                if provider == "ollama":
                    return self._ollama_embed(text)
                else:
                    return self._litellm_embed(text, provider)
            except Exception as e:
                log.warning(f"Embedding via {provider} failed: {e}")
                continue
        raise EmbeddingUnavailableError("All embedding providers failed")
    
    def _ollama_embed(self, text: str) -> list[float]:
        """Local Ollama embedding ($0)."""
        cfg = self.config["ollama"]
        resp = requests.post(
            f"{cfg['base_url']}/api/embed",
            json={"model": cfg["model"], "input": text},
            timeout=self.config["timeout_seconds"]
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]
    
    def _litellm_embed(self, text: str, provider: str) -> list[float]:
        """Cloud embedding via LiteLLM (OpenRouter, OpenAI, etc.)."""
        cfg = self.config[provider]
        response = litellm_embedding(
            model=cfg["model"],
            input=[text],
            dimensions=cfg.get("dimensions", 768),
            api_key=cfg.get("api_key"),
        )
        return response.data[0]["embedding"]
```

**Critical**: All providers MUST output the same dimensionality (1536). Mixing
dimensions in the same `rag_chunks` table will corrupt vector search results.

### 2.4 Text Preparation

Before embedding, each chunk is prepared with a context prefix:

```python
def prepare_chunk_text(section_label: str, content: str, 
                       ticker: str | None, doc_type: str) -> str:
    """Add context prefix to improve embedding relevance."""
    prefix_parts = [f"[{doc_type}]"]
    if ticker:
        prefix_parts.append(f"[{ticker}]")
    prefix_parts.append(f"[{section_label}]")
    prefix = " ".join(prefix_parts)
    return f"{prefix}\n{content}"
```

Example prepared chunk:

```
[earnings-analysis] [NVDA] [Competitive Context]
Compare ABSOLUTE DOLLARS, not percentages. NVDA adding $17B vs AMD 
adding $1B - 17x more absolute growth. Revenue $35.1B, growth 94%.
```

---

## 3. Document Processing

### 3.1 Chunking Strategy: Section-Level

Trading YAMLs have natural semantic boundaries at top-level keys.
We split by YAML section rather than fixed token windows.

```
YAML Document
    │
    ├── _meta          → SKIP (metadata, not searchable content)
    ├── thesis         → CHUNK: "Thesis"
    ├── catalysts      → CHUNK: "Catalysts"  
    ├── risks          → CHUNK: "Risks"
    ├── technicals     → CHUNK: "Technical Analysis"
    ├── execution      → CHUNK: "Execution"
    ├── results        → CHUNK: "Results"
    ├── review         → CHUNK: "Review"
    ├── _graph         → SKIP (used by graph system, not for vector search)
    └── _links         → SKIP (references, not content)
```

### 3.2 Section Mapping by Document Type

Each document type has sections worth embedding (skip metadata/structural keys). Updated for v2.3 skill templates:

| Document Type | Sections to Embed | Skip |
|---------------|-------------------|------|
| **stock-analysis** (v2.3) | `data_quality`, `catalyst`, `news_age_check`, `market_environment`, `post_mortem`, `technical`, `fundamentals`, `sentiment`, `expectations_assessment`, `bear_case_analysis` (summary, arguments, why_bull_wins), `threat_assessment`, `thesis_reversal`, `scenarios` (4 scenarios), `bias_check` (biases_detected, pre_exit_gate, countermeasures), `do_nothing_gate`, `falsification`, `alert_levels`, `alternative_strategies`, `trade_plan`, `summary`, `meta_learning` | `_meta`, `_graph`, `_links`, `_indexing`, `ticker` |
| **earnings-analysis** (v2.3) | `phase1_preparation`, `phase2_fundamentals.*`, `phase3_technicals`, `phase4_trade_structure`, `phase5_risk_management`, `historical_moves`, `news_age_check`, `expectations_assessment`, `bear_case_analysis`, `bias_check`, `falsification`, `meta_learning`, `thesis` | `_meta`, `_graph`, `_links`, `_indexing`, `ticker`, `earnings_date` |
| **research-analysis** (v2.1) | `research_question`, `thesis` (statement, reasoning), `supporting_arguments`, `counter_thesis` (steel-manned), `bias_check`, `sources`, `implications` | `_meta`, `_graph`, `_links`, `_indexing` |
| **watchlist** (v2.1) | `thesis` (summary, reasoning, why_not_now), `conviction` (level, conditions), `analysis_quality_check`, `entry_trigger`, `invalidation`, `resolution` | `_meta`, `_graph`, `_links`, `_indexing` |
| **trade-journal** (v2.1) | `pre_trade_checklist`, `thesis`, `execution`, `psychological_state` (entry/exit), `decision_quality`, `loss_aversion_check`, `during_trade`, `results`, `review` | `_meta`, `_graph`, `_links`, `_indexing`, `ticker` |
| **post-trade-review** (v2.1) | `analysis`, `data_source_effectiveness`, `bias_review` (with costs), `countermeasures_needed`, `lessons`, `rule_validation`, `comparison_to_similar_trades`, `framework_updates` | `_meta`, `_graph`, `_links`, `_indexing` |
| **ticker-profile** (v2.1) | `company`, `earnings_patterns`, `technical_levels`, `your_edge`, `analysis_track_record`, `trading_history`, `bias_history`, `known_risks`, `learned_patterns` | `_meta`, `_graph`, `_links`, `_indexing` |
| **strategy** | `description`, `entry_rules`, `exit_rules`, `risk_management`, `performance` | `_meta`, `_graph`, `_links`, `_indexing` |
| **learning** (v2.1) | `pattern`, `root_cause`, `countermeasure` (rule, implementation, mantra), `validation`, `evidence` | `_meta`, `_graph`, `_links`, `_indexing` |

### 3.3 Subsection Handling

For deep documents (e.g., earnings-analysis with nested `phase2_fundamentals`),
flatten subsections individually if the parent exceeds 1500 tokens:

```python
def chunk_yaml_section(key: str, value: Any, max_tokens: int = 1500) -> list[dict]:
    """Split a YAML section into chunks, respecting token limits."""
    text = yaml_to_text(key, value)
    
    if estimate_tokens(text) <= max_tokens:
        return [{"section_path": key, "section_label": humanize(key), 
                 "content": text, "chunk_index": 0}]
    
    # If value is a dict, split by sub-keys
    if isinstance(value, dict):
        chunks = []
        for sub_key, sub_value in value.items():
            sub_text = yaml_to_text(sub_key, sub_value)
            chunks.append({
                "section_path": f"{key}.{sub_key}",
                "section_label": f"{humanize(key)} — {humanize(sub_key)}",
                "content": sub_text,
                "chunk_index": 0
            })
        return chunks
    
    # If still too long (list or large text), split by token window
    return split_by_tokens(key, text, max_tokens)
```

### 3.4 YAML Flattening Rules

Convert YAML structures to readable text for embedding:

| YAML Structure | Flattened Text |
|---------------|----------------|
| `key: value` | `key: value` |
| `key: [a, b, c]` | `key: a, b, c` |
| `list of dicts` | One line per dict, key-value pairs |
| `nested dict` | `parent.child: value` |
| `null / empty` | Skip entirely |

Example — this YAML:

```yaml
business_performance:
  revenue_trend_8q:
    - {quarter: Q4-FY24, revenue_b: 22.1, yoy_pct: 265}
    - {quarter: Q1-FY25, revenue_b: 26.0, yoy_pct: 262}
  margin_trend:
    gross_margin_current: 75.0
    trend: expanding
```

Becomes this text:

```
Business Performance — Revenue Trend (8Q):
Q4-FY24: revenue $22.1B, YoY +265%
Q1-FY25: revenue $26.0B, YoY +262%

Business Performance — Margin Trend:
Gross margin current: 75.0%
Trend: expanding
```

---

## 4. Query Interface

### 4.1 Core Search Function

```python
def semantic_search(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    section: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    top_k: int = 5,
    min_similarity: float = 0.3
) -> list[SearchResult]:
    """
    Semantic search with optional metadata filters.
    
    Returns SearchResult with: content, similarity, doc_id, ticker, 
    doc_type, section_label, doc_date, file_path
    """
```

### 4.2 SQL Query Patterns

**Pure semantic search** (no filters):

```sql
SELECT c.content, c.section_label, c.ticker, c.doc_type, c.doc_date,
       d.file_path, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
ORDER BY c.embedding <=> $1::vector
LIMIT $2;
```

**Filtered semantic search** (by ticker + type):

```sql
SELECT c.content, c.section_label, c.doc_date,
       d.file_path, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.ticker = $2
  AND c.doc_type = $3
ORDER BY c.embedding <=> $1::vector
LIMIT $4;
```

**Time-bounded search** (recent analyses only):

```sql
SELECT c.content, c.section_label, c.ticker, c.doc_type,
       d.file_path, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.doc_date >= $2
  AND c.doc_date <= $3
ORDER BY c.embedding <=> $1::vector
LIMIT $4;
```

**Section-specific search** (e.g., only risk sections):

```sql
SELECT c.content, c.ticker, c.doc_date,
       d.file_path, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.section_label ILIKE '%risk%'
ORDER BY c.embedding <=> $1::vector
LIMIT $2;
```

### 4.3 Hybrid RAG: Vector + Graph

When providing context to Claude for a new analysis:

```python
def get_hybrid_context(ticker: str, query: str) -> str:
    """Combine vector search + graph context for Claude."""
    
    # 1. Vector search: find similar past analyses
    vector_results = semantic_search(
        query=query,
        ticker=ticker,
        top_k=5,
        min_similarity=0.4
    )
    
    # 2. Graph search: get structural context from Neo4j
    graph_context = trading_graph.get_ticker_context(ticker)
    # Returns: related biases, strategies used, catalysts, peer tickers
    
    # 3. Combine into context block for Claude
    context = "## Past Analyses (Semantic Search)\n\n"
    for r in vector_results:
        context += f"### {r.doc_id} — {r.section_label} ({r.doc_date})\n"
        context += f"{r.content}\n\n"
    
    context += "## Knowledge Graph Context\n\n"
    context += graph_context
    
    return context
```

### 4.4 Similarity Score Interpretation

| Cosine Similarity | Interpretation | Use |
|-------------------|---------------|-----|
| > 0.8 | Near-identical content | Dedup candidate |
| 0.6 – 0.8 | Highly relevant | Primary context |
| 0.4 – 0.6 | Somewhat relevant | Supporting context |
| 0.3 – 0.4 | Loosely related | Include if few results |
| < 0.3 | Irrelevant | Exclude |

---

## 5. Integration Points

### 5.1 Orchestrator CLI (new `rag` command group)

```bash
# Schema management
python orchestrator.py rag init               # Create pgvector extension + tables
python orchestrator.py rag reset              # Drop and recreate tables (dev only)

# Embedding
python orchestrator.py rag embed FILE         # Embed a single document
python orchestrator.py rag embed --dir DIR    # Embed all docs in directory
                                              # (skips template.yaml, files without ISO 8601 date)
python orchestrator.py rag reembed --all      # Re-embed all docs (after model/chunking changes)
python orchestrator.py rag reembed --version 1.0.0  # Re-embed docs embedded with older version

# Search
python orchestrator.py rag search "QUERY"              # Pure semantic search
python orchestrator.py rag search "QUERY" --ticker NVDA # Filtered by ticker
python orchestrator.py rag search "QUERY" --type earnings-analysis  # Filtered by doc type
python orchestrator.py rag search "QUERY" --section risks           # Search only risk sections
python orchestrator.py rag search "QUERY" --since 2026-01-01        # Time-bounded

# Status
python orchestrator.py rag status             # Document count, chunk count, index stats
python orchestrator.py rag list               # List all embedded documents
python orchestrator.py rag show DOC_ID        # Show chunks for a specific document

# Maintenance
python orchestrator.py rag delete DOC_ID      # Remove document and its chunks
python orchestrator.py rag reindex            # Rebuild vector index (after bulk operations)
python orchestrator.py rag validate           # Check for orphaned chunks, missing embeddings
```

### 5.2 Claude Skills — Post-Execution Hook

After each skill saves a real analysis YAML, the same hook that triggers
graph extraction also triggers embedding:

```
## Post-Execution: RAG Integration

After saving the analysis file:
1. Call `python orchestrator.py rag embed <saved_file>`
2. Chunking + embedding runs (~500ms total for a typical document)
3. Document is immediately searchable
```

### 5.3 Pre-Analysis Context Injection

Before a skill analyzes a ticker, query RAG for relevant context:

```python
# In orchestrator.py, before invoking Claude for analysis
def build_analysis_context(ticker: str, analysis_type: str) -> str:
    """Gather RAG + Graph context for a new analysis."""
    
    # Vector: past analyses for this ticker
    past_analyses = rag_search(
        query=f"{ticker} {analysis_type} thesis catalysts risks",
        ticker=ticker,
        top_k=3
    )
    
    # Vector: similar analyses for peer tickers
    peers = graph_query_peers(ticker)  # From Neo4j
    peer_analyses = rag_search(
        query=f"{analysis_type} thesis catalysts",
        ticker=peers,  # Filter to peer tickers
        top_k=2
    )
    
    # Vector: relevant learnings and biases
    learnings = rag_search(
        query=f"{ticker} lessons bias mistakes",
        doc_type="post-trade-review",
        top_k=3
    )
    
    # Graph: structural context
    graph_ctx = trading_graph.get_ticker_context(ticker)
    
    return format_context(past_analyses, peer_analyses, learnings, graph_ctx)
```

### 5.4 Service Integration (Future)

```python
# In service.py — watch for new YAML files
# Auto-embed when files appear in knowledge/ directories
# Re-embed if embed_version has changed since last run
```

### 5.5 Python API (Direct Import)

Any Python code can call the embedding and search functions directly:

```python
from trader.rag.embed import embed_document, embed_text
from trader.rag.search import semantic_search, get_similar_analyses
from trader.rag.embedding_client import EmbeddingClient

# Option 1: Embed a YAML file
result = embed_document(
    file_path="trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml",
    force=False  # Skip if file_hash unchanged
)
print(f"Embedded {result.chunk_count} chunks")

# Option 2: Embed raw text (for external content)
result = embed_text(
    text="NVIDIA reported strong Q4 with data center revenue up 400%...",
    doc_id="external-article-001",
    doc_type="article",
    ticker="NVDA"
)

# Option 3: Semantic search
results = semantic_search(
    query="AI capex thesis semiconductor",
    ticker="NVDA",           # Optional filter
    doc_type="earnings-analysis",  # Optional filter
    top_k=5,
    min_similarity=0.4
)
for r in results:
    print(f"{r.doc_id} ({r.similarity:.2f}): {r.content[:100]}...")

# Option 4: Get similar past analyses for a ticker
similar = get_similar_analyses(
    ticker="NVDA",
    analysis_type="earnings-analysis",
    top_k=3
)

# Option 5: Direct embedding client (for custom use)
client = EmbeddingClient(config)
embedding = client.get_embedding("NVIDIA data center growth thesis")
```

### 5.6 HTTP Webhook API

For external systems (CI/CD, monitoring tools, other services):

```python
# tradegent/rag/webhook.py — FastAPI endpoints

POST /api/rag/embed
{
    "file_path": "trading/knowledge/analysis/earnings/NVDA_20260219T0900.yaml",
    "force": false
}
# Returns: {"doc_id": "EA-NVDA-Q4-2025", "chunks": 8, "status": "embedded"}

POST /api/rag/embed-text
{
    "text": "NVIDIA reported strong Q4...",
    "doc_id": "external-001",
    "doc_type": "article",
    "ticker": "NVDA"
}
# Returns: {"doc_id": "external-001", "chunks": 1, "status": "embedded"}

POST /api/rag/search
{
    "query": "AI capex thesis",
    "ticker": "NVDA",
    "doc_type": "earnings-analysis",
    "top_k": 5,
    "min_similarity": 0.4
}
# Returns: {"results": [...], "count": 5}

GET /api/rag/status
# Returns: {"documents": 45, "chunks": 312, "index_size_mb": 24.5}

DELETE /api/rag/document/{doc_id}
# Returns: {"doc_id": "EA-NVDA-Q4-2025", "chunks_deleted": 8, "status": "deleted"}
```

Webhook server runs as optional sidecar or integrated into service.py:

```bash
# Standalone
uvicorn trader.rag.webhook:app --host 0.0.0.0 --port 8081

# Or add to docker-compose.yml as rag-api service
```

---

## 6. File Structure

```
tradegent/
├── rag/
│   ├── __init__.py           # Package init: RAG_VERSION, EMBED_DIMS, model constants
│   ├── config.yaml           # Embedding provider config (Ollama, OpenRouter, OpenAI)
│   ├── schema.py             # pgvector schema init (CREATE EXTENSION, tables)
│   ├── embed.py              # Embedding pipeline (chunk → embed → store)
│   ├── embedding_client.py   # Unified embedding client with fallback chain (section 2.3)
│   ├── chunk.py              # YAML-aware chunking logic
│   ├── flatten.py            # YAML-to-text flattening for embedding
│   ├── search.py             # Semantic search queries + hybrid RAG
│   ├── webhook.py            # FastAPI HTTP endpoints (section 5.6)
│   └── ollama.py             # Ollama-specific API client (used by embedding_client)
├── db/
│   ├── init.sql              # (existing) Nexus schema
│   └── rag_schema.sql        # pgvector tables, indexes, constraints
└── orchestrator.py           # (modify) add `rag` command group

mcp_trading_rag/              # MCP Server (Phase 3)
├── __init__.py
├── server.py                 # MCP server entry point
└── tools/
    ├── search.py             # rag_search, rag_similar tools
    └── embed.py              # rag_embed tool
```

---

## 7. Example Queries

### 7.1 "What risks did I identify for NVDA in past analyses?"

```sql
-- Embed the query, then:
SELECT c.content, c.doc_date, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.ticker = 'NVDA'
  AND c.section_label ILIKE '%risk%'
ORDER BY c.embedding <=> $1::vector
LIMIT 5;
```

### 7.2 "Find past earnings analyses with high confidence thesis"

```sql
SELECT c.content, c.ticker, c.doc_date, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.doc_type = 'earnings-analysis'
  AND c.section_label = 'Thesis'
ORDER BY c.embedding <=> $1::vector
LIMIT 5;
```

### 7.3 "What biases have I exhibited in past trades?"

```sql
SELECT c.content, c.ticker, c.doc_date, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.doc_type = 'trade-journal'
  AND c.section_label = 'Review'
ORDER BY c.embedding <=> $1::vector
LIMIT 5;
```

### 7.4 "How did semiconductor stocks perform around earnings?"

```sql
-- Broad semantic search, no ticker filter
SELECT c.content, c.ticker, c.doc_date, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.doc_type IN ('earnings-analysis', 'trade-journal')
ORDER BY c.embedding <=> $1::vector
LIMIT 10;
```

### 7.5 "Show me all exit reviews where I left money on the table"

```sql
SELECT c.content, c.ticker, c.doc_date, d.doc_id,
       1 - (c.embedding <=> $1::vector) AS similarity
FROM nexus.rag_chunks c
JOIN nexus.rag_documents d ON d.id = c.doc_id
WHERE c.section_label IN ('Review', 'Lessons', 'Bias Review')
ORDER BY c.embedding <=> $1::vector
LIMIT 5;
```

---

## 8. Implementation Phases

### Phase 1 — Schema + Embedding Pipeline (~4 hrs)

| Deliverable | Description |
|-------------|-------------|
| `db/rag_schema.sql` | pgvector extension + tables + indexes |
| `rag/schema.py` | Python schema initializer |
| `rag/ollama.py` | Ollama embedding API client with retry |
| `rag/flatten.py` | YAML-to-text flattener |
| `rag/chunk.py` | Section-level chunking with subsection handling |
| `rag/embed.py` | Full pipeline: parse → chunk → embed → store |
| `rag/__init__.py` | Package init with `RAG_VERSION = "1.0.0"` |
| `orchestrator.py` | `rag init`, `rag embed`, `rag status` |
| **Test** | Embed a synthetic document, verify chunks + embeddings in DB |

### Phase 2 — Search + Hybrid RAG (~3 hrs)

| Deliverable | Description |
|-------------|-------------|
| `rag/search.py` | Semantic search with metadata filters |
| `orchestrator.py` | `rag search` command with all filter options |
| Hybrid context builder | Combine vector + graph results for Claude |
| Pre-analysis hook | Inject RAG context before skill execution |
| **Test** | Search across multiple embedded documents, verify relevance |

### Phase 3 — Skills Integration + MCP Server (~3 hrs)

| Deliverable | Description |
|-------------|-------------|
| Post-execution hooks | Auto-embed after skill saves real analysis |
| Context injection | Pass hybrid RAG context to Claude skills |
| `rag list` / `rag show` | Inspect embedded documents |
| `mcp_trading_rag/` | MCP server wrapping search + embed tools |
| MCP tools: `rag_search` | Semantic search with filters for Claude skills |
| MCP tools: `rag_embed` | Trigger embedding from Claude context |
| MCP tools: `rag_similar` | Find similar analyses for a ticker |

### Phase 4 — Production Hardening

| Deliverable | Description |
|-------------|-------------|
| HNSW index migration | Switch from IVFFlat when chunk count warrants |
| Re-embedding pipeline | `rag reembed` with version tracking |
| Embedding model upgrade | Evaluate larger models if quality insufficient |
| Service integration | Auto-embed in service.py file watcher |

---

## 9. Infrastructure

### Current Docker Stack (no changes needed)

| Service | Container | Port | Role |
|---------|-----------|------|------|
| PostgreSQL + pgvector | nexus-postgres | 5433 | Vector storage (existing instance) |
| Ollama | (host) | 11434 | Primary embedding generation ($0) |
| LiteLLM | (library) | — | Unified API for cloud embedding fallback |
| OpenRouter | (cloud) | — | Cloud embedding provider (pay-per-use backup) |

### pgvector Availability

```
pgvector 0.8.1 — already available in pgvector/pgvector:pg16 image
No container rebuild needed. Just CREATE EXTENSION vector;
```

### Dependencies

```
# tradegent/requirements.txt additions
psycopg[binary]>=3.1     # Already installed (PostgreSQL driver)
pyyaml>=6.0              # Already installed (YAML parsing)
requests>=2.28.0         # Already installed (Ollama API)
litellm>=1.40.0          # NEW — unified LLM/embedding API (OpenRouter, OpenAI, etc.)
```

### Environment Variables

```bash
# .env additions (only needed if using cloud fallback)
OPENROUTER_API_KEY=sk-or-...       # OpenRouter API key (pay-per-use, no minimums)
OPENAI_API_KEY=sk-...               # Optional: direct OpenAI (alternative to OpenRouter)
```

### LightRAG Deprecation

After both the graph system (Phase 1) and RAG system (Phase 1) are validated:

| Item | Action |
|------|--------|
| `nexus-lightrag` container | Stop and remove from docker-compose.yml |
| LightRAG env vars in docker-compose | Remove `LLM_BINDING`, `EMBEDDING_BINDING`, etc. |
| `trading/workflows/.lightrag/` | Delete directory |
| Settings: `lightrag_url`, `lightrag_ingest_enabled`, `lightrag_query_enabled` | Remove from nexus.settings |
| `allowed_tools_analysis` setting | Remove `mcp__lightrag__*` |

---

## 10. Error Handling & Resilience

### 10.1 Embedding Failures

| Failure Mode | Behavior |
|--------------|----------|
| **Ollama timeout** | Retry 2x with exponential backoff (5s, 15s), then fallback to LiteLLM/OpenRouter |
| **Ollama unavailable** | Automatic fallback to LiteLLM/OpenRouter; if all providers fail, log and skip |
| **Malformed YAML** | Log parse error, skip document |
| **PostgreSQL connection failure** | Retry 2x, then abort with error (data integrity critical) |
| **Embedding dimension mismatch** | Fatal error — model changed; requires re-embed all |
| **LiteLLM/OpenRouter rate limit** | Retry with backoff; degrade to Ollama-only mode |
| **OpenRouter API key missing** | Skip cloud fallback silently; Ollama-only mode |
| **Chunk too long (>2048 tokens)** | Auto-split into sub-chunks; log warning |

### 10.2 Graceful Degradation

Skills must function even if RAG is unavailable:

```python
# In pre-analysis context builder
try:
    rag_context = rag_search(query, ticker=ticker, top_k=5)
except RAGUnavailableError:
    log.warning(f"RAG search skipped for {ticker} - pgvector unavailable")
    rag_context = []  # Claude proceeds without historical context
```

### 10.3 Data Integrity

| Concern | Mitigation |
|---------|-----------|
| **Stale embeddings** | `file_hash` in `rag_documents` detects changes; re-embed on mismatch |
| **Orphaned chunks** | `ON DELETE CASCADE` ensures chunks are cleaned when document is deleted |
| **Duplicate documents** | `doc_id UNIQUE` constraint prevents double-embedding |
| **Version drift** | `embed_version` tracks which chunking/model version was used; enables selective re-embedding |
| **Mixed providers** | `embed_model` column in `rag_documents` records which provider was used; all must output 768 dims |

---

## 11. Operations

### 11.1 Monitoring Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Total documents embedded | `rag status` | N/A (growth indicator) |
| Total chunks | `rag status` | N/A (growth indicator) |
| Avg chunks per document | `rag status` | > 20 (chunking too granular?) |
| Embedding latency | `rag_embed_log` | > 2s per document avg |
| Embedding failures | `rag_embed_log` | > 5% over 24h |
| Cloud fallback usage | `rag_embed_log` (embed_model column) | > 20% (Ollama may be unhealthy) |
| OpenRouter spend | OpenRouter dashboard / LiteLLM logs | > $1/day (unexpected volume) |
| Search latency (p95) | Application logs | > 200ms |
| Index size | `pg_total_relation_size` | > 1GB (consider HNSW) |

### 11.2 Maintenance

```bash
# Re-embed all documents (after model or chunking changes)
python orchestrator.py rag reembed --all

# Re-embed only docs embedded with an older version
python orchestrator.py rag reembed --version 1.0.0

# Remove embeddings for a deleted document
python orchestrator.py rag delete DOC_ID

# Rebuild vector index (after bulk inserts)
REINDEX INDEX CONCURRENTLY nexus.idx_rag_chunks_embedding;

# Check index health
SELECT pg_size_pretty(pg_total_relation_size('nexus.rag_chunks'));
SELECT count(*) FROM nexus.rag_chunks;
```

### 11.3 Backup

Included in the standard PostgreSQL backup — no separate backup needed:

```bash
# Full nexus-postgres backup (includes both nexus schema and RAG tables)
docker exec nexus-postgres pg_dump -U lightrag lightrag > ~/backups/nexus_pg_$(date +%Y%m%d).sql
```

### 11.4 Schema Versioning

Version tracked in `rag/__init__.py`:

```python
RAG_VERSION = "1.0.0"       # Bump on schema/chunking/model changes
EMBED_DIMS = 1536           # All providers must match this (pgvector HNSW limit: 2000)
```

> **Note**: Embedding dimensions are configured in `config.yaml` via `EMBED_DIMENSIONS` env var (default: 1536). The model is selected by `EMBED_MODEL` env var.

Migration strategy:

| Change Type | Action |
|-------------|--------|
| **Add column to rag_documents** | ALTER TABLE, no re-embed needed |
| **Change chunking logic** | Bump `RAG_VERSION`, run `rag reembed --all` |
| **Change embedding model** | Bump `RAG_VERSION`, drop all embeddings, re-embed all |
| **Change vector dimensions** | Drop index + column, recreate with new size, re-embed all |
| **Add new cloud provider** | Add to `config.yaml` fallback chain, no re-embed needed (same dims) |
| **Switch default from Ollama to cloud** | Update `config.yaml`, no re-embed needed if dims match |

---

## 12. Testing Strategy

### 12.1 Unit Tests

| Module | Test Coverage |
|--------|---------------|
| `rag/chunk.py` | Section splitting, subsection handling, token limits |
| `rag/flatten.py` | YAML-to-text conversion for all structures |
| `rag/embedding_client.py` | Fallback chain, provider switching, dimension validation |
| `rag/ollama.py` | Ollama-specific API calls, retry logic (mock Ollama) |
| `rag/embed.py` | Full pipeline: parse → chunk → embed → store (mock DB) |
| `rag/search.py` | Query building, result formatting (mock DB) |

### 12.2 Integration Tests

| Test | Description |
|------|-------------|
| **Round-trip** | Embed document → search → verify result contains source content |
| **Idempotency** | Embed same doc twice → same chunk count, updated embeddings |
| **Filtered search** | Embed 3 tickers → search with ticker filter → only matching results |
| **File hash change** | Modify source file → re-embed → verify embeddings updated |
| **Hybrid RAG** | Vector search + graph query → combined context is valid |

### 12.3 Test Fixtures

```text
tradegent/rag/tests/
├── fixtures/
│   ├── sample_earnings.yaml       # Synthetic earnings analysis
│   ├── sample_trade.yaml          # Synthetic trade journal
│   ├── sample_research.yaml       # Synthetic research analysis
│   └── expected_chunks/           # Expected chunk output per fixture
├── test_chunk.py
├── test_flatten.py
├── test_embed.py
└── test_search.py
```

---

## 13. Comparison: Graph vs RAG — When to Use Which

| Question Type | Use | Why |
|--------------|-----|-----|
| "What biases affect my NVDA trades?" | **Graph** | Structural: Bias→Trade→Ticker relationships |
| "Find analyses similar to this thesis" | **RAG** | Semantic: vector similarity on text content |
| "Which strategies work for earnings?" | **Graph** | Structural: Strategy→Ticker→Catalyst relationships |
| "What risks did I identify in past semiconductor analyses?" | **RAG** | Semantic: search risk sections across docs |
| "NVDA competitive landscape" | **Graph** | Structural: Company→COMPETES_WITH relationships |
| "How did I frame the AI capex thesis before?" | **RAG** | Semantic: find similar thesis text |
| "Am I repeating the same bias?" | **Both** | Graph finds bias pattern, RAG finds context of past occurrences |
| "Full context for NVDA earnings analysis" | **Both** | Graph: structural relationships. RAG: similar past analyses |
