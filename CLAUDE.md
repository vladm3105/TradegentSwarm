# TradegentSwarm - Claude Code Instructions

> **Skills Version**: v2.5 (stock-analysis, earnings-analysis), v2.1 (other skills)
> **Last Updated**: 2026-02-22

**Tradegent** — AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system. A multi-agent swarm for market analysis, trade execution, and knowledge persistence.

## Temporary Files and Implementation Plans

Use the `tmp/` directory for ephemeral content that should not be committed:

| Directory | Purpose |
|-----------|---------|
| `tmp/` | One-time scripts, temporary docs, scratch files |
| `tmp/IPLAN/` | Implementation plans (session-based execution plans) |

**IPLAN Format**: `IPLAN-NNN_{descriptive_slug}.md`
- Session-based execution plans with bash commands
- Not committed to git (ephemeral)
- Example: `tmp/IPLAN/IPLAN-001_observability_integration.md`

```bash
# Create tmp directories if needed
mkdir -p tmp/IPLAN
```

## Project Structure

```
tradegent/
├── .claude/skills/          # Claude Code skills (auto-invoke enabled)
├── tradegent/               # Tradegent Platform (Python)
│   ├── service.py           # Long-running daemon
│   ├── orchestrator.py      # Pipeline engine + CLI
│   ├── db_layer.py          # PostgreSQL access layer
│   ├── docker-compose.yml   # Infrastructure services
│   ├── rag/                 # RAG module (embeddings, search)
│   │   └── mcp_server.py    # MCP server (primary interface)
│   └── graph/               # Graph module (Neo4j, extraction)
│       └── mcp_server.py    # MCP server (primary interface)
│
└── tradegent_knowledge/     # Trading Knowledge System (separate private repo)
    ├── skills/              # Agent skill definitions (SKILL.md + template.yaml)
    ├── knowledge/           # Trading data & analyses (YAML documents)
    ├── examples/            # Sample configs and analyses for reference
    └── workflows/           # CI/CD & validation schemas
```

## Claude Code Skills

Skills in `.claude/skills/` auto-invoke based on context. Each skill has:
- YAML frontmatter with metadata and triggers
- Pre-analysis context retrieval (RAG + Graph)
- Real-time data gathering (IB MCP)
- Post-save hooks (index to knowledge base)
- Chaining to related skills

### Skill Index

| Skill                 | Version | Triggers                                                 | Category   |
| --------------------- | ------- | -------------------------------------------------------- | ---------- |
| **stock-analysis**    | v2.5    | "stock analysis", "technical analysis", "value analysis" | Analysis   |
| **earnings-analysis** | v2.5    | "earnings analysis", "pre-earnings", "before earnings"   | Analysis   |
| **research-analysis** | v2.1    | "research", "macro analysis", "sector analysis"          | Research   |
| **ticker-profile**    | v2.1    | "ticker profile", "what do I know about"                 | Knowledge  |
| **trade-journal**     | v2.1    | "log trade", "bought", "sold", "entered position"        | Trade Mgmt |
| **watchlist**         | v2.1    | "watchlist", "add to watchlist", "watch this"            | Trade Mgmt |
| **post-trade-review** | v2.1    | "review trade", "closed trade", "what did I learn"       | Learning   |
| **scan**              | v1.0    | "scan", "find opportunities", "what should I trade"      | Scanning   |

### v2.3 Key Features (stock-analysis, earnings-analysis)

- **Steel-man bear case** with scored arguments
- **Bias countermeasures** (rule + implementation + checklist + mantra)
- **Pre-exit gate** for loss aversion prevention
- **Do Nothing gate** (EV >5%, Confidence >60%, R:R >2:1, Edge exists)
- **4-scenario framework** (bull, base, bear, disaster)
- **Meta-learning** with validation tracking
- **Falsification criteria** (conditions that break thesis)
- **Data quality** and news age checks

### Skill Workflow Pattern

Every skill follows this integrated pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│                         SKILL WORKFLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   PRE-      │    │   EXECUTE   │    │   POST-     │         │
│  │   ANALYSIS  │───▶│   SKILL     │───▶│   SAVE      │         │
│  │   CONTEXT   │    │   WORKFLOW  │    │   HOOKS     │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│        │                  │                  │                  │
│        ▼                  ▼                  ▼                  │
│  ┌───────────┐      ┌───────────┐      ┌───────────┐           │
│  │ RAG+Graph │      │ IB MCP +  │      │ Graph +   │           │
│  │ Context   │      │ Web Data  │      │ RAG Index │           │
│  └───────────┘      └───────────┘      └───────────┘           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Step 1: Pre-Analysis Context**
```yaml
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings analysis", "analysis_type": "earnings-analysis"}
```

