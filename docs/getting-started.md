# Getting Started

This guide walks you through setting up TradegentSwarm from scratch.

---

## Prerequisites

| Requirement | Purpose | Version | Check Command |
|-------------|---------|---------|---------------|
| Docker | Infrastructure services | 20+ | `docker --version` |
| Docker Compose | Service orchestration | 2.0+ | `docker compose version` |
| Python | Platform runtime | 3.11+ | `python3 --version` |
| Node.js | Claude Code dependency | 20+ | `node --version` |
| Claude Code CLI | AI engine | Latest | `claude --version` |
| Anthropic API key | For Claude Code calls | — | console.anthropic.com |
| OpenAI API key | For embeddings | — | platform.openai.com |
| IB Account | Paper trading | — | interactivebrokers.com |

### Install Claude Code CLI

```bash
npm install -g @anthropic-ai/claude-code
claude  # Sign in or set ANTHROPIC_API_KEY
```

---

## Installation

### 1. Clone the Repository

```bash
git clone git@github.com:vladm3105/TradegentSwarm.git
cd TradegentSwarm
```

### 2. Create Environment File

```bash
cp tradegent/.env.template tradegent/.env
```

Edit `tradegent/.env` with your credentials:

```bash
# Interactive Brokers (paper trading account)
IB_USER=your_ib_username
IB_PASS=your_ib_password
IB_ACCOUNT=DU_PAPER_ACCOUNT
VNC_PASS=nexus123

# LLM Providers
EMBED_PROVIDER=openai
EXTRACT_PROVIDER=openai
OPENAI_API_KEY=sk-proj-...

# PostgreSQL
PG_USER=tradegent
PG_PASS=your_secure_password
PG_DB=tradegent
PG_HOST=localhost
PG_PORT=5433

# Neo4j
NEO4J_PASS=your_secure_password
```

### 3. Start Infrastructure Services

```bash
cd tradegent
docker compose up -d
```

Verify services are running:

```bash
docker compose ps
```

Expected output:
```
NAME                  STATUS
tradegent-postgres-1  Up (healthy)
tradegent-neo4j-1     Up (healthy)
paper-ib-gateway      Up (healthy)
```

### 4. Initialize the Database

```bash
python orchestrator.py db-init
```

### 5. Verify Setup

```bash
python orchestrator.py status
```

Expected output:
```
=== Tradegent Status ===
Database: Connected
Service: running
Today: 0 analyses, 0 executions
Dry run mode: true
```

---

## First Analysis

### 1. Run Preflight Check

Before running your first analysis, verify all services are healthy:

```bash
cd tradegent && python preflight.py --full
```

Expected output shows all services healthy:
```
============================================================
  📋 PAPER TRADING (Simulated)
  Account: DUK291525
  Port: 4002 | Container: paper-ib-gateway
============================================================

Preflight Check (full) - 2026-02-26 17:37:56
------------------------------------------------------------
  ✓ postgres_container: healthy - Container running (tradegent-postgres-1)
  ✓ neo4j_container: healthy - Container running (tradegent-neo4j-1)
  ✓ ib_gateway: healthy - PAPER container healthy (paper-ib-gateway)
  ✓ rag: healthy - 59 docs, 86 chunks
  ✓ graph: healthy - 211 nodes, 256 edges
  ✓ ib_mcp: healthy - Server responding on port 8100
  ✓ ib_gateway_port: healthy - PAPER: IB Gateway port 4002 accessible
  ✓ market: degraded - After-hours (17:37 ET)
------------------------------------------------------------
Status: READY
```

If any service shows unhealthy, check the [Troubleshooting](#troubleshooting) section.

### 2. Disable Dry Run Mode

By default, the system runs in dry run mode (no Claude Code calls). Disable it:

```bash
python orchestrator.py settings set dry_run_mode false
```

### 3. Run Your First Analysis

```bash
python orchestrator.py analyze MSFT --type stock
```

This will:
1. Query RAG for historical MSFT context
2. Fetch real-time data from IB Gateway
3. Run the stock-analysis skill
4. Save the analysis to `analyses/`
5. Index the analysis in RAG and Graph

### 3. View the Analysis

```bash
ls -la analyses/
cat analyses/MSFT_stock_*.md
```

---

## Verify RAG and Graph

After running an analysis, verify the knowledge systems:

```bash
# Set environment variables
source tradegent/.env

# Test RAG search
python -c "
from rag.search import semantic_search, get_rag_stats
stats = get_rag_stats()
print(f'RAG: {stats.document_count} docs, {stats.chunk_count} chunks')
results = semantic_search('MSFT analysis', ticker='MSFT', top_k=3)
print(f'Found {len(results)} results')
"

# Test Graph query
python -c "
from graph.layer import TradingGraph
graph = TradingGraph()
graph.connect()
ctx = graph.get_ticker_context('MSFT')
print(f'MSFT context: {ctx}')
graph.close()
"
```

---

## IB Gateway Access

The IB Gateway runs in Docker with VNC access for initial login:

```bash
# Connect via VNC
vncviewer localhost:5900
# Password: (value of VNC_PASS in .env)
```

First-time setup:
1. Connect via VNC
2. Enter IB credentials
3. Complete 2FA if required
4. Gateway will auto-reconnect on subsequent starts

---

## Directory Structure

After setup, your directories look like this:

```
TradegentSwarm/
├── tradegent/                 # Platform code
│   ├── orchestrator.py        # CLI entry point
│   ├── service.py             # Long-running daemon
│   ├── rag/                   # RAG module
│   ├── graph/                 # Graph module
│   ├── analyses/              # Generated analyses
│   └── docker-compose.yml     # Infrastructure
│
├── tradegent_knowledge/       # Knowledge base
│   ├── skills/                # Skill definitions
│   └── knowledge/             # Trading data
│
├── docs/                      # Documentation
│
└── .claude/skills/            # Claude Code skills
```

---

## Next Steps

| Goal | Document |
|------|----------|
| Understand the architecture | [Architecture Overview](architecture/overview.md) |
| Learn all CLI commands | [CLI Reference](user-guide/cli-reference.md) |
| Run earnings analyses | [Analysis Workflow](user-guide/analysis-workflow.md) |
| Set up scanners | [Scanners Guide](user-guide/scanners.md) |
| Deploy to production | [Deployment Guide](operations/deployment.md) |

---

## Troubleshooting

### "claude" command not found

The Claude Code CLI isn't on PATH. If using nvm:

```bash
export PATH="$HOME/.nvm/versions/node/v20.x.x/bin:$PATH"
```

### Database connection failed

Check Docker is running:

```bash
docker compose ps
docker compose logs postgres
```

### IB Gateway not connecting

1. Connect via VNC (localhost:5900)
2. Check credentials on login screen
3. Complete 2FA if prompted

### Dimension mismatch error

Embedding provider changed. Use consistent provider or re-embed:

```bash
# Check current provider
echo $EMBED_PROVIDER

# Re-embed all documents if needed
python scripts/index_knowledge_base.py --force
```

See [Troubleshooting](operations/troubleshooting.md) for more issues.
