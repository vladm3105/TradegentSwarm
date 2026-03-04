# Auto-Ingest Hook

Automatically indexes documents when files are written to `tradegent_knowledge/knowledge/`.

## How It Works

```
Write tool → knowledge/*.yaml → Hook triggers → ingest.py runs
                                                    ├── [1] DB insert (kb_* tables)
                                                    ├── [2] RAG embed (pgvector)
                                                    └── [3] Graph extract (Neo4j)
```

## Setup

Add to `.claude/settings.json`:

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

## Manual Ingest (CLI)

If hook is not configured:

```bash
cd tradegent
python scripts/ingest.py ../tradegent_knowledge/knowledge/analysis/stock/NVDA_20260224T0900.yaml

# With JSON output
python scripts/ingest.py --json <file_path>
```

## Manual MCP Tools

```yaml
# 1. Embed for RAG
Tool: rag_embed
Input: {"file_path": "tradegent_knowledge/knowledge/{output_path}"}

# 2. Extract to Graph
Tool: graph_extract
Input: {"file_path": "tradegent_knowledge/knowledge/{output_path}"}

# 3. Push to Knowledge Repo
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: tradegent-knowledge
  branch: main
  files: [{path: "knowledge/{output_path}", content: ...}]
  message: "Add {skill_name} for {TICKER}"
```

## Why Indexing Matters

- Without indexing, documents are invisible to RAG search and Graph queries
- Pre-analysis context retrieval depends on indexed documents
- The learning loop requires indexed post-trade reviews and learnings

## Notes

- Hook triggers on **new Claude sessions** (hooks loaded at session start)
- RAG/Graph modules filter out template/test files automatically
- GitHub push still requires manual step (MCP tool or git)