**Step 2: Real-Time Data**
```yaml
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "NVDA"}

Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "NVDA", "duration": "3 M", "bar_size": "1 day"}
```

**Step 3: Execute Skill Workflow** (read SKILL.md, follow phases)

**Step 4: Save Output** (to `tradegent_knowledge/knowledge/`)

**Step 5: Post-Save Indexing** (REQUIRED for all skills)

Every skill MUST complete these steps after saving output:

```yaml
# 1. Index in Graph (entity extraction)
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/{output_path}"}

# 2. Embed for RAG (semantic search)
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/{output_path}"}

# 3. Push to Knowledge Repo (PRIVATE)
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge   # PRIVATE knowledge repo
  branch: main
  files: [{path: "knowledge/{output_path}", content: ...}]
  message: "Add {skill_name} for {TICKER}"
```

**Why this matters:**
- Without indexing, documents are invisible to RAG search and Graph queries
- Pre-analysis context retrieval (Step 1) depends on previous documents being indexed
- The learning loop requires indexed post-trade reviews and learnings

### Workflow Chains

```text
scan → earnings-analysis → watchlist → trade-journal → post-trade-review
         ↓                                    ↓
    stock-analysis ─────────────────────→ ticker-profile
         ↓
      research
```

**Automatic chaining:**

- Analysis recommends WATCH → triggers watchlist skill
- Trade journal exit → triggers post-trade-review skill
- Scanner high score → triggers appropriate analysis skill
- Post-trade review → updates ticker-profile

## Key Conventions

### File Naming
All trading documents use ISO 8601 format:
```
{TICKER}_{YYYYMMDDTHHMM}.yaml
```
Example: `NVDA_20250120T0900.yaml`

### Skill → Knowledge Mapping

| Skill | Output Location |
|-------|------------------|
| earnings-analysis | `knowledge/analysis/earnings/` |
| stock-analysis | `knowledge/analysis/stock/` |
| research-analysis | `knowledge/analysis/research/` |
| ticker-profile | `knowledge/analysis/ticker-profiles/` |
| trade-journal | `knowledge/trades/` |
| watchlist | `knowledge/watchlist/` |
| post-trade-review | `knowledge/reviews/` |
| market-scanning | Uses `knowledge/scanners/`, outputs to `watchlist/` |

## Executing Skills

When a skill is invoked (auto or manual):

1. Read the `SKILL.md` file from `tradegent_knowledge/skills/{skill-name}/`
2. Follow the workflow steps exactly
3. Use the `template.yaml` structure for output
4. Save output to corresponding `tradegent_knowledge/knowledge/` folder
5. Check for chaining actions (WATCH → watchlist, exit → review)

## Scanner System

Scanners are YAML configurations that define systematic rules for finding trading opportunities. They encode your trading edge in a repeatable way.

### Scanner Types

| Type | Folder | Run Time | Examples |
|------|--------|----------|----------|
| **Daily** | `scanners/daily/` | Once per day | Pre-market gaps, earnings momentum |
| **Intraday** | `scanners/intraday/` | Multiple times | Options flow, unusual volume |
| **Weekly** | `scanners/weekly/` | Weekly | Earnings calendar, 13F filings |

### Daily Schedule (ET)

| Time | Scanner | Purpose |
|------|---------|---------|
| 07:00 | news-catalyst | Find overnight news |
| 08:30 | premarket-gap | Identify gaps >3% |
| 09:35 | market-regime | Classify bull/bear/neutral |
| 09:45 | earnings-momentum | Pre-earnings setups |
| 10:00+ | unusual-volume | Volume spikes (repeats) |
| 15:45 | 52w-extremes | Breakouts/breakdowns |
| 16:15 | sector-rotation | Money flow analysis |

### Scanner Structure

