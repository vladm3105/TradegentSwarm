# TradegentSwarm Documentation

AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system.

---

## Quick Links

| I want to... | Go to |
|--------------|-------|
| Set up the platform | [Getting Started](getting-started.md) |
| Run my first analysis | [Analysis Workflow](user-guide/analysis-workflow.md) |
| Understand the architecture | [Architecture Overview](architecture/overview.md) |
| Use the CLI | [CLI Reference](user-guide/cli-reference.md) |
| Fix a problem | [Troubleshooting](operations/troubleshooting.md) |
| Contribute code | [Contributing Guide](development/contributing.md) |

---

## Documentation Map

### Getting Started
- [**Getting Started**](getting-started.md) - Installation, prerequisites, first run

### Architecture
System design and technical foundations.

| Document | Description |
|----------|-------------|
| [Overview](architecture/overview.md) | High-level system architecture |
| [LiteLLM Integration](architecture/litellm-integration.md) | Multi-provider LLM gateway, role routing, UCX integration |
| [ADK Multi-Provider Orchestration](architecture/adk-multi-provider-orchestration.md) | ADK control plane, config manager governance |
| [ADK Multi-Provider Orchestration SVG](architecture/adk-multi-provider-orchestration.svg) | End-to-end visual map for sections 1-21 and workflow charts |
| [Skill-Database Mapping](architecture/skill-database-mapping.md) | Skill output to database field mapping |
| [Database Schema](architecture/database-schema.md) | PostgreSQL and Neo4j schemas |
| [RAG System](architecture/rag-system.md) | Semantic search and embeddings |
| [Graph System](architecture/graph-system.md) | Knowledge graph and entity extraction |
| [MCP Servers](architecture/mcp-servers.md) | MCP server configuration |

### User Guide
How to use the platform for trading analysis.

| Document | Description |
|----------|-------------|
| [CLI Reference](user-guide/cli-reference.md) | All command-line commands |
| [Skills Guide](user-guide/skills-guide.md) | Trading skills (analysis, journal, watchlist) |
| [Analysis Workflow](user-guide/analysis-workflow.md) | Running stock and earnings analyses |
| [Scanners](user-guide/scanners.md) | Market scanners and opportunity discovery |
| [Knowledge Base](user-guide/knowledge-base.md) | Managing trading knowledge |

### Operations
Running the platform in production.

| Document | Description |
|----------|-------------|
| [Deployment](operations/deployment.md) | Docker, systemd, cloud deployment |
| [Monitoring](operations/monitoring.md) | Health checks, metrics, alerts |
| [Troubleshooting](operations/troubleshooting.md) | Common issues and solutions |
| [Runbooks](operations/runbooks.md) | Operational procedures |
| [Security Remediation Runbook (2026-03-08)](operations/security-remediation-runbook-20260308.md) | Secret rotation, token/API key revocation, log hygiene |
| [Risk Management](operations/risk-management.md) | Position sizing, stops, gates |

### Development
For contributors and developers.

| Document | Description |
|----------|-------------|
| [API Reference](development/api-reference.md) | Python API documentation |
| [Testing](development/testing.md) | Test framework and coverage |
| [Contributing](development/contributing.md) | Development workflow |

---

## Component Documentation

These documents live alongside their code:

| Component | Location | Description |
|-----------|----------|-------------|
| RAG Module | [`tradegent/rag/README.md`](../tradegent/rag/README.md) | Embedding and search implementation |
| Graph Module | [`tradegent/graph/README.md`](../tradegent/graph/README.md) | Entity extraction and graph queries |
| Knowledge Base | [`tradegent_knowledge/README.md`](../tradegent_knowledge/README.md) | Trading data and skill definitions |
| Claude Skills | [`.claude/skills/`](../.claude/skills/) | Auto-invoked skill definitions |

---

## Key Concepts

### Four-Layer Data Model

```
Layer 1: FILES (Source of Truth)
  Location: tradegent_knowledge/knowledge/**/*.yaml
  Purpose: Authoritative trading data, portable, rebuildable

Layer 2: DATABASE (Structured Queries) ← PRIORITY 1
  Storage: PostgreSQL nexus.kb_* tables
  Purpose: Fast SQL queries, UI rendering

Layer 3: RAG (Semantic Search) ← PRIORITY 2
  Storage: PostgreSQL with pgvector
  Purpose: Find similar analyses, historical context

Layer 4: GRAPH (Entity Relations) ← PRIORITY 3
  Storage: Neo4j
  Purpose: Ticker peers, risks, bias patterns, relationships
```

**Ingestion priority**: DB first (UI needs it immediately), then RAG, then Graph.

### Trading Modes

| Mode | Description | Safety |
|------|-------------|--------|
| Dry Run | Logs actions, no execution | Default ON |
| Analysis Only | Generates reports, no orders | Safe |
| Paper Trading | Orders to IB paper account | Testing |
| Live Trading | Real orders | Not implemented |

### Skill Workflow

Every analysis follows this pattern:

```
PRE-ANALYSIS          EXECUTE            POST-SAVE (priority order)
    │                    │                   │
    ▼                    ▼                   ▼
┌─────────┐        ┌─────────┐        ┌─────────────────────┐
│ RAG +   │───────▶│  Run    │───────▶│ [1] DB (kb_* tables)│
│ Graph   │        │ Skill   │        │ [2] RAG (pgvector)  │
│ Context │        │ Phases  │        │ [3] Graph (Neo4j)   │
└─────────┘        └─────────┘        └─────────────────────┘
```

**UI Visualization**: Rendered from database tables. SVG generation deprecated.

---

## Version Information

| Component | Version |
|-----------|---------|
| Platform | v2.3 |
| Skills | v2.7 (stock), v2.6 (earnings), v2.1 (other) |
| RAG | v2.0 |
| Graph | v1.0 |
| Ingest | v1.2 (DB-first priority) |

---

## Support

- **Issues**: [GitHub Issues](https://github.com/vladm3105/TradegentSwarm/issues)
- **Documentation Issues**: File an issue with `docs` label
