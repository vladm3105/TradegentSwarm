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
5. POST-SAVE INDEXING (priority order for fast UI)
   │
   ├─ [1] DB: upsert_kb_*() → UI can display immediately
   ├─ [2] RAG: embed_document() → semantic search
   ├─ [3] Graph: extract_document() → entity relations
   └─ GitHub: push_files(tradegent-knowledge)
   │
   ▼
6. EXECUTION (if gate passed + paper mode)
   │
   └─ IB: place_order(...)
```

### Knowledge Indexing (ingest.py)

```
YAML File (source of truth)
    │
    │  auto-ingest hook triggers ingest.py
    ▼
┌─────────────────────────────────────────────────┐
│  PRIORITY ORDER (optimized for UI delivery)     │
├─────────────────────────────────────────────────┤
│  [1] PostgreSQL kb_* tables                     │
│      └─ UI can display analysis immediately     │
│                                                 │
│  [2] pgvector RAG chunks                        │
│      └─ Semantic search for similar analyses    │
│                                                 │
│  [3] Neo4j Graph nodes                          │
│      └─ Entity relationships and patterns       │
└─────────────────────────────────────────────────┘
```

**Why DB first?** The UI queries `kb_*` tables directly. Database insert is fastest,
so the UI can display new analysis immediately while RAG/Graph indexing continues.

---

## Four-Layer Data Model

```
Layer 1: FILES (Source of Truth)
─────────────────────────────────
Location: tradegent_knowledge/knowledge/**/*.yaml
Properties:
  - Authoritative: Files define what's true
  - Portable: Can move between systems
  - Git versioned: Full audit trail
  - Rebuildable: All derived storage can be rebuilt from files

Layer 2: DATABASE (Structured Queries) - PRIORITY 1
─────────────────────────────────
Storage: PostgreSQL nexus.kb_* tables
Purpose: Fast SQL queries, UI rendering
Rebuilds from: Layer 1 files via upsert_kb_*()
Tables: kb_stock_analyses, kb_earnings_analyses, kb_trade_journals, etc.

Layer 3: RAG (Semantic Search) - PRIORITY 2
─────────────────────────────────
Storage: PostgreSQL with pgvector extension
Schema: nexus.rag_documents, nexus.rag_chunks
Rebuilds from: Layer 1 files via embed_document()

Layer 4: GRAPH (Entity Relations) - PRIORITY 3
─────────────────────────────────
Storage: Neo4j
Rebuilds from: Layer 1 files via extract_document()
```

**Conflict resolution:** If derived storage conflicts with files, files win. Re-ingest to fix.

**UI Visualization:** The tradegent_ui renders visualizations directly from Layer 2
(kb_* tables). SVG file generation is deprecated (`svg_generation_enabled=false`).

### Layer 5: UI Parser Registry

Because analysis skill templates evolve across versions, the frontend uses a **version-specific parser registry** to translate raw `yaml_content` (JSONB) into the `AnalysisDetail` display model:

```
kb_stock_analyses / kb_earnings_analyses
  .yaml_content (JSONB)  ←  source of truth
  .schema_version        ←  e.g. "2.7"
  .analysis_type         ←  "stock-analysis" | "earnings-analysis"
         │
         │  frontend/lib/parsers/registry.ts
         │  resolves key: "<type>:<major.minor>"
         ▼
  version-specific parser  (one per schema version)
         │
         ▼
  AnalysisDetail  →  React components
```

**Registered parsers:**

| Key | File |
|-----|------|
| `stock-analysis:2.6` | `lib/parsers/stock/v2.6.ts` |
| `stock-analysis:2.7` | `lib/parsers/stock/v2.7.ts` |
| `earnings-analysis:2.3` | `lib/parsers/earnings/v2.3.ts` |
| `earnings-analysis:2.5` | `lib/parsers/earnings/v2.5.ts` |
| `earnings-analysis:2.6` | `lib/parsers/earnings/v2.6.ts` |

To support a new schema version: add `lib/parsers/<type>/vX.Y.ts` and one `REGISTRY.set()` line in `registry.ts`.

See [UI_FEATURES — Analysis Display System](../../tradegent_ui/docs/UI_FEATURES.md#8-analysis-display-system) for field-path mappings per version.

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

## LiteLLM Multi-Provider Gateway

TradegentSwarm uses **LiteLLM** as a unified gateway for multi-provider LLM access:

| Role Alias | Purpose | Default Route |
|------------|---------|---------------|
| `reasoning_premium` | High-stakes synthesis | `openai/gpt-4o` |
| `reasoning_standard` | Primary analysis | `openrouter/gpt-4o-mini` |
| `extraction_fast` | Parsing, normalization | `openai/gpt-4o-mini` |
| `critic_model` | Self-review | `openai/gpt-4o-mini` |
| `summarizer_fast` | UI summaries | `openai/gpt-4o-mini` |

**Supported providers**: OpenAI, Anthropic, Azure, Gemini, OpenRouter, Ollama, Mistral

See [LiteLLM Integration](litellm-integration.md) for configuration details.

---

## ADK Migration Architecture

For the ADK + LiteLLM target architecture, configuration governance model, and workflow visualizations, see:

- [LiteLLM Integration](litellm-integration.md) - Multi-provider gateway configuration
- [ADK Multi-Provider Orchestration](adk-multi-provider-orchestration.md) - Full orchestration architecture
- [ADK Multi-Provider Orchestration SVG](adk-multi-provider-orchestration.svg) - Visual diagram

---

## Related Documentation

- [Skill-Database Mapping](skill-database-mapping.md) - Complete field mapping from skills to tables
- [Database Schema](database-schema.md) - Table definitions
- [RAG System](rag-system.md) - Embedding and search details
- [Graph System](graph-system.md) - Entity extraction and queries
- [MCP Servers](mcp-servers.md) - Server configuration