```yaml
_meta:              # ID, version, schedule
scanner_config:     # Name, priority, limits
scanner:            # Data sources (IB + web)
quality_filters:    # Liquidity, fundamentals, exclusions
scoring:            # Weighted criteria (sum to 1.0)
output:             # Format, fields, storage
agent_instructions: # Step-by-step execution
```

### Scoring and Routing

Scanners score candidates using weighted criteria (weights sum to 1.0):

```
Score = Σ (Criterion × Weight)

≥ 7.5: High Priority → Trigger full analysis (earnings-analysis or stock-analysis)
6.5-7.4: Good → Add to watchlist, monitor closely
5.5-6.4: Marginal → Add to watchlist, lower priority
< 5.5: Skip
```

See `docs/SCANNER_ARCHITECTURE.md` for detailed scoring criteria and routing logic.

### Running Scanners

```yaml
# Load scanner config
Read: tradegent_knowledge/knowledge/scanners/daily/earnings-momentum.yaml

# Execute IB scanner
Tool: mcp__ib-mcp__run_scanner
Input: {"scan_code": "TOP_OPEN_PERC_GAIN", "max_results": 50}

# Get detailed quotes
Tool: mcp__ib-mcp__get_quotes_batch
Input: {"symbols": ["NVDA", "AAPL", "..."]}

# Search for catalysts
Tool: mcp__brave-search__brave_web_search
Input: {"query": "NVDA earnings preview analyst"}
```

### Available Scanners

| Scanner | Category | Key Criteria |
|---------|----------|--------------|
| `premarket-gap` | Momentum | Gap >3%, catalyst, volume |
| `earnings-momentum` | Earnings | Beat history, IV, sentiment |
| `news-catalyst` | Event | Material news, price impact |
| `52w-extremes` | Technical | Breakout/breakdown, volume |
| `oversold-bounce` | Mean Reversion | RSI, support, oversold |
| `sector-rotation` | Macro | Sector flows, relative strength |
| `options-flow` | Sentiment | Unusual options activity |
| `unusual-volume` | Momentum | Volume spikes, news |

Scanner configs are in `tradegent_knowledge/knowledge/scanners/` — treat as sensitive (they encode your edge).

## Watchlist Management

Watchlist entries track potential trades waiting for specific trigger conditions.

### Watchlist Lifecycle

```
ENTRY SOURCES           ACTIVE              RESOLUTION
────────────────────────────────────────────────────────
Scanner (5.5-7.4)  ─┐
Analysis (WATCH)   ─┼─▶ status: active ─┬─▶ triggered → trade-journal
User request       ─┘   Daily review    ├─▶ invalidated → archive
                                        └─▶ expired → archive
```

### Adding to Watchlist

| Source | Condition |
|--------|-----------|
| Scanner | Score 5.5-7.4 (not high enough for immediate analysis) |
| Analysis | WATCH recommendation (good setup, wrong timing/price) |
| User | "add TICKER to watchlist" |

**Required fields:**
- `entry_trigger`: Specific condition (price, event, combined)
- `invalidation`: When to remove without triggering
- `expires`: Max 30 days
- `priority`: high / medium / low

### Removing from Watchlist

| Reason | Status | Action |
|--------|--------|--------|
| Trigger fired | `triggered` | Create trade journal, archive |
| Thesis broken | `invalidated` | Archive with lesson |
| Time exceeded | `expired` | Archive |
| User removes | N/A | Delete or archive |

### Expiration Rules

**If a stock is not traded within 30 days, it is marked as expired.**

| Setup Type | Recommended Expiration |
|------------|------------------------|
| Earnings play | Earnings date |
| Breakout watch | 7-14 days |
| Pullback entry | 5-10 days |
| General thesis | 30 days (max) |

Two expiration mechanisms (whichever comes first):
- **Absolute**: `_meta.expires: "2025-03-22"` — Hard deadline
- **Relative**: `invalidation.time_limit_days: 10` — Days from creation

### Daily Review

```yaml
FOR EACH active entry:
  1. Check expiration → expired? (cheapest check first)
  2. Check invalidation → invalidated?
  3. Check trigger → triggered?
  4. Check news → update or invalidate?
```

### Trigger → Trade Journal Chain

```yaml
# When trigger fires
IF entry_trigger MET:
  status: "triggered"
  → Invoke trade-journal skill
  → Archive watchlist entry
```

See `tradegent_knowledge/knowledge/watchlist/README.md` for full documentation.

## Tradegent Platform

