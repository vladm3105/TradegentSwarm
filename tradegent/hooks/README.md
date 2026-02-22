# Claude Code Hooks

This directory contains hooks for Claude Code that automate knowledge base operations.

## Setup

Add to your `.claude/settings.json` (or `~/.claude/settings.json` for global):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/tradegent/hooks/post-write-ingest.sh",
            "timeout": 120
          }
        ]
      }
    ]
  }
}
```

## Available Hooks

### post-write-ingest.sh

**Trigger:** After `Write` tool completes successfully

**Condition:** File path matches `tradegent_knowledge/knowledge/*.yaml`

**Action:**
1. Embeds document in RAG (pgvector) for semantic search
2. Extracts entities to Graph (Neo4j) for relationship queries
3. Returns feedback to Claude about ingestion status

**Dependencies:**
- `tradegent/scripts/ingest.py`
- PostgreSQL with pgvector running
- Neo4j running
- Environment variables configured (see `.env`)

## Manual Ingestion

If hooks are not configured, run manually:

```bash
cd tradegent
python scripts/ingest.py ../tradegent_knowledge/knowledge/analysis/stock/ORCL_20260222T1600.yaml
```

Or with JSON output:

```bash
python scripts/ingest.py --json <file_path>
```
