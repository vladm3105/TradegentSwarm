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
│   ├── orchestrator.py        # CLI entry point
│   ├── service.py             # Long-running daemon
│   ├── rag/                   # RAG module (pgvector)
│   ├── graph/                 # Graph module (Neo4j)
│   └── docker-compose.yml     # Infrastructure
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

## Documentation

| Section | Contents |
|---------|----------|
| [Getting Started](docs/getting-started.md) | Installation and first analysis |
| [Architecture](docs/architecture/overview.md) | System design, RAG, Graph |
| [User Guide](docs/user-guide/cli-reference.md) | CLI, skills, workflows |
| [Operations](docs/operations/deployment.md) | Deployment, monitoring, troubleshooting |

## Key Features

### Trading Skills (v2.4)
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
| PostgreSQL | RAG embeddings | 5433 |
| Neo4j | Knowledge graph | 7688 |
| IB Gateway | Paper trading | 4002 |
| IB MCP | Market data API | 8100 |

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