### Environment Variables

Required environment variables for running the orchestrator (set in `.env` or export):

```bash
# PostgreSQL (pgvector for RAG embeddings)
export PG_USER=lightrag
export PG_PASS=<password>
export PG_DB=lightrag
export PG_HOST=localhost
export PG_PORT=5433

# Neo4j (Knowledge Graph)
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASS=<password>

# LLM Providers (separate for embeddings vs extraction)
export EMBED_PROVIDER=ollama          # RAG embeddings (keep consistent!)
export EXTRACT_PROVIDER=openrouter    # Graph extraction (can use cloud for speed)
export LLM_API_KEY=<api-key>          # Required for openrouter/openai/claude_api
```

### LLM Provider Configuration

| Task | Variable | Options | Notes |
|------|----------|---------|-------|
| RAG Embeddings | `EMBED_PROVIDER` | ollama, openrouter, openai | **Must stay consistent** - don't mix |
| Graph Extraction | `EXTRACT_PROVIDER` | ollama, openrouter, openai, claude_api | Can switch freely |

**Recommended setup (current):**
- `EMBED_PROVIDER=openai` - Best quality embeddings (text-embedding-3-large, 1536 dims via API truncation, ~$2/year)
- `EXTRACT_PROVIDER=openai` - Fast entity extraction (gpt-4o-mini, 12x faster than Ollama, ~$0.001/analysis)

> **Note**: We use 1536 dimensions (not 3072) because pgvector's HNSW index has a 2000 dimension limit. The OpenAI API truncates embeddings to the requested dimension.

### Running Commands
```bash
cd tradegent

# Set environment variables first (or source .env)
export PG_USER=lightrag PG_PASS=... PG_DB=lightrag PG_HOST=localhost PG_PORT=5433
export NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASS=...

python orchestrator.py --help     # CLI commands
python orchestrator.py analyze NVDA --type stock  # Run analysis
python service.py                 # Start daemon
```

### Infrastructure
```bash
cd tradegent
docker compose up -d              # Start PostgreSQL, IB Gateway, Neo4j
docker compose logs -f            # View logs
```

### Database
- PostgreSQL stores all pipeline config, tickers, and results
- Schema in `tradegent/db/init.sql`
- Use `db_layer.py` for all database operations

### Watchlist Management

Stocks are stored in `nexus.stocks` table with state machine: `analysis` → `paper` → `live`

```bash
# List all stocks
python orchestrator.py stock list

# Add a stock
python orchestrator.py stock add PLTR --priority 6 --tags ai defense --comment "Palantir"

# Enable/disable for automated runs
python orchestrator.py stock enable NVDA
python orchestrator.py stock disable TSLA

# Change state (analysis → paper enables paper trading)
python orchestrator.py stock set-state NVDA paper

# Analyze all enabled stocks
python orchestrator.py watchlist
```

| Column | Purpose |
|--------|---------|
| `ticker` | Stock symbol (primary key) |
| `state` | `analysis` (observe) / `paper` (paper trade) / `live` (future) |
| `is_enabled` | Include in automated `watchlist` runs (see below) |
| `priority` | Processing order (10=highest) |
| `default_analysis_type` | `earnings` or `stock` |
| `next_earnings_date` | Triggers pre-earnings analysis |
| `tags` | Filterable categories (mega_cap, ai, etc.) |

**Enable/Disable behavior:**
- `is_enabled=true`: Stock included in `watchlist` and `run-due` batch commands
- `is_enabled=false`: Stock skipped in batch runs, but manual `analyze TICKER` still works
- Use case: Temporarily pause a stock (too volatile, no catalyst) without removing it

### Trading Modes

> **Safety Default**: The system starts with `dry_run_mode=true`, which blocks ALL Claude Code calls and only logs what it would do. You must explicitly disable dry run mode to enable any operation.

| Mode | Settings | Stock State | Behavior |
|------|----------|-------------|----------|
| **Dry Run** (default) | `dry_run_mode=true` | any | Logs only, no Claude Code calls, no orders |
| **Analysis Only** | `dry_run_mode=false`, `auto_execute_enabled=false` | `analysis` | Reports only, no orders |
| **Paper Trading** | `dry_run_mode=false`, `auto_execute_enabled=true` | `paper` | Paper orders via IB Gateway |
| **Live Trading** | — | `live` | 🚫 **Blocked in code** (not implemented) |

