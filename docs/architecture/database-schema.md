# Database Schema

TradegentSwarm uses PostgreSQL (with pgvector) and Neo4j for data storage.

---

## Overview

| Database | Purpose | Port |
|----------|---------|------|
| PostgreSQL | Orchestrator state, RAG embeddings | 5433 |
| Neo4j | Knowledge graph | 7688 |

---

## PostgreSQL Schema

### Schema: `nexus`

Core orchestrator tables for stocks, settings, and run history.

#### `nexus.stocks`

Stock watchlist and state machine.

```sql
CREATE TABLE nexus.stocks (
    ticker VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100),
    state VARCHAR(20) DEFAULT 'analysis',
    is_enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 5,
    default_analysis_type VARCHAR(20) DEFAULT 'stock',
    next_earnings_date DATE,
    tags TEXT[],
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

| Column | Type | Description |
|--------|------|-------------|
| `ticker` | VARCHAR(10) | Stock symbol (PK) |
| `name` | VARCHAR(100) | Company name |
| `state` | VARCHAR(20) | analysis, paper, live |
| `is_enabled` | BOOLEAN | Include in batch runs |
| `priority` | INTEGER | Processing order (10=highest) |
| `default_analysis_type` | VARCHAR(20) | stock or earnings |
| `next_earnings_date` | DATE | Triggers pre-earnings |
| `tags` | TEXT[] | Categories (ai, tech, etc.) |

#### `nexus.settings`

System configuration key-value store.

```sql
CREATE TABLE nexus.settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `dry_run_mode` | true | Block all Claude calls |
| `auto_execute_enabled` | false | Enable order placement |
| `max_daily_analyses` | 10 | Rate limit |
| `max_daily_executions` | 5 | Rate limit |

#### `nexus.schedules`

Cron-like scheduling for automated runs.

```sql
CREATE TABLE nexus.schedules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    schedule_type VARCHAR(20),
    cron_expression VARCHAR(50),
    is_enabled BOOLEAN DEFAULT true,
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    config JSONB
);
```

#### `nexus.run_history`

Audit log of all pipeline runs.

```sql
CREATE TABLE nexus.run_history (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(10),
    run_type VARCHAR(50),
    status VARCHAR(20),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    output_path TEXT,
    error_message TEXT,
    metadata JSONB
);
```

#### `nexus.service_status`

Service daemon heartbeat.

```sql
CREATE TABLE nexus.service_status (
    id INTEGER PRIMARY KEY DEFAULT 1,
    status VARCHAR(20),
    last_heartbeat TIMESTAMP,
    started_at TIMESTAMP,
    pid INTEGER
);
```

---

### Schema: `nexus` (RAG Tables)

RAG embedding storage using pgvector.

#### `nexus.rag_documents`

Document metadata.

```sql
CREATE TABLE nexus.rag_documents (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    file_path TEXT,
    doc_type VARCHAR(50),
    ticker VARCHAR(10),
    chunk_count INTEGER,
    embed_model VARCHAR(100),
    embed_version VARCHAR(20),
    content_hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rag_docs_ticker ON nexus.rag_documents(ticker);
CREATE INDEX idx_rag_docs_type ON nexus.rag_documents(doc_type);
```

| Column | Type | Description |
|--------|------|-------------|
| `doc_id` | VARCHAR(255) | Unique document ID |
| `file_path` | TEXT | Source file path |
| `doc_type` | VARCHAR(50) | stock-analysis, earnings, etc. |
| `ticker` | VARCHAR(10) | Associated ticker |
| `chunk_count` | INTEGER | Number of chunks |
| `embed_model` | VARCHAR(100) | Model used |
| `content_hash` | VARCHAR(64) | SHA-256 for change detection |

#### `nexus.rag_chunks`

Embedded text chunks with vectors.

```sql
CREATE TABLE nexus.rag_chunks (
    id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES nexus.rag_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    section_path TEXT,
    content TEXT NOT NULL,
    content_tokens INTEGER,
    embedding vector(1536),
    content_tsv tsvector,
    ticker VARCHAR(10),
    doc_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Vector similarity index (HNSW)
CREATE INDEX idx_rag_chunks_embedding ON nexus.rag_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Full-text search index (BM25)
CREATE INDEX idx_rag_chunks_tsv ON nexus.rag_chunks USING gin(content_tsv);

-- Filtering indexes
CREATE INDEX idx_rag_chunks_ticker ON nexus.rag_chunks(ticker);
CREATE INDEX idx_rag_chunks_doc_type ON nexus.rag_chunks(doc_type);
```

| Column | Type | Description |
|--------|------|-------------|
| `doc_id` | INTEGER | FK to rag_documents |
| `chunk_index` | INTEGER | Position in document |
| `section_path` | TEXT | YAML path (e.g., "analysis.catalyst") |
| `content` | TEXT | Chunk text |
| `content_tokens` | INTEGER | Token count |
| `embedding` | vector(1536) | OpenAI embedding |
| `content_tsv` | tsvector | BM25 full-text |

---

## Neo4j Schema

Knowledge graph for entities and relationships.

### Node Labels

