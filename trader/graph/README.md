# Trading Graph Module

Knowledge graph layer for trading intelligence. Extracts entities and relationships from trading documents, stores them in Neo4j, and enables graph-based queries.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Graph Pipeline                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Document Input                                                 │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐  │
│  │  Parse  │───▶│ Extract  │───▶│Normalize │───▶│   Store   │  │
│  │  YAML   │    │  (LLM)   │    │ Entities │    │  (Neo4j)  │  │
│  └─────────┘    └──────────┘    └──────────┘    └───────────┘  │
│                                                                 │
│  Query Types                                                    │
│       │                                                         │
│       ├──▶ Ticker Context (peers, risks, strategies)           │
│       ├──▶ Bias History (trading psychology patterns)          │
│       ├──▶ Related Entities (N-hop graph traversal)            │
│       └──▶ Custom Cypher Queries                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```python
from graph.layer import TradingGraph
from graph.extract import extract_document, extract_text

# Extract entities from document
result = extract_document(
    file_path="/path/to/analysis.yaml",
    extractor="ollama",
    commit=True,
)
print(f"Extracted {len(result.entities)} entities")

# Query the graph
with TradingGraph() as graph:
    # Get ticker context
    context = graph.get_ticker_context("NVDA")
    print(f"Peers: {context['peers']}")
    print(f"Risks: {context['risks']}")

    # Get bias history
    biases = graph.get_bias_history()
    for b in biases:
        print(f"{b['name']}: {b['count']} occurrences")
```

## Components

| File | Purpose |
|------|---------|
| `mcp_server.py` | **MCP server (primary interface)** |
| `layer.py` | Neo4j connection and CRUD operations |
| `extract.py` | LLM-based entity extraction |
| `normalize.py` | Entity standardization and dedup |
| `query.py` | Pre-built Cypher query catalog |
| `models.py` | Data classes (EntityExtraction, GraphStats) |
| `webhook.py` | FastAPI HTTP endpoints |
| `config.yaml` | Configuration settings |
| `.env` | Environment variables (not committed) |
| `.env.template` | Environment template |

## Configuration

Settings are loaded from `.env` and `config.yaml` with environment variable overrides.

**Setup:**
```bash
cp .env.template .env
# Edit .env with your Neo4j credentials
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7688` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASS` | (required) | Neo4j password |
| `NEO4J_DATABASE` | `neo4j` | Database name |
| `LLM_PROVIDER` | `ollama` | Extraction LLM provider |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `LLM_API_KEY` | (none) | API key for OpenRouter/Claude |
| `LLM_MODEL` | `llama3.2` | Extraction model |
| `EXTRACT_TIMEOUT_SECONDS` | `120` | LLM timeout |
| `EXTRACT_COMMIT_THRESHOLD` | `0.7` | Auto-commit confidence |
| `EXTRACT_FLAG_THRESHOLD` | `0.5` | Review flag confidence |

### Generation Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_TEMPERATURE` | `0.1` | Generation temperature |
| `LLM_NUM_PREDICT` | `2000` | Max tokens (Ollama) |
| `LLM_MAX_TOKENS` | `2000` | Max tokens (cloud LLMs) |
| `LLM_TOP_P` | `0.9` | Top-p sampling |
| `LLM_TOP_K` | `40` | Top-k sampling |

## Entity Types

| Type | Description | Example |
|------|-------------|---------|
| `Ticker` | Stock symbol | NVDA, AAPL |
| `Company` | Company name | NVIDIA Corporation |
| `Sector` | Industry sector | Semiconductors |
| `Risk` | Risk factor | Supply chain disruption |
| `Strategy` | Trading strategy | Earnings momentum |
| `Bias` | Cognitive bias | Confirmation bias |
| `Pattern` | Chart pattern | Cup and handle |
| `Catalyst` | Price catalyst | Product launch |

## Relationship Types