```bash
# Step 1: Disable dry run mode (required for any real operation)
python orchestrator.py settings set dry_run_mode false

# Step 2a: Analysis only (no auto-execute)
python orchestrator.py settings set auto_execute_enabled false

# Step 2b: Enable paper trading for a stock
python orchestrator.py settings set auto_execute_enabled true
python orchestrator.py stock set-state NVDA paper
```

## Code Standards

- Python 3.11+ with type hints
- Follow PEP 8 conventions
- Use existing patterns in `orchestrator.py` and `db_layer.py`
- All SQL queries go through `db_layer.py`

## GitHub MCP Server (Preferred)

Use the `github-vl` MCP server for pushing skill outputs directly to GitHub. This avoids conda/SSH issues and provides atomic commits.

### Auto-Commit Skill Outputs

When skills save to `tradegent_knowledge/knowledge/`, use:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: TradegentSwarm
  branch: main
  files:
    - path: tradegent_knowledge/knowledge/{output_path}
      content: [generated content]
  message: "Add {skill_name} for {TICKER}"
```

### Available MCP Tools

| Tool | Purpose |
|------|----------|
| `mcp__github-vl__push_files` | Push multiple files in single commit |
| `mcp__github-vl__create_or_update_file` | Create/update single file |
| `mcp__github-vl__get_file_contents` | Read file from repo |
| `mcp__github-vl__list_commits` | View commit history |

## Trading RAG MCP Server (v2.0)

Semantic search and embedding for trading knowledge with cross-encoder reranking, query expansion, adaptive retrieval, and RAGAS evaluation.

**Server**: `trading-rag` | **Location**: `tradegent/rag/mcp_server.py` | **Transport**: stdio | **Version**: 2.0.0

> **Note**: This MCP server must be configured in Claude Code settings to be available. See [MCP Configuration](#mcp-configuration) below.

### Prerequisites

```bash
# 1. Start Docker services (PostgreSQL with pgvector)
cd tradegent && docker compose up -d postgres

# 2. Set environment variables
export PG_USER=lightrag PG_PASS=<password> PG_DB=lightrag PG_HOST=localhost PG_PORT=5433
export EMBED_PROVIDER=openai OPENAI_API_KEY=<key>
```

### Available Tools (12 total)

**Core Tools:**
| Tool | Purpose |
|------|----------|
| `rag_embed` | Embed a YAML document for semantic search |
| `rag_embed_text` | Embed raw text for semantic search |
| `rag_search` | Semantic search across embedded documents |
| `rag_similar` | Find similar past analyses for a ticker |
| `rag_hybrid_context` | Get combined vector + graph context (adaptive routing) |
| `rag_status` | Get RAG statistics (document/chunk counts) |

**v2.0 Tools:**
| Tool | Purpose |
|------|----------|
| `rag_search_rerank` | Search with cross-encoder reranking (higher relevance) |
| `rag_search_expanded` | Search with LLM query expansion (better recall) |
| `rag_classify_query` | Classify query type and optimal retrieval strategy |
| `rag_expand_query` | Generate semantic query variations |
| `rag_evaluate` | Evaluate RAG quality using RAGAS metrics |
| `rag_metrics_summary` | Get search metrics summary for analysis |

### Usage Examples

```yaml
# Embed a document
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/earnings/NVDA_20250120T0900.yaml"}

# Standard search
Tool: rag_search
Input: {"query": "NVDA earnings surprise", "ticker": "NVDA", "top_k": 5}

# Reranked search (higher relevance)
Tool: rag_search_rerank
Input: {"query": "NVDA competitive position vs AMD", "ticker": "NVDA", "top_k": 5}

# Expanded search (better recall)
Tool: rag_search_expanded
Input: {"query": "AI chip demand", "top_k": 5, "n_expansions": 3}

# Classify query for optimal strategy
Tool: rag_classify_query
Input: {"query": "Compare NVDA vs AMD earnings"}
# Returns: {query_type: "comparison", suggested_strategy: "vector", tickers: ["NVDA", "AMD"]}

# Get hybrid context (vector + graph, uses adaptive routing)
Tool: rag_hybrid_context
Input: {"ticker": "NVDA", "query": "earnings catalyst analysis"}

