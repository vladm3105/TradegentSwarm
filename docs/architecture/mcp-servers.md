# MCP Server Configuration

MCP (Model Context Protocol) servers provide tool access for Claude Code. TradegentSwarm uses five MCP servers for trading operations.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server Architecture                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Claude Code CLI                                                │
│       │                                                         │
│       ├──▶ ib-mcp (HTTP) ───▶ IB Gateway ────▶ IB Servers      │
│       │    :8100              :4002                             │
│       │                                                         │
│       ├──▶ trading-rag (stdio) ────▶ PostgreSQL                │
│       │                              :5433                      │
│       │                                                         │
│       ├──▶ trading-graph (stdio) ────▶ Neo4j                   │
│       │                                :7688                    │
│       │                                                         │
│       ├──▶ brave-browser (stdio) ────▶ Playwright/Chromium     │
│       │                                 (persistent profile)    │
│       │                                                         │
│       └──▶ github-vl (stdio) ────▶ GitHub API                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Server Summary

| Server | Transport | Port | Purpose |
|--------|-----------|------|---------|
| `ib-mcp` | streamable-http | 8100 | Market data, orders |
| `trading-rag` | stdio | — | Semantic search |
| `trading-graph` | stdio | — | Entity queries |
| `brave-browser` | stdio | — | Web scraping (protected content) |
| `github-vl` | stdio | — | Knowledge repo |

---

## IB MCP Server

Interactive Brokers integration for market data and trading.

### Configuration

```json
{
  "mcpServers": {
    "ib-mcp": {
      "url": "http://localhost:8100/mcp"
    }
  }
}
```

### Starting the Server

```bash
cd /opt/data/trading/mcp_ib
PYTHONPATH=src \
IB_GATEWAY_HOST=localhost \
IB_GATEWAY_PORT=4002 \
IB_CLIENT_ID=2 \
IB_READONLY=false \
IB_OUTSIDE_RTH=true \
python -m ibmcp --transport streamable-http --host 0.0.0.0 --port 8100
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `IB_GATEWAY_HOST` | localhost | TWS/Gateway host |
| `IB_GATEWAY_PORT` | 4002 | Paper: 4002, Live: 4001 |
| `IB_CLIENT_ID` | 2 | Unique client ID |
| `IB_READONLY` | false | Set `true` to block order placement |
| `IB_OUTSIDE_RTH` | true | Allow orders outside regular trading hours |
| `IB_RATE_LIMIT` | 45 | Requests/second |

### Available Tools (22)

**Market Data:**
- `get_stock_price` — Real-time quote
- `get_quotes_batch` — Multiple symbols
- `get_historical_data` — OHLCV bars
- `get_option_chain` — Option expirations/strikes
- `get_option_quotes` — Option prices
- `get_market_depth` — Level 2 book
- `get_fundamental_data` — Fundamentals

**Portfolio:**
- `get_positions` — Current positions
- `get_portfolio` — Full portfolio with P&L
- `get_account_summary` — Account balances
- `get_pnl` — P&L summary
- `get_executions` — Trade executions

**Orders:**
- `place_order` — Submit order
- `cancel_order` — Cancel order
- `get_open_orders` — Open orders
- `get_order_status` — Order status

**Research:**
- `search_symbols` — Symbol search
- `get_contract_details` — Contract specs
- `run_scanner` — Market scanner
- `get_scanner_params` — Scanner params
- `get_news_providers` — News providers
- `get_news_headlines` — Headlines

**Options:**
- `calc_implied_volatility` — IV calculation
- `calc_option_price` — Theoretical price
- `what_if_order` — Margin simulation

**System:**
- `health_check` — Connection status

---

## Trading RAG Server

Semantic search over trading knowledge using pgvector.

### Configuration

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
        "PG_USER": "tradegent",
        "PG_DB": "tradegent",
        "EMBED_PROVIDER": "openai"
      }
    }
  }
}
```

