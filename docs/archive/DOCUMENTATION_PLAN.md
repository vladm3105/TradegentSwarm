# TradegentSwarm Documentation Plan

## Current State Assessment

### Existing Documentation (to be consolidated)

| Location | Files | Status |
|----------|-------|--------|
| `/README.md` | Main project README | Keep, update |
| `/CLAUDE.md` | Claude Code instructions | Keep as-is |
| `/CONTRIBUTING.md` | Contribution guidelines | Keep, update |
| `/docs/` | 12 architecture/planning docs | Consolidate |
| `/tradegent/README.md` | Platform docs (1175 lines) | Extract & reorganize |
| `/tradegent/rag/README.md` | RAG module docs | Keep in place |
| `/tradegent/graph/README.md` | Graph module docs | Keep in place |
| `/tradegent/docs/` | Operational docs | Move to main docs/ |
| `/tradegent_knowledge/` | Knowledge base docs | Keep separate |
| `/.claude/skills/` | Skill definitions | Keep in place |

### Issues with Current Documentation

1. **Scattered** - Documentation in 6+ locations
2. **Overlapping** - Same content in multiple files (README.md, CLAUDE.md, tradegent/README.md)
3. **Inconsistent structure** - Different formats and depths
4. **Missing index** - No central navigation
5. **Outdated sections** - Some attribute names, function signatures wrong

---

## Proposed Structure

```
docs/
├── index.md                    # Documentation home & navigation
├── getting-started.md          # Installation, setup, first run
│
├── architecture/               # System design
│   ├── overview.md             # High-level architecture
│   ├── rag-system.md           # RAG pipeline details
│   ├── graph-system.md         # Graph knowledge system
│   ├── mcp-servers.md          # MCP server configuration
│   └── database-schema.md      # PostgreSQL & Neo4j schemas
│
├── user-guide/                 # How to use
│   ├── cli-reference.md        # All CLI commands
│   ├── skills-guide.md         # Trading skills overview
│   ├── analysis-workflow.md    # Running analyses
│   ├── scanners.md             # Market scanners
│   └── knowledge-base.md       # Knowledge management
│
├── operations/                 # Running in production
│   ├── deployment.md           # Docker, systemd, cloud
│   ├── monitoring.md           # Health checks, metrics
│   ├── troubleshooting.md      # Common issues & solutions
│   └── runbooks.md             # Operational procedures
│
└── development/                # For contributors
    ├── api-reference.md        # Python API docs
    ├── testing.md              # Test framework
    └── contributing.md         # Development workflow
```

### Files That Stay In Place

| File | Reason |
|------|--------|
| `/CLAUDE.md` | Claude Code specific, auto-loaded |
| `/tradegent/rag/README.md` | Module-specific, close to code |
| `/tradegent/graph/README.md` | Module-specific, close to code |
| `/tradegent_knowledge/README.md` | Separate repo context |
| `/.claude/skills/*.md` | Skill definitions, auto-invoked |

### Files to Remove/Archive After Migration

| File | Action |
|------|--------|
| `/tradegent/README.md` | Content moved to docs/, keep minimal pointer |
| `/docs/ARCHITECTURE.md` | → `docs/architecture/overview.md` |
| `/docs/TRADING_RAG_ARCHITECTURE.md` | → `docs/architecture/rag-system.md` |
| `/docs/TRADING_GRAPH_ARCHITECTURE.md` | → `docs/architecture/graph-system.md` |
| `/docs/DATABASE_SCHEMA.md` | → `docs/architecture/database-schema.md` |
| `/docs/GRAPH_SCHEMA.md` | → `docs/architecture/database-schema.md` |
| `/docs/SCANNER_ARCHITECTURE.md` | → `docs/user-guide/scanners.md` |
| `/docs/TESTING.md` | → `docs/development/testing.md` |
| `/docs/TROUBLESHOOTING.md` | → `docs/operations/troubleshooting.md` |
| `/docs/RUNBOOKS.md` | → `docs/operations/runbooks.md` |
| `/docs/RISK_MANAGEMENT.md` | → `docs/user-guide/analysis-workflow.md` |
| `/tradegent/docs/*.md` | → Appropriate docs/ location |

---

## Documentation Standards

### Format

- Markdown with GitHub-flavored extensions
- Max 400 lines per file (split if longer)
- Clear hierarchy with H1 → H2 → H3
- Code blocks with language tags
- Tables for structured data

### Content Guidelines

- Objective, factual language
- No promotional content
- Include tested examples
- Document error conditions
- Provide troubleshooting for each feature

### Required Sections (per doc type)

**Conceptual docs:**
- Overview
- Key concepts
- Architecture diagram
- Related docs

**How-to docs:**
- Prerequisites
- Steps (numbered)
- Expected output
- Common errors

**Reference docs:**
- Synopsis
- Parameters table
- Examples
- See also

---

## Implementation Order

1. **Create structure** - mkdir for new folders
2. **Write index.md** - Central navigation
3. **Write getting-started.md** - Entry point
4. **Write architecture/** - Foundation docs
5. **Write user-guide/** - Primary user docs
6. **Write operations/** - Admin docs
7. **Write development/** - Contributor docs
8. **Update root README.md** - Point to docs/
9. **Archive old files** - Move to tmp/old-docs/
10. **Update CLAUDE.md** - Refresh references

---

## Content Sources

### For architecture/overview.md
- `/docs/ARCHITECTURE.md`
- `/tradegent/README.md` (Architecture section)
- `/CLAUDE.md` (Project Structure section)

### For architecture/rag-system.md
- `/docs/TRADING_RAG_ARCHITECTURE.md`
- `/tradegent/rag/README.md`
- `/docs/RAG_IMPROVEMENT_PLAN.md`

### For architecture/graph-system.md
- `/docs/TRADING_GRAPH_ARCHITECTURE.md`
- `/docs/GRAPH_SCHEMA.md`
- `/tradegent/graph/README.md`

### For user-guide/cli-reference.md
- `/tradegent/README.md` (CLI Commands section)

### For user-guide/skills-guide.md
- `/tradegent_knowledge/skills/README.md`
- `/tradegent_knowledge/skills/KNOWLEDGE_BASE_INTEGRATION.md`
- `/.claude/skills/*.md`

### For operations/troubleshooting.md
- `/docs/TROUBLESHOOTING.md`
- `/tradegent/README.md` (Troubleshooting section)

---

## Success Criteria

1. Single entry point (`docs/index.md`) links to all docs
2. No duplicate content across files
3. All examples tested and working
4. Clear navigation between related docs
5. Search-friendly titles and headings