# Evaluate RAG quality
Tool: rag_evaluate
Input: {"query": "What are NVDA risks?", "contexts": ["..."], "answer": "..."}

# Get metrics summary
Tool: rag_metrics_summary
Input: {"days": 7}
```

## Trading Graph MCP Server

Knowledge graph for entities, relationships, and trading patterns.

**Server**: `trading-graph` | **Location**: `tradegent/graph/mcp_server.py` | **Transport**: stdio

> **Note**: This MCP server must be configured in Claude Code settings to be available. See [MCP Configuration](#mcp-configuration) below.

### Prerequisites

```bash
# 1. Start Docker services (Neo4j)
cd tradegent && docker compose up -d neo4j

# 2. Set environment variables
export NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASS=<password>
export EXTRACT_PROVIDER=openai OPENAI_API_KEY=<key>
```

### Available Tools

| Tool | Purpose |
|------|----------|
| `graph_extract` | Extract entities and relationships from a YAML document |
| `graph_extract_text` | Extract entities from raw text (for external content) |
| `graph_search` | Find all nodes connected to a ticker within N hops |
| `graph_peers` | Get sector peers and competitors for a ticker |
| `graph_risks` | Get known risks for a ticker |
| `graph_biases` | Get bias history across trades |
| `graph_context` | Get comprehensive context (peers, risks, strategies, biases) |
| `graph_query` | Execute raw Cypher query |
| `graph_status` | Get graph statistics (node/edge counts) |

### Usage Examples

```yaml
# Extract from document
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/earnings/NVDA_20250120T0900.yaml"}

# Get ticker context
Tool: graph_context
Input: {"ticker": "NVDA"}

# Find sector peers
Tool: graph_peers
Input: {"ticker": "NVDA"}

# Get known risks
Tool: graph_risks
Input: {"ticker": "NVDA"}

# Check for trading biases
Tool: graph_biases
Input: {}

# Custom Cypher query
Tool: graph_query
Input: {"cypher": "MATCH (t:Ticker {symbol: $ticker})-[r]->(n) RETURN type(r), n.name LIMIT 10", "params": {"ticker": "NVDA"}}
```

## MCP Configuration

To use the Trading RAG and Graph MCP servers, add them to your Claude Code MCP settings (`~/.claude/mcp_settings.json`):

```json
{
  "mcpServers": {
    "trading-rag": {
      "command": "python",
      "args": ["-m", "tradegent.rag.mcp_server"],
      "cwd": "/opt/data/tradegent_swarm",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "5433",
        "PG_USER": "lightrag",
        "PG_PASS": "<password>",
        "PG_DB": "lightrag",
        "EMBED_PROVIDER": "openai",
        "OPENAI_API_KEY": "<key>"
      }
    },
    "trading-graph": {
      "command": "python",
      "args": ["-m", "tradegent.graph.mcp_server"],
      "cwd": "/opt/data/tradegent_swarm",
      "env": {
        "NEO4J_URI": "bolt://localhost:7688",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASS": "<password>",
        "EXTRACT_PROVIDER": "openai",
        "OPENAI_API_KEY": "<key>"
      }
    }
  }
}
```

### Direct Python Usage (Alternative)

If MCP servers are not configured, use Python directly:

```bash
# Set environment variables first
export PG_USER=lightrag PG_PASS=<password> PG_DB=lightrag PG_HOST=localhost PG_PORT=5433
export NEO4J_URI=bolt://localhost:7688 NEO4J_USER=neo4j NEO4J_PASS=<password>
export EMBED_PROVIDER=openai EXTRACT_PROVIDER=openai OPENAI_API_KEY=<key>

# RAG Embedding
cd tradegent && python -c "
from rag.embed import embed_document
result = embed_document('../tradegent_knowledge/knowledge/analysis/stock/MSFT_20260221T1715.yaml')
print(f'Embedded: {result.doc_id}, Chunks: {result.chunk_count}')
"

# RAG Search
cd tradegent && python -c "
from rag.search import semantic_search, get_rag_stats
stats = get_rag_stats()
print(f'RAG: {stats.document_count} docs, {stats.chunk_count} chunks')
results = semantic_search('MSFT Azure analysis', ticker='MSFT', top_k=3)
for r in results:
    print(f'  {r.doc_id}: {r.content[:60]}...')
"