| Label | Properties | Description |
|-------|------------|-------------|
| `Ticker` | symbol, name | Stock symbol |
| `Company` | name, description | Company entity |
| `Sector` | name | Industry sector |
| `Industry` | name | Specific industry |
| `Risk` | name, description | Risk factor |
| `Strategy` | name, description | Trading strategy |
| `Bias` | name, description | Cognitive bias |
| `Pattern` | name, description | Chart pattern |
| `Catalyst` | name, description | Price catalyst |
| `Product` | name, description | Company product |
| `FinancialMetric` | name, value | Financial data |
| `Document` | doc_id, file_path, doc_type | Source document |

### Relationship Types

| Relationship | From | To | Properties |
|--------------|------|----|-----------|
| `ISSUED` | Company | Ticker | — |
| `IN_SECTOR` | Company | Sector | — |
| `IN_INDUSTRY` | Company | Industry | — |
| `COMPETES_WITH` | Company | Company | — |
| `THREATENS` | Risk | Ticker | severity |
| `EXPOSED_TO` | Ticker | Risk | — |
| `WORKS_FOR` | Strategy | Ticker | win_rate |
| `DETECTED_IN` | Bias | Document | count |
| `EXTRACTED_FROM` | * | Document | confidence |

### Indexes

```cypher
-- Ticker lookup
CREATE INDEX ticker_symbol FOR (t:Ticker) ON (t.symbol);

-- Document lookup
CREATE INDEX doc_id FOR (d:Document) ON (d.doc_id);

-- Entity names
CREATE INDEX company_name FOR (c:Company) ON (c.name);
CREATE INDEX risk_name FOR (r:Risk) ON (r.name);
CREATE INDEX bias_name FOR (b:Bias) ON (b.name);
```

### Example Queries

```cypher
-- Get ticker context
MATCH (t:Ticker {symbol: $ticker})
OPTIONAL MATCH (t)<-[:ISSUED]-(c:Company)-[:IN_SECTOR]->(s:Sector)
OPTIONAL MATCH (r:Risk)-[:THREATENS]->(t)
RETURN t, c, s, collect(r) as risks;

-- Find sector peers
MATCH (t:Ticker {symbol: $ticker})<-[:ISSUED]-(c:Company)-[:IN_SECTOR]->(s:Sector)
MATCH (s)<-[:IN_SECTOR]-(peer:Company)-[:ISSUED]->(pt:Ticker)
WHERE pt.symbol <> $ticker
RETURN pt.symbol as peer, s.name as sector;

-- Get bias history
MATCH (b:Bias)-[d:DETECTED_IN]->(doc:Document)
RETURN b.name as bias, count(d) as occurrences,
       collect(DISTINCT doc.ticker) as tickers
ORDER BY occurrences DESC;
```

---

## Data Flow

```
YAML Document (source of truth)
        │
        ├─────────────────────────────────────┐
        │                                     │
        ▼                                     ▼
┌───────────────────┐               ┌───────────────────┐
│    PostgreSQL     │               │      Neo4j        │
│                   │               │                   │
│ ┌───────────────┐ │               │ ┌───────────────┐ │
│ │ rag_documents │ │               │ │    Nodes      │ │
│ └───────┬───────┘ │               │ │ - Ticker      │ │
│         │         │               │ │ - Company     │ │
│ ┌───────▼───────┐ │               │ │ - Risk        │ │
│ │  rag_chunks   │ │               │ │ - Strategy    │ │
│ │  (vectors)    │ │               │ └───────────────┘ │
│ └───────────────┘ │               │                   │
│                   │               │ ┌───────────────┐ │
│ Semantic Search   │               │ │ Relationships │ │
│ "similar analyses"│               │ │ - IN_SECTOR   │ │
│                   │               │ │ - THREATENS   │ │
└───────────────────┘               │ │ - WORKS_FOR   │ │
                                    │ └───────────────┘ │
                                    │                   │
                                    │ Graph Queries     │
                                    │ "NVDA's peers"    │
                                    └───────────────────┘
```

---

## Maintenance

### PostgreSQL

```bash
# Check RAG statistics
psql -h localhost -p 5433 -U tradegent -d tradegent -c "
SELECT
    (SELECT COUNT(*) FROM nexus.rag_documents) as documents,
    (SELECT COUNT(*) FROM nexus.rag_chunks) as chunks;
"

# Check embedding dimensions
psql -h localhost -p 5433 -U tradegent -d tradegent -c "
SELECT embed_model, COUNT(*) FROM nexus.rag_documents GROUP BY embed_model;
"

# Vacuum and analyze
psql -h localhost -p 5433 -U tradegent -d tradegent -c "
VACUUM ANALYZE nexus.rag_chunks;
"
```

### Neo4j

```cypher
// Check node counts
MATCH (n) RETURN labels(n) as label, count(n) as count;

// Check relationship counts
MATCH ()-[r]->() RETURN type(r) as type, count(r) as count;

// Clear all data (development only)
MATCH (n) DETACH DELETE n;
```

---

## Related Documentation

- [Architecture Overview](overview.md)
- [RAG System](rag-system.md)
- [Graph System](graph-system.md)
