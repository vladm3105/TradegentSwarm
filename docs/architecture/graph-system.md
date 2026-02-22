# Graph System Architecture

The Graph system provides entity extraction and relationship queries using Neo4j, enabling knowledge graph operations for trading intelligence.

---

## Overview

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

---

## Components

| Module | Purpose |
|--------|---------|
| `layer.py` | TradingGraph class, Neo4j operations |
| `extract.py` | LLM-based entity extraction |
| `normalize.py` | Entity standardization |
| `query.py` | Pre-built Cypher catalog |
| `mcp_server.py` | MCP server (9 tools) |

---

## Entity Types

| Type | Description | Example |
|------|-------------|---------|
| `Ticker` | Stock symbol | NVDA, MSFT |
| `Company` | Company name | NVIDIA Corporation |
| `Sector` | Industry sector | Technology |
| `Industry` | Specific industry | Cloud Computing |
| `Risk` | Risk factor | Supply chain disruption |
| `Strategy` | Trading strategy | Earnings momentum |
| `Bias` | Cognitive bias | Confirmation bias |
| `Pattern` | Chart pattern | Cup and handle |
| `Catalyst` | Price catalyst | Product launch |
| `Product` | Company product | Azure, Copilot |
| `FinancialMetric` | Financial data | $74.5B FCF |

---

## Relationship Types

| Relationship | From | To | Description |
|--------------|------|----| ------------|
| `ISSUED` | Company | Ticker | Company issues stock |
| `IN_SECTOR` | Company | Sector | Sector membership |
| `IN_INDUSTRY` | Company | Industry | Industry membership |
| `COMPETES_WITH` | Company | Company | Competitive relationship |
| `THREATENS` | Risk | Ticker | Risk threatens company |
| `EXPOSED_TO` | Ticker | Risk | Company exposed to risk |
| `WORKS_FOR` | Strategy | Ticker | Strategy effective for ticker |
| `DETECTED_IN` | Bias | Document | Bias found in analysis |
| `EXTRACTED_FROM` | Entity | Document | Entity source |

---

## Extraction Pipeline

### Extract from Document

```python
from graph.extract import extract_document

result = extract_document(
    file_path="path/to/analysis.yaml",
    extractor="openai",
    commit=True,
)

print(f"Entities: {len(result.entities)}")
print(f"Relations: {len(result.relations)}")
print(f"Committed: {result.committed}")
```

### ExtractionResult Attributes

| Attribute | Description |
|-----------|-------------|
| `entities` | List of EntityExtraction |
| `relations` | List of RelationExtraction |
| `source_doc_id` | Document identifier |
| `source_doc_type` | Document type |
| `fields_processed` | Fields extracted from |
| `fields_failed` | Failed extractions |
| `committed` | Stored in Neo4j |
| `extractor` | Provider used |

### Extraction Provider

| Provider | Model | Speed | Quality | Cost |
|----------|-------|-------|---------|------|
| `openai` | gpt-4o-mini | ~5s | Best | ~$0.001/doc |
| `ollama` | qwen3:8b | ~66s | Variable | Free |
| `openrouter` | claude-3.5-sonnet | ~3s | Good | ~$0.003/1K |

**Recommendation:** Use `openai` for production (12x faster, better JSON).

---

## Graph Queries

### TradingGraph Class

```python
from graph.layer import TradingGraph

with TradingGraph() as graph:
    # Health check
    graph.health_check()  # True/False

    # Get statistics
    stats = graph.get_stats()
    print(f"Nodes: {sum(stats.node_counts.values())}")
    print(f"Edges: {sum(stats.edge_counts.values())}")
```

### Ticker Context

Comprehensive context for a ticker:

```python
ctx = graph.get_ticker_context("NVDA")
# Returns:
# {
#   "symbol": "NVDA",
#   "peers": [{"peer": "AMD", "sector": "Technology"}],
#   "risks": [{"risk": "Supply chain", "description": "..."}],
#   "strategies": [{"strategy": "Momentum", "win_rate": 0.7}],
#   "biases": [{"bias": "Confirmation", "count": 2}],
#   "supply_chain": {"suppliers": [], "customers": []}
# }
```