# Graph Extraction
cd tradegent && python -c "
from graph.extract import extract_document
result = extract_document('../tradegent_knowledge/knowledge/analysis/stock/MSFT_20260221T1715.yaml')
print(f'Extracted: {len(result.entities)} entities, {len(result.relations)} relations, Committed: {result.committed}')
"

# Graph Query
cd tradegent && python -c "
from graph.layer import TradingGraph
graph = TradingGraph()
graph.connect()
ctx = graph.get_ticker_context('MSFT')
print(f'MSFT peers: {ctx.get(\"peers\", [])}')
stats = graph.get_stats()
print(f'Graph: {sum(stats.node_counts.values())} nodes, {sum(stats.edge_counts.values())} edges')
graph.close()
"
```

## IB MCP Server (Interactive Brokers)

Access Interactive Brokers TWS/Gateway for market data, portfolio, and trading.

**Server**: `ib-mcp` | **Source**: `/opt/data/trading/mcp_ib` | **Transport**: SSE

### Starting the Server

The IB MCP server runs in SSE mode for reliable connection:

```bash
cd /opt/data/trading/mcp_ib
PYTHONPATH=src \
IB_GATEWAY_HOST=localhost \
IB_GATEWAY_PORT=4002 \
IB_CLIENT_ID=2 \
IB_READONLY=true \
python -m ibmcp --transport sse --port 8100
```

Server URL: `http://localhost:8100/sse`

> **Note**: Port 8100 is used when running IB MCP directly. The README.md shows Docker deployment using port 8002. Either works - use whatever matches your setup.

### Architecture: IB Gateway as Proxy

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Claude Code    │────▶│   IB MCP Server  │────▶│   IB Gateway    │────▶│  IB Servers      │
│  (orchestrator) │ SSE │  (localhost:8100)│ API │  (localhost:4002)│ TLS │  (interactivebrokers.com)
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────────┘
```

**IB Gateway Docker container** (`nexus-ib-gateway`) acts as a proxy:

1. **Runs headless** in Docker with VNC access (port 5900) for initial login/2FA
2. **Maintains persistent connection** to Interactive Brokers servers
3. **Exposes local API** on ports 4001 (live) / 4002 (paper)
4. **Handles authentication** - stores credentials, manages session renewal
5. **Rate limiting** - IB enforces 50 requests/second; Gateway handles throttling

**Connection flow:**
- IB MCP Server connects to IB Gateway via TCP (port 4002)
- IB Gateway proxies requests to IB servers over TLS
- Market data, account info, and orders flow through this chain

**VNC Access** (for 2FA or troubleshooting):
```bash
# Connect to IB Gateway UI
vncviewer localhost:5900
# Password: nexus123 (from VNC_PASS in .env)
```

### Available Tools (22 total)

**Market Data**:
| Tool | Purpose |
|------|----------|
| `get_stock_price` | Real-time quote (bid, ask, last, volume) |
| `get_quotes_batch` | Batch quotes for multiple symbols |
| `get_option_chain` | Option chain (expirations, strikes) |
| `get_option_quotes` | Option prices for specific contracts |
| `get_historical_data` | OHLCV historical bars |
| `get_market_depth` | Level 2 order book |
| `get_fundamental_data` | Company fundamentals |

**Portfolio & Account**:
| Tool | Purpose |
|------|----------|
| `get_positions` | Current portfolio positions |
| `get_portfolio` | Full portfolio with P&L |
| `get_account_summary` | Account balances and metrics |
| `get_pnl` | Profit/loss summary |
| `get_executions` | Recent trade executions |

**Orders**:
| Tool | Purpose |
|------|----------|
| `place_order` | Submit new order |
| `cancel_order` | Cancel existing order |
| `get_open_orders` | List open orders |
| `get_order_status` | Check order status |

**Research & Discovery**:
| Tool | Purpose |
|------|----------|
| `search_symbols` | Search for symbols |
| `get_contract_details` | Contract specifications |
| `run_scanner` | Run market scanner |
| `get_scanner_params` | Available scanner parameters |
| `get_news_providers` | News provider list |
| `get_news_headlines` | Recent news headlines |

**Options Analytics**:
| Tool | Purpose |
|------|----------|
| `calc_implied_volatility` | Calculate implied volatility |
| `calc_option_price` | Calculate theoretical option price |
| `what_if_order` | Simulate order impact on margin/P&L |

**System**:
| Tool | Purpose |
|------|----------|
| `health_check` | Check IB Gateway connection |

### Usage Examples

```yaml
# Get stock price
Tool: mcp__ib-mcp__get_stock_price
Input: {"symbol": "NVDA"}

