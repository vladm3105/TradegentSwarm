# Architecture Overview

TradegentSwarm is a multi-agent trading platform that combines Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system.

---

## System Architecture

```
┌─ HOST MACHINE ─────────────────────────────────────────────────────────────┐
│                                                                            │
│  ┌─ ORCHESTRATOR ─────────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  service.py (daemon)                                                │   │
│  │    │                                                                │   │
│  │    ├─ Tick loop: settings → schedules → earnings → heartbeat       │   │
│  │    │                                                                │   │
│  │    └─ orchestrator.py                                               │   │
│  │         │                                                           │   │
│  │         ├─ Stage 1: Analysis                                        │   │
│  │         │   └─ subprocess: claude --print ...                       │   │
│  │         │        ├─ mcp__ib-mcp (market data)                       │   │
│  │         │        ├─ trading-rag (semantic search)                   │   │
│  │         │        ├─ trading-graph (entity queries)                  │   │
│  │         │        └─ WebSearch / brave-browser (web research)        │   │
│  │         │                                                           │   │
│  │         ├─ Gate: Do Nothing? (EV >5%, confidence >60%, R:R >2:1)   │   │
│  │         │                                                           │   │
│  │         └─ Stage 2: Execution (if gate passes, paper mode)          │   │
│  │              └─ subprocess: claude --print ...                      │   │
│  │                   └─ mcp__ib-mcp (order placement)                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌─ KNOWLEDGE LAYER ──────────────────────────────────────────────────┐   │
│  │                                                                     │   │
│  │  RAG (pgvector)              Graph (Neo4j)                         │   │
│  │  ├─ Semantic search          ├─ Entity relationships               │   │
│  │  ├─ Similar analyses         ├─ Ticker peers                       │   │
│  │  ├─ Historical context       ├─ Risk factors                       │   │
│  │  └─ Reranking (v2.0)         └─ Bias patterns                      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
└─────────────────────── connects via localhost ports ───────────────────────┘
                              │          │          │
                         :5433 PG   :4002 IB   :7688 Neo4j
                              │          │          │
┌─ DOCKER COMPOSE ────────────┴──────────┴──────────┴────────────────────────┐
│                                                                            │
│  postgres              ib-gateway              neo4j                       │
│  pgvector:pg16         ghcr.io/gnzsnz/ib-gw   neo4j:5-community           │
│                                                                            │
│  nexus schema:         TWS API                 Knowledge Graph             │
│  - stocks              paper trading           Entity storage              │
│  - settings            VNC :5900               Cypher queries              │
│  - schedules                                                               │
│  - run_history         rag schema:                                         │
│  - ib_scanners         - documents                                         │
│  - service_status      - chunks                                            │
│                        - embeddings                                        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### Orchestrator

The orchestrator (`orchestrator.py`) is the central control plane:

| Component | Purpose |
|-----------|---------|
| `service.py` | Long-running daemon, tick loop |
| `orchestrator.py` | Pipeline engine, CLI commands |
| `db_layer.py` | PostgreSQL access (NexusDB class) |

**Why host-based (not Docker):** Claude Code CLI requires Node.js, `~/.claude/` auth, and MCP server configs—all on the host.

### Knowledge Layer

Two complementary systems provide historical context:

| System | Storage | Purpose | Use Case |
|--------|---------|---------|----------|
| **RAG** | PostgreSQL (pgvector) | Semantic search | "Find similar analyses" |
| **Graph** | Neo4j | Entity relationships | "What are NVDA's peers?" |

### Infrastructure (Docker)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | pgvector/pgvector:pg16 | 5433 | Database + embeddings |
| ib-gateway | gnzsnz/ib-gateway | 4002 | Paper trading API |
| neo4j | neo4j:5-community | 7688 | Knowledge graph |

---

## Data Flow

### Analysis Pipeline

```
1. TRIGGER
   │
   ├─ Manual: orchestrator.py analyze MSFT
   ├─ Schedule: service.py tick loop
   └─ Scanner: auto-analyze top results
   │
   ▼
2. PRE-ANALYSIS CONTEXT
   │
   ├─ RAG: semantic_search("MSFT analysis history")
   ├─ Graph: get_ticker_context("MSFT")
   └─ IB: get_stock_price("MSFT"), get_historical_data(...)
   │
   ▼
