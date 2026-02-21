# IPLAN-001: Trading Knowledge Base Implementation

> **Status**: Planning
> **Created**: 2026-02-19
> **Updated**: 2026-02-19
> **Reviewed**: 2026-02-19 (15 issues fixed — see review notes)
> **Target**: Trading Knowledge Graph + RAG System
> **Scope**: Phases 1-8 (core system). Phases 9-12 deferred to IPLAN-002 after 30+ documents ingested.

## Overview

Implement the hybrid knowledge base system for trading_light_pilot:
- **Knowledge Graph** (Neo4j) — Entity extraction, relationship mapping, structural queries
- **RAG System** (pgvector) — Semantic search, vector embeddings, similarity retrieval

Both systems replace the existing LightRAG dependency with domain-specific, Ollama-first alternatives.

## Architecture Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Trading Knowledge Base                               │
├──────────────────────────────────┬──────────────────────────────────────────┤
│         Knowledge Graph          │              RAG System                   │
│        (Neo4j + Claude)          │          (pgvector + Ollama)             │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ • 16 entity types                │ • Section-level YAML chunking            │
│ • 20+ relationship types         │ • 768-dim embeddings (nomic-embed)       │
│ • Field-by-field extraction      │ • Metadata-first filtering               │
│ • Claude + Ollama backends       │ • Ollama + OpenRouter fallback           │
│ • HTTP webhook API               │ • HTTP webhook API                       │
│ • MCP server tools               │ • MCP server tools                       │
├──────────────────────────────────┴──────────────────────────────────────────┤
│                        Trading Intelligence Layer                            │
├──────────────────────────────────┬──────────────────────────────────────────┤
│    Graph Intelligence (Ph 11)    │      RAG Intelligence (Ph 9-10)          │
├──────────────────────────────────┼──────────────────────────────────────────┤
│ • Outcome-weighted traversal     │ • Hybrid BM25 + vector search            │
│ • Bias chain detection           │ • Cross-encoder reranking                │
│ • Strategy performance tracking  │ • Outcome-weighted retrieval             │
│ • Conviction calibration         │ • Bias history injection                 │
│ • Portfolio risk correlation     │ • Counter-argument retrieval             │
│ • Learning loop integration      │ • Pattern-to-outcome matching            │
│ • Graph analytics (centrality)   │ • Position-aware context                 │
├──────────────────────────────────┴──────────────────────────────────────────┤
│                      Unified Hybrid Layer (Phase 12)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ • Graph-guided RAG search • Unified trading context • Skills integration    │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Dependencies

**Existing Infrastructure (No Changes)**:
- Neo4j 5 (nexus-neo4j) — port 7475 (http), 7688 (bolt)
- PostgreSQL + pgvector (nexus-postgres) — port 5433
- Ollama (host) — port 11434

**Deferred Infrastructure (IPLAN-002, Phase 9+)**:
- Redis 7 (nexus-redis) — port 6379 (for RAG query caching, not needed until >100 queries/day)

**New Python Dependencies**:
```
# Core - use >= for flexibility in early development
neo4j>=5.15.0                    # Neo4j Python driver
litellm>=1.40.0                  # Unified LLM/embedding API
fastapi>=0.109.0                 # Webhook APIs (optional, for MCP servers)
uvicorn>=0.27.0                  # ASGI server (optional, for MCP servers)
tiktoken>=0.5.2                  # Token estimation
pyyaml>=6.0.1                    # YAML parsing

# Rate limiting & resilience
ratelimit>=2.2.1                 # Rate limiting decorator
tenacity>=8.2.3                  # Retry with backoff

# Deferred to IPLAN-002 (Phase 9+):
# sentence-transformers>=2.3.1   # Cross-encoder reranking (~2GB PyTorch)
# redis>=5.0.1                   # Distributed caching (lru_cache sufficient for single-user)
# numpy>=1.26.3                  # Graph analytics
```

---

## Phase 1: Foundation — Schema + Package Structure (4-6 hrs)

### 1.1 Create Package Structure

```bash
# Create directories
mkdir -p /opt/data/trading_light_pilot/trader/graph
mkdir -p /opt/data/trading_light_pilot/trader/graph/tests/fixtures/expected_extractions
mkdir -p /opt/data/trading_light_pilot/trader/graph/migrations
mkdir -p /opt/data/trading_light_pilot/trader/rag
mkdir -p /opt/data/trading_light_pilot/trader/rag/tests/fixtures/expected_chunks
mkdir -p /opt/data/trading_light_pilot/trader/db
mkdir -p /opt/data/trading_light_pilot/mcp_trading_graph/tools
mkdir -p /opt/data/trading_light_pilot/mcp_trading_rag/tools
```

### 1.2 Shared Utilities

| File | Purpose |
|------|---------|
| `trader/utils.py` | `is_real_document()` — shared by graph/extract.py and rag/embed.py |

> **Important**: `is_real_document()` MUST be defined once in `trader/utils.py` and imported
> by both modules. Do not duplicate this function.

### 1.3 Graph Package Files

| File | Purpose |
|------|---------|
| `graph/__init__.py` | Package init, `SCHEMA_VERSION`, `EXTRACT_VERSION`, exports |
| `graph/schema.py` | Neo4j schema init (constraints, indexes, full-text) |
| `graph/layer.py` | `TradingGraph` class (connect, MERGE, query) |
| `graph/prompts.py` | Domain-specific extraction prompts |
| `graph/extract.py` | Two-pass entity/relationship extraction |
| `graph/normalize.py` | Dedup, name standardization, alias resolution, disambiguation |
| `graph/aliases.yaml` | Ticker/company alias table |
| `graph/field_mappings.yaml` | Extraction fields by document type |
| `graph/query.py` | Preset query patterns for CLI |
| `graph/config.yaml` | Extraction settings (Ollama, OpenRouter, timeouts) |
| `graph/models.py` | Data classes: `ExtractionResult`, `EntityExtraction`, etc. |
| `graph/exceptions.py` | `GraphUnavailableError`, `ExtractionError` |
| `graph/webhook.py` | FastAPI HTTP endpoints |

### 1.4 RAG Package Files

| File | Purpose |
|------|---------|
| `rag/__init__.py` | Package init, `RAG_VERSION`, `EMBED_DIMS`, exports |
| `rag/schema.py` | pgvector extension + tables init |
| `rag/embed.py` | Full pipeline: parse → chunk → embed → store |
| `rag/embedding_client.py` | Ollama + LiteLLM fallback client |
| `rag/chunk.py` | YAML section-level chunking |
| `rag/flatten.py` | YAML-to-text conversion rules |
| `rag/section_mappings.yaml` | Sections to embed by document type |
| `rag/search.py` | Semantic search with filters |
| `rag/hybrid.py` | Combined vector + graph context builder |
| `rag/ollama.py` | Ollama-specific API client |
| `rag/config.yaml` | Embedding settings (model, fallback chain) |
| `rag/models.py` | Data classes: `SearchResult`, `EmbedResult`, etc. |
| `rag/exceptions.py` | `RAGUnavailableError`, `EmbeddingUnavailableError` |
| `rag/webhook.py` | FastAPI HTTP endpoints |
| `rag/tokens.py` | Token estimation using tiktoken |

### 1.5 MCP Server Structure

```
mcp_trading_graph/
├── __init__.py
├── server.py              # MCP server entry point
└── tools/
    ├── __init__.py
    ├── extract.py         # graph_extract, graph_extract_text tools
    ├── query.py           # graph_query, graph_search, graph_peers, graph_risks
    └── status.py          # graph_status tool

mcp_trading_rag/
├── __init__.py
├── server.py              # MCP server entry point
└── tools/
    ├── __init__.py
    ├── search.py          # rag_search, rag_similar tools
    ├── embed.py           # rag_embed tool
    └── context.py         # rag_hybrid_context tool
```

### 1.6 Neo4j Plugins Setup (APOC + GDS)

**APOC (Required)** - Utility procedures for data manipulation:

```bash
# Download APOC plugin matching Neo4j version
# For Neo4j 5.x, use APOC 5.x
wget -O /path/to/neo4j/plugins/apoc-5.15.0-core.jar \
  https://github.com/neo4j/apoc/releases/download/5.15.0/apoc-5.15.0-core.jar
```

**neo4j.conf additions**:
```properties
# APOC configuration
dbms.security.procedures.unrestricted=apoc.*
dbms.security.procedures.allowlist=apoc.*
```

**GDS (Deferred to IPLAN-002, Phase 11)** - Graph Data Science algorithms:

> **Note**: GDS is deferred to IPLAN-002. All core functionality (Phases 1-8) works with APOC only.
> GDS Community Edition supports PageRank, Louvain, WCC, Label Propagation, and a few others.
> GDS Enterprise features (e.g., node similarity, graph sage) are NOT available without a paid license.
> The `most_connected()` query in Phase 11 uses plain Cypher and works without GDS.

```bash
# DEFERRED — install only when IPLAN-002 Phase 11 begins
# For Neo4j Community Edition - manual installation
# wget -O /path/to/neo4j/plugins/neo4j-graph-data-science-2.6.0.jar \
#   https://graphdatascience.ninja/neo4j-graph-data-science-2.6.0.jar
```

**Docker-compose.yml** (current — APOC only, no GDS):
```yaml
services:
  nexus-neo4j:
    image: neo4j:5-community
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASS}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*
    volumes:
      - neo4j_data:/data
```

**GDS Graph Projection** (deferred to IPLAN-002, Phase 11 — requires GDS plugin):
```cypher
// DEFERRED — Run only after GDS plugin is installed and data is loaded
// Create in-memory graph projection for analytics
CALL gds.graph.project(
  'trading-graph',
  ['Ticker', 'Company', 'Strategy', 'Bias', 'Trade', 'Pattern', 'Risk', 'Learning'],
  {
    ISSUED: {orientation: 'UNDIRECTED'},
    COMPETES_WITH: {orientation: 'UNDIRECTED'},
    WORKS_FOR: {orientation: 'NATURAL'},
    DETECTED_IN: {orientation: 'NATURAL'},
    TRADED: {orientation: 'NATURAL'},
    DERIVED_FROM: {orientation: 'NATURAL'},
    ADDRESSES: {orientation: 'NATURAL'},
    THREATENS: {orientation: 'NATURAL'}
  }
);
```

### 1.7 Neo4j Schema (db/neo4j_schema.cypher)

```cypher
// ============================================================
// CONSTRAINTS (16 entity types)
// ============================================================

// Market Entities
CREATE CONSTRAINT ticker_symbol IF NOT EXISTS FOR (t:Ticker) REQUIRE t.symbol IS UNIQUE;
CREATE CONSTRAINT company_name IF NOT EXISTS FOR (c:Company) REQUIRE c.name IS UNIQUE;
CREATE CONSTRAINT sector_name IF NOT EXISTS FOR (s:Sector) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT industry_name IF NOT EXISTS FOR (i:Industry) REQUIRE i.name IS UNIQUE;
CREATE CONSTRAINT product_name IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS UNIQUE;

// Trading Concepts
CREATE CONSTRAINT strategy_name IF NOT EXISTS FOR (s:Strategy) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT structure_name IF NOT EXISTS FOR (s:Structure) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT pattern_name IF NOT EXISTS FOR (p:Pattern) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT bias_name IF NOT EXISTS FOR (b:Bias) REQUIRE b.name IS UNIQUE;
CREATE CONSTRAINT signal_name IF NOT EXISTS FOR (s:Signal) REQUIRE s.name IS UNIQUE;
CREATE CONSTRAINT risk_name IF NOT EXISTS FOR (r:Risk) REQUIRE r.name IS UNIQUE;

// Events (no unique constraint - multiple events can have same type)
// EarningsEvent, Catalyst, Conference, MacroEvent indexed but not unique

// People
CREATE CONSTRAINT executive_name IF NOT EXISTS FOR (e:Executive) REQUIRE e.name IS UNIQUE;
CREATE CONSTRAINT analyst_name IF NOT EXISTS FOR (a:Analyst) REQUIRE a.name IS UNIQUE;

// Analysis & Learning
CREATE CONSTRAINT analysis_id IF NOT EXISTS FOR (a:Analysis) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT trade_id IF NOT EXISTS FOR (t:Trade) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT learning_id IF NOT EXISTS FOR (l:Learning) REQUIRE l.id IS UNIQUE;

// Provenance
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;

// Time
CREATE CONSTRAINT timeframe_name IF NOT EXISTS FOR (t:Timeframe) REQUIRE t.name IS UNIQUE;

// Metrics (no unique - multiple price levels possible)
CREATE CONSTRAINT financial_metric_name IF NOT EXISTS FOR (f:FinancialMetric) REQUIRE f.name IS UNIQUE;

// ============================================================
// INDEXES
// ============================================================

// High-traffic lookups
CREATE INDEX ticker_symbol_idx IF NOT EXISTS FOR (t:Ticker) ON (t.symbol);
CREATE INDEX company_name_idx IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX sector_name_idx IF NOT EXISTS FOR (s:Sector) ON (s.name);

// Temporal queries
CREATE INDEX earnings_date_idx IF NOT EXISTS FOR (e:EarningsEvent) ON (e.date);
CREATE INDEX catalyst_date_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.date);
CREATE INDEX analysis_created_idx IF NOT EXISTS FOR (a:Analysis) ON (a.created_at);
CREATE INDEX trade_created_idx IF NOT EXISTS FOR (t:Trade) ON (t.created_at);

// Type-based filtering
CREATE INDEX analysis_type_idx IF NOT EXISTS FOR (a:Analysis) ON (a.type);
CREATE INDEX catalyst_type_idx IF NOT EXISTS FOR (c:Catalyst) ON (c.type);
CREATE INDEX trade_outcome_idx IF NOT EXISTS FOR (t:Trade) ON (t.outcome);
CREATE INDEX learning_category_idx IF NOT EXISTS FOR (l:Learning) ON (l.category);

// Extraction tracking
CREATE INDEX analysis_extract_ver_idx IF NOT EXISTS FOR (a:Analysis) ON (a.extraction_version);

// ============================================================
// FULL-TEXT SEARCH
// ============================================================

CALL db.index.fulltext.createNodeIndex(
  'entitySearch',
  ['Ticker', 'Company', 'Executive', 'Product', 'Pattern', 'Risk', 'Strategy', 'Bias'],
  ['name', 'symbol', 'description']
);
```

### 1.8 Relationship Types (20 types)

```cypher
// ============================================================
// RELATIONSHIP TYPES WITH PROPERTIES
// ============================================================

// STRUCTURAL (5)
// (Company)-[:ISSUED]->(Ticker)
// (Company)-[:IN_SECTOR]->(Sector)
// (Company)-[:IN_INDUSTRY]->(Industry)
// (Company)-[:MAKES]->(Product)
// (Executive)-[:LEADS {title, since}]->(Company)

// COMPETITIVE (4)
// (Company)-[:COMPETES_WITH]->(Company)
// (Company)-[:SUPPLIES_TO]->(Company)
// (Company)-[:CUSTOMER_OF]->(Company)
// (Ticker)-[:CORRELATED_WITH {coefficient, period, calculated_at}]->(Ticker)

// TRADING (4)
// (Strategy)-[:WORKS_FOR {win_rate, sample_size, last_used}]->(Ticker)
// (Strategy)-[:USES]->(Structure)
// (Bias)-[:DETECTED_IN {severity, impact_description}]->(Trade)
// (Pattern)-[:OBSERVED_IN]->(Ticker)
// (Signal)-[:INDICATES]->(Ticker)

// EVENTS (3)
// (Ticker)-[:HAS_EARNINGS]->(EarningsEvent)
// (Ticker)-[:AFFECTED_BY]->(Catalyst)
// (Ticker)-[:EXPOSED_TO]->(MacroEvent)
// (Risk)-[:THREATENS]->(Ticker)

// ANALYSIS (3)
// (Analysis)-[:ANALYZES]->(Ticker)
// (Analysis)-[:MENTIONS]->(any entity)
// (Trade)-[:BASED_ON]->(Analysis)
// (Trade)-[:TRADED]->(Ticker)
// (Analyst)-[:COVERS {rating, target_price, updated_at}]->(Ticker)

// LEARNING (3)
// (Learning)-[:DERIVED_FROM]->(Trade)
// (Learning)-[:ADDRESSES]->(Bias)
// (Learning)-[:UPDATES]->(Strategy)
// (Risk)-[:MITIGATED_BY]->(Strategy)

// PROVENANCE (1)
// (any)-[:EXTRACTED_FROM {field_path, confidence, extracted_at}]->(Document)
```

