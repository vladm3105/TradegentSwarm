# TradegentSwarm

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system.

## Quick Start

```bash
# Clone and configure
git clone git@github.com:vladm3105/TradegentSwarm.git
cd TradegentSwarm/tradegent
cp .env.template .env  # Fill in credentials

# Start infrastructure
docker compose up -d

# Initialize database
python orchestrator.py db-init

# Run first analysis
python orchestrator.py settings set dry_run_mode false
python orchestrator.py analyze MSFT --type stock
```

See [Getting Started](docs/getting-started.md) for detailed setup instructions.

### Start Tradegent UI (Backend + Frontend)

Use the helper script to avoid partial startup (frontend up, backend down):

```bash
./scripts/start_tradegent_ui.sh
```

The script ensures:
- AGUI backend is healthy on `:8081`
- Frontend is listening on `:3001`
- Existing running services are reused (not duplicated)

## Architecture

```
┌─ HOST MACHINE ─────────────────────────────────────────────────┐
│                                                                │
│  ┌─ ORCHESTRATOR ─────────────────────────────────────────┐   │
│  │  service.py (daemon) → orchestrator.py (pipeline)      │   │
│  │    ├─ mcp__ib-mcp (market data)                        │   │
│  │    ├─ trading-rag (semantic search)                    │   │
│  │    └─ trading-graph (entity queries)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─ KNOWLEDGE LAYER ──────────────────────────────────────┐   │
│  │  RAG (pgvector)           Graph (Neo4j)                │   │
│  │  └─ Semantic search       └─ Entity relationships      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
└─────────────────── connects via localhost ports ───────────────┘
                         │          │          │
                    :5433 PG   :4002 IB   :7688 Neo4j
```

## Repository Structure

```
TradegentSwarm/
├── tradegent/                 # Platform code
│   ├── orchestrator.py        # CLI entry point + pipeline engine
│   ├── service.py             # Long-running daemon
│   ├── rag/                   # RAG module (pgvector, MCP server)
│   ├── graph/                 # Graph module (Neo4j, MCP server)
│   └── docker-compose.yml     # Infrastructure
│
├── tradegent_ui/              # Agent UI (FastAPI + Next.js)
│   ├── server/                # FastAPI backend — port 8081
│   ├── frontend/              # Next.js 14 frontend — port 3001
│   └── db/migrations/         # Auth schema migrations
│
├── tradegent_knowledge/       # Knowledge base (private repo)
│   ├── skills/                # Skill definitions
│   └── knowledge/             # Trading data (YAML)
│
├── docs/                      # Documentation
│   ├── architecture/          # System design
│   ├── user-guide/            # Usage guides
│   └── operations/            # Deployment & ops
│
└── .claude/skills/            # Claude Code skills
```

## Communication Architecture

Tradegent uses a **unified message envelope** across all client-server communication (REST and WebSocket), enabling consistent handling, error reporting, and request correlation:

```typescript
// All messages use TradegentMessage envelope
interface TradegentMessage {
  type: 'request' | 'response' | 'subscription' | 'event' | 'error';
  action: string;           // 'patch_schedule', 'subscribe_prices', etc.
  request_id?: string;      // UUID for correlation
  payload?: any;            // Action-specific data
  timestamp?: number;       // Message creation time
  error?: TradegentError;   // If type='error'
}
```

**Transport Selection:**
- **REST**: User-initiated actions (create, update, read), configuration
- **WebSocket**: Real-time streams (prices, P&L, order fills, alerts)

### Transport Decision Table

| Surface | Primary Transport | Secondary | Notes |
|---------|-------------------|-----------|-------|
| A2UI command/query actions | REST | WebSocket (events only) | Keep request-response on REST; use WS for progress and live state changes |
| Grafana-style dashboards | REST | WebSocket (refresh hints) | Pull metrics/query APIs via REST; add WS only for active live updates |
| Neo4j graph exploration | REST | WebSocket (incremental updates) | Use REST for graph query/layout payloads; WS only for live graph deltas |
| Market/portfolio/order streams | WebSocket | REST (fallback snapshots) | WS is the default for high-frequency updates |

Policy:
- Keep exactly two primary browser interaction gates: REST + WebSocket
- Do not adopt WS-only architecture
- Add SSE only for one-way high-fanout notifications when WS overhead is proven by metrics

**Key Benefits:**
- ✅ Single error format, codes, and handling across both transports
- ✅ Request-response correlation via `request_id` for debugging
- ✅ Unified logging and monitoring
- ✅ Type-safe frontend/backend contract

### Chat Logging

Tradegent UI now performs backend-authoritative chat logging for both REST and WebSocket roundtrips.

- Persists chat messages to `nexus.agent_sessions` and `nexus.agent_messages`
- Captures `user` + `assistant` records at roundtrip completion
- Applies to sync REST, sync WS, and async task completion paths
- Persistence failures are logged (`*.persistence_failed`) without interrupting chat delivery

### Chat Command Coverage (Tradegent UI)

The Tradegent UI chat layer routes intents to analysis/trade/portfolio/research agents and also handles operational system commands.

Current operational chat support includes:

- Automation status and mode changes (`dry_run`, `paper`, `live` with explicit confirm)
- Trading pause/resume controls
- Schedule operations (list, enable, disable, run-now)
- Knowledge-base report count queries with optional ticker follow-up filters

Example chat commands:

- `what is average recommendation for NVDA?`
- `automation status`
- `pause trading`
- `set trading mode to paper`
- `list schedules`
- `disable schedule 3`
- `how many reports do you have?`
- `how many NVDA only?`

See [tradegent_ui/README.md](tradegent_ui/README.md) for endpoint details and interaction flow.

See [tradegent_ui/README.md](tradegent_ui/README.md) for query examples and log event names.

**Quick Reference:**
```typescript
// Frontend: make request-response call
const schedule = await client.request('patch_schedule', { id: 1 });

// Frontend: subscribe to push stream
client.subscribe('subscribe_prices', { tickers: ['NVDA'] }, (event) => { ... });

// Backend: return response
return wrap_response({ schedule_id: 1, ... }, action='patch_schedule');

// Backend: return error
return error_to_response(action='patch_schedule', code='VALIDATION_ERROR', message='...');
```

See [Unified Messages Architecture](docs/architecture/UNIFIED_MESSAGES.md) and [Communication Guide](docs/COMMUNICATION_GUIDE.md) for details.

## Documentation

| Section | Contents |
|---------|----------|
| [Getting Started](docs/getting-started.md) | Installation and first analysis |
| [Communication Guide](docs/COMMUNICATION_GUIDE.md) | Client-server protocol reference |
| [Unified Messages](docs/architecture/UNIFIED_MESSAGES.md) | Message envelope specification |
| [Architecture](docs/architecture/overview.md) | System design, RAG, Graph |
| [User Guide](docs/user-guide/cli-reference.md) | CLI, skills, workflows |
| [Operations](docs/operations/deployment.md) | Deployment, monitoring, troubleshooting |

## Key Features

### Trading Skills (v2.7)
- **Stock Analysis**: 13-phase framework with bias countermeasures
- **Earnings Analysis**: Pre-earnings IV and catalyst analysis
- **Do Nothing Gate**: EV >5%, Confidence >60%, R:R >2:1

### Knowledge System
- **RAG (pgvector)**: Semantic search with reranking
- **Graph (Neo4j)**: Entity extraction and relationships
- **Three-layer model**: Files → RAG → Graph

### Safety Architecture
- Dry run mode (default ON)
- Paper trading only (port 4002)
- Rate limits and gate checks

## Components

| Component | Purpose | Port |
|-----------|---------|------|
| PostgreSQL | Config, KB tables, pgvector RAG | 5433 |
| Neo4j | Knowledge graph | 7688 |
| IB Gateway | Paper trading (TWS API) | 4002 |
| IB MCP | Market data / order API | 8100 |
| tradegent_ui server | Agent UI backend (FastAPI) | 8081 |
| tradegent_ui frontend | Agent UI (Next.js) | 3001 |

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Docker | 20+ | Infrastructure |
| Python | 3.11+ | Platform runtime |
| Node.js | 20+ | Claude Code CLI |
| Claude Code CLI | Latest | AI engine |

## Development

```bash
# Create/activate local virtualenv
/opt/anaconda/bin/virtualenv .venv
source .venv/bin/activate

# Install pinned dependencies from snapshot
pip install -c requirements/constraints-adk.txt -e ".[adk,dev]"

# Setup pre-commit hooks
pip install pre-commit
pre-commit install

# Run tests
pytest tradegent/
```

Re-generate constraints after dependency updates:

```bash
.venv/bin/pip freeze --exclude-editable | sort > requirements/constraints-adk.txt
```

### LiteLLM Multi-Provider Gateway

Tradegent uses **LiteLLM** for unified LLM access across providers. Configuration is in `tradegent/.env`:

```bash
# Provider API keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...

# Default model
LLM_MODEL=gpt-4o-mini

# Role-based routing (ordered fallback chains)
LITELLM_ROUTE_REASONING_PREMIUM=openai/gpt-4o
LITELLM_ROUTE_REASONING_STANDARD=openrouter/openai/gpt-4o-mini,openai/gpt-4o-mini
LITELLM_ROUTE_EXTRACTION_FAST=openai/gpt-4o-mini
LITELLM_ROUTE_CRITIC_MODEL=openai/gpt-4o-mini
LITELLM_ROUTE_SUMMARIZER_FAST=openai/gpt-4o-mini

# Global fallback chain
LITELLM_FALLBACK_MODELS=anthropic/claude-3-5-haiku-20241022

# ADK sub-agent LLM control
ADK_SUBAGENT_LLM_ENABLED=false
```

**Supported providers**: OpenAI, Anthropic, Azure OpenAI, Google Gemini, OpenRouter, Ollama (local), Mistral

**Local Ollama alternative** (free, slower):
```bash
LLM_MODEL=ollama/llama3
LITELLM_ROUTE_REASONING_STANDARD=ollama/llama3
```

See [LiteLLM Integration](docs/architecture/litellm-integration.md) for full documentation

## Security

- Pre-commit hooks for secret scanning
- CI/CD with Gitleaks + TruffleHog
- API key rotation procedures

## License

MIT License - see [LICENSE](LICENSE) for details.