| Relationship | Description |
|--------------|-------------|
| `BELONGS_TO` | Ticker → Sector |
| `COMPETES_WITH` | Company ↔ Company |
| `HAS_RISK` | Ticker → Risk |
| `USES_STRATEGY` | Trade → Strategy |
| `EXHIBITS_BIAS` | Trade → Bias |
| `TRIGGERED_BY` | Trade → Catalyst |

## Extraction Functions

### extract_document(file_path, extractor, commit)

Extract entities from a YAML document.

```python
from graph.extract import extract_document

result = extract_document(
    file_path="/path/to/earnings_analysis.yaml",
    extractor="ollama",  # or "openrouter", "claude-api"
    commit=True,
)

print(f"Entities: {len(result.entities)}")
print(f"Relations: {len(result.relations)}")
for e in result.entities:
    print(f"  {e.type}: {e.name} ({e.confidence:.2f})")
```

### extract_text(text, doc_type, doc_id, ...)

Extract from raw text.

```python
from graph.extract import extract_text

result = extract_text(
    text="NVDA faces supply chain risks from TSMC dependency...",
    doc_type="research",
    doc_id="nvda_risk_001",
    extractor="ollama",
)
```

## Confidence Thresholds

Entities are filtered by confidence score:

| Confidence | Action |
|------------|--------|
| `≥ 0.7` | Auto-commit to graph |
| `0.5 - 0.7` | Commit with `needs_review` flag |
| `< 0.5` | Excluded from results |

## Graph Queries

### TradingGraph Context Manager

```python
from graph.layer import TradingGraph

with TradingGraph() as graph:
    # Health check
    if graph.health_check():
        print("Connected to Neo4j")

    # Get statistics
    stats = graph.get_stats()
    print(f"Nodes: {stats.total_nodes}")
    print(f"Edges: {stats.total_edges}")
```

### Pre-built Queries

```python
with TradingGraph() as graph:
    # Ticker context (comprehensive)
    ctx = graph.get_ticker_context("NVDA")
    # Returns: peers, competitors, risks, strategies, biases

    # Sector peers
    peers = graph.get_sector_peers("NVDA")
    # Returns: ["AMD", "INTC", "QCOM"]

    # Competitors
    competitors = graph.get_competitors("NVDA")

    # Known risks
    risks = graph.get_risks("NVDA")

    # Bias history
    biases = graph.get_bias_history("confirmation-bias")

    # Strategy performance
    strategies = graph.get_strategy_performance("momentum")

    # N-hop related entities
    related = graph.find_related("NVDA", depth=2)
```

### Custom Cypher

```python
with TradingGraph() as graph:
    results = graph.run_cypher(
        "MATCH (t:Ticker)-[:HAS_RISK]->(r:Risk) "
        "WHERE t.name = $ticker "
        "RETURN r.name, r.severity",
        params={"ticker": "NVDA"}
    )
```

## HTTP API (Webhook)

The graph module exposes a FastAPI server:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/graph/extract` | POST | Extract from YAML file |
| `/api/graph/extract-text` | POST | Extract from text |
| `/api/graph/query` | POST | Execute Cypher |
| `/api/graph/status` | GET | Graph statistics |
| `/api/graph/ticker/{symbol}` | GET | Ticker context |
| `/api/graph/ticker/{symbol}/peers` | GET | Sector peers |
| `/api/graph/ticker/{symbol}/risks` | GET | Known risks |
| `/api/graph/biases` | GET | Bias history |
| `/api/graph/strategies` | GET | Strategy performance |
| `/api/graph/health` | GET | Health check |
| `/api/graph/ready` | GET | Readiness check |

## MCP Server (Primary Interface)

The graph module is exposed via MCP server at `mcp_server.py`. **Use MCP tools as the primary interface** for all graph operations.

**Server name:** `trading-graph`

| Tool | Description |
|------|-------------|
| `graph_extract` | Extract entities from YAML |
| `graph_extract_text` | Extract from raw text |
| `graph_search` | Find related entities |
| `graph_peers` | Get sector peers |
| `graph_risks` | Get ticker risks |
| `graph_biases` | Get bias history |
| `graph_context` | Comprehensive ticker context |
| `graph_query` | Execute Cypher query |
| `graph_status` | Graph statistics |

### MCP Usage Examples

```yaml
# Extract from document
Tool: graph_extract
Input: {"file_path": "trading/knowledge/analysis/earnings/NVDA_20250120T0900.yaml"}