### 1.9 pgvector Schema (db/rag_schema.sql)

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- DOCUMENTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS nexus.rag_documents (
    id              SERIAL PRIMARY KEY,
    doc_id          VARCHAR(100) NOT NULL UNIQUE,    -- _meta.id (e.g., "EA-NVDA-Q4-2024")
    file_path       VARCHAR(500) NOT NULL,           -- Relative path from project root
    doc_type        VARCHAR(50) NOT NULL,            -- earnings-analysis, stock-analysis, etc.
    ticker          VARCHAR(10),                     -- Primary ticker (NULL for research/macro)

    -- Temporal
    doc_date        DATE,                            -- Analysis/trade date
    quarter         VARCHAR(20),                     -- Q4-FY2025 (for earnings)

    -- Processing state
    chunk_count     INTEGER DEFAULT 0,
    embed_version   VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    embed_model     VARCHAR(50) NOT NULL DEFAULT 'nomic-embed-text',

    -- Source tracking
    file_hash       VARCHAR(64),                     -- SHA-256 of source file

    tags            TEXT[],

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- CHUNKS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS nexus.rag_chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          INTEGER NOT NULL REFERENCES nexus.rag_documents(id) ON DELETE CASCADE,

    -- Chunk identity
    section_path    VARCHAR(200) NOT NULL,           -- YAML key path
    section_label   VARCHAR(100) NOT NULL,           -- Human-readable label
    chunk_index     SMALLINT NOT NULL DEFAULT 0,     -- For split sections

    -- Content
    content         TEXT NOT NULL,                   -- Flattened text
    content_tokens  INTEGER,                         -- Token count

    -- Embedding
    embedding       vector(768) NOT NULL,            -- nomic-embed-text output

    -- Denormalized for filtered search (avoids JOINs)
    doc_type        VARCHAR(50) NOT NULL,
    ticker          VARCHAR(10),
    doc_date        DATE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- EMBEDDING LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS nexus.rag_embed_log (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          INTEGER REFERENCES nexus.rag_documents(id),
    file_path       VARCHAR(500),
    action          VARCHAR(20) NOT NULL,            -- 'embed', 'reembed', 'delete'
    chunks_created  INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    embed_model     VARCHAR(50),
    embed_version   VARCHAR(20),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Document lookups
CREATE INDEX IF NOT EXISTS idx_rag_docs_type ON nexus.rag_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_docs_ticker ON nexus.rag_documents(ticker);
CREATE INDEX IF NOT EXISTS idx_rag_docs_date ON nexus.rag_documents(doc_date);
CREATE INDEX IF NOT EXISTS idx_rag_docs_tags ON nexus.rag_documents USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_rag_docs_version ON nexus.rag_documents(embed_version);

-- Vector similarity (IVFFlat for <100K chunks)
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding
    ON nexus.rag_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- Filtered search
CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc ON nexus.rag_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_ticker ON nexus.rag_chunks(ticker);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_type ON nexus.rag_chunks(doc_type);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_section ON nexus.rag_chunks(section_label);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_date ON nexus.rag_chunks(doc_date);

-- Unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_rag_chunks_unique
    ON nexus.rag_chunks(doc_id, section_path, chunk_index);

-- ============================================================
-- INDEX TUNING THRESHOLDS
-- ============================================================
-- < 10,000 chunks:    IVFFlat with lists = 50 (current)
-- 10,000 - 100,000:   IVFFlat with lists = 100
-- > 100,000:          Switch to HNSW with m = 16, ef_construction = 64
--
-- To upgrade to HNSW:
-- DROP INDEX IF EXISTS nexus.idx_rag_chunks_embedding;
-- CREATE INDEX idx_rag_chunks_embedding
--     ON nexus.rag_chunks USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
```

### 1.10 Configuration Files

**graph/config.yaml**:
```yaml
schema_version: "1.0.0"
extract_version: "1.0.0"

neo4j:
  uri: "bolt://localhost:7688"
  user: "neo4j"
  password: "${NEO4J_PASS}"
  database: "neo4j"

extraction:
  default_extractor: ollama
  fallback_chain:
    - ollama           # Try local first ($0)
    - openrouter       # Fallback to cloud if Ollama fails
  timeout_seconds: 30

  # Confidence thresholds
  commit_threshold: 0.7       # >= 0.7: commit normally
  flag_threshold: 0.5         # 0.5-0.7: commit with needs_review flag
  skip_threshold: 0.5         # < 0.5: do not commit

  ollama:
    base_url: "http://localhost:11434"
    model: "qwen3:8b"

  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-3-5-sonnet"
    fallback_model: "anthropic/claude-3-haiku"

  claude_api:
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-3-5-sonnet-20241022"

logging:
  extraction_log: "logs/graph_extractions.jsonl"
  pending_commits: "logs/pending_commits.jsonl"
```

**rag/config.yaml**:
```yaml
rag_version: "1.0.0"
embed_dims: 768

embedding:
  default_provider: ollama
  fallback_chain:
    - ollama           # Try local first ($0)
    - openrouter       # Fallback to cloud
  timeout_seconds: 30
  dimensions: 768      # All providers must match

  ollama:
    base_url: "http://localhost:11434"
    model: "nomic-embed-text"

  openrouter:
    api_key: "${OPENROUTER_API_KEY}"
    model: "openai/text-embedding-3-small"
    dimensions: 768    # Request truncated output

  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "text-embedding-3-small"
    dimensions: 768

chunking:
  max_tokens: 1500
  min_tokens: 50       # Skip very short sections

logging:
  embed_log: "logs/rag_embed.jsonl"
```

### 1.11 Field Mappings for Graph Extraction

**graph/field_mappings.yaml**:
```yaml
# Fields to extract entities from, by document type
# Each field path supports dot notation for nested keys

earnings-analysis:
  extract_fields:
    - "phase1_preparation.key_questions"
    - "phase2_fundamentals.customer_demand.customers[].key_quote"
    - "phase2_fundamentals.competitive_context.vs_competitors"
    - "phase2_fundamentals.competitive_context.market_position"
    - "phase2_fundamentals.business_performance.guidance_summary"
    - "phase3_technicals.support_resistance"
    - "phase4_trade_structure.thesis.detailed"
    - "phase5_risk_management.risks[].risk"
    - "steel_man.bear_case"
    - "steel_man.bull_case"
    - "recent_developments[].event"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"
    - "ticker"
    - "earnings_date"

stock-analysis:
  extract_fields:
    - "thesis.detailed"
    - "thesis.edge"
    - "catalysts[].description"
    - "catalysts[].expected_impact"
    - "what_is_priced_in.bull_case"
    - "what_is_priced_in.bear_case"
    - "bias_checks[].analysis"
    - "decision_rationale"
    - "risks[].risk"
    - "risks[].mitigation"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"
    - "ticker"

trade-journal:
  extract_fields:
    - "thesis.summary"
    - "thesis.edge"
    - "thesis.catalyst"
    - "execution.entry_rationale"
    - "execution.exit_rationale"
    - "review.what_worked[]"
    - "review.what_failed[]"
    - "review.lessons[]"
    - "review.biases_detected[].bias"
    - "review.biases_detected[].impact"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"

post-trade-review:
  extract_fields:
    - "analysis.outcome_vs_thesis"
    - "analysis.execution_quality"
    - "lessons[].lesson"
    - "lessons[].category"
    - "framework_updates[].update"
    - "bias_review[].bias"
    - "bias_review[].manifestation"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"

research-analysis:
  extract_fields:
    - "key_finding"
    - "thesis"
    - "data_points[].quote"
    - "data_points[].implication"
    - "risks[].risk"
    - "risks[].mitigation"
    - "implications[].implication"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"

strategy:
  extract_fields:
    - "overview.description"
    - "edge_source"
    - "entry_rules[].rule"
    - "exit_rules[].rule"
    - "known_weaknesses[].weakness"
    - "known_weaknesses[].countermeasure"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"

learning:
  extract_fields:
    - "pattern.description"
    - "pattern.behavior"
    - "root_cause.analysis"
    - "countermeasure.rule"
    - "evidence.observations[]"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"

ticker-profile:
  extract_fields:
    - "company.description"
    - "company.business_model"
    - "what_works[]"
    - "what_to_avoid[]"
    - "watch_out_for[].risk"
    - "trading_patterns.tendencies"
    - "notes[].note"
  skip_fields:
    - "_meta"
    - "_graph"
    - "_links"
```

### 1.12 Section Mappings for RAG Embedding

**rag/section_mappings.yaml**:
```yaml
# Sections to embed, by document type
# Sections not listed are skipped

earnings-analysis:
  sections:
    - path: "phase1_preparation"
      label: "Preparation"
    - path: "phase2_fundamentals.customer_demand"
      label: "Customer Demand"
    - path: "phase2_fundamentals.competitive_context"
      label: "Competitive Context"
    - path: "phase2_fundamentals.business_performance"
      label: "Business Performance"
    - path: "phase3_technicals"
      label: "Technical Analysis"
    - path: "phase4_trade_structure"
      label: "Trade Structure"
    - path: "phase5_risk_management"
      label: "Risk Management"
    - path: "thesis"
      label: "Thesis"
    - path: "steel_man"
      label: "Steel Man Arguments"
  skip:
    - "_meta"
    - "_graph"
    - "_links"
    - "ticker"
    - "earnings_date"

stock-analysis:
  sections:
    - path: "thesis"
      label: "Thesis"
    - path: "catalysts"
      label: "Catalysts"
    - path: "risks"
      label: "Risks"
    - path: "technicals"
      label: "Technical Analysis"
    - path: "fundamentals"
      label: "Fundamentals"
    - path: "competitive_position"
      label: "Competitive Position"
    - path: "sentiment"
      label: "Sentiment"
    - path: "what_is_priced_in"
      label: "What Is Priced In"
    - path: "bias_checks"
      label: "Bias Checks"
  skip:
    - "_meta"
    - "_graph"
    - "_links"
    - "ticker"

trade-journal:
  sections:
    - path: "thesis"
      label: "Thesis"
    - path: "execution"
      label: "Execution"
    - path: "results"
      label: "Results"
    - path: "review"
      label: "Review"
  skip:
    - "_meta"
    - "_graph"
    - "_links"

post-trade-review:
  sections:
    - path: "analysis"
      label: "Analysis"
    - path: "lessons"
      label: "Lessons"
    - path: "framework_updates"
      label: "Framework Updates"
    - path: "bias_review"
      label: "Bias Review"
  skip:
    - "_meta"
    - "_graph"
    - "_links"

research-analysis:
  sections:
    - path: "thesis"
      label: "Thesis"
    - path: "findings"
      label: "Findings"
    - path: "data_points"
      label: "Data Points"
    - path: "implications"
      label: "Implications"
    - path: "risks"
      label: "Risks"
  skip:
    - "_meta"
    - "_graph"
    - "_links"

strategy:
  sections:
    - path: "overview"
      label: "Overview"
    - path: "edge_source"
      label: "Edge Source"
    - path: "entry_rules"
      label: "Entry Rules"
    - path: "exit_rules"
      label: "Exit Rules"
    - path: "risk_management"
      label: "Risk Management"
    - path: "known_weaknesses"
      label: "Known Weaknesses"
    - path: "performance"
      label: "Performance"
  skip:
    - "_meta"
    - "_graph"
    - "_links"

learning:
  sections:
    - path: "pattern"
      label: "Pattern"
    - path: "root_cause"
      label: "Root Cause"
    - path: "countermeasure"
      label: "Countermeasure"
    - path: "evidence"
      label: "Evidence"
    - path: "application"
      label: "Application"
  skip:
    - "_meta"
    - "_graph"
    - "_links"

ticker-profile:
  sections:
    - path: "company"
      label: "Company Overview"
    - path: "what_works"
      label: "What Works"
    - path: "what_to_avoid"
      label: "What to Avoid"
    - path: "watch_out_for"
      label: "Watch Out For"
    - path: "trading_patterns"
      label: "Trading Patterns"
    - path: "notes"
      label: "Notes"
  skip:
    - "_meta"
    - "_graph"
    - "_links"
```

### 1.13 Update requirements.txt

```bash
cat >> /opt/data/trading_light_pilot/trader/requirements.txt << 'EOF'
neo4j>=5.0.0
litellm>=1.40.0
fastapi>=0.100.0
uvicorn>=0.23.0
tiktoken>=0.5.0
EOF
```

### 1.14 Phase 1 Deliverables

- [ ] Directory structure created
- [ ] `db/neo4j_schema.cypher` with all constraints/indexes/relationships
- [ ] `db/rag_schema.sql` with pgvector tables and index tuning comments
- [ ] `graph/config.yaml` with full settings
- [ ] `rag/config.yaml` with full settings
- [ ] `graph/field_mappings.yaml` for all document types
- [ ] `rag/section_mappings.yaml` for all document types
- [ ] Updated `requirements.txt`
- [ ] MCP server directory structure

---

## Phase 2: Graph Layer Implementation (8-12 hrs)

### 2.1 Data Classes (graph/models.py)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class EntityExtraction:
    """Single extracted entity."""
    type: str                    # PascalCase: Ticker, Company, Bias, etc.
    value: str                   # Title Case: "NVIDIA", "Loss Aversion"
    confidence: float            # 0.0 - 1.0
    evidence: str                # Quote from source text
    properties: dict = field(default_factory=dict)
    needs_review: bool = False   # True if 0.5 <= confidence < 0.7

@dataclass
class RelationExtraction:
    """Single extracted relationship."""
    from_entity: EntityExtraction
    relation: str                # UPPER_SNAKE: COMPETES_WITH, AFFECTED_BY
    to_entity: EntityExtraction
    confidence: float
    evidence: str
    properties: dict = field(default_factory=dict)

@dataclass
class ExtractionResult:
    """Complete extraction result for a document."""
    source_doc_id: str
    source_doc_type: str
    source_file_path: str
    source_text_hash: str
    extracted_at: datetime
    extractor: str               # ollama, claude, openrouter
    extraction_version: str

    entities: list[EntityExtraction] = field(default_factory=list)
    relations: list[RelationExtraction] = field(default_factory=list)

    # Stats
    fields_processed: int = 0
    fields_failed: int = 0
    committed: bool = False
    error_message: str | None = None

@dataclass
class GraphStats:
    """Graph statistics for status command."""
    node_counts: dict[str, int]      # {"Ticker": 45, "Company": 32, ...}
    edge_counts: dict[str, int]      # {"ISSUED": 45, "COMPETES_WITH": 12, ...}
    total_nodes: int
    total_edges: int
    last_extraction: datetime | None
```

### 2.2 Exceptions (graph/exceptions.py)

```python
class GraphError(Exception):
    """Base exception for graph operations."""
    pass

class GraphUnavailableError(GraphError):
    """Neo4j is not reachable."""
    pass

class ExtractionError(GraphError):
    """Entity/relationship extraction failed."""
    pass

class NormalizationError(GraphError):
    """Entity normalization failed."""
    pass

class SchemaError(GraphError):
    """Schema initialization or migration failed."""
    pass
```

### 2.3 TradingGraph Class (graph/layer.py)

```python
class TradingGraph:
    """Neo4j graph layer for trading knowledge."""

    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """Initialize connection parameters from config or args."""

    def __enter__(self) -> "TradingGraph":
        """Context manager entry - connect to Neo4j."""

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""

    def connect(self) -> None:
        """Establish Neo4j connection."""

    def close(self) -> None:
        """Close Neo4j connection."""

    def health_check(self) -> bool:
        """Check if Neo4j is reachable."""

    # --- Schema Management ---

    def init_schema(self) -> None:
        """Run all constraints and indexes from neo4j_schema.cypher."""

    def reset_schema(self) -> None:
        """Drop all nodes and relationships (dev only)."""

    def migrate(self, target_version: str) -> None:
        """Run migration scripts to target version."""

    # --- Node Operations ---

    def merge_node(self, label: str, key_prop: str, props: dict) -> int:
        """
        MERGE node with properties. Returns node ID.

        Example:
            merge_node("Ticker", "symbol", {"symbol": "NVDA", "name": "NVIDIA"})
        """

    def get_node(self, label: str, key_prop: str, key_value: Any) -> dict | None:
        """Get node by label and key property."""

    # --- Relationship Operations ---

    def merge_relation(
        self,
        from_node: tuple[str, Any],  # (label, key_value)
        rel_type: str,
        to_node: tuple[str, Any],
        props: dict = None
    ) -> None:
        """
        MERGE relationship between nodes.

        Example:
            merge_relation(("Company", "NVIDIA"), "ISSUED", ("Ticker", "NVDA"))
        """

    # --- Query Operations ---

    def find_related(self, symbol: str, depth: int = 2) -> list[dict]:
        """Find all nodes within N hops of a ticker."""

    def get_sector_peers(self, symbol: str) -> list[dict]:
        """Get tickers in the same sector."""

    def get_competitors(self, symbol: str) -> list[dict]:
        """Get companies that compete with this ticker's company."""

    def get_risks(self, symbol: str) -> list[dict]:
        """Get all risks threatening this ticker."""

    def get_bias_history(self, bias_name: str = None) -> list[dict]:
        """Get bias occurrences across trades."""

    def get_strategy_performance(self, strategy_name: str = None) -> list[dict]:
        """Get strategy win rates by ticker."""

    def get_learning_loop(self, bias_name: str) -> list[dict]:
        """Bias → Trade → Learning path."""

    def get_supply_chain(self, symbol: str) -> list[dict]:
        """Get suppliers and customers for a company."""

    def get_ticker_context(self, symbol: str) -> dict:
        """
        Get comprehensive context for a ticker:
        - Sector peers
        - Competitors
        - Known risks
        - Strategies that work
        - Past biases in trades
        """

    def run_cypher(self, query: str, params: dict = None) -> list[dict]:
        """Execute raw Cypher query."""

    # --- Maintenance ---

    def get_stats(self) -> GraphStats:
        """Get node/edge counts by type."""

    def prune_old(self, days: int = 365) -> int:
        """Archive nodes older than N days (relabel to :Archived)."""

    def dedupe_entities(self) -> int:
        """Merge duplicate entities based on normalization rules."""

    def validate_constraints(self) -> list[str]:
        """Check for constraint violations."""
```

### 2.4 Extraction Prompts (graph/prompts.py)

```python
ENTITY_EXTRACTION_PROMPT = """
Extract trading-relevant entities from this text. Return JSON only.

ENTITY TYPES (use exactly these labels):
- Ticker: Stock symbols (NVDA, AAPL, MSFT)
- Company: Company names (NVIDIA, Apple Inc, Microsoft)
- Executive: Named executives with titles (Jensen Huang CEO)
- Analyst: Named analysts with firms (Dan Ives Wedbush)
- Product: Products/services (Blackwell GPU, iPhone, Azure)
- Catalyst: Events that move stock price (earnings beat, FDA approval, product launch)
- Sector: Market sectors (Technology, Healthcare, Financials)
- Industry: Specific industries (Semiconductors, Cloud Computing, Biotechnology)
- Pattern: Trading patterns (gap and go, earnings drift, mean reversion)
- Bias: Cognitive biases (loss aversion, confirmation bias, recency bias)
- Strategy: Trading strategies (earnings momentum, breakout, swing trade)
- Structure: Trade structures (bull call spread, iron condor, shares)
- Risk: Identified risks (concentration risk, macro exposure, execution risk)
- Signal: Trading signals (RSI oversold, volume breakout, MACD cross)
- EarningsEvent: Quarterly/annual reports (Q4 2025, FY 2025)
- MacroEvent: Macro events (Fed rate decision, CPI release, tariff announcement)
- Timeframe: Time horizons (intraday, swing, position)
- FinancialMetric: Metrics (revenue growth, gross margin, EPS)

TEXT:
{text}

Return JSON array:
[{{"type": "...", "value": "...", "confidence": 0.0-1.0, "evidence": "quote from text"}}]

Rules:
- Only extract entities EXPLICITLY mentioned in the text
- Do NOT infer entities not directly stated
- Confidence should reflect how clearly the entity is identified
- Evidence must be a direct quote from the text
"""

RELATION_EXTRACTION_PROMPT = """
Given these entities extracted from a trading document, identify relationships between them.

ENTITIES:
{entities_json}

RELATIONSHIP TYPES (use exactly these):
- ISSUED: Company issued Ticker
- IN_SECTOR: Company belongs to Sector
- IN_INDUSTRY: Company belongs to Industry
- MAKES: Company makes Product
- LEADS: Executive leads Company
- COMPETES_WITH: Company competes with Company
- SUPPLIES_TO: Company supplies to Company
- CUSTOMER_OF: Company is customer of Company
- CORRELATED_WITH: Ticker correlates with Ticker
- COVERS: Analyst covers Ticker
- AFFECTED_BY: Ticker affected by Catalyst
- EXPOSED_TO: Ticker exposed to MacroEvent
- HAS_EARNINGS: Ticker has EarningsEvent
- THREATENS: Risk threatens Ticker
- WORKS_FOR: Strategy works for Ticker
- USES: Strategy uses Structure
- DETECTED_IN: Bias detected in Trade
- OBSERVED_IN: Pattern observed in Ticker
- INDICATES: Signal indicates Ticker
- DERIVED_FROM: Learning derived from Trade
- ADDRESSES: Learning addresses Bias
- UPDATES: Learning updates Strategy
- MITIGATED_BY: Risk mitigated by Strategy
- ANALYZES: Analysis analyzes Ticker
- MENTIONS: Analysis mentions (any entity)
- BASED_ON: Trade based on Analysis
- TRADED: Trade traded Ticker

SOURCE TEXT:
{text}

Return JSON array:
[{{"from": {{"type": "...", "value": "..."}}, "relation": "...", "to": {{"type": "...", "value": "..."}}, "confidence": 0.0-1.0, "evidence": "quote"}}]

Rules:
- Only extract relationships explicitly stated or strongly implied
- Do NOT infer weak or speculative connections
- Confidence should reflect how clearly the relationship is stated
"""
```

### 2.5 Normalization with Disambiguation (graph/normalize.py)

```python
def normalize_entity(entity: dict, aliases: dict, context: str = None) -> dict:
    """
    Apply normalization rules to an extracted entity.

    Rules applied:
    1. Separator standardization (underscores → hyphens)
    2. Case normalization (PascalCase types, Title Case values)
    3. Ticker resolution (company name → ticker symbol)
    4. Alias resolution (GOOG → GOOGL)
    5. Disambiguation (Company vs Ticker, Strategy vs Pattern)
    """

def disambiguate_entity(entity: dict, context: str) -> dict:
    """
    Resolve ambiguous entities based on context.

    Disambiguation rules:
    - Company vs Ticker: $ prefix or price context → Ticker; otherwise Company
    - "Apple" in trading: Default to AAPL unless food/agriculture context
    - Person name only: Look up in alias table; if not found, Executive with needs_review
    - Generic pattern name: Normalize to canonical form ("gap up" → "gap-and-go")
    - Same name different entity: Append disambiguator ("Apple (company)" vs "Apple (product)")
    - Strategy vs Pattern: Strategy has entry/exit rules; Pattern is observed behavior
    """

def resolve_ticker(company_name: str, aliases: dict) -> str | None:
    """Convert company name to ticker symbol using aliases."""

def standardize_separators(value: str) -> str:
    """Convert underscores to hyphens."""

def normalize_case(entity_type: str, value: str) -> tuple[str, str]:
    """PascalCase for types, Title Case for values."""
```

### 2.6 Aliases Table (graph/aliases.yaml)

```yaml
# Ticker aliases (map variations to canonical symbol)
tickers:
  GOOG: GOOGL
  BRK.A: BRK-B
  FB: META

# Company name to ticker mappings
companies:
  "Alphabet": {ticker: GOOGL}
  "Alphabet Inc": {ticker: GOOGL}
  "Google": {ticker: GOOGL}
  "Meta Platforms": {ticker: META}
  "Meta": {ticker: META}
  "Facebook": {ticker: META}
  "NVIDIA": {ticker: NVDA}
  "NVIDIA Corporation": {ticker: NVDA}
  "Apple": {ticker: AAPL}
  "Apple Inc": {ticker: AAPL}
  "Microsoft": {ticker: MSFT}
  "Microsoft Corporation": {ticker: MSFT}
  "Amazon": {ticker: AMZN}
  "Amazon.com": {ticker: AMZN}
  "Tesla": {ticker: TSLA}
  "Tesla Inc": {ticker: TSLA}
  "Advanced Micro Devices": {ticker: AMD}
  "AMD": {ticker: AMD}
  "Netflix": {ticker: NFLX}
  "Netflix Inc": {ticker: NFLX}

# Pattern name canonicalization
patterns:
  "gap up": "gap-and-go"
  "gap down": "gap-and-fade"
  "earnings beat": "earnings-momentum"
  "post-earnings drift": "earnings-drift"
  "PEAD": "earnings-drift"

# Bias name canonicalization
biases:
  "loss aversion": "loss-aversion"
  "confirmation bias": "confirmation-bias"
  "recency bias": "recency-bias"
  "anchoring": "anchoring-bias"
  "FOMO": "fear-of-missing-out"
  "fear of missing out": "fear-of-missing-out"

# Strategy name canonicalization
strategies:
  "earnings play": "earnings-momentum"
  "breakout trade": "breakout"
  "mean reversion": "mean-reversion"
```

### 2.7 Extraction Pipeline (graph/extract.py)

```python
def extract_document(
    file_path: str,
    extractor: str = "ollama",
    commit: bool = True,
    dry_run: bool = False
) -> ExtractionResult:
    """
    Extract entities and relationships from a YAML document.

    Pipeline:
    1. Validate file (must be real document, not template)
    2. Parse YAML
    3. Load field mappings for document type
    4. Pass 1: Entity extraction (per field)
    5. Pass 2: Relationship extraction (whole document)
    6. Normalize all entities
    7. Apply confidence thresholds
    8. Commit to Neo4j (if commit=True and not dry_run)
    9. Log extraction result
    """

def extract_text(
    text: str,
    doc_type: str,
    doc_id: str,
    source_url: str = None,
    extractor: str = "ollama"
) -> ExtractionResult:
    """Extract from raw text (for external content)."""

# NOTE: is_real_document() is defined in a shared utility module.
# See trader/utils.py — imported by both graph/extract.py and rag/embed.py.
# Do NOT duplicate this function.

def _extract_entities_from_field(
    text: str,
    extractor: str,
    timeout: int
) -> list[EntityExtraction]:
    """Pass 1: Extract entities from a single text field."""

def _extract_relations_from_entities(
    entities: list[EntityExtraction],
    full_text: str,
    extractor: str,
    timeout: int
) -> list[RelationExtraction]:
    """Pass 2: Extract relationships given discovered entities."""

def _apply_confidence_thresholds(
    result: ExtractionResult,
    config: dict
) -> ExtractionResult:
    """
    Apply confidence thresholds:
    - >= commit_threshold (0.7): include normally
    - >= flag_threshold (0.5): include with needs_review=True
    - < flag_threshold: exclude from result
    """

def _commit_to_graph(result: ExtractionResult, graph: TradingGraph) -> None:
    """Commit extraction result to Neo4j."""

def _queue_pending_commit(result: ExtractionResult) -> None:
    """Queue failed commit to pending_commits.jsonl for retry."""

# --- Rate Limiting & Retry Logic ---

import re
from pathlib import Path
from ratelimit import limits, sleep_and_retry
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ISO 8601 date pattern for real document detection
REAL_DOC_PATTERN = re.compile(r'\d{8}T\d{4}')
TEMPLATE_NAMES = {'template', 'sample', 'example', 'test'}

def is_real_document(file_path: str) -> bool:
    """
    Check if file is a real document (not a template).

    Real document criteria:
    1. Filename not in TEMPLATE_NAMES
    2. Contains ISO 8601 date pattern (YYYYMMDDTHHMM)
    3. Has _meta.id field (checked during parsing)
    """
    filename = Path(file_path).stem.lower()

    # Reject known template names
    if filename in TEMPLATE_NAMES:
        return False

    # Require ISO 8601 date pattern
    return bool(REAL_DOC_PATTERN.search(filename))

@sleep_and_retry
@limits(calls=45, period=1)  # Ollama rate limit: 45 req/sec
def _call_ollama_rate_limited(prompt: str, model: str, timeout: int) -> str:
    """Rate-limited Ollama API call."""
    import requests
    response = requests.post(
        f"{config.ollama.base_url}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()["response"]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=10, max=30),
    retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError))
)
def _extract_with_retry(text: str, extractor: str, timeout: int) -> list[dict]:
    """
    Extract entities with exponential backoff retry.

    Retry schedule: 10s → 20s → 30s (then fail)
    """
    if extractor == "ollama":
        response = _call_ollama_rate_limited(
            ENTITY_EXTRACTION_PROMPT.format(text=text),
            config.extraction.ollama.model,
            timeout
        )
    else:
        # Claude/OpenRouter path
        response = _call_cloud_llm(text, extractor, timeout)

    return _parse_json_response(response)

def _parse_json_response(response: str) -> list[dict]:
    """Parse JSON from LLM response with error handling."""
    import json

    # Try to extract JSON array from response
    # LLMs sometimes wrap in markdown code blocks
    response = response.strip()
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("json"):
            response = response[4:]

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
        return []
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse JSON response: {e}")
        log.debug(f"Raw response: {response[:500]}")
        return []
```

### 2.8 Preset Queries (graph/query.py)

```python
# Cypher query templates for CLI commands

QUERIES = {
    "biases_for_ticker": """
        MATCH (t:Trade)-[:TRADED]->(tk:Ticker {symbol: $symbol}),
              (b:Bias)-[:DETECTED_IN]->(t)
        RETURN b.name AS bias, count(t) AS occurrences
        ORDER BY occurrences DESC
    """,

    "strategies_for_earnings": """
        MATCH (s:Strategy)-[:WORKS_FOR]->(tk:Ticker),
              (tk)-[:AFFECTED_BY]->(c:Catalyst {type: 'earnings'})
        RETURN s.name AS strategy, collect(DISTINCT tk.symbol) AS tickers, count(*) AS uses
    """,

    "competitive_landscape": """
        MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol: $symbol}),
              (c1)-[:COMPETES_WITH]-(c2:Company)-[:ISSUED]->(t2:Ticker)
        RETURN c2.name AS competitor, t2.symbol AS ticker
    """,

    "risks_open_positions": """
        MATCH (r:Risk)-[:THREATENS]->(tk:Ticker)<-[:TRADED]-(t:Trade)
        WHERE t.status = 'open'
        RETURN r.name AS risk, collect(DISTINCT tk.symbol) AS exposed_tickers
    """,

    "learning_loop": """
        MATCH path = (b:Bias)-[:DETECTED_IN]->(t:Trade)<-[:DERIVED_FROM]-(l:Learning)
        RETURN b.name AS bias, t.id AS trade, l.rule AS lesson
    """,

    "supply_chain": """
        MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol: $symbol}),
              (c2:Company)-[:SUPPLIES_TO]->(c1)
        RETURN c2.name AS supplier
        UNION
        MATCH (c1:Company)-[:ISSUED]->(t:Ticker {symbol: $symbol}),
              (c2:Company)-[:CUSTOMER_OF]->(c1)
        RETURN c2.name AS customer
    """,

    "learnings_for_bias": """
        MATCH (b:Bias {name: $bias_name})<-[:ADDRESSES]-(l:Learning)
        RETURN l.id AS learning_id, l.rule AS rule, l.category AS category
    """,

    "sector_peers": """
        MATCH (t1:Ticker {symbol: $symbol})<-[:ISSUED]-(c1:Company)-[:IN_SECTOR]->(s:Sector),
              (c2:Company)-[:IN_SECTOR]->(s), (c2)-[:ISSUED]->(t2:Ticker)
        WHERE t1 <> t2
        RETURN t2.symbol AS peer, c2.name AS company, s.name AS sector
    """,

    "node_counts": """
        MATCH (n)
        RETURN labels(n)[0] AS label, count(n) AS count
        ORDER BY count DESC
    """,

    "edge_counts": """
        MATCH ()-[r]->()
        RETURN type(r) AS relationship, count(r) AS count
        ORDER BY count DESC
    """
}
```

### 2.9 HTTP Webhook API (graph/webhook.py)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Trading Graph API")

class ExtractRequest(BaseModel):
    file_path: str
    extractor: str = "ollama"
    commit: bool = True

class ExtractTextRequest(BaseModel):
    text: str
    doc_type: str
    doc_id: str
    source_url: str | None = None
    extractor: str = "ollama"

class QueryRequest(BaseModel):
    cypher: str
    params: dict = {}

@app.post("/api/graph/extract")
async def extract_document(req: ExtractRequest):
    """Extract entities from a YAML file."""

@app.post("/api/graph/extract-text")
async def extract_text(req: ExtractTextRequest):
    """Extract entities from raw text."""

@app.get("/api/graph/status")
async def get_status():
    """Get graph statistics."""

@app.post("/api/graph/query")
async def run_query(req: QueryRequest):
    """Execute Cypher query."""

@app.get("/api/graph/ticker/{symbol}")
async def get_ticker_context(symbol: str):
    """Get comprehensive context for a ticker."""

@app.get("/api/graph/health")
async def health_check():
    """Health check endpoint."""
```

### 2.10 Phase 2 Deliverables

- [ ] `graph/__init__.py` with version constants and exports
- [ ] `graph/models.py` — Data classes
- [ ] `graph/exceptions.py` — Exception classes
- [ ] `graph/layer.py` — TradingGraph class with all methods
- [ ] `graph/schema.py` — Schema initializer
- [ ] `graph/prompts.py` — Extraction prompts
- [ ] `graph/extract.py` — Two-pass extraction with confidence thresholds
- [ ] `graph/normalize.py` — Normalization with disambiguation
- [ ] `graph/aliases.yaml` — Alias table
- [ ] `graph/query.py` — Preset queries
- [ ] `graph/webhook.py` — FastAPI endpoints

---

## Phase 3: RAG Layer Implementation (6-10 hrs)

### 3.1 Data Classes (rag/models.py)

```python
from dataclasses import dataclass, field
from datetime import date, datetime

@dataclass
class ChunkResult:
    """Single chunk from a document."""
    section_path: str            # YAML path: "phase2_fundamentals.competitive_context"
    section_label: str           # Human-readable: "Competitive Context"
    chunk_index: int             # 0 for first chunk of section
    content: str                 # Flattened text
    content_tokens: int          # Token count
    prepared_text: str           # With context prefix for embedding

@dataclass
class EmbedResult:
    """Result of embedding a document."""
    doc_id: str
    file_path: str
    doc_type: str
    ticker: str | None
    doc_date: date | None
    chunk_count: int
    embed_model: str
    embed_version: str
    duration_ms: int
    error_message: str | None = None

@dataclass
class SearchResult:
    """Single search result."""
    doc_id: str
    file_path: str
    doc_type: str
    ticker: str | None
    doc_date: date | None
    section_label: str
    content: str
    similarity: float            # 0.0 - 1.0 (cosine similarity)

@dataclass
class HybridContext:
    """Combined vector + graph context for Claude."""
    ticker: str
    vector_results: list[SearchResult]
    graph_context: dict          # From TradingGraph.get_ticker_context()
    formatted: str               # Ready-to-use context block
```

### 3.2 Exceptions (rag/exceptions.py)

```python
class RAGError(Exception):
    """Base exception for RAG operations."""
    pass

class RAGUnavailableError(RAGError):
    """pgvector/PostgreSQL is not reachable."""
    pass

class EmbeddingUnavailableError(RAGError):
    """All embedding providers failed."""
    pass

class ChunkingError(RAGError):
    """Document chunking failed."""
    pass

class EmbedError(RAGError):
    """Embedding pipeline failed."""
    pass
```

### 3.3 Token Estimation (rag/tokens.py)

```python
import tiktoken

# Use cl100k_base (GPT-4/Claude tokenizer approximation)
_encoder = tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str) -> int:
    """Estimate token count for text."""
    return len(_encoder.encode(text))

def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token limit."""
    tokens = _encoder.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _encoder.decode(tokens[:max_tokens])
```

### 3.4 YAML Flattening Rules (rag/flatten.py)

```python
def yaml_to_text(key: str, value: Any, depth: int = 0) -> str:
    """
    Convert YAML structure to readable text for embedding.

    Flattening rules:
    - key: value           → "Key: value"
    - key: [a, b, c]       → "Key: a, b, c"
    - key: [{k1: v1}, ...] → "Key:\n- k1: v1\n- ..."
    - nested dict          → "Parent — Child: value"
    - null / empty         → skip entirely
    - numbers              → format with context (e.g., "75%" for margin)
    """

def humanize_key(key: str) -> str:
    """
    Convert YAML key to human-readable label.

    Examples:
    - "revenue_trend_8q" → "Revenue Trend (8Q)"
    - "phase2_fundamentals" → "Phase 2 Fundamentals"
    - "yoy_pct" → "YoY %"
    """

def flatten_list(items: list, item_formatter: callable = None) -> str:
    """Flatten a list to comma-separated or bullet points."""

def flatten_dict_list(items: list[dict]) -> str:
    """Flatten a list of dicts to formatted lines."""
```

### 3.5 Text Preparation (rag/chunk.py)

```python
def prepare_chunk_text(
    section_label: str,
    content: str,
    ticker: str | None,
    doc_type: str
) -> str:
    """
    Add context prefix to improve embedding relevance.

    Format: [doc_type] [ticker] [section_label]\n{content}

    Example:
    [earnings-analysis] [NVDA] [Competitive Context]
    Compare ABSOLUTE DOLLARS, not percentages. NVDA adding $17B vs AMD...
    """
    prefix_parts = [f"[{doc_type}]"]
    if ticker:
        prefix_parts.append(f"[{ticker}]")
    prefix_parts.append(f"[{section_label}]")
    prefix = " ".join(prefix_parts)
    return f"{prefix}\n{content}"

def chunk_yaml_document(
    file_path: str,
    section_mappings: dict,
    max_tokens: int = 1500,
    min_tokens: int = 50
) -> list[ChunkResult]:
    """
    Split YAML document into semantic chunks.

    Pipeline:
    1. Parse YAML
    2. Get section mappings for this doc type
    3. Extract and flatten each section
    4. Split large sections (>max_tokens) into sub-chunks
    5. Skip very small sections (<min_tokens)
    6. Prepare text with context prefix
    """

def chunk_yaml_section(
    key: str,
    value: Any,
    section_label: str,
    max_tokens: int = 1500
) -> list[ChunkResult]:
    """
    Split a single YAML section into chunks.

    If section exceeds max_tokens:
    - If dict: split by sub-keys
    - If list: split into groups
    - If text: split by sentences/paragraphs
    """
```

### 3.6 Embedding Client (rag/embedding_client.py)

```python
from litellm import embedding as litellm_embedding
import requests

class EmbeddingClient:
    """Embedding with Ollama-first, LiteLLM/OpenRouter fallback."""

    def __init__(self, config: dict):
        self.config = config
        self.fallback_chain = config["embedding"]["fallback_chain"]
        self.dimensions = config["embedding"]["dimensions"]

    def get_embedding(self, text: str) -> list[float]:
        """
        Get embedding vector for text.
        Tries each provider in fallback chain until success.
        """
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

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Batch embedding for multiple texts."""

    def _ollama_embed(self, text: str) -> list[float]:
        """Local Ollama embedding ($0)."""
        cfg = self.config["embedding"]["ollama"]
        resp = requests.post(
            f"{cfg['base_url']}/api/embed",
            json={"model": cfg["model"], "input": text},
            timeout=self.config["embedding"]["timeout_seconds"]
        )
        resp.raise_for_status()
        embedding = resp.json()["embeddings"][0]
        assert len(embedding) == self.dimensions, f"Dimension mismatch: {len(embedding)}"
        return embedding

    def _litellm_embed(self, text: str, provider: str) -> list[float]:
        """Cloud embedding via LiteLLM."""
        cfg = self.config["embedding"][provider]
        response = litellm_embedding(
            model=cfg["model"],
            input=[text],
            dimensions=cfg.get("dimensions", self.dimensions),
            api_key=cfg.get("api_key"),
        )
        embedding = response.data[0]["embedding"]
        # Truncate if needed (OpenAI returns 1536 by default)
        return embedding[:self.dimensions]
```

### 3.7 Embed Pipeline (rag/embed.py)

```python
def embed_document(
    file_path: str,
    force: bool = False
) -> EmbedResult:
    """
    Embed a YAML document into pgvector.

    Pipeline:
    1. Validate file (must be real document)
    2. Check file_hash (skip if unchanged and not force)
    3. Parse YAML and extract metadata
    4. Chunk document using section_mappings
    5. Embed each chunk
    6. Store in rag_documents and rag_chunks tables
    7. Log to rag_embed_log
    """

def embed_text(
    text: str,
    doc_id: str,
    doc_type: str,
    ticker: str = None
) -> EmbedResult:
    """Embed raw text (for external content)."""

# NOTE: is_real_document() imported from trader/utils.py (shared utility).
# Do NOT duplicate — see graph/extract.py section for canonical definition.
from trader.utils import is_real_document

def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of file contents."""

def _store_document(
    doc_id: str,
    file_path: str,
    doc_type: str,
    ticker: str,
    doc_date: date,
    file_hash: str,
    chunks: list[ChunkResult],
    embeddings: list[list[float]]
) -> None:
    """Store document and chunks in PostgreSQL."""

def delete_document(doc_id: str) -> bool:
    """Delete document and all its chunks."""

def reembed_all(version: str = None) -> int:
    """Re-embed all documents (or those with specific version)."""
```

### 3.8 Search Module (rag/search.py)

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

    Similarity interpretation:
    - > 0.8: Near-identical content (dedup candidate)
    - 0.6 - 0.8: Highly relevant (primary context)
    - 0.4 - 0.6: Somewhat relevant (supporting context)
    - 0.3 - 0.4: Loosely related (include if few results)
    - < 0.3: Irrelevant (exclude)
    """

def get_similar_analyses(
    ticker: str,
    analysis_type: str,
    top_k: int = 3
) -> list[SearchResult]:
    """Find similar past analyses for a ticker."""

def get_learnings_for_topic(
    topic: str,
    top_k: int = 5
) -> list[SearchResult]:
    """Find learnings related to a topic."""

def _build_search_query(
    ticker: str | None,
    doc_type: str | None,
    section: str | None,
    date_from: date | None,
    date_to: date | None
) -> tuple[str, dict]:
    """Build SQL query with appropriate filters."""
```

### 3.9 Hybrid Context Builder (rag/hybrid.py)

```python
def get_hybrid_context(
    ticker: str,
    query: str,
    analysis_type: str = None
) -> HybridContext:
    """
    Combine vector search + graph context for Claude.

    Steps:
    1. Vector search: past analyses for this ticker
    2. Vector search: similar analyses for peer tickers (from graph)
    3. Vector search: relevant learnings and biases
    4. Graph search: structural context (peers, competitors, risks, strategies)
    5. Format into context block
    """

def build_analysis_context(
    ticker: str,
    analysis_type: str
) -> str:
    """
    Build pre-analysis context for Claude skills.

    Includes:
    - Past analyses for this ticker (top 3)
    - Similar analyses for peer tickers (top 2)
    - Relevant learnings (top 3)
    - Graph structural context
    """

def format_context(
    vector_results: list[SearchResult],
    graph_context: dict
) -> str:
    """Format hybrid context as markdown for Claude."""
```

### 3.10 HTTP Webhook API (rag/webhook.py)

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Trading RAG API")

class EmbedRequest(BaseModel):
    file_path: str
    force: bool = False

class EmbedTextRequest(BaseModel):
    text: str
    doc_id: str
    doc_type: str
    ticker: str | None = None

class SearchRequest(BaseModel):
    query: str
    ticker: str | None = None
    doc_type: str | None = None
    section: str | None = None
    date_from: str | None = None  # YYYY-MM-DD
    date_to: str | None = None
    top_k: int = 5
    min_similarity: float = 0.3

class HybridContextRequest(BaseModel):
    ticker: str
    query: str
    analysis_type: str | None = None

@app.post("/api/rag/embed")
async def embed_document(req: EmbedRequest):
    """Embed a YAML file."""

@app.post("/api/rag/embed-text")
async def embed_text(req: EmbedTextRequest):
    """Embed raw text."""

@app.post("/api/rag/search")
async def search(req: SearchRequest):
    """Semantic search with filters."""

@app.post("/api/rag/hybrid-context")
async def get_hybrid_context(req: HybridContextRequest):
    """Get combined vector + graph context."""

@app.get("/api/rag/status")
async def get_status():
    """Get RAG statistics."""

@app.get("/api/rag/document/{doc_id}")
async def get_document(doc_id: str):
    """Get document and its chunks."""

@app.delete("/api/rag/document/{doc_id}")
async def delete_document(doc_id: str):
    """Delete document and chunks."""

@app.get("/api/rag/health")
async def health_check():
    """Health check endpoint."""
```

### 3.11 Phase 3 Deliverables

- [ ] `rag/__init__.py` with version constants and exports
- [ ] `rag/models.py` — Data classes
- [ ] `rag/exceptions.py` — Exception classes
- [ ] `rag/tokens.py` — Token estimation
- [ ] `rag/flatten.py` — YAML-to-text rules
- [ ] `rag/chunk.py` — Section-level chunking with text preparation
- [ ] `rag/embedding_client.py` — Ollama + fallback client
- [ ] `rag/ollama.py` — Ollama API client
- [ ] `rag/embed.py` — Full embedding pipeline
- [ ] `rag/search.py` — Semantic search
- [ ] `rag/hybrid.py` — Combined context builder
- [ ] `rag/schema.py` — pgvector tables init
- [ ] `rag/webhook.py` — FastAPI endpoints

---

## Phase 4: MCP Servers (3-4 hrs)

### 4.1 Graph MCP Server (mcp_trading_graph/server.py)

```python
# MCP server providing graph tools for Claude skills

TOOLS = [
    {
        "name": "graph_extract",
        "description": "Extract entities and relationships from a YAML document",
        "parameters": {
            "file_path": {"type": "string", "required": True},
            "extractor": {"type": "string", "default": "ollama"},
            "commit": {"type": "boolean", "default": True}
        }
    },
    {
        "name": "graph_search",
        "description": "Find all nodes connected to a ticker within N hops",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "depth": {"type": "integer", "default": 2}
        }
    },
    {
        "name": "graph_peers",
        "description": "Get sector peers and competitors for a ticker",
        "parameters": {
            "ticker": {"type": "string", "required": True}
        }
    },
    {
        "name": "graph_risks",
        "description": "Get known risks for a ticker",
        "parameters": {
            "ticker": {"type": "string", "required": True}
        }
    },
    {
        "name": "graph_biases",
        "description": "Get bias history across trades",
        "parameters": {
            "bias_name": {"type": "string", "required": False}
        }
    },
    {
        "name": "graph_context",
        "description": "Get comprehensive context for a ticker (peers, risks, strategies, biases)",
        "parameters": {
            "ticker": {"type": "string", "required": True}
        }
    },
    {
        "name": "graph_query",
        "description": "Execute raw Cypher query",
        "parameters": {
            "cypher": {"type": "string", "required": True},
            "params": {"type": "object", "default": {}}
        }
    },
    {
        "name": "graph_status",
        "description": "Get graph statistics (node/edge counts)",
        "parameters": {}
    }
]
```

### 4.2 RAG MCP Server (mcp_trading_rag/server.py)

```python
# MCP server providing RAG tools for Claude skills

TOOLS = [
    {
        "name": "rag_embed",
        "description": "Embed a YAML document for semantic search",
        "parameters": {
            "file_path": {"type": "string", "required": True},
            "force": {"type": "boolean", "default": False}
        }
    },
    {
        "name": "rag_search",
        "description": "Semantic search across embedded documents",
        "parameters": {
            "query": {"type": "string", "required": True},
            "ticker": {"type": "string", "required": False},
            "doc_type": {"type": "string", "required": False},
            "section": {"type": "string", "required": False},
            "top_k": {"type": "integer", "default": 5}
        }
    },
    {
        "name": "rag_similar",
        "description": "Find similar past analyses for a ticker",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "analysis_type": {"type": "string", "required": False},
            "top_k": {"type": "integer", "default": 3}
        }
    },
    {
        "name": "rag_hybrid_context",
        "description": "Get combined vector + graph context for analysis",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "query": {"type": "string", "required": True},
            "analysis_type": {"type": "string", "required": False}
        }
    },
    {
        "name": "rag_status",
        "description": "Get RAG statistics (document/chunk counts)",
        "parameters": {}
    }
]
```

### 4.3 MCP Server Registration

**Claude Code Configuration** (`.claude/settings.json` or update existing `nexus.settings`):

```json
{
  "mcpServers": {
    "trading-graph": {
      "command": "python",
      "args": ["-m", "mcp_trading_graph.server"],
      "cwd": "/opt/data/trading_light_pilot/trader",
      "env": {
        "NEO4J_URI": "bolt://localhost:7688",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASS": "${NEO4J_PASS}"
      }
    },
    "trading-rag": {
      "command": "python",
      "args": ["-m", "mcp_trading_rag.server"],
      "cwd": "/opt/data/trading_light_pilot/trader",
      "env": {
        "DATABASE_URL": "postgresql://lightrag:lightrag@localhost:5433/lightrag",
        "OLLAMA_BASE_URL": "http://localhost:11434"
      }
    },
    "trading-unified": {
      "command": "python",
      "args": ["-m", "mcp_trading_unified.server"],
      "cwd": "/opt/data/trading_light_pilot/trader",
      "env": {
        "NEO4J_URI": "bolt://localhost:7688",
        "DATABASE_URL": "postgresql://lightrag:lightrag@localhost:5433/lightrag"
      }
    }
  }
}
```

**Tool Registration for Skills** (update `nexus.settings`):
```yaml
# Add to allowed_tools_analysis or allowed_tools_all
allowed_tools_analysis:
  - mcp__trading-graph__graph_extract
  - mcp__trading-graph__graph_search
  - mcp__trading-graph__graph_peers
  - mcp__trading-graph__graph_risks
  - mcp__trading-graph__graph_biases
  - mcp__trading-graph__graph_context
  - mcp__trading-graph__graph_query
  - mcp__trading-graph__graph_status
  - mcp__trading-rag__rag_embed
  - mcp__trading-rag__rag_search
  - mcp__trading-rag__rag_similar
  - mcp__trading-rag__rag_hybrid_context
  - mcp__trading-rag__rag_status
  - mcp__trading-unified__unified_trading_context
  - mcp__trading-unified__graph_guided_search
```

### 4.4 Health Check Endpoints

Each MCP server must implement health checks for monitoring:

**Graph MCP Server** (`mcp_trading_graph/server.py`):
```python
from fastapi import FastAPI, Response
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

app = FastAPI()

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        with TradingGraph() as g:
            if g.health_check():
                return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return Response(
            content=json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json"
        )
    return Response(
        content=json.dumps({"status": "unhealthy", "neo4j": "disconnected"}),
        status_code=HTTP_503_SERVICE_UNAVAILABLE
    )

@app.get("/ready")
async def readiness_check():
    """Readiness check - can accept traffic."""
    try:
        with TradingGraph() as g:
            # Verify schema is initialized
            stats = g.get_stats()
            return {
                "status": "ready",
                "schema_initialized": True,
                "node_count": stats.total_nodes,
                "edge_count": stats.total_edges
            }
    except SchemaError:
        return Response(
            content=json.dumps({"status": "not_ready", "reason": "schema_not_initialized"}),
            status_code=HTTP_503_SERVICE_UNAVAILABLE
        )
```

**RAG MCP Server** (`mcp_trading_rag/server.py`):
```python
@app.get("/health")
async def health_check():
    """Health check for RAG service."""
    try:
        # Check PostgreSQL + pgvector
        async with get_db() as db:
            await db.execute("SELECT 1")
            await db.execute("SELECT vector_dims('[1,2,3]'::vector)")
        return {"status": "healthy", "pgvector": "connected"}
    except Exception as e:
        return Response(
            content=json.dumps({"status": "unhealthy", "error": str(e)}),
            status_code=HTTP_503_SERVICE_UNAVAILABLE
        )

@app.get("/ready")
async def readiness_check():
    """Readiness check - can accept traffic."""
    # Check Ollama availability for embeddings
    ollama_healthy = await check_ollama_health()
    return {
        "status": "ready" if ollama_healthy else "degraded",
        "ollama": "connected" if ollama_healthy else "unavailable",
        "fallback_available": bool(config.embedding.openrouter.api_key)
    }
```

### 4.5 Phase 4 Deliverables

- [ ] `mcp_trading_graph/__init__.py`
- [ ] `mcp_trading_graph/server.py` — MCP server entry point with health checks
- [ ] `mcp_trading_graph/tools/extract.py`
- [ ] `mcp_trading_graph/tools/query.py`
- [ ] `mcp_trading_graph/tools/status.py`
- [ ] `mcp_trading_rag/__init__.py`
- [ ] `mcp_trading_rag/server.py` — MCP server entry point with health checks
- [ ] `mcp_trading_rag/tools/search.py`
- [ ] `mcp_trading_rag/tools/embed.py`
- [ ] `mcp_trading_rag/tools/context.py`
- [ ] `.claude/settings.json` — MCP server registration
- [ ] Update `nexus.settings` — Tool allowlist

---

## Phase 5: CLI Integration (3-4 hrs)

### 5.1 Graph Command Group

```python
# Add to orchestrator.py

graph_parser = subparsers.add_parser('graph', help='Knowledge graph commands')
graph_sub = graph_parser.add_subparsers(dest='graph_cmd')

# Schema management
graph_sub.add_parser('init', help='Initialize Neo4j schema')
graph_sub.add_parser('reset', help='Wipe graph (dev only)')

migrate_p = graph_sub.add_parser('migrate', help='Run schema migrations')
migrate_p.add_argument('--to', required=True, help='Target version')

# Extraction
extract_p = graph_sub.add_parser('extract', help='Extract from document')
extract_p.add_argument('file', nargs='?', help='File to extract')
extract_p.add_argument('--dir', help='Directory to extract')
extract_p.add_argument('--extractor', default='ollama', choices=['ollama', 'claude-api', 'openrouter'])
extract_p.add_argument('--dry-run', action='store_true', help='Preview without committing')

reextract_p = graph_sub.add_parser('reextract', help='Re-extract documents')
reextract_p.add_argument('--all', action='store_true')
reextract_p.add_argument('--since', type=str, help='Date (YYYY-MM-DD)')
reextract_p.add_argument('--version', type=str, help='Extraction version')

# Queries
graph_sub.add_parser('status', help='Show graph statistics')

search_p = graph_sub.add_parser('search', help='Search around ticker')
search_p.add_argument('ticker', help='Ticker symbol')
search_p.add_argument('--depth', type=int, default=2)

peers_p = graph_sub.add_parser('peers', help='Find sector peers')
peers_p.add_argument('ticker', help='Ticker symbol')

risks_p = graph_sub.add_parser('risks', help='Find known risks')
risks_p.add_argument('ticker', help='Ticker symbol')

biases_p = graph_sub.add_parser('biases', help='Show bias history')
biases_p.add_argument('--name', help='Filter by bias name')

query_p = graph_sub.add_parser('query', help='Raw Cypher query')
query_p.add_argument('cypher', help='Cypher query string')

# Maintenance
prune_p = graph_sub.add_parser('prune', help='Archive old nodes')
prune_p.add_argument('--older-than', type=int, default=365, help='Days')

graph_sub.add_parser('dedupe', help='Merge duplicate entities')
graph_sub.add_parser('validate', help='Check constraint violations')
```

### 5.2 RAG Command Group

```python
# Add to orchestrator.py

rag_parser = subparsers.add_parser('rag', help='RAG/embedding commands')
rag_sub = rag_parser.add_subparsers(dest='rag_cmd')

# Schema management
rag_sub.add_parser('init', help='Initialize pgvector schema')
rag_sub.add_parser('reset', help='Drop and recreate tables (dev only)')

# Embedding
embed_p = rag_sub.add_parser('embed', help='Embed document')
embed_p.add_argument('file', nargs='?', help='File to embed')
embed_p.add_argument('--dir', help='Directory to embed')
embed_p.add_argument('--force', action='store_true', help='Re-embed even if unchanged')

reembed_p = rag_sub.add_parser('reembed', help='Re-embed documents')
reembed_p.add_argument('--all', action='store_true')
reembed_p.add_argument('--version', type=str, help='Embed version')

# Search
search_p = rag_sub.add_parser('search', help='Semantic search')
search_p.add_argument('query', help='Search query')
search_p.add_argument('--ticker', help='Filter by ticker')
search_p.add_argument('--type', dest='doc_type', help='Filter by doc type')
search_p.add_argument('--section', help='Filter by section')
search_p.add_argument('--since', type=str, help='Date filter (YYYY-MM-DD)')
search_p.add_argument('--top', type=int, default=5)
search_p.add_argument('--min-sim', type=float, default=0.3, help='Min similarity')

# Status and inspection
rag_sub.add_parser('status', help='Show embedding statistics')
rag_sub.add_parser('list', help='List embedded documents')

show_p = rag_sub.add_parser('show', help='Show document chunks')
show_p.add_argument('doc_id', help='Document ID')

# Maintenance
delete_p = rag_sub.add_parser('delete', help='Delete document')
delete_p.add_argument('doc_id', help='Document ID')

rag_sub.add_parser('reindex', help='Rebuild vector index')
rag_sub.add_parser('validate', help='Check for orphaned chunks')
```

### 5.3 Phase 5 Deliverables

- [ ] `graph` command group in orchestrator.py
- [ ] `rag` command group in orchestrator.py
- [ ] All command handlers implemented
- [ ] Help text and argument validation
- [ ] Error handling with graceful messages

---

## Phase 6: Skills Integration (3-4 hrs)

### 6.1 Post-Execution Hooks

Update skill templates in `tradegent_knowledge/skills/*/SKILL.md`:

```markdown
## Post-Execution: Knowledge Base Integration

After saving the analysis file to `tradegent_knowledge/knowledge/`:

1. **Graph Extraction** (entities and relationships):
   ```bash
   python orchestrator.py graph extract <saved_file>
   ```
   Extracts: {skill-specific entities}

2. **RAG Embedding** (semantic search):
   ```bash
   python orchestrator.py rag embed <saved_file>
   ```

3. **Verification**:
   - Check extraction: `python orchestrator.py graph status`
   - Check embedding: `python orchestrator.py rag status`
```

### 6.2 Skill-Specific Entities

| Skill | Entities Extracted |
|-------|-------------------|
| `earnings-analysis` | Ticker, Company, EarningsEvent, Catalyst, Product, Executive, Sector, Industry |
| `stock-analysis` | Ticker, Catalyst, Sector, Industry, Pattern, Signal, Risk |
| `research-analysis` | Company, Product, MacroEvent, Risk, Industry |
| `trade-journal` | Trade, Ticker, Strategy, Structure, Bias, Pattern |
| `post-trade-review` | Learning, Bias, Strategy, Pattern |
| `ticker-profile` | Ticker, Company, Sector, Industry, Product, Risk, Pattern |
| `strategy` | Strategy, Structure, Risk, Pattern, Timeframe |

### 6.3 Pre-Analysis Context Injection

Modify orchestrator.py `build_analysis_prompt()`:

```python
def build_analysis_context(ticker: str, analysis_type: str) -> str:
    """
    Gather hybrid RAG + Graph context before analysis.

    Called by build_analysis_prompt() to inject historical context.
    """
    try:
        from trader.rag.hybrid import build_analysis_context as rag_context
        return rag_context(ticker, analysis_type)
    except Exception as e:
        log.warning(f"Context injection failed: {e}")
        return ""  # Proceed without context
```

### 6.4 Service.py Integration

Add file watcher to service.py:

```python
def watch_knowledge_files(self):
    """
    Watch for new YAML files in tradegent_knowledge/knowledge/.
    Auto-extract and embed when files appear.
    """
    # Check for new files since last tick
    # Run graph extract + rag embed for each
    # Skip if extraction_version matches current

def check_extraction_versions(self):
    """
    Re-extract documents if extraction version has changed.
    """
    # Compare EXTRACT_VERSION with stored extraction_version
    # Queue re-extraction for outdated documents
```

### 6.5 Phase 6 Deliverables

- [ ] Post-execution hooks in all skill templates
- [ ] Skill-to-entity mapping documented
- [ ] Pre-analysis context injection in orchestrator.py
- [ ] Service.py file watcher (optional, can defer)
- [ ] Integration testing with real skill outputs

---

## Phase 7: Testing & Validation (6-10 hrs)

### 7.1 Test Fixtures

```bash
# Create fixtures
mkdir -p trader/graph/tests/fixtures/expected_extractions
mkdir -p trader/rag/tests/fixtures/expected_chunks

# Synthetic test documents
# - sample_earnings.yaml (NVDA Q4 earnings analysis)
# - sample_trade.yaml (completed trade with review)
# - sample_research.yaml (sector research)
```

### 7.2 Unit Tests

| Module | Test File | Coverage |
|--------|-----------|----------|
| `graph/normalize.py` | `test_normalize.py` | Alias resolution, case normalization, disambiguation |
| `graph/extract.py` | `test_extract.py` | JSON parsing, confidence thresholds, field mapping |
| `graph/layer.py` | `test_layer.py` | MERGE operations, queries (mock Neo4j) |
| `graph/query.py` | `test_query.py` | Preset query execution |
| `rag/tokens.py` | `test_tokens.py` | Token estimation accuracy |
| `rag/flatten.py` | `test_flatten.py` | YAML-to-text conversion |
| `rag/chunk.py` | `test_chunk.py` | Section splitting, token limits, text preparation |
| `rag/embedding_client.py` | `test_embedding.py` | Fallback chain, dimension validation |
| `rag/embed.py` | `test_embed.py` | Pipeline flow (mock DB) |
| `rag/search.py` | `test_search.py` | Query building, result formatting |
| `rag/hybrid.py` | `test_hybrid.py` | Context combination |

### 7.3 Deferred Tests (IPLAN-002, Phases 9-12)

> These test definitions are included for completeness but should be implemented
> alongside their respective phases in IPLAN-002, not during Phase 7.

#### 7.3.1 Tests for Phase 9 (RAG Advanced)

| Module | Test File | Coverage |
|--------|-----------|----------|
| `rag/search.py` | `test_hybrid_search.py` | BM25 + vector fusion, RRF scoring |
| `rag/rerank.py` | `test_rerank.py` | Cross-encoder reranking, score normalization |
| `rag/cache.py` | `test_cache.py` | Query caching, TTL expiration, cache invalidation |
| `rag/evaluation.py` | `test_evaluation.py` | MRR, NDCG, recall metrics calculation |

```python
# test_hybrid_search.py
def test_bm25_vector_fusion():
    """Verify RRF combines BM25 and vector scores correctly."""

def test_hybrid_search_with_filters():
    """Verify filters apply to both BM25 and vector search."""

def test_time_weighted_scoring():
    """Verify recent documents get higher scores."""

# test_rerank.py
def test_cross_encoder_reranks_correctly():
    """Verify cross-encoder improves relevance ordering."""

def test_rerank_handles_empty_candidates():
    """Verify graceful handling of no candidates."""

# test_cache.py
def test_cache_hit_returns_cached_results():
    """Verify cache returns stored results for same query."""

def test_cache_miss_computes_and_stores():
    """Verify cache miss triggers computation and storage."""

def test_cache_ttl_expiration():
    """Verify cached results expire after TTL."""
```

#### 7.3.2 Tests for Phase 10 (RAG Trading Intelligence)

| Module | Test File | Coverage |
|--------|-----------|----------|
| `rag/trading/outcomes.py` | `test_trading_outcomes.py` | Outcome weighting, setup statistics |
| `rag/trading/bias.py` | `test_trading_bias.py` | Bias warnings, impact calculation |
| `rag/trading/balanced.py` | `test_trading_balanced.py` | Counter-argument retrieval |
| `rag/trading/calibration.py` | `test_trading_calibration.py` | Conviction calibration |
| `rag/trading/position.py` | `test_trading_position.py` | Position-aware context switching |
| `rag/trading/patterns.py` | `test_trading_patterns.py` | Setup matching, similarity scoring |
| `rag/trading/exits.py` | `test_trading_exits.py` | Exit trigger retrieval |
| `rag/trading/portfolio.py` | `test_trading_portfolio.py` | Risk correlation detection |
| `rag/trading/context.py` | `test_trading_context.py` | Unified context building |

```python
# test_trading_outcomes.py
def test_outcome_weighted_search_boosts_winners():
    """Verify analyses from winning trades get higher scores."""

def test_get_setup_statistics_calculates_win_rate():
    """Verify win rate calculation for similar setups."""

# test_trading_bias.py
def test_bias_warnings_surfaced_for_ticker():
    """Verify bias warnings are retrieved for ticker."""

def test_bias_impact_calculated_correctly():
    """Verify P&L impact is calculated from trade history."""

# test_trading_calibration.py
def test_conviction_calibration_detects_overconfidence():
    """Verify overconfidence warning when stated > actual."""

def test_calibration_with_insufficient_history():
    """Verify graceful handling of sparse data."""
```

#### 7.3.3 Tests for Phase 11 (Graph Trading Intelligence)

| Module | Test File | Coverage |
|--------|-----------|----------|
| `graph/intelligence/outcomes.py` | `test_graph_outcomes.py` | Outcome-weighted traversal |
| `graph/intelligence/calibration.py` | `test_graph_calibration.py` | Conviction queries |
| `graph/intelligence/bias_tracker.py` | `test_graph_bias_tracker.py` | Bias chain detection |
| `graph/intelligence/strategy_perf.py` | `test_graph_strategy.py` | Strategy decay detection |
| `graph/intelligence/portfolio.py` | `test_graph_portfolio.py` | Position correlations |
| `graph/analytics/centrality.py` | `test_graph_centrality.py` | PageRank, degree centrality |
| `graph/analytics/export.py` | `test_graph_export.py` | Mermaid export |

```python
# test_graph_outcomes.py
def test_strategy_rankings_returns_ordered_list():
    """Verify strategies are ranked by win_weight."""

def test_entity_contribution_sums_correctly():
    """Verify P&L contributions are summed per entity."""

# test_graph_bias_tracker.py
def test_detect_bias_chains():
    """Verify bias chain detection identifies sequential biases."""

def test_bias_chain_respects_lag_days():
    """Verify lag_days parameter filters correctly."""

# test_graph_strategy.py
def test_detect_strategy_decay():
    """Verify decay detection compares early vs recent performance."""

# test_graph_portfolio.py
def test_find_position_correlations():
    """Verify correlated positions are identified via shared entities."""
```

#### 7.3.4 Tests for Phase 12 (Graph-RAG Hybrid)

| Module | Test File | Coverage |
|--------|-----------|----------|
| `hybrid/context.py` | `test_unified_context.py` | Context building, formatting |
| `hybrid/search.py` | `test_graph_guided_search.py` | Graph-guided filtering |

```python
# test_unified_context.py
def test_build_unified_context_combines_graph_and_rag():
    """Verify unified context includes both graph and RAG results."""

def test_unified_context_graceful_degradation():
    """Verify context builds even if graph or RAG unavailable."""

# test_graph_guided_search.py
def test_graph_guided_search_filters_to_related_docs():
    """Verify search is filtered to graph-connected documents."""
```

### 7.4 Integration Tests

| Test | Description |
|------|-------------|
| **Graph round-trip** | Extract → Commit → Query → Verify entities |
| **Graph idempotency** | Extract same doc twice → same graph state |
| **Graph confidence** | Verify threshold logic (commit, flag, skip) |
| **RAG round-trip** | Embed → Search → Verify content match |
| **RAG file hash** | Modify file → re-embed → new embeddings |
| **RAG filtered search** | Embed 3 tickers → filter search → correct results |
| **Hybrid context** | Vector + Graph → valid combined context |
| **Real document detection** | Template vs real document filtering |

### 7.5 pytest Configuration

```ini
# trader/pytest.ini
[pytest]
testpaths = graph/tests rag/tests hybrid/tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
markers =
    unit: Unit tests (no external dependencies)
    integration: Integration tests (requires Neo4j, PostgreSQL)
    slow: Slow tests (embedding, extraction)
    phase9: Phase 9 RAG Advanced tests
    phase10: Phase 10 RAG Trading Intelligence tests
    phase11: Phase 11 Graph Trading Intelligence tests
    phase12: Phase 12 Graph-RAG Hybrid tests
```

### 7.6 Phase 7 Deliverables

- [ ] Test fixtures created (earnings, trade, research samples)
- [ ] Unit tests for all core modules (Phases 1-6)
- [ ] Integration tests for round-trip flows
- [ ] pytest configuration with markers
- [ ] CI-ready test commands
- [ ] Deferred: Phase 9-12 test stubs documented (implement in IPLAN-002)

---

## Phase 8: Production Hardening (3-4 hrs)

### 8.1 Error Handling

```python
# Graceful degradation in skills
try:
    from trader.graph.extract import extract_document
    extract_document(saved_file)
except GraphUnavailableError:
    log.warning(f"Graph extraction skipped - Neo4j unavailable")
except ExtractionError as e:
    log.error(f"Graph extraction failed: {e}")
    # Queue for retry
    _queue_pending_commit(saved_file)

try:
    from trader.rag.embed import embed_document
    embed_document(saved_file)
except RAGUnavailableError:
    log.warning(f"RAG embedding skipped - pgvector unavailable")
except EmbeddingUnavailableError:
    log.warning(f"RAG embedding skipped - all providers failed")
```

### 8.2 Logging

```python
# Extraction log: trader/logs/graph_extractions.jsonl
{"ts": "2026-02-19T10:00:00Z", "doc": "EA-NVDA-Q4-2025", "extractor": "ollama",
 "entities": 12, "relations": 8, "committed": true, "duration_ms": 1500}

# Pending commits: trader/logs/pending_commits.jsonl
{"ts": "2026-02-19T10:00:00Z", "doc": "EA-NVDA-Q4-2025", "reason": "neo4j_unavailable",
 "retry_count": 0, "result": null}

# Embed log: trader/logs/rag_embed.jsonl
{"ts": "2026-02-19T10:00:00Z", "doc": "EA-NVDA-Q4-2025", "model": "nomic-embed-text",
 "chunks": 8, "duration_ms": 450, "status": "success"}
```

### 8.3 Monitoring Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Graph: node count by type | `graph status` | N/A (growth) |
| Graph: extraction success rate | `graph_extractions.jsonl` | < 90% over 24h |
| Graph: avg confidence | Extraction logs | < 0.6 avg |
| Graph: pending commits queue | `pending_commits.jsonl` | > 10 items |
| Graph: Neo4j query latency | App logs | > 500ms p95 |
| RAG: document count | `rag status` | N/A (growth) |
| RAG: chunk count | `rag status` | N/A (growth) |
| RAG: embedding latency | `rag_embed.jsonl` | > 2s per doc |
| RAG: embedding failures | `rag_embed.jsonl` | > 5% over 24h |
| RAG: cloud fallback usage | `rag_embed.jsonl` | > 20% (Ollama unhealthy) |
| RAG: search latency | App logs | > 200ms p95 |

### 8.4 LightRAG Deprecation

After validation:

```bash
# 1. Remove from docker-compose.yml
# - nexus-lightrag service
# - LightRAG env vars (LLM_BINDING, EMBEDDING_BINDING, etc.)

# 2. Remove from nexus.settings
# - lightrag_url
# - lightrag_ingest_enabled
# - lightrag_query_enabled

# 3. Remove from allowed_tools_analysis
# - mcp__lightrag__*

# 4. Delete lightrag directories
# rm -rf tradegent_knowledge/workflows/.lightrag/
```

### 8.5 Backup Strategy

```bash
# Neo4j backup (Community Edition - requires stop)
docker stop nexus-neo4j
docker cp nexus-neo4j:/data/ ~/backups/neo4j_$(date +%Y%m%d)/
docker start nexus-neo4j

# PostgreSQL backup (includes RAG tables)
docker exec nexus-postgres pg_dump -U lightrag lightrag > ~/backups/nexus_pg_$(date +%Y%m%d).sql
```

### 8.6 Docker-Compose Updates

> **Architecture note**: For single-user operation, CLI-first is preferred.
> The Graph and RAG API services below are **optional** — only add them if you need
> external integrations (e.g., n8n webhooks, MCP servers running in separate containers).
> Redis is deferred to IPLAN-002 (Python `lru_cache` is sufficient for <100 queries/day).

Add new services to `trader/docker-compose.yml`:

```yaml
version: '3.8'

services:
  # Existing services: nexus-neo4j, nexus-postgres, nexus-ib-gateway

  # DEFERRED to IPLAN-002: Redis for RAG query caching (Phase 9)
  # nexus-redis:
  #   image: redis:7-alpine
  #   container_name: nexus-redis
  #   ports:
  #     - "6379:6379"
  #   volumes:
  #     - redis_data:/data
  #   command: redis-server --appendonly yes
  #   restart: unless-stopped

  # OPTIONAL: Graph API service (for external integrations only)
  # nexus-graph-api:
  #   build:
  #     context: .
  #     dockerfile: Dockerfile.graph-api
  #   container_name: nexus-graph-api
  #   ports:
  #     - "8081:8080"

  # OPTIONAL: RAG API service (for external integrations only)
  # nexus-rag-api:
  #   build:
  #     context: .
  #     dockerfile: Dockerfile.rag-api
  #   container_name: nexus-rag-api
  #   ports:
  #     - "8082:8080"
```

**Neo4j Plugin Configuration** (update existing nexus-neo4j service):

```yaml
  nexus-neo4j:
    image: neo4j:5-community
    container_name: nexus-neo4j
    ports:
      - "7475:7474"  # HTTP
      - "7688:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASS}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
      - NEO4J_dbms_security_procedures_allowlist=apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./db/neo4j_schema.cypher:/docker-entrypoint-initdb.d/schema.cypher
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 10
```

### 8.7 Migration Rollback Strategy

**Neo4j Migration Rollback**:

```bash
# Before any migration, create a backup
docker stop nexus-neo4j
docker cp nexus-neo4j:/data/ ~/backups/neo4j_pre_migration_$(date +%Y%m%d)/
docker start nexus-neo4j

# Run migration
python orchestrator.py graph migrate --to 1.1.0

# If migration fails, restore from backup
docker stop nexus-neo4j
docker rm nexus-neo4j
docker run -d --name nexus-neo4j \
  -v ~/backups/neo4j_pre_migration_20260219/data:/data \
  -p 7475:7474 -p 7688:7687 \
  neo4j:5-community
```

**Migration Script Template** (`graph/migrations/v1_0_0_to_v1_1_0.cypher`):

```cypher
// Migration: v1.0.0 -> v1.1.0
// Description: Add trading intelligence properties
// Rollback: Remove properties added by this migration

// === FORWARD MIGRATION ===

// Step 1: Add new indexes (safe - additive)
CREATE INDEX trade_pnl_idx IF NOT EXISTS FOR (t:Trade) ON (t.pnl_percent);
CREATE INDEX trade_conviction_idx IF NOT EXISTS FOR (t:Trade) ON (t.stated_conviction);

// Step 2: Add default values to existing nodes
MATCH (t:Trade) WHERE t.pnl_percent IS NULL
SET t.pnl_percent = 0.0;

// === ROLLBACK (keep commented, run manually if needed) ===
// DROP INDEX trade_pnl_idx IF EXISTS;
// DROP INDEX trade_conviction_idx IF EXISTS;
// MATCH (t:Trade) REMOVE t.pnl_percent, t.stated_conviction;
```

**PostgreSQL Migration Rollback**:

```bash
# Before migration
pg_dump -U lightrag lightrag > ~/backups/nexus_pg_pre_migration_$(date +%Y%m%d).sql

# Run migration
python orchestrator.py rag migrate --to 1.1.0

# If migration fails, restore
psql -U lightrag lightrag < ~/backups/nexus_pg_pre_migration_20260219.sql
```

**Migration Testing Checklist**:

| Step | Action |
|------|--------|
| 1 | Create backup before migration |
| 2 | Run migration in dev environment first |
| 3 | Verify schema changes applied |
| 4 | Run integration tests against migrated schema |
| 5 | Test rollback procedure in dev |
| 6 | Schedule production migration in maintenance window |
| 7 | Monitor for errors after migration |

### 8.8 Phase 8 Deliverables

- [ ] Graceful degradation in all integration points
- [ ] JSONL logging for extraction and embedding
- [ ] Pending commits queue with retry logic
- [ ] Monitoring metrics documented
- [ ] LightRAG deprecation checklist
- [ ] Backup procedures documented
- [ ] Docker-compose updates (API services documented as optional)
- [ ] Neo4j plugin configuration (APOC)
- [ ] Migration rollback procedures documented
- [ ] Migration testing checklist

---

> **─── IPLAN-002 BOUNDARY ───**
>
> **Phases 9-12 below are deferred to IPLAN-002.** They require 30+ documents
> in the system to validate with real data. Implementing trading intelligence
> (outcome weighting, bias chains, conviction calibration, strategy decay)
> before any data exists is premature optimization.
>
> **Trigger for IPLAN-002**: Graph has 50+ entities AND RAG has 30+ embedded documents.

---

## Phase 9: RAG Advanced Features (4-6 hrs) — DEFERRED TO IPLAN-002

### 9.1 Hybrid Search (BM25 + Vector)

**Problem**: Pure vector search misses exact term matches (ticker symbols, metric names).

**Schema Addition**:
```sql
-- Add full-text search column to rag_chunks
ALTER TABLE nexus.rag_chunks
ADD COLUMN content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

CREATE INDEX idx_rag_chunks_fts ON nexus.rag_chunks USING gin(content_tsv);
```

**Implementation** (`rag/search.py`):
```python
def hybrid_search(
    query: str,
    ticker: str | None = None,
    doc_type: str | None = None,
    top_k: int = 5,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> list[SearchResult]:
    """
    Combined BM25 + vector search using Reciprocal Rank Fusion.

    1. Run vector search (top 50)
    2. Run BM25 full-text search (top 50)
    3. Combine scores using RRF: 1/(k + rank_vector) + 1/(k + rank_bm25)
    4. Return top_k results
    """
```

**SQL Query**:
```sql
WITH vector_results AS (
    SELECT id, content,
           ROW_NUMBER() OVER (ORDER BY embedding <=> $1::vector) as v_rank
    FROM nexus.rag_chunks
    WHERE ($2::varchar IS NULL OR ticker = $2)
    LIMIT 50
),
bm25_results AS (
    SELECT id, content,
           ROW_NUMBER() OVER (ORDER BY ts_rank(content_tsv, plainto_tsquery($3)) DESC) as b_rank
    FROM nexus.rag_chunks
    WHERE content_tsv @@ plainto_tsquery($3)
      AND ($2::varchar IS NULL OR ticker = $2)
    LIMIT 50
)
SELECT COALESCE(v.id, b.id) as id,
       COALESCE(v.content, b.content) as content,
       (1.0 / (60 + COALESCE(v.v_rank, 100))) * $4 +
       (1.0 / (60 + COALESCE(b.b_rank, 100))) * $5 as hybrid_score
FROM vector_results v
FULL OUTER JOIN bm25_results b ON v.id = b.id
ORDER BY hybrid_score DESC
LIMIT $6;
```

### 9.2 Cross-Encoder Reranking

**Implementation** (`rag/rerank.py`):
```python
from sentence_transformers import CrossEncoder

class Reranker:
    """Two-stage retrieve-then-rerank for improved relevance."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        """
        Rerank candidates using cross-encoder.

        Cross-encoder sees (query, document) pairs together,
        enabling deeper semantic matching than bi-encoder.
        """
        pairs = [(query, c.content) for c in candidates]
        scores = self.model.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate.rerank_score = float(score)

        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]

def search_with_rerank(
    query: str,
    ticker: str | None = None,
    top_k: int = 5,
    retrieval_k: int = 50
) -> list[SearchResult]:
    """
    Two-stage search:
    1. Fast retrieval (vector search, top 50)
    2. Accurate reranking (cross-encoder, top 5)
    """
    candidates = semantic_search(query, ticker=ticker, top_k=retrieval_k)
    reranker = Reranker()
    return reranker.rerank(query, candidates, top_k=top_k)
```

### 9.3 Time-Weighted Scoring

**Implementation** (`rag/search.py`):
```python
import math
from datetime import date

def time_weighted_search(
    query: str,
    ticker: str | None = None,
    top_k: int = 5,
    recency_weight: float = 0.3,
    half_life_days: int = 365
) -> list[SearchResult]:
    """
    Weight recent documents higher.

    Final score = base_similarity * (1 - recency_weight + recency_weight * decay)
    where decay = exp(-days_old / half_life)
    """
    results = semantic_search(query, ticker=ticker, top_k=top_k * 2)

    today = date.today()
    for r in results:
        if r.doc_date:
            days_old = (today - r.doc_date).days
            decay = math.exp(-days_old / half_life_days)
            r.time_weighted_score = r.similarity * (1 - recency_weight + recency_weight * decay)
        else:
            r.time_weighted_score = r.similarity * (1 - recency_weight)

    return sorted(results, key=lambda r: r.time_weighted_score, reverse=True)[:top_k]
```

### 9.4 Query Caching

**Implementation** (`rag/cache.py`):
```python
from functools import lru_cache
import hashlib
import redis

class RAGCache:
    """Cache for embeddings and search results."""

    def __init__(self, redis_url: str = None, ttl_seconds: int = 3600):
        self.redis = redis.from_url(redis_url) if redis_url else None
        self.ttl = ttl_seconds
        self._local_cache = {}

    @lru_cache(maxsize=1000)
    def get_query_embedding(self, query: str) -> list[float]:
        """Cache query embeddings (most queries repeat)."""
        return embedding_client.get_embedding(query)

    def get_search_results(self, query_hash: str) -> list[dict] | None:
        """Check cache for search results."""
        if self.redis:
            cached = self.redis.get(f"rag:search:{query_hash}")
            if cached:
                return json.loads(cached)
        return self._local_cache.get(query_hash)

    def set_search_results(self, query_hash: str, results: list[dict]):
        """Cache search results with TTL."""
        if self.redis:
            self.redis.setex(f"rag:search:{query_hash}", self.ttl, json.dumps(results))
        else:
            self._local_cache[query_hash] = results

    @staticmethod
    def hash_query(query: str, filters: dict) -> str:
        """Generate cache key from query and filters."""
        key = f"{query}:{json.dumps(filters, sort_keys=True)}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]
```

### 9.5 Parent Document Retrieval

**Schema Addition**:
```sql
-- Add parent chunk reference
ALTER TABLE nexus.rag_chunks ADD COLUMN parent_chunk_id BIGINT REFERENCES nexus.rag_chunks(id);
ALTER TABLE nexus.rag_chunks ADD COLUMN chunk_level SMALLINT DEFAULT 0;
-- 0 = section, 1 = subsection, 2 = paragraph

CREATE INDEX idx_rag_chunks_parent ON nexus.rag_chunks(parent_chunk_id);
```

**Implementation** (`rag/search.py`):
```python
@dataclass
class SearchResultWithContext(SearchResult):
    """Search result with surrounding context."""
    parent_content: str | None = None
    sibling_chunks: list[str] = field(default_factory=list)

def search_with_context(
    query: str,
    ticker: str | None = None,
    top_k: int = 5,
    include_parent: bool = True,
    include_siblings: bool = False
) -> list[SearchResultWithContext]:
    """
    Search and return matched chunks with surrounding context.
    """
    results = semantic_search(query, ticker=ticker, top_k=top_k)

    enriched = []
    for r in results:
        enriched_result = SearchResultWithContext(**r.__dict__)

        if include_parent and r.parent_chunk_id:
            parent = get_chunk_by_id(r.parent_chunk_id)
            enriched_result.parent_content = parent.content if parent else None

        if include_siblings:
            siblings = get_sibling_chunks(r.doc_id, r.section_path)
            enriched_result.sibling_chunks = [s.content for s in siblings]

        enriched.append(enriched_result)

    return enriched
```

### 9.6 Evaluation Framework

**Implementation** (`rag/evaluation.py`):
```python
@dataclass
class RetrievalMetrics:
    """Retrieval quality metrics."""
    mrr: float              # Mean Reciprocal Rank
    ndcg_at_5: float        # Normalized DCG @ 5
    recall_at_5: float      # Recall @ 5
    recall_at_10: float     # Recall @ 10
    avg_latency_ms: float

@dataclass
class EvaluationQuery:
    """Test query with relevance judgments."""
    query: str
    ticker: str | None
    relevant_doc_ids: list[str]  # Ground truth relevant documents

def evaluate_retrieval(
    test_queries: list[EvaluationQuery],
    search_fn: callable = semantic_search
) -> RetrievalMetrics:
    """
    Evaluate retrieval quality against labeled test set.

    Run periodically to catch regressions.
    """
    mrr_scores = []
    ndcg_scores = []
    recall_5_scores = []
    recall_10_scores = []
    latencies = []

    for eq in test_queries:
        start = time.time()
        results = search_fn(eq.query, ticker=eq.ticker, top_k=10)
        latencies.append((time.time() - start) * 1000)

        result_ids = [r.doc_id for r in results]

        # MRR
        for i, doc_id in enumerate(result_ids):
            if doc_id in eq.relevant_doc_ids:
                mrr_scores.append(1.0 / (i + 1))
                break
        else:
            mrr_scores.append(0.0)

        # Recall @ K
        hits_5 = len(set(result_ids[:5]) & set(eq.relevant_doc_ids))
        hits_10 = len(set(result_ids[:10]) & set(eq.relevant_doc_ids))
        recall_5_scores.append(hits_5 / len(eq.relevant_doc_ids))
        recall_10_scores.append(hits_10 / len(eq.relevant_doc_ids))

        # NDCG @ 5
        ndcg_scores.append(compute_ndcg(result_ids[:5], eq.relevant_doc_ids))

    return RetrievalMetrics(
        mrr=sum(mrr_scores) / len(mrr_scores),
        ndcg_at_5=sum(ndcg_scores) / len(ndcg_scores),
        recall_at_5=sum(recall_5_scores) / len(recall_5_scores),
        recall_at_10=sum(recall_10_scores) / len(recall_10_scores),
        avg_latency_ms=sum(latencies) / len(latencies)
    )
```

### 9.7 New Dependencies

```bash
# Add to requirements.txt
sentence-transformers>=2.2.0   # Cross-encoder reranking
redis>=4.5.0                   # Optional: distributed caching
```

### 9.8 Phase 9 Deliverables

- [ ] `rag/search.py` — Hybrid BM25 + vector search
- [ ] `rag/rerank.py` — Cross-encoder reranking
- [ ] `rag/cache.py` — Query/embedding caching
- [ ] `rag/evaluation.py` — Retrieval metrics framework
- [ ] Schema migration for FTS column and parent chunks
- [ ] Time-weighted scoring in search
- [ ] CLI: `rag search --hybrid`, `rag search --rerank`
- [ ] Evaluation test set (10-20 labeled queries)

---

## Phase 10: Trading Intelligence Layer (6-8 hrs) — DEFERRED TO IPLAN-002

### 10.1 Outcome-Weighted Retrieval

**Schema Addition**:
```sql
-- Track trade outcomes linked to analyses
CREATE TABLE IF NOT EXISTS nexus.rag_trade_outcomes (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES nexus.rag_documents(id),
    trade_id VARCHAR(100),           -- From trade-journal
    outcome VARCHAR(20),             -- win, loss, scratch, open
    pnl_pct DECIMAL(10,4),           -- Actual P&L percentage
    thesis_accuracy DECIMAL(3,2),    -- Did thesis play out? 0.0-1.0
    days_held INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_rag_outcomes_doc ON nexus.rag_trade_outcomes(doc_id);
CREATE INDEX idx_rag_outcomes_outcome ON nexus.rag_trade_outcomes(outcome);
```

**Implementation** (`rag/trading/outcomes.py`):
```python
@dataclass
class TradingSearchResult(SearchResult):
    """Search result enriched with trade outcome data."""
    trade_outcome: str | None = None      # win, loss, scratch, open
    pnl_pct: float | None = None          # Actual P&L
    thesis_accuracy: float | None = None  # Did thesis play out?
    days_held: int | None = None

def outcome_weighted_search(
    query: str,
    ticker: str | None = None,
    top_k: int = 5,
    winner_boost: float = 1.2
) -> list[TradingSearchResult]:
    """
    Search with outcome-weighted scoring.

    Prioritizes analyses that led to winning trades,
    but doesn't hide losers (learning value).
    """
    results = semantic_search(query, ticker=ticker, top_k=top_k * 2)

    enriched = []
    for r in results:
        outcome = get_trade_outcome(r.doc_id)
        tr = TradingSearchResult(**r.__dict__)

        if outcome:
            tr.trade_outcome = outcome.outcome
            tr.pnl_pct = outcome.pnl_pct
            tr.thesis_accuracy = outcome.thesis_accuracy
            tr.days_held = outcome.days_held

            # Boost winners
            if outcome.pnl_pct and outcome.pnl_pct > 0:
                tr.similarity *= winner_boost

        enriched.append(tr)

    return sorted(enriched, key=lambda r: r.similarity, reverse=True)[:top_k]

def get_setup_statistics(
    query: str,
    ticker: str | None = None,
    min_samples: int = 3
) -> dict:
    """
    Get win rate and avg P&L for similar setups.

    Returns:
    {
        "sample_size": 8,
        "win_rate": 0.625,
        "avg_pnl_pct": 8.5,
        "avg_days_held": 12,
        "best_outcome": {"doc_id": "...", "pnl_pct": 18.5},
        "worst_outcome": {"doc_id": "...", "pnl_pct": -8.2}
    }
    """
```

### 10.2 Bias History Injection

**Implementation** (`rag/trading/bias.py`):
```python
@dataclass
class BiasWarning:
    """Warning about a historical bias pattern."""
    bias_name: str
    occurrences: int
    last_occurrence: str      # Trade ID
    last_impact: str          # Description of what happened
    ticker_specific: bool     # Was this bias specific to this ticker?

def get_bias_warnings(
    ticker: str,
    decision_type: str       # 'entry', 'exit', 'size', 'hold'
) -> list[BiasWarning]:
    """
    Get bias warnings relevant to current decision.

    Queries both graph (bias-trade relationships) and
    RAG (bias descriptions from post-trade reviews).
    """
    # Graph: Get biases detected in past trades for this ticker
    ticker_biases = graph.query("""
        MATCH (b:Bias)-[:DETECTED_IN]->(t:Trade)-[:TRADED]->(tk:Ticker {symbol: $ticker})
        RETURN b.name as bias, count(t) as occurrences,
               collect(t.id)[0] as last_trade
        ORDER BY occurrences DESC
    """, {"ticker": ticker})

    # RAG: Get bias context from post-trade reviews
    bias_context = semantic_search(
        f"{decision_type} decision bias mistake regret",
        doc_type="post-trade-review",
        top_k=5
    )

    warnings = []
    for tb in ticker_biases:
        # Get impact description from RAG
        impact = semantic_search(
            f"{tb['bias']} impact consequence",
            doc_type="post-trade-review",
            ticker=ticker,
            top_k=1
        )

        warnings.append(BiasWarning(
            bias_name=tb['bias'],
            occurrences=tb['occurrences'],
            last_occurrence=tb['last_trade'],
            last_impact=impact[0].content if impact else "No description available",
            ticker_specific=True
        ))

    return warnings

def format_bias_warnings(warnings: list[BiasWarning]) -> str:
    """Format warnings for Claude context injection."""
    if not warnings:
        return ""

    output = "⚠️ BIAS WARNINGS:\n\n"
    for w in warnings:
        output += f"**{w.bias_name}** ({w.occurrences} occurrences)\n"
        output += f"Last: {w.last_impact}\n\n"

    return output
```

### 10.3 Counter-Argument Retrieval

**Implementation** (`rag/trading/balanced.py`):
```python
@dataclass
class BalancedContext:
    """Balanced bull/bear context to combat confirmation bias."""
    supporting: list[SearchResult]
    contrary: list[SearchResult]
    past_mistakes: list[SearchResult]
    formatted: str

def get_balanced_context(
    ticker: str,
    thesis_direction: str,    # 'long' or 'short'
    top_k_per_side: int = 3
) -> BalancedContext:
    """
    Force retrieval of both supporting AND contrary evidence.

    Combats confirmation bias by always including the other side.
    """
    # Supporting evidence
    bull_query = f"{ticker} bullish thesis catalyst upside growth"
    bear_query = f"{ticker} bearish risk downside concern weakness"

    if thesis_direction == "long":
        supporting = semantic_search(bull_query, ticker=ticker, top_k=top_k_per_side)
        contrary = semantic_search(bear_query, ticker=ticker, top_k=top_k_per_side)
    else:
        supporting = semantic_search(bear_query, ticker=ticker, top_k=top_k_per_side)
        contrary = semantic_search(bull_query, ticker=ticker, top_k=top_k_per_side)

    # Always get past mistakes on this ticker
    past_mistakes = semantic_search(
        f"{ticker} mistake wrong failed lesson",
        doc_type="post-trade-review",
        top_k=2
    )

    return BalancedContext(
        supporting=supporting,
        contrary=contrary,
        past_mistakes=past_mistakes,
        formatted=_format_balanced_context(supporting, contrary, past_mistakes, thesis_direction)
    )

def _format_balanced_context(
    supporting: list[SearchResult],
    contrary: list[SearchResult],
    mistakes: list[SearchResult],
    direction: str
) -> str:
    """Format balanced context for Claude."""
    output = f"## Balanced Analysis Context ({direction.upper()} thesis)\n\n"

    output += "### Supporting Evidence\n"
    for s in supporting:
        output += f"- [{s.doc_date}] {s.content[:200]}...\n"

    output += "\n### ⚠️ Contrary Evidence (REQUIRED READING)\n"
    for c in contrary:
        output += f"- [{c.doc_date}] {c.content[:200]}...\n"

    if mistakes:
        output += "\n### Past Mistakes on This Ticker\n"
        for m in mistakes:
            output += f"- [{m.doc_date}] {m.content[:200]}...\n"

    return output
```

### 10.4 Conviction Calibration

**Implementation** (`rag/trading/calibration.py`):
```python
@dataclass
class CalibrationResult:
    """Conviction calibration check."""
    stated_confidence: float
    historical_accuracy: float
    sample_size: int
    confidence_gap: float       # stated - historical
    warning: str | None

def calibrate_conviction(
    ticker: str,
    current_confidence: float,
    analysis_type: str
) -> CalibrationResult:
    """
    How accurate have you been at this confidence level?

    Compares stated confidence to historical accuracy.
    """
    # Get past analyses with similar confidence levels (±10%)
    similar = db.query("""
        SELECT ar.confidence, ar.gate_passed,
               CASE WHEN t.pnl_pct > 0 THEN 1 ELSE 0 END as won
        FROM nexus.analysis_results ar
        LEFT JOIN nexus.run_history rh ON ar.run_id = rh.id
        LEFT JOIN (
            -- NOTE: nexus.trades table must be created before Phase 10.
            -- It does not exist in current init.sql — add migration in Phase 10.
            SELECT ticker, entry_date, pnl_pct
            FROM nexus.trades WHERE exit_date IS NOT NULL
        ) t ON ar.ticker = t.ticker AND DATE(rh.started_at) = t.entry_date
        WHERE ar.confidence BETWEEN $1 - 0.1 AND $1 + 0.1
          AND ar.analysis_type = $2
          AND t.pnl_pct IS NOT NULL
    """, (current_confidence, analysis_type))

    if len(similar) < 3:
        return CalibrationResult(
            stated_confidence=current_confidence,
            historical_accuracy=0.0,
            sample_size=len(similar),
            confidence_gap=0.0,
            warning="Insufficient history for calibration"
        )

    historical_accuracy = sum(r['won'] for r in similar) / len(similar)
    confidence_gap = current_confidence - historical_accuracy

    warning = None
    if confidence_gap > 0.15:
        warning = f"OVERCONFIDENCE: You're {current_confidence:.0%} confident, but historically {historical_accuracy:.0%} accurate at this level"
    elif confidence_gap < -0.15:
        warning = f"UNDERCONFIDENCE: You're {current_confidence:.0%} confident, but historically {historical_accuracy:.0%} accurate"

    return CalibrationResult(
        stated_confidence=current_confidence,
        historical_accuracy=historical_accuracy,
        sample_size=len(similar),
        confidence_gap=confidence_gap,
        warning=warning
    )
```

### 10.5 Position-Aware Context

**Implementation** (`rag/trading/position.py`):
```python
@dataclass
class PositionContext:
    """Context adapted to current position state."""
    mode: str                           # 'manage' or 'evaluate'
    position: dict | None               # Current position if any
    context_results: list[SearchResult]
    formatted: str

def get_position_aware_context(ticker: str) -> PositionContext:
    """
    Adapt retrieval based on whether position is open.

    - Open position: Focus on exits, risk management
    - No position: Focus on entries, setup quality
    """
    position = get_open_position(ticker)

    if position:
        # OPEN POSITION: Focus on exit criteria
        exit_triggers = semantic_search(
            f"{ticker} exit sell take profit stop loss when to sell",
            top_k=3
        )
        risk_factors = semantic_search(
            f"{ticker} risk concern downside threat",
            section="risks",
            top_k=3
        )
        thesis_invalidation = semantic_search(
            f"{ticker} thesis wrong invalidated failed",
            top_k=2
        )

        results = exit_triggers + risk_factors + thesis_invalidation
        formatted = _format_manage_context(position, exit_triggers, risk_factors, thesis_invalidation)

        return PositionContext(
            mode="manage",
            position=position,
            context_results=results,
            formatted=formatted
        )
    else:
        # NO POSITION: Focus on entry criteria
        entry_setups = semantic_search(
            f"{ticker} entry setup catalyst trigger",
            top_k=3
        )
        similar_winners = outcome_weighted_search(
            f"{ticker} winning trade success",
            top_k=3
        )
        red_flags = semantic_search(
            f"{ticker} avoid warning red flag concern",
            top_k=2
        )

        results = entry_setups + similar_winners + red_flags
        formatted = _format_evaluate_context(entry_setups, similar_winners, red_flags)

        return PositionContext(
            mode="evaluate",
            position=None,
            context_results=results,
            formatted=formatted
        )
```

### 10.6 Pattern-to-Outcome Matching

**Implementation** (`rag/trading/patterns.py`):
```python
@dataclass
class SetupMatch:
    """Past setup match with outcome."""
    analysis: SearchResult
    outcome: dict | None
    setup_similarity: float
    pnl_pct: float | None
    days_held: int | None

def find_similar_setups(
    current_analysis: dict,
    top_k: int = 5
) -> list[SetupMatch]:
    """
    Find past analyses with similar setups and their outcomes.

    "This looks like X" → show X's outcome.
    """
    # Build setup description
    setup_text = f"""
    Ticker: {current_analysis.get('ticker', 'Unknown')}
    Catalyst: {current_analysis.get('catalyst', '')}
    Technical setup: {current_analysis.get('technicals', '')}
    Thesis: {current_analysis.get('thesis', '')}
    """

    # Find similar past setups
    similar = semantic_search(
        setup_text,
        doc_type="stock-analysis",
        top_k=top_k * 2
    )

    # Enrich with outcomes
    matches = []
    for s in similar:
        outcome = get_trade_outcome(s.doc_id)
        matches.append(SetupMatch(
            analysis=s,
            outcome=outcome,
            setup_similarity=s.similarity,
            pnl_pct=outcome['pnl_pct'] if outcome else None,
            days_held=outcome['days_held'] if outcome else None
        ))

    # Sort by similarity, return top_k
    return sorted(matches, key=lambda m: m.setup_similarity, reverse=True)[:top_k]

def format_setup_matches(matches: list[SetupMatch]) -> str:
    """Format setup matches for Claude context."""
    if not matches:
        return "No similar past setups found."

    output = "## Similar Past Setups\n\n"

    wins = [m for m in matches if m.pnl_pct and m.pnl_pct > 0]
    losses = [m for m in matches if m.pnl_pct and m.pnl_pct <= 0]

    if wins or losses:
        win_rate = len(wins) / len([m for m in matches if m.pnl_pct is not None])
        avg_pnl = sum(m.pnl_pct for m in matches if m.pnl_pct) / len([m for m in matches if m.pnl_pct])
        output += f"**Statistics**: {win_rate:.0%} win rate, avg P&L {avg_pnl:+.1f}%\n\n"

    for i, m in enumerate(matches, 1):
        icon = "✓" if m.pnl_pct and m.pnl_pct > 0 else "✗" if m.pnl_pct else "?"
        output += f"{i}. **{m.analysis.doc_id}** ({m.setup_similarity:.0%} similar) {icon}\n"
        if m.pnl_pct:
            output += f"   Result: {m.pnl_pct:+.1f}% in {m.days_held} days\n"
        output += f"   {m.analysis.content[:150]}...\n\n"

    return output
```

### 10.7 Exit Trigger Library

**Implementation** (`rag/trading/exits.py`):
```python
@dataclass
class ExitTriggerContext:
    """Structured exit decision support."""
    original_thesis: SearchResult | None
    invalidation_signals: list[SearchResult]
    past_exit_patterns: list[SearchResult]
    exit_lessons: list[SearchResult]
    current_pnl_pct: float
    formatted: str

def get_exit_triggers(ticker: str, position: dict) -> ExitTriggerContext:
    """
    What conditions should trigger an exit?

    Retrieves:
    - Original entry thesis
    - What would invalidate it
    - How you've exited similar positions
    - Lessons from past exits
    """
    # Original thesis from entry
    entry_thesis = semantic_search(
        f"{ticker} thesis entry rationale",
        doc_type="trade-journal",
        date_from=position['entry_date'],
        date_to=position['entry_date'],
        top_k=1
    )

    # What invalidates this thesis?
    invalidation = semantic_search(
        f"{ticker} thesis wrong invalidated bearish breakdown",
        top_k=3
    )

    # How have you exited similar positions?
    past_exits = semantic_search(
        f"{ticker} exit sold closed position took profit stopped out",
        doc_type="trade-journal",
        section="execution",
        top_k=5
    )

    # What do you regret about past exits?
    exit_regrets = semantic_search(
        f"exit too early too late regret should have held sold",
        doc_type="post-trade-review",
        top_k=3
    )

    return ExitTriggerContext(
        original_thesis=entry_thesis[0] if entry_thesis else None,
        invalidation_signals=invalidation,
        past_exit_patterns=past_exits,
        exit_lessons=exit_regrets,
        current_pnl_pct=position.get('unrealized_pnl_pct', 0),
        formatted=_format_exit_context(...)
    )
```

### 10.8 Learning Loop Integration

**Implementation** (`rag/trading/learning.py`):
```python
@dataclass
class LearningContext:
    """Lessons surfaced at decision time."""
    ticker_lessons: list[SearchResult]
    decision_lessons: list[SearchResult]
    active_rules: list[dict]
    formatted: str

def get_learning_context(
    ticker: str,
    decision_type: str       # 'entry', 'exit', 'size', 'hold'
) -> LearningContext:
    """
    Surface relevant lessons at decision time.

    Closes the feedback loop: past lessons → current decisions.
    """
    # Lessons specific to this ticker
    ticker_lessons = semantic_search(
        f"{ticker} lesson learned mistake improvement",
        doc_type="learning",
        top_k=3
    )

    # Lessons for this decision type
    decision_lessons = semantic_search(
        f"{decision_type} lesson rule framework",
        doc_type="learning",
        top_k=3
    )

    # Active rules from graph
    active_rules = graph.query("""
        MATCH (l:Learning)-[:UPDATES]->(s:Strategy)
        WHERE s.name IN $active_strategies
        RETURN l.rule as rule, l.category as category, s.name as strategy
        ORDER BY l.created_at DESC
        LIMIT 5
    """, {"active_strategies": get_active_strategies()})

    return LearningContext(
        ticker_lessons=ticker_lessons,
        decision_lessons=decision_lessons,
        active_rules=active_rules,
        formatted=_format_learning_context(...)
    )

def inject_learning_context(
    ticker: str,
    decision_type: str,
    base_context: str
) -> str:
    """
    Inject learning context into analysis prompt.

    Called by orchestrator.py before Claude analysis.
    """
    learning = get_learning_context(ticker, decision_type)

    if not learning.formatted:
        return base_context

    return f"{base_context}\n\n{learning.formatted}"
```

### 10.9 Portfolio Risk Correlation

**Implementation** (`rag/trading/portfolio.py`):
```python
@dataclass
class PortfolioRiskContext:
    """Cross-position risk awareness."""
    correlated_positions: list[dict]
    shared_risks: list[SearchResult]
    sector_exposure_pct: float
    concentration_warning: str | None
    formatted: str

def get_portfolio_risk_context(ticker: str) -> PortfolioRiskContext:
    """
    Risk context considering existing portfolio.

    Before adding a position, surface:
    - Correlated existing positions
    - Shared risk factors
    - Sector concentration
    """
    positions = get_open_positions()
    if not positions:
        return PortfolioRiskContext(
            correlated_positions=[],
            shared_risks=[],
            sector_exposure_pct=0,
            concentration_warning=None,
            formatted=""
        )

    # Find correlated tickers in portfolio
    correlated = graph.query("""
        MATCH (t1:Ticker {symbol: $ticker})-[r:CORRELATED_WITH]-(t2:Ticker)
        WHERE t2.symbol IN $portfolio_tickers
        RETURN t2.symbol as ticker, r.coefficient as correlation
        ORDER BY r.coefficient DESC
    """, {
        "ticker": ticker,
        "portfolio_tickers": [p['ticker'] for p in positions]
    })

    # Retrieve shared risks
    shared_risks = []
    for corr in correlated:
        risks = semantic_search(
            f"{ticker} {corr['ticker']} shared risk correlation",
            section="risks",
            top_k=2
        )
        shared_risks.extend(risks)

    # Calculate sector exposure
    sector = get_sector(ticker)
    sector_value = sum(
        p['market_value'] for p in positions
        if get_sector(p['ticker']) == sector
    )
    total_value = sum(p['market_value'] for p in positions)
    sector_exposure = sector_value / total_value if total_value > 0 else 0

    # Concentration warning
    warning = None
    if sector_exposure > 0.3:
        warning = f"Adding {ticker} increases {sector} exposure to {sector_exposure + 0.1:.0%}"
    if len(correlated) >= 2:
        warning = (warning or "") + f"\n{len(correlated)} correlated positions already in portfolio"

    return PortfolioRiskContext(
        correlated_positions=correlated,
        shared_risks=shared_risks,
        sector_exposure_pct=sector_exposure,
        concentration_warning=warning,
        formatted=_format_portfolio_risk(...)
    )
```

### 10.10 Unified Trading Context Builder

**Implementation** (`rag/trading/context.py`):
```python
@dataclass
class TradingContext:
    """Complete trading context combining all intelligence layers."""
    ticker: str
    decision_type: str

    # Core context
    hybrid_context: HybridContext

    # Trading intelligence
    bias_warnings: list[BiasWarning]
    calibration: CalibrationResult | None
    balanced_context: BalancedContext
    position_context: PositionContext
    similar_setups: list[SetupMatch]
    learning_context: LearningContext
    portfolio_risk: PortfolioRiskContext

    # Exit-specific (if managing position)
    exit_triggers: ExitTriggerContext | None

    formatted: str

def build_trading_context(
    ticker: str,
    decision_type: str,           # 'entry', 'exit', 'size', 'hold', 'analysis'
    thesis_direction: str = None, # 'long', 'short', or None
    current_confidence: float = None,
    current_analysis: dict = None
) -> TradingContext:
    """
    Build comprehensive trading context for Claude.

    Combines all trading intelligence layers into a single context block.
    """
    # Base hybrid context (vector + graph)
    hybrid = get_hybrid_context(ticker, f"{ticker} {decision_type}")

    # Trading intelligence layers
    bias_warnings = get_bias_warnings(ticker, decision_type)

    calibration = None
    if current_confidence:
        calibration = calibrate_conviction(ticker, current_confidence, decision_type)

    balanced = None
    if thesis_direction:
        balanced = get_balanced_context(ticker, thesis_direction)

    position_ctx = get_position_aware_context(ticker)

    similar_setups = []
    if current_analysis:
        similar_setups = find_similar_setups(current_analysis)

    learning = get_learning_context(ticker, decision_type)

    portfolio_risk = get_portfolio_risk_context(ticker)

    exit_triggers = None
    if position_ctx.mode == "manage":
        exit_triggers = get_exit_triggers(ticker, position_ctx.position)

    # Format everything
    formatted = _format_full_trading_context(
        ticker=ticker,
        decision_type=decision_type,
        hybrid=hybrid,
        bias_warnings=bias_warnings,
        calibration=calibration,
        balanced=balanced,
        position_ctx=position_ctx,
        similar_setups=similar_setups,
        learning=learning,
        portfolio_risk=portfolio_risk,
        exit_triggers=exit_triggers
    )

    return TradingContext(
        ticker=ticker,
        decision_type=decision_type,
        hybrid_context=hybrid,
        bias_warnings=bias_warnings,
        calibration=calibration,
        balanced_context=balanced,
        position_context=position_ctx,
        similar_setups=similar_setups,
        learning_context=learning,
        portfolio_risk=portfolio_risk,
        exit_triggers=exit_triggers,
        formatted=formatted
    )
```

### 10.11 MCP Tools for Trading Intelligence

Add to `mcp_trading_rag/tools/trading.py`:

```python
TRADING_TOOLS = [
    {
        "name": "trading_context",
        "description": "Get comprehensive trading context (biases, calibration, patterns, risks)",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "decision_type": {"type": "string", "enum": ["entry", "exit", "size", "hold", "analysis"]},
            "thesis_direction": {"type": "string", "enum": ["long", "short"]},
            "confidence": {"type": "number"}
        }
    },
    {
        "name": "bias_check",
        "description": "Get bias warnings for a trading decision",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "decision_type": {"type": "string", "required": True}
        }
    },
    {
        "name": "similar_setups",
        "description": "Find similar past setups with their outcomes",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "catalyst": {"type": "string"},
            "thesis": {"type": "string"},
            "top_k": {"type": "integer", "default": 5}
        }
    },
    {
        "name": "exit_triggers",
        "description": "Get exit trigger context for an open position",
        "parameters": {
            "ticker": {"type": "string", "required": True}
        }
    },
    {
        "name": "portfolio_risk",
        "description": "Check portfolio risk before adding a position",
        "parameters": {
            "ticker": {"type": "string", "required": True}
        }
    }
]
```

### 10.12 CLI Commands for Trading Intelligence

Add to orchestrator.py:

```python
# Trading intelligence commands
trading_parser = subparsers.add_parser('trading', help='Trading intelligence commands')
trading_sub = trading_parser.add_subparsers(dest='trading_cmd')

# trading context TICKER
ctx_p = trading_sub.add_parser('context', help='Full trading context')
ctx_p.add_argument('ticker', help='Ticker symbol')
ctx_p.add_argument('--decision', choices=['entry', 'exit', 'hold', 'analysis'], default='analysis')
ctx_p.add_argument('--direction', choices=['long', 'short'])
ctx_p.add_argument('--confidence', type=float)

# trading biases TICKER
bias_p = trading_sub.add_parser('biases', help='Bias warnings for ticker')
bias_p.add_argument('ticker', help='Ticker symbol')
bias_p.add_argument('--decision', default='entry')

# trading calibrate
cal_p = trading_sub.add_parser('calibrate', help='Conviction calibration')
cal_p.add_argument('--confidence', type=float, required=True)
cal_p.add_argument('--type', dest='analysis_type', default='stock-analysis')

# trading similar TICKER
sim_p = trading_sub.add_parser('similar', help='Find similar setups')
sim_p.add_argument('ticker', help='Ticker symbol')
sim_p.add_argument('--top', type=int, default=5)

# trading portfolio-risk TICKER
risk_p = trading_sub.add_parser('portfolio-risk', help='Portfolio risk check')
risk_p.add_argument('ticker', help='Ticker to evaluate adding')
```

### 10.13 Phase 10 Deliverables

- [ ] `rag/trading/__init__.py` — Trading intelligence module
- [ ] `rag/trading/outcomes.py` — Outcome-weighted retrieval
- [ ] `rag/trading/bias.py` — Bias history injection
- [ ] `rag/trading/balanced.py` — Counter-argument retrieval
- [ ] `rag/trading/calibration.py` — Conviction calibration
- [ ] `rag/trading/position.py` — Position-aware context
- [ ] `rag/trading/patterns.py` — Pattern-to-outcome matching
- [ ] `rag/trading/exits.py` — Exit trigger library
- [ ] `rag/trading/learning.py` — Learning loop integration
- [ ] `rag/trading/portfolio.py` — Portfolio risk correlation
- [ ] `rag/trading/context.py` — Unified context builder
- [ ] Schema migration for trade outcomes table
- [ ] MCP tools for trading intelligence
- [ ] CLI commands for trading intelligence
- [ ] Integration with orchestrator.py analysis pipeline

---

## Phase 11: Graph Trading Intelligence Layer (6-8 hrs) — DEFERRED TO IPLAN-002

> Corresponds to TRADING_GRAPH_ARCHITECTURE.md Sections 14-18

### 11.1 Enhanced Entity Properties

Add trading intelligence properties to existing graph nodes:

**Schema Migration** (`graph/migrations/v1_1_0_trading_intelligence.cypher`):
```cypher
// ============================================================
// ENHANCED TRADE NODE PROPERTIES
// ============================================================
// Trade nodes now track detailed outcome metrics

// Add indexes for new properties
CREATE INDEX trade_pnl_idx IF NOT EXISTS FOR (t:Trade) ON (t.pnl_percent);
CREATE INDEX trade_conviction_idx IF NOT EXISTS FOR (t:Trade) ON (t.stated_conviction);
CREATE INDEX trade_exit_trigger_idx IF NOT EXISTS FOR (t:Trade) ON (t.exit_trigger);
CREATE INDEX trade_status_idx IF NOT EXISTS FOR (t:Trade) ON (t.status);

// Strategy performance tracking
CREATE INDEX strategy_win_rate_idx IF NOT EXISTS FOR (s:Strategy) ON (s.win_rate);
CREATE INDEX strategy_profit_factor_idx IF NOT EXISTS FOR (s:Strategy) ON (s.profit_factor);
CREATE INDEX strategy_last_used_idx IF NOT EXISTS FOR (s:Strategy) ON (s.last_used);

// Bias impact tracking
CREATE INDEX bias_occurrences_idx IF NOT EXISTS FOR (b:Bias) ON (b.total_occurrences);

// Pattern reliability
CREATE INDEX pattern_reliability_idx IF NOT EXISTS FOR (p:Pattern) ON (p.reliability_score);

// Learning effectiveness
CREATE INDEX learning_effectiveness_idx IF NOT EXISTS FOR (l:Learning) ON (l.effectiveness_score);
CREATE INDEX learning_compliance_idx IF NOT EXISTS FOR (l:Learning) ON (l.compliance_rate);
```

**Node Property Extensions** (`graph/models.py`):
```python
@dataclass
class TradeIntelligenceProps:
    """Extended Trade node properties for trading intelligence."""
    pnl_dollars: float | None = None
    pnl_percent: float | None = None
    stated_conviction: int | None = None      # 1-5 scale at entry
    actual_edge: float | None = None          # Calculated post-trade (0.0-1.0)
    hold_duration_days: int | None = None
    exit_trigger: str | None = None           # stop, target, time, catalyst
    thesis_accuracy: float | None = None      # How accurate was thesis (0.0-1.0)

@dataclass
class StrategyIntelligenceProps:
    """Extended Strategy node properties for trading intelligence."""
    sample_size: int = 0
    avg_pnl_percent: float = 0.0
    profit_factor: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    last_used: datetime | None = None
    optimal_hold_days: float | None = None
    best_market_regime: str | None = None     # trending, ranging, volatile

@dataclass
class BiasIntelligenceProps:
    """Extended Bias node properties for trading intelligence."""
    total_occurrences: int = 0
    avg_pnl_impact: float | None = None
    worst_impact_trade: str | None = None
    effective_countermeasures: list[str] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)

@dataclass
class PatternIntelligenceProps:
    """Extended Pattern node properties for trading intelligence."""
    sample_size: int = 0
    avg_magnitude: float | None = None
    reliability_score: float | None = None
    last_observed: datetime | None = None
    optimal_timeframe: str | None = None
    decay_rate: float | None = None

@dataclass
class LearningIntelligenceProps:
    """Extended Learning node properties for trading intelligence."""
    compliance_rate: float | None = None
    effectiveness_score: float | None = None
    last_applied: datetime | None = None
    violation_count: int = 0
    successful_applications: int = 0
```

### 11.2 Trading Intelligence Relationships

**New Relationship Types**:
```cypher
// Bias chain detection (one bias triggering another)
// (Bias)-[:TRIGGERED {frequency: float, lag_days: int}]->(Bias)
// (Bias)-[:COUNTERED_BY {effectiveness: float}]->(Learning)

// Conviction tracking
// (Trade)-[:HAD_CONVICTION {stated: int, actual: float}]->(ConvictionRecord)

// Strategy optimization
// (Strategy)-[:OPTIMAL_FOR {win_rate: float, profit_factor: float}]->(Sector)
// (Strategy)-[:OPTIMAL_FOR {win_rate: float, profit_factor: float}]->(Timeframe)
// (Strategy)-[:DECAY_AFTER {days: int, effectiveness_drop: float}]->(MarketRegime)

// Exit trigger tracking
// (ExitTrigger)-[:EFFECTIVE_FOR {success_rate: float}]->(Strategy)
// (ExitTrigger)-[:USED_IN]->(Trade)

// Portfolio correlation
// (Ticker)-[:RISK_CORRELATED {coefficient: float, period: string}]->(Ticker)
// (Position)-[:OVERLAPS_RISK]->(Position)

// Learning compliance
// (Learning)-[:FOLLOWED]->(Trade)
// (Learning)-[:VIOLATED]->(Trade)
```

### 11.3 Graph Intelligence Module

**File Structure** (`trader/graph/intelligence/`):
```
graph/intelligence/
├── __init__.py           # Module init with exports
├── outcomes.py           # Outcome-weighted traversal algorithms
├── calibration.py        # Conviction calibration tracking
├── bias_tracker.py       # Bias detection and chain analysis
├── strategy_perf.py      # Strategy performance and decay detection
├── patterns.py           # Pattern-to-outcome matching
├── exits.py              # Exit trigger library and effectiveness
├── portfolio.py          # Portfolio correlation and risk analysis
└── learning.py           # Learning loop integration
```

**Implementation** (`graph/intelligence/outcomes.py`):
```python
class OutcomeWeightedTraversal:
    """Weight graph traversals by historical trade outcomes."""

    def get_strategy_rankings(
        self,
        ticker: str,
        min_sample: int = 3
    ) -> list[dict]:
        """
        Find strategies with positive outcome weight for a ticker.

        Returns strategies ranked by win_weight = wins / (wins + losses).
        """
        return self.graph.query("""
            MATCH (s:Strategy)-[w:WORKS_FOR]->(t:Ticker {symbol: $symbol}),
                  (s)<-[:BASED_ON]-(tr:Trade)-[:TRADED]->(t)
            WITH s,
                 sum(CASE WHEN tr.outcome = 'win' THEN tr.pnl_percent ELSE 0 END) as total_wins,
                 sum(CASE WHEN tr.outcome = 'loss' THEN abs(tr.pnl_percent) ELSE 0 END) as total_losses,
                 count(tr) as sample
            WHERE sample >= $min_sample
            RETURN s.name as strategy,
                   total_wins / (total_wins + total_losses + 0.001) as win_weight,
                   s.profit_factor as profit_factor,
                   sample
            ORDER BY win_weight DESC
        """, {"symbol": ticker, "min_sample": min_sample})

    def get_entity_contribution(self, top_k: int = 20) -> list[dict]:
        """Rank entities by contribution to profitable trades."""
        return self.graph.query("""
            MATCH (e)-[r]-(tr:Trade)
            WHERE tr.outcome = 'win' AND tr.pnl_percent > 0
            WITH labels(e)[0] as entity_type, e.name as entity_name,
                 sum(tr.pnl_percent) as total_contribution,
                 count(tr) as appearances
            RETURN entity_type, entity_name, total_contribution, appearances
            ORDER BY total_contribution DESC
            LIMIT $top_k
        """, {"top_k": top_k})
```

**Implementation** (`graph/intelligence/bias_tracker.py`):
```python
class BiasTracker:
    """Track bias patterns across time and trades."""

    def get_bias_frequency_impact(self, ticker: str = None) -> list[dict]:
        """Bias frequency and impact over time."""
        query = """
            MATCH (b:Bias)-[:DETECTED_IN]->(tr:Trade)
            {ticker_filter}
            WITH b.name as bias,
                 collect({{date: tr.entry_date, impact: tr.pnl_percent}}) as occurrences,
                 avg(tr.pnl_percent) as avg_impact,
                 count(*) as total
            RETURN bias, total, avg_impact, occurrences[-5..] as recent_five
            ORDER BY total DESC
        """
        ticker_filter = "-[:TRADED]->(tk:Ticker {symbol: $ticker})" if ticker else ""
        return self.graph.query(
            query.format(ticker_filter=ticker_filter),
            {"ticker": ticker} if ticker else {}
        )

    def detect_bias_chains(self, lag_days: int = 7, min_count: int = 2) -> list[dict]:
        """Find bias chains (one bias triggering another)."""
        return self.graph.query("""
            MATCH (b1:Bias)-[:DETECTED_IN]->(t1:Trade),
                  (b2:Bias)-[:DETECTED_IN]->(t2:Trade)
            WHERE t2.entry_date > t1.entry_date
              AND t2.entry_date < t1.entry_date + duration('P' + $lag_days + 'D')
              AND b1 <> b2
            WITH b1, b2, count(*) as chain_count
            WHERE chain_count >= $min_count
            RETURN b1.name as trigger_bias, b2.name as subsequent_bias, chain_count
            ORDER BY chain_count DESC
        """, {"lag_days": str(lag_days), "min_count": min_count})

    def get_effective_countermeasures(self, bias_name: str) -> list[dict]:
        """Get countermeasures that work against a specific bias."""
        return self.graph.query("""
            MATCH (b:Bias {name: $bias_name})<-[:ADDRESSES]-(l:Learning)
            OPTIONAL MATCH (l)<-[:FOLLOWED]-(tr:Trade)
            WITH l, count(tr) as applications,
                 avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as success_rate
            RETURN l.rule as rule, applications, success_rate
            ORDER BY success_rate DESC
        """, {"bias_name": bias_name})
```

**Implementation** (`graph/intelligence/calibration.py`):
```python
class ConvictionCalibration:
    """Track stated conviction vs actual outcomes."""

    def get_calibration_report(self) -> list[dict]:
        """Conviction accuracy by level."""
        return self.graph.query("""
            MATCH (tr:Trade)
            WHERE tr.stated_conviction IS NOT NULL
            WITH tr.stated_conviction as conviction,
                 count(*) as trades,
                 avg(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) as actual_win_rate,
                 avg(tr.pnl_percent) as avg_return
            RETURN conviction, trades,
                   actual_win_rate,
                   CASE conviction
                     WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
                     WHEN 2 THEN 0.5 WHEN 1 THEN 0.4
                   END as expected_win_rate,
                   actual_win_rate - CASE conviction
                     WHEN 5 THEN 0.8 WHEN 4 THEN 0.7 WHEN 3 THEN 0.6
                     WHEN 2 THEN 0.5 WHEN 1 THEN 0.4
                   END as calibration_error
            ORDER BY conviction
        """)

    def detect_overconfidence(self, min_conviction: int = 4, top_k: int = 10) -> list[dict]:
        """Find high-conviction losses for review."""
        return self.graph.query("""
            MATCH (tr:Trade)
            WHERE tr.stated_conviction >= $min_conviction AND tr.outcome = 'loss'
            WITH tr,
                 [(b:Bias)-[:DETECTED_IN]->(tr) | b.name] as biases,
                 [(s:Strategy)<-[:BASED_ON]-(tr) | s.name] as strategies
            RETURN tr.id, tr.stated_conviction, tr.pnl_percent, biases, strategies
            ORDER BY tr.pnl_percent ASC
            LIMIT $top_k
        """, {"min_conviction": min_conviction, "top_k": top_k})
```

**Implementation** (`graph/intelligence/strategy_perf.py`):
```python
class StrategyPerformance:
    """Strategy performance analysis and decay detection."""

    def detect_strategy_decay(self, min_trades: int = 10) -> list[dict]:
        """Find strategies with declining performance over time."""
        return self.graph.query("""
            MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)
            WITH s, tr ORDER BY tr.entry_date
            WITH s.name as strategy,
                 collect(tr.pnl_percent) as returns,
                 count(tr) as n
            WHERE n >= $min_trades
            WITH strategy, returns, n,
                 reduce(s = 0.0, x IN returns[0..n/2] | s + x) / (n/2) as early_avg,
                 reduce(s = 0.0, x IN returns[n/2..] | s + x) / (n/2) as recent_avg
            RETURN strategy, early_avg, recent_avg,
                   recent_avg - early_avg as performance_change
            ORDER BY performance_change ASC
        """, {"min_trades": min_trades})

    def get_optimal_strategy_per_sector(self, min_trades: int = 3) -> list[dict]:
        """Find best-performing strategy for each sector."""
        return self.graph.query("""
            MATCH (s:Strategy)<-[:BASED_ON]-(tr:Trade)-[:TRADED]->(tk:Ticker),
                  (c:Company)-[:ISSUED]->(tk),
                  (c)-[:IN_SECTOR]->(sec:Sector)
            WITH sec.name as sector, s.name as strategy,
                 count(tr) as trades,
                 avg(tr.pnl_percent) as avg_return,
                 sum(CASE WHEN tr.outcome = 'win' THEN 1 ELSE 0 END) * 1.0 / count(tr) as win_rate
            WHERE trades >= $min_trades
            WITH sector, strategy, trades, avg_return, win_rate,
                 avg_return * win_rate as score
            ORDER BY sector, score DESC
            WITH sector, collect({strategy: strategy, score: score, trades: trades})[0] as best
            RETURN sector, best.strategy as best_strategy, best.score, best.trades
        """, {"min_trades": min_trades})
```

**Implementation** (`graph/intelligence/portfolio.py`):
```python
class PortfolioRiskAnalysis:
    """Portfolio correlation and risk analysis via graph."""

    def find_position_correlations(self) -> list[dict]:
        """Find correlated positions via shared entities."""
        return self.graph.query("""
            MATCH (tr1:Trade {status: 'open'})-[:TRADED]->(t1:Ticker),
                  (tr2:Trade {status: 'open'})-[:TRADED]->(t2:Ticker),
                  (t1)-[r1]-(shared)-[r2]-(t2)
            WHERE t1 <> t2
            WITH t1.symbol as ticker1, t2.symbol as ticker2,
                 collect(DISTINCT labels(shared)[0] + ':' + shared.name) as shared_factors,
                 count(DISTINCT shared) as overlap_count
            WHERE overlap_count >= 2
            RETURN ticker1, ticker2, shared_factors, overlap_count
            ORDER BY overlap_count DESC
        """)

    def get_sector_concentration(self) -> list[dict]:
        """Analyze sector concentration risk."""
        return self.graph.query("""
            MATCH (tr:Trade {status: 'open'})-[:TRADED]->(tk:Ticker),
                  (c:Company)-[:ISSUED]->(tk),
                  (c)-[:IN_SECTOR]->(s:Sector)
            WITH s.name as sector, collect(tk.symbol) as tickers, count(*) as position_count
            WITH sector, tickers, position_count,
                 collect {MATCH (tr2:Trade {status: 'open'}) RETURN count(tr2) as total}[0].total as total_positions
            RETURN sector, tickers, position_count,
                   position_count * 1.0 / total_positions as concentration
            ORDER BY concentration DESC
        """)

    def get_risk_factor_exposure(self) -> list[dict]:
        """Analyze risk factor exposure across portfolio."""
        return self.graph.query("""
            MATCH (tr:Trade {status: 'open'})-[:TRADED]->(tk:Ticker),
                  (r:Risk)-[:THREATENS]->(tk)
            WITH r.name as risk, collect(DISTINCT tk.symbol) as exposed_tickers
            RETURN risk, exposed_tickers, size(exposed_tickers) as exposure_count
            ORDER BY exposure_count DESC
        """)
```

### 11.4 Graph Intelligence CLI Commands

Add to orchestrator.py:

```python
# Graph intelligence commands
graph_intel_parser = subparsers.add_parser('graph-intel', help='Graph intelligence commands')
graph_intel_sub = graph_intel_parser.add_subparsers(dest='intel_cmd')

# Outcome analysis
outcome_p = graph_intel_sub.add_parser('outcomes', help='Outcome-weighted analysis')
outcome_p.add_argument('ticker', nargs='?', help='Ticker symbol (optional)')
outcome_p.add_argument('--strategy', action='store_true', help='Strategy performance summary')
outcome_p.add_argument('--period', default='all', help='Time period (e.g., 90d)')

# Bias analysis
bias_p = graph_intel_sub.add_parser('biases', help='Bias analysis')
bias_p.add_argument('--impact', action='store_true', help='Rank by P&L impact')
bias_p.add_argument('--chains', action='store_true', help='Detect bias chains')
bias_p.add_argument('--counter', metavar='BIAS', help='Get countermeasures for bias')

# Conviction calibration
cal_p = graph_intel_sub.add_parser('calibration', help='Conviction calibration report')
cal_p.add_argument('--detail', action='store_true', help='Per-level breakdown')

# Strategy analysis
strat_p = graph_intel_sub.add_parser('strategy-decay', help='Detect decaying strategies')
strat_fit_p = graph_intel_sub.add_parser('strategy-fit', help='Best strategy for context')
strat_fit_p.add_argument('ticker', nargs='?', help='Ticker symbol')
strat_fit_p.add_argument('--sector', action='store_true', help='Best per sector')

# Pattern analysis
pat_p = graph_intel_sub.add_parser('patterns', help='Pattern analysis')
pat_p.add_argument('--predictive', action='store_true', help='Pattern predictive value')
pat_p.add_argument('--combos', action='store_true', help='Best pattern+strategy combos')

# Exit analysis
exit_p = graph_intel_sub.add_parser('exits', help='Exit trigger analysis')
exit_p.add_argument('--by-strategy', action='store_true', help='Group by strategy')

# Portfolio risk
risk_p = graph_intel_sub.add_parser('risk-correlation', help='Position correlations')
conc_p = graph_intel_sub.add_parser('risk-concentration', help='Sector concentration')
exp_p = graph_intel_sub.add_parser('risk-exposure', help='Risk factor exposure')

# Learning effectiveness
learn_p = graph_intel_sub.add_parser('learning-impact', help='Learning rule value')
comp_p = graph_intel_sub.add_parser('learning-compliance', help='Rule compliance rates')

# Graph analytics
cent_p = graph_intel_sub.add_parser('centrality', help='Entity importance ranking')
comm_p = graph_intel_sub.add_parser('communities', help='Entity clusters')
path_p = graph_intel_sub.add_parser('path', help='Shortest path between entities')
path_p.add_argument('from_entity', help='Source entity')
path_p.add_argument('to_entity', help='Target entity')
```

### 11.5 Advanced Graph Analytics Module

**File Structure** (`trader/graph/analytics/`):
```
graph/analytics/
├── __init__.py           # Module init
├── centrality.py         # PageRank, betweenness, degree centrality
├── communities.py        # Louvain community detection
├── temporal.py           # Time-windowed analysis
└── export.py             # Mermaid/GraphViz export
```

**Implementation** (`graph/analytics/centrality.py`):
```python
class CentralityAnalysis:
    """Entity importance ranking using graph algorithms.
    
    NOTE: pagerank() requires GDS plugin (Community or Enterprise).
    most_connected() uses plain Cypher and works without GDS.
    """

    def pagerank(self, top_k: int = 20) -> list[dict]:
        """Most influential entities via PageRank. Requires GDS plugin."""
        return self.graph.query("""
            CALL gds.pageRank.stream('trading-graph', {
              maxIterations: 20,
              dampingFactor: 0.85
            })
            YIELD nodeId, score
            WITH gds.util.asNode(nodeId) AS node, score
            RETURN labels(node)[0] as type, node.name as entity, score
            ORDER BY score DESC
            LIMIT $top_k
        """, {"top_k": top_k})

    def most_connected(self, top_k: int = 20) -> list[dict]:
        """Entities with most relationships."""
        return self.graph.query("""
            MATCH (n)-[r]-()
            WITH labels(n)[0] as type, n.name as entity, count(r) as connections
            RETURN type, entity, connections
            ORDER BY connections DESC
            LIMIT $top_k
        """, {"top_k": top_k})
```

**Implementation** (`graph/analytics/export.py`):
```python
def export_subgraph_mermaid(ticker: str, depth: int = 2) -> str:
    """Export ticker subgraph as Mermaid diagram."""
    edges = graph.query("""
        MATCH path = (t:Ticker {symbol: $symbol})-[r*1..$depth]-(connected)
        WITH relationships(path) as rels
        UNWIND rels as rel
        WITH DISTINCT startNode(rel) as from_node, rel, endNode(rel) as to_node
        RETURN
          labels(from_node)[0] + '_' + coalesce(from_node.symbol, from_node.name, from_node.id) as from_id,
          type(rel) as relationship,
          labels(to_node)[0] + '_' + coalesce(to_node.symbol, to_node.name, to_node.id) as to_id
    """, {"symbol": ticker, "depth": depth})

    mermaid = "graph LR\n"
    for e in edges:
        mermaid += f"    {e['from_id']} -->|{e['relationship']}| {e['to_id']}\n"

    return mermaid
```

### 11.6 Post-Trade Feedback Loop

**Implementation** (`graph/intelligence/feedback.py`):
```python
def process_trade_outcome(trade_id: str) -> list[str]:
    """
    Update graph intelligence based on trade outcome.

    Called automatically when a trade is closed.
    Returns list of suggested learnings.
    """
    with TradingGraph() as g:
        trade = g.get_trade(trade_id)
        learnings = []

        # 1. Update strategy performance stats
        g.update_strategy_stats(trade.strategy, trade.outcome, trade.pnl_percent)

        # 2. Record bias impact
        for bias in trade.detected_biases:
            g.record_bias_impact(bias, trade.pnl_percent)

        # 3. Update pattern reliability
        for pattern in trade.observed_patterns:
            g.update_pattern_stats(pattern, trade.outcome)

        # 4. Track conviction calibration
        g.record_conviction_outcome(trade.stated_conviction, trade.outcome)

        # 5. Update exit trigger effectiveness
        if trade.exit_trigger:
            g.update_exit_stats(trade.exit_trigger, trade.strategy, trade.pnl_percent)

        # 6. Check for new bias chains
        new_chains = g.detect_bias_chains_for_trade(trade)
        if new_chains:
            learnings.append(f"Bias chain detected: {' → '.join(new_chains)}")

        # 7. Generate learning suggestions
        if trade.outcome == 'loss' and trade.pnl_percent < -5:
            learnings.extend(g.suggest_learnings(trade))

        return learnings
```

### 11.7 Graph-RAG Decision Support Integration

**Implementation** (`graph/intelligence/decision_support.py`):
```python
def enrich_analysis_context(ticker: str) -> dict:
    """
    Query graph for decision-relevant intelligence.

    Called by skills before Claude analysis to inject graph context.
    """
    with TradingGraph() as g:
        outcomes = OutcomeWeightedTraversal(g)
        bias_tracker = BiasTracker(g)
        calibration = ConvictionCalibration(g)
        portfolio = PortfolioRiskAnalysis(g)

        return {
            # Historical performance
            "strategy_rankings": outcomes.get_strategy_rankings(ticker),
            "pattern_signals": g.get_recent_patterns(ticker, days=7),

            # Bias warnings
            "active_biases": bias_tracker.get_user_bias_tendency(),
            "bias_impact_history": bias_tracker.get_bias_frequency_impact(ticker),

            # Calibration feedback
            "conviction_accuracy": calibration.get_calibration_report(),

            # Risk context
            "correlated_positions": portfolio.find_position_correlations(),
            "risk_exposure": portfolio.get_risk_factor_exposure(),

            # Learning reminders
            "relevant_learnings": g.get_applicable_learnings(ticker)
        }
```

### 11.8 Phase 11 Deliverables

- [ ] `graph/migrations/v1_1_0_trading_intelligence.cypher` — Schema migration
- [ ] `graph/intelligence/__init__.py` — Trading intelligence module
- [ ] `graph/intelligence/outcomes.py` — Outcome-weighted traversal
- [ ] `graph/intelligence/calibration.py` — Conviction calibration
- [ ] `graph/intelligence/bias_tracker.py` — Bias detection and chains
- [ ] `graph/intelligence/strategy_perf.py` — Strategy performance/decay
- [ ] `graph/intelligence/patterns.py` — Pattern-to-outcome matching
- [ ] `graph/intelligence/exits.py` — Exit trigger library
- [ ] `graph/intelligence/portfolio.py` — Portfolio correlation/risk
- [ ] `graph/intelligence/learning.py` — Learning loop integration
- [ ] `graph/intelligence/feedback.py` — Post-trade feedback processor
- [ ] `graph/intelligence/decision_support.py` — Decision support integration
- [ ] `graph/analytics/centrality.py` — Centrality analysis
- [ ] `graph/analytics/communities.py` — Community detection
- [ ] `graph/analytics/temporal.py` — Time-windowed queries
- [ ] `graph/analytics/export.py` — Visualization export
- [ ] CLI commands for graph intelligence
- [ ] Integration with orchestrator.py

---

## Phase 12: Graph-RAG Hybrid Integration (4-6 hrs) — DEFERRED TO IPLAN-002

> Combines Graph Trading Intelligence (Phase 11) with RAG Trading Intelligence (Phase 10)

### 12.1 Hybrid Context Builder

**Implementation** (`trader/hybrid/context.py`):
```python
@dataclass
class UnifiedTradingContext:
    """Complete trading context combining Graph and RAG intelligence."""
    ticker: str
    decision_type: str

    # Graph intelligence
    graph_context: dict               # From graph/intelligence/decision_support.py
    strategy_rankings: list[dict]
    bias_chains: list[dict]
    portfolio_correlations: list[dict]

    # RAG intelligence
    rag_context: TradingContext       # From rag/trading/context.py
    semantic_results: list[SearchResult]
    bias_warnings: list[BiasWarning]
    similar_setups: list[SetupMatch]

    # Combined
    formatted: str

def build_unified_context(
    ticker: str,
    decision_type: str,
    thesis_direction: str = None,
    current_confidence: float = None,
    current_analysis: dict = None
) -> UnifiedTradingContext:
    """
    Build comprehensive trading context combining Graph and RAG.

    Graph provides: structural relationships, performance stats, bias chains
    RAG provides: semantic similarity, text content, outcome history
    """
    # Graph intelligence
    graph_ctx = enrich_analysis_context(ticker)

    with TradingGraph() as g:
        strategy_rankings = OutcomeWeightedTraversal(g).get_strategy_rankings(ticker)
        bias_chains = BiasTracker(g).detect_bias_chains()
        portfolio_corr = PortfolioRiskAnalysis(g).find_position_correlations()

    # RAG intelligence
    rag_ctx = build_trading_context(
        ticker=ticker,
        decision_type=decision_type,
        thesis_direction=thesis_direction,
        current_confidence=current_confidence,
        current_analysis=current_analysis
    )

    # Format combined context
    formatted = _format_unified_context(
        ticker=ticker,
        decision_type=decision_type,
        graph_ctx=graph_ctx,
        strategy_rankings=strategy_rankings,
        bias_chains=bias_chains,
        portfolio_corr=portfolio_corr,
        rag_ctx=rag_ctx
    )

    return UnifiedTradingContext(
        ticker=ticker,
        decision_type=decision_type,
        graph_context=graph_ctx,
        strategy_rankings=strategy_rankings,
        bias_chains=bias_chains,
        portfolio_correlations=portfolio_corr,
        rag_context=rag_ctx,
        semantic_results=rag_ctx.hybrid_context.results,
        bias_warnings=rag_ctx.bias_warnings,
        similar_setups=rag_ctx.similar_setups,
        formatted=formatted
    )
```

### 12.2 Graph-Guided RAG Search

**Implementation** (`trader/hybrid/search.py`):
```python
def graph_guided_rag_search(
    query: str,
    ticker: str,
    top_k: int = 5
) -> list[SearchResult]:
    """
    Use graph structure to guide RAG search.

    1. Get structurally related entities from graph
    2. Filter RAG search to documents mentioning those entities
    3. Return semantically relevant results within structural context
    """
    # Step 1: Get graph context
    with TradingGraph() as g:
        related_entities = g.find_related(ticker, depth=2)
        entity_names = [e['name'] for e in related_entities]

    # Step 2: Get document IDs that mention related entities
    related_docs = db.query("""
        SELECT DISTINCT doc_id
        FROM nexus.rag_chunks
        WHERE content ILIKE ANY($1)
    """, [[f'%{name}%' for name in entity_names[:20]]])

    # Step 3: Run RAG search within filtered documents
    return semantic_search(
        query=query,
        ticker=ticker,
        top_k=top_k,
        doc_ids=[d['doc_id'] for d in related_docs]
    )
```

### 12.3 Unified MCP Tools

**Implementation** (`mcp_trading_unified/tools/context.py`):
```python
UNIFIED_TOOLS = [
    {
        "name": "unified_trading_context",
        "description": "Get comprehensive trading context combining graph and RAG intelligence",
        "parameters": {
            "ticker": {"type": "string", "required": True},
            "decision_type": {"type": "string", "enum": ["entry", "exit", "size", "hold", "analysis"]},
            "thesis_direction": {"type": "string", "enum": ["long", "short"]},
            "confidence": {"type": "number"}
        }
    },
    {
        "name": "graph_guided_search",
        "description": "Search RAG within graph-connected context",
        "parameters": {
            "query": {"type": "string", "required": True},
            "ticker": {"type": "string", "required": True},
            "top_k": {"type": "integer", "default": 5}
        }
    }
]
```

### 12.4 Skill Integration

Update Claude skills to use unified context:

```python
# In skill execution flow (pre-analysis hook)
def inject_unified_context(ticker: str, decision_type: str, prompt: str) -> str:
    """Inject unified trading context before Claude analysis."""
    try:
        ctx = build_unified_context(
            ticker=ticker,
            decision_type=decision_type
        )
        return f"{prompt}\n\n## Trading Intelligence Context\n\n{ctx.formatted}"
    except Exception as e:
        log.warning(f"Failed to build unified context: {e}")
        return prompt  # Graceful degradation
```

### 12.5 Phase 12 Deliverables

- [ ] `trader/hybrid/__init__.py` — Hybrid module init
- [ ] `trader/hybrid/context.py` — Unified context builder
- [ ] `trader/hybrid/search.py` — Graph-guided RAG search
- [ ] `mcp_trading_unified/` — Unified MCP server
- [ ] Skill pre-analysis hooks for context injection
- [ ] CLI: `trading unified-context TICKER`
- [ ] Integration tests for hybrid queries

---

## Execution Order

### IPLAN-001 Scope (Phases 1-8): ~35-50 hrs

```
Phase 1 (Foundation) ─── 4-6 hrs
    │
    ├──→ Phase 2 (Graph Layer) ──┬──→ Phase 4 (MCP Servers) ─── 3-4 hrs
    │    8-12 hrs                │
    │                            │
    └──→ Phase 3 (RAG Layer) ────┘
         6-10 hrs
                                 │
                                 ▼
                    Phase 5 (CLI Integration) ─── 3-4 hrs
                                 │
                                 ▼
                    Phase 6 (Skills Integration) ─── 3-4 hrs
                                 │
                                 ▼
                    Phase 7 (Testing) ─── 6-10 hrs
                                 │
                                 ▼
                    Phase 8 (Hardening) ─── 3-4 hrs
                                 │
                    ═══════ IPLAN-001 COMPLETE ═══════
```

### IPLAN-002 Scope (Phases 9-12): ~25-40 hrs — DEFERRED

```
                    (Trigger: 50+ graph entities, 30+ RAG documents)
                                 │
    ┌────────────────────────────┼────────────────────────────┐
    │                            │                            │
    ▼                            ▼                            ▼
Phase 9                    Phase 10                    Phase 11
(RAG Advanced)         (RAG Trading Intel)        (Graph Trading Intel)
4-6 hrs                 6-8 hrs                    6-8 hrs
    │                            │                            │
    └────────────────────────────┼────────────────────────────┘
                                 │
                                 ▼
                    Phase 12 (Graph-RAG Hybrid) ─── 4-6 hrs
```

**Parallel execution**:
- Phases 2 and 3 can run in parallel after Phase 1
- Phase 4 (MCP Servers) depends on Phases 2 and 3
- Phases 9, 10, and 11 can run in parallel after Phase 8 (IPLAN-002)
- Phase 12 requires Phases 10 and 11 completion

---

## Environment Setup

### Required Environment Variables

```bash
# .env additions
NEO4J_PASS=trading2024              # Neo4j password

# Optional - for cloud fallback
OPENROUTER_API_KEY=sk-or-...        # OpenRouter API (pay-per-use)
ANTHROPIC_API_KEY=sk-ant-...        # Direct Claude API
OPENAI_API_KEY=sk-...               # Direct OpenAI
```

### Infrastructure Verification

```bash
# Verify Neo4j
curl -s http://localhost:7475/ | head -5

# Verify Ollama + required models
curl -s http://localhost:11434/api/tags | jq '.models[].name'
# Should include: qwen3:8b, nomic-embed-text

# Pull models if missing
ollama pull qwen3:8b
ollama pull nomic-embed-text

# Verify pgvector
docker exec nexus-postgres psql -U lightrag -c "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
```

---

## Success Criteria

### IPLAN-001 (Phases 1-8)

| Criterion | Measurement |
|-----------|-------------|
| Graph schema initialized | `graph init` succeeds, constraints visible in Neo4j |
| RAG schema initialized | `rag init` succeeds, tables exist in PostgreSQL |
| Graph extraction works | `graph extract FILE` returns entities with confidence |
| RAG embedding works | `rag embed FILE` creates chunks with embeddings |
| Graph search returns data | `graph search NVDA` shows connected nodes |
| RAG search returns data | `rag search "thesis"` shows relevant chunks |
| Hybrid context works | `rag_hybrid_context` combines vector + graph |
| MCP servers operational | Claude skills can call graph/rag tools |
| CLI fully functional | All subcommands execute without error |
| Tests pass | `pytest` runs clean in CI |
| Graceful degradation | Skills work when graph/RAG unavailable |

### IPLAN-002 (Phases 9-12) — Deferred

| Criterion | Measurement |
|-----------|-------------|
| Hybrid search works | `rag search --hybrid` returns BM25+vector results |
| Reranking improves relevance | Cross-encoder rerank shows better top-5 precision |
| Bias warnings surfaced | `trading biases TICKER` shows historical bias patterns |
| Calibration feedback works | `trading calibrate` shows conviction accuracy |
| Outcome-weighted queries work | `graph-intel outcomes TICKER` shows strategy rankings |
| Bias chains detected | `graph-intel biases --chains` identifies trigger patterns |
| Strategy decay detected | `graph-intel strategy-decay` flags declining strategies |
| Portfolio risk visible | `graph-intel risk-correlation` shows position overlaps |
| Unified context builds | `trading unified-context TICKER` combines both systems |
| Graph-guided RAG works | Search within structurally related context |
| Skills auto-inject context | Analysis prompts enriched with trading intelligence |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Ollama timeout | Field-by-field extraction (small prompts, 10-30s each) |
| Neo4j unavailable | Skills continue; pending commits queue for retry |
| pgvector unavailable | Skills continue without RAG context |
| All embedding providers fail | Log warning, skill proceeds without embedding |
| Mixed embedding dimensions | Enforce 768 dims; fatal error if mismatch |
| Schema migration breaks | Version tracking, tested migration scripts |
| Extraction quality low | Confidence thresholds, needs_review flag, re-extraction |

---

## References

- [TRADING_GRAPH_ARCHITECTURE.md](../TRADING_GRAPH_ARCHITECTURE.md)
- [TRADING_RAG_ARCHITECTURE.md](../TRADING_RAG_ARCHITECTURE.md)
