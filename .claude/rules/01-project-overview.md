# Project Overview

> **Skills**: v2.7 (stock-analysis), v2.6 (earnings-analysis), v2.1 (other)
> **Production Start**: 2026-02-23

**Tradegent** is an AI-driven trading platform using Claude Code CLI, Interactive Brokers, and a hybrid RAG+Graph knowledge system.

## Project Structure

```
tradegent/
├── .claude/skills/          # Claude Code skills (auto-invoke enabled)
├── tradegent/               # Platform (Python)
│   ├── tradegent.py         # CLI entry point
│   ├── service.py           # Long-running daemon
│   ├── orchestrator.py      # Pipeline engine
│   ├── db_layer.py          # PostgreSQL access layer
│   ├── rag/                 # RAG module (MCP server)
│   └── graph/               # Graph module (MCP server)
│
└── tradegent_knowledge/     # Knowledge System (private repo)
    ├── skills/              # Skill definitions (SKILL.md + template.yaml)
    ├── knowledge/           # Trading data & analyses (YAML)
    └── workflows/           # CI/CD & validation schemas
```

## Temporary Files

Use `tmp/` for ephemeral content (not committed):

| Directory | Purpose |
|-----------|---------|
| `tmp/` | One-time scripts, scratch files |
| `tmp/IPLAN/` | Implementation plans |

## Code Standards

- Python 3.11+ with type hints
- Follow PEP 8 conventions
- Use existing patterns in `orchestrator.py` and `db_layer.py`
- All SQL queries go through `db_layer.py`