> **Note**: API keys (`OPENAI_API_KEY`, `PG_PASS`) should be set in your shell environment, not in the config file.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PG_HOST` | localhost | PostgreSQL host |
| `PG_PORT` | 5433 | PostgreSQL port |
| `PG_USER` | tradegent | Database user |
| `PG_PASS` | — | Database password (set in shell) |
| `PG_DB` | tradegent | Database name |
| `EMBED_PROVIDER` | openai | openai, ollama |
| `OPENAI_API_KEY` | — | For OpenAI embeddings (set in shell) |

### Available Tools (12)

**Core:**
- `rag_embed` — Embed YAML document
- `rag_embed_text` — Embed raw text
- `rag_search` — Semantic search
- `rag_similar` — Find similar analyses
- `rag_hybrid_context` — Vector + graph context
- `rag_status` — Statistics

**v2.0:**
- `rag_search_rerank` — Cross-encoder reranking
- `rag_search_expanded` — Query expansion
- `rag_classify_query` — Query classification
- `rag_expand_query` — Generate variations
- `rag_evaluate` — RAGAS evaluation
- `rag_metrics_summary` — Search metrics

---

## Trading Graph Server

Knowledge graph for entities and relationships.

### Configuration

```json
{
  "mcpServers": {
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

> **Note**: API keys (`OPENAI_API_KEY`, `NEO4J_PASS`) should be set in your shell environment, not in the config file.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | bolt://localhost:7688 | Neo4j connection |
| `NEO4J_USER` | neo4j | Neo4j user |
| `NEO4J_PASS` | — | Neo4j password (set in shell) |
| `EXTRACT_PROVIDER` | openai | openai, ollama, openrouter |
| `OPENAI_API_KEY` | — | For OpenAI extraction (set in shell) |

### Available Tools (9)

- `graph_extract` — Extract from YAML
- `graph_extract_text` — Extract from text
- `graph_search` — Find related entities
- `graph_peers` — Sector peers
- `graph_risks` — Ticker risks
- `graph_biases` — Bias history
- `graph_context` — Comprehensive context
- `graph_query` — Execute Cypher
- `graph_status` — Statistics

---

## Brave Browser Server

Browser automation for accessing protected content (Seeking Alpha, Medium, analyst reports). Uses Playwright with a persistent profile for session management.

### Configuration

```json
{
  "mcpServers": {
    "brave-browser": {
      "command": "python",
      "args": ["-m", "app.main"],
      "cwd": "/opt/data/trading/mcp_brave-browser",
      "env": {
        "MODE": "stdio",
        "BROWSER_PROFILE": "/opt/data/trading/mcp_brave-browser/brave-profile-browser-mcp/data",
        "HEADLESS": "true",
        "PAGE_TIMEOUT": "30000",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MODE` | http | `stdio` for MCP, `http` for API server |
| `BROWSER_PROFILE` | /app/profile | Path to persistent browser profile |
| `HEADLESS` | true | Run browser in headless mode |
| `PAGE_TIMEOUT` | 30000 | Page load timeout (ms) |
| `LOG_LEVEL` | INFO | Logging level |

### Available Tools

- `fetch_protected_article` — Fetch paywalled/protected content
- `take_screenshot` — Capture page screenshot (base64 PNG)
- `extract_structured_data` — Extract data via CSS selectors
- `search_and_extract` — Search and extract results

### Features

- **Persistent Profile**: Maintains login sessions across restarts
- **Article Caching**: SHA-256 keyed cache with TTL support
- **SSRF Protection**: Blocks access to internal networks
- **Headless Mode**: Runs without display for server environments

---

## GitHub Server

Knowledge repository management.

### Configuration

```json
{
  "mcpServers": {
    "github-vl": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<token>"
      }
    }
  }
}
```

### Key Tools

- `push_files` — Push to repo
- `create_or_update_file` — Single file
- `get_file_contents` — Read file
- `list_commits` — Commit history

---

## Full Configuration

Complete `~/.claude/mcp.json`:

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
    },
    "brave-browser": {
      "command": "python",
      "args": ["-m", "app.main"],
      "cwd": "/opt/data/trading/mcp_brave-browser",
      "env": {
        "MODE": "stdio",
        "BROWSER_PROFILE": "/opt/data/trading/mcp_brave-browser/brave-profile-browser-mcp/data",
        "HEADLESS": "true",
        "PAGE_TIMEOUT": "30000",
        "LOG_LEVEL": "INFO"
      }
    },
    "github-vl": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-github"]
    }
  }
}
```

> **Note**: Sensitive credentials (`OPENAI_API_KEY`, `PG_PASS`, `NEO4J_PASS`, `GITHUB_PERSONAL_ACCESS_TOKEN`) should be set in your shell environment rather than in the config file.

---

## Troubleshooting

### IB MCP not connecting

1. Check IB Gateway is running: `docker compose ps`
2. Verify port 4002 is open: `nc -zv localhost 4002`
3. Verify IB MCP server is running: `curl http://localhost:8100/mcp`
4. Check server logs: `tail -f /tmp/ib-mcp.log`

### RAG/Graph MCP not loading

1. Check Python environment has dependencies
2. Verify environment variables are set
3. Test directly: `python -c "from rag.mcp_server import main; main()"`

### MCP server timeout

- Increase timeout in Claude Code settings
- Check network connectivity to backend services

---

## Related Documentation

- [Architecture Overview](overview.md)
- [RAG System](rag-system.md)
- [Graph System](graph-system.md)