### Specific Queries

```python
# Sector peers
peers = graph.get_sector_peers("NVDA")
# [{"peer": "AMD", "company": "AMD Inc", "sector": "Technology"}]

# Competitors
competitors = graph.get_competitors("NVDA")

# Known risks
risks = graph.get_risks("NVDA")
# [{"risk": "Geopolitical", "description": "..."}]

# Bias history
biases = graph.get_bias_history("confirmation-bias")
# [{"name": "Confirmation bias", "count": 5, "tickers": ["NVDA"]}]

# N-hop related entities
related = graph.find_related("NVDA", depth=2)
```

### Custom Cypher

```python
results = graph.run_cypher(
    "MATCH (t:Ticker {symbol: $ticker})-[r]->(n) "
    "RETURN type(r) AS rel, labels(n) AS labels, n.value AS value "
    "LIMIT 10",
    params={"ticker": "NVDA"},
    allow_writes=False,
)
```

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `graph_extract` | Extract from YAML document |
| `graph_extract_text` | Extract from raw text |
| `graph_search` | Find related entities |
| `graph_peers` | Get sector peers |
| `graph_risks` | Get ticker risks |
| `graph_biases` | Get bias history |
| `graph_context` | Comprehensive ticker context |
| `graph_query` | Execute Cypher query |
| `graph_status` | Graph statistics |

### MCP Usage

```yaml
# Extract entities
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/analysis/stock/NVDA.yaml"}

# Get ticker context
Tool: graph_context
Input: {"ticker": "NVDA"}

# Custom Cypher
Tool: graph_query
Input: {
  "cypher": "MATCH (t:Ticker {symbol: $ticker})-[:IN_SECTOR]->(s) RETURN s",
  "params": {"ticker": "NVDA"}
}
```

---

## Confidence Thresholds

Entities are filtered by LLM confidence score:

| Confidence | Action |
|------------|--------|
| ≥ 0.7 | Auto-commit to graph |
| 0.5 - 0.7 | Commit with `needs_review` flag |
| < 0.5 | Excluded from results |

Configuration:
```bash
EXTRACT_COMMIT_THRESHOLD=0.7
EXTRACT_FLAG_THRESHOLD=0.5
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7688` | Neo4j connection |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASS` | — | Neo4j password |
| `EXTRACT_PROVIDER` | `openai` | LLM for extraction |
| `OPENAI_API_KEY` | — | Required for OpenAI |
| `EXTRACT_TIMEOUT_SECONDS` | `30` | LLM timeout |

---

## Python API

### GraphStats

```python
stats = graph.get_stats()

stats.node_counts      # {"Ticker": 4, "Company": 5, ...}
stats.edge_counts      # {"ISSUED": 4, "IN_SECTOR": 6, ...}
```

### EntityExtraction

```python
for entity in result.entities:
    entity.type        # "Company"
    entity.value       # "Microsoft"
    entity.confidence  # 0.95
    entity.evidence    # "Microsoft is a technology company..."
    entity.needs_review # False
```

### RelationExtraction

```python
for rel in result.relations:
    rel.from_entity    # EntityExtraction
    rel.relation       # "IN_SECTOR"
    rel.to_entity      # EntityExtraction
    rel.confidence     # 0.9
    rel.evidence       # "Microsoft operates in Technology"
```

---

## Troubleshooting

### "Failed to connect to Neo4j"

- Check `NEO4J_PASS` in environment
- Verify Neo4j is running: `docker compose ps`
- Check port: default is 7688 (bolt)

### Empty extraction results

- Verify `EXTRACT_PROVIDER` and API key
- Check document has extractable content
- Try `openai` instead of `ollama` (better JSON parsing)

### Slow extraction

- Switch to `EXTRACT_PROVIDER=openai` (12x faster)
- Increase `EXTRACT_TIMEOUT_SECONDS`
- Reduce document size

---

## Related Documentation

- [Architecture Overview](overview.md)
- [RAG System](rag-system.md)
- [Database Schema](database-schema.md)
- Module: [`tradegent/graph/README.md`](../../tradegent/graph/README.md)