# Get historical data
Tool: mcp__ib-mcp__get_historical_data
Input: {"symbol": "NVDA", "duration": "1 D", "bar_size": "5 mins"}

# Get portfolio P&L
Tool: mcp__ib-mcp__get_pnl

# Search symbols
Tool: mcp__ib-mcp__search_symbols
Input: {"pattern": "NVDA"}
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `IB_GATEWAY_HOST` | localhost | TWS/Gateway hostname |
| `IB_GATEWAY_PORT` | 4002 | API port (7496=TWS live, 7497=TWS paper, 4001=Gateway live, 4002=Gateway paper) |
| `IB_CLIENT_ID` | 2 | Unique client ID |
| `IB_READONLY` | true | Read-only mode (blocks order placement) |
| `IB_RATE_LIMIT` | 45 | Requests per second limit |

## Brave Browser MCP (Web Scraping)

Browser automation for accessing protected content (Medium, Seeking Alpha, analyst reports).

**Source**: `/opt/data/trading/mcp_brave-browser`

### MCP Tools (stdio mode)

| Tool | Purpose |
|------|----------|
| `fetch_protected_article` | Fetch paywalled/protected article content |
| `take_screenshot` | Take page screenshot (base64 PNG) |
| `extract_structured_data` | Extract data using CSS selectors |
| `search_and_extract` | Search and extract results |

### HTTP API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|----------|
| `/health` | GET | Health check (no auth) |
| `/api/fetch_article` | POST | Fetch article content |
| `/api/screenshot` | POST | Take screenshot |
| `/api/extract_data` | POST | Extract structured data |
| `/api/search` | POST | Search and extract |
| `/api/cache/clear` | POST | Clear article cache |

### Usage Examples

```yaml
# Fetch article content (MCP)
Tool: fetch_protected_article
Input: {"url": "https://seekingalpha.com/article/...", "wait_for_selector": "article"}

# Take screenshot (MCP)
Tool: take_screenshot
Input: {"url": "https://finviz.com/chart.ashx?t=NVDA", "full_page": true}

# Extract consensus data
Tool: extract_data
Input: {
  "url": "https://seekingalpha.com/symbol/NVDA/earnings",
  "selectors": {"eps": "[data-test-id='eps']", "revenue": "[data-test-id='revenue']"}
}
```

### Features

- Profile persistence (maintains login sessions)
- Article caching (SHA-256 keyed, TTL support)
- SSRF protection (blocks internal networks)
- API key authentication

## Git Workflow (Fallback)

### Pushing Changes

This project uses SSH authentication. The remote is configured as:

```bash
git remote set-url origin git@github.com:vladm3105/TradegentSwarm.git
```

**Standard workflow (when MCP unavailable):**

```bash
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

### Git Push with Conda/OpenSSL Issue

If using conda, its `LD_LIBRARY_PATH` loads a newer OpenSSL that conflicts with system SSH. Fix options:

```bash
# Option 1: Clear LD_LIBRARY_PATH for SSH during git operations
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push

# Option 2: Use git alias (one-time setup)
git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
# Then use: git pushs

# Option 3: Deactivate conda before git operations
conda deactivate
git push
```

### SSH Configuration

Requires `~/.ssh/config` entry:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/your-github-key
    IdentitiesOnly yes
```

## Important Notes

- **Use MCP servers as primary interface** for IB (`ib-mcp`), RAG (`trading-rag`), and Graph (`trading-graph`) operations
- **IB MCP runs via SSE** at `http://localhost:8100/sse` - start it before running analyses
- Do not commit `.env` files (contains credentials)
- IB Gateway requires valid paper trading account
- RAG (pgvector) handles semantic search, Graph (Neo4j) handles entity relationships
- Scanner configs in `knowledge/scanners/` encode trading edge - treat as sensitive
- Skills auto-invoke based on conversation context - no manual `/command` needed
- Always use the SSH git push command with `LD_LIBRARY_PATH=` fix when in conda environment
- Set all PG_* and NEO4J_* environment variables before running orchestrator
