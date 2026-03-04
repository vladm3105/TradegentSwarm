# MCP Servers

Use MCP servers as primary interface for IB, RAG, and Graph operations.

## Server Overview

| Server | Transport | URL/Command |
|--------|-----------|-------------|
| `ib-mcp` | streamable-http | `http://localhost:8100/mcp` |
| `trading-rag` | stdio | `python -m tradegent.rag.mcp_server` |
| `trading-graph` | stdio | `python -m tradegent.graph.mcp_server` |

## IB MCP Server

**Start command:**
```bash
cd /opt/data/trading/mcp_ib
PYTHONPATH=src IB_GATEWAY_HOST=localhost IB_GATEWAY_PORT=4002 \
  python -m ibmcp --transport streamable-http --host 0.0.0.0 --port 8100
```

**Key tools:**
- `get_stock_price` - Real-time quote
- `get_historical_data` - OHLCV bars
- `get_positions` - Portfolio positions
- `place_order` - Submit order
- `run_scanner` - Market scanner

## Trading RAG MCP Server

**Key tools:**
- `rag_embed` - Embed YAML document
- `rag_search` - Semantic search
- `rag_hybrid_context` - Combined vector + graph context
- `rag_search_rerank` - Search with cross-encoder reranking

## Trading Graph MCP Server

**Key tools:**
- `graph_extract` - Extract entities from YAML
- `graph_context` - Get ticker context (peers, risks)
- `graph_peers` - Sector peers and competitors
- `graph_risks` - Known risks for ticker

## MCP Configuration (~/.claude/mcp.json)

```json
{
  "mcpServers": {
    "ib-mcp": {
      "url": "http://localhost:8100/mcp"
    },
    "trading-rag": {
      "command": "python",
      "args": ["-m", "tradegent.rag.mcp_server"],
      "cwd": "/opt/data/tradegent_swarm",
      "env": {
        "PG_HOST": "localhost",
        "PG_PORT": "5433",
        "PG_USER": "tradegent",
        "PG_DB": "tradegent",
        "EMBED_PROVIDER": "openai"
      }
    },
    "trading-graph": {
      "command": "python",
      "args": ["-m", "tradegent.graph.mcp_server"],
      "cwd": "/opt/data/tradegent_swarm",
      "env": {
        "NEO4J_URI": "bolt://localhost:7688",
        "NEO4J_USER": "neo4j",
        "EXTRACT_PROVIDER": "openai"
      }
    }
  }
}
```

## GitHub MCP Server

Use `github-vl` for pushing skill outputs:

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