3. SKILL EXECUTION
   │
   ├─ Load skill: .claude/skills/stock-analysis.md
   ├─ Execute phases: Catalyst → Technical → Scenarios → ...
   └─ Generate recommendation: WATCH/BUY/SELL
   │
   ▼
4. GATE CHECK
   │
   ├─ EV > 5%?
   ├─ Confidence > 60%?
   ├─ R:R > 2:1?
   └─ Edge not priced in?
   │
   ├─ FAIL → Save analysis, skip execution
   │
   ▼
5. POST-SAVE INDEXING
   │
   ├─ RAG: embed_document(analysis.yaml)
   ├─ Graph: extract_document(analysis.yaml)
   └─ GitHub: push_files(tradegent-knowledge)
   │
   ▼
6. EXECUTION (if gate passed + paper mode)
   │
   └─ IB: place_order(...)
```

### Knowledge Indexing

```
YAML File (source of truth)
    │
    ├───────────────┐
    │               │
    ▼               ▼
┌─────────┐   ┌─────────┐
│   RAG   │   │  Graph  │
│ Embed   │   │ Extract │
└────┬────┘   └────┬────┘
     │             │
     ▼             ▼
┌─────────┐   ┌─────────┐
│pgvector │   │  Neo4j  │
│ chunks  │   │  nodes  │
└─────────┘   └─────────┘
```

---

## Three-Layer Data Model

```
Layer 1: FILES (Source of Truth)
─────────────────────────────────
Location: tradegent_knowledge/knowledge/**/*.yaml
Properties:
  - Authoritative: Files define what's true
  - Portable: Can move between systems
  - Rebuildable: RAG/Graph derived from files

Layer 2: RAG (Semantic Search)
─────────────────────────────────
Storage: PostgreSQL with pgvector extension
Schema: nexus.rag_documents, nexus.rag_chunks
Rebuilds from: Layer 1 files via embed_document()

Layer 3: GRAPH (Entity Relations)
─────────────────────────────────
Storage: Neo4j
Rebuilds from: Layer 1 files via extract_document()
```

**Conflict resolution:** If RAG/Graph conflict with files, files win. Re-index to fix.

---

## MCP Server Integration

Claude Code uses MCP (Model Context Protocol) servers for tool access:

| Server | Transport | Purpose |
|--------|-----------|---------|
| `ib-mcp` | SSE (http://localhost:8100) | Market data, orders |
| `trading-rag` | stdio | Semantic search |
| `trading-graph` | stdio | Entity queries |
| `brave-browser` | stdio | Web scraping (protected content) |
| `github-vl` | stdio | Knowledge repo commits |

> **Note**: For general web search, use Claude Code's built-in `WebSearch` tool. The `brave-browser` MCP is for scraping protected content (Seeking Alpha, Medium, etc.) with persistent login sessions.

See [MCP Servers](mcp-servers.md) for configuration details.

---

## Safety Architecture

### Defense in Depth

```
Layer 1: dry_run_mode = true (default)
         └─ Blocks ALL Claude Code calls

Layer 2: auto_execute_enabled = false
         └─ Blocks Stage 2 (order placement)

Layer 3: stock.state = analysis
         └─ Per-stock gate, no orders until "paper"

Layer 4: Do Nothing Gate
         └─ EV, confidence, R:R thresholds

Layer 5: Paper trading only
         └─ IB Gateway port 4002 (paper account)

Layer 6: Rate limits
         └─ max_daily_analyses, max_daily_executions
```

### Trading Modes

| Mode | dry_run | auto_execute | stock.state | Behavior |
|------|---------|--------------|-------------|----------|
| Dry Run | true | any | any | Logs only, no calls |
| Analysis Only | false | false | analysis | Reports, no orders |
| Paper Trading | false | true | paper | Paper orders |
| Live Trading | — | — | live | **Blocked in code** |

---

## Related Documentation

- [RAG System](rag-system.md) - Embedding and search details
- [Graph System](graph-system.md) - Entity extraction and queries
- [MCP Servers](mcp-servers.md) - Server configuration
- [Database Schema](database-schema.md) - Table definitions