# Get ticker context
Tool: graph_context
Input: {"ticker": "NVDA"}

# Find sector peers
Tool: graph_peers
Input: {"ticker": "NVDA"}

# Get known risks
Tool: graph_risks
Input: {"ticker": "NVDA"}

# Custom Cypher query
Tool: graph_query
Input: {"cypher": "MATCH (t:Ticker {symbol: $ticker})-[r]->(n) RETURN type(r), n LIMIT 10", "params": {"ticker": "NVDA"}}

# Check graph status
Tool: graph_status
Input: {}
```

### Running the MCP Server

```bash
# Direct execution
python trader/graph/mcp_server.py

# Or import and run
python -c "from graph.mcp_server import server; print(server.name)"
```

## Testing

```bash
cd trader

# Run graph tests
pytest graph/tests/ -v

# Run with coverage
pytest graph/tests/ --cov=graph --cov-report=term-missing

# Specific test modules
pytest graph/tests/test_webhook.py -v      # API tests
pytest graph/tests/test_rate_limit.py -v   # Rate limiting
pytest graph/tests/test_extract.py -v      # Extraction

# Integration tests (requires Neo4j)
pytest graph/tests/test_integration.py --run-integration
```

### Full Graph Test

```bash
# Ensure .env is configured
cp trader/graph/.env.template trader/graph/.env
# Edit trader/graph/.env with your Neo4j credentials

# Run full pipeline test (extract → store → query)
python tmp/test_graph.py
```

**Expected output:**
```
======================================================================
Graph Test: Extract → Store → Query
======================================================================

[1] Checking Neo4j connection...
    Connected to Neo4j
    Nodes: 0, Edges: 0

[2] Extracting entities from story...
    Entities: 9
    Relations: 0
    Extractor: ollama
    Sample entities:
      - Ticker: NVDA
      - Company: NVIDIA
      - Executive: Jensen Huang Ceo
      - Product: Blackwell Gpu
      - Catalyst: Earnings Beat
    Committing to Neo4j...
    Committed!

[3] Querying graph for NVDA context...
    Peers: 0
    Competitors: 0
    Risks: 0
    Strategies: 0

[4] Running custom Cypher query...
    Found 1 relationships:
      EXTRACTED_FROM -> Document: None

======================================================================
Graph Test Complete
======================================================================
```

## Rate Limiting

The extraction module includes rate limiting for LLM APIs:

```python
# Ollama: 45 requests/second
@limits(calls=45, period=1)
def _call_ollama_rate_limited(...)

# Retry with exponential backoff
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=10, max=30),
    retry=retry_if_exception_type((Timeout, ConnectionError))
)
def _extract_entities_from_field(...)
```

## Troubleshooting

**"Failed to connect to Neo4j"**
- Check `trader/graph/.env` has correct `NEO4J_PASS`
- Verify password matches `NEO4J_PASS` in `trader/.env`
- Check Neo4j is running: `docker compose ps`
- Check port (default: 7688 for bolt)

**Empty extraction results**
- Verify LLM is running: `curl http://localhost:11434/api/tags`
- Check model is available: `ollama list`
- Use `llama3.2` instead of `qwen3:8b` (qwen3 uses thinking mode)
- Check document has extractable content
- Lower confidence thresholds for testing

**Slow extraction**
- Use local Ollama instead of cloud APIs
- Increase `EXTRACT_TIMEOUT_SECONDS` in `.env`
- Reduce document size / fields to extract
- Check rate limiting isn't throttling

**"Failed to parse JSON response"**
- Some models wrap JSON in markdown (```json ... ```)
- Use `llama3.2` which returns cleaner JSON
- Check LLM response format in logs
