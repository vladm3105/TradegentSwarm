#!/usr/bin/env python3
"""Auto-ingest script for knowledge base documents.

Handles:
- RAG embedding (pgvector)
- Graph extraction (Neo4j)
- GitHub push (optional, via MCP or git)

Usage:
    python ingest.py <file_path> [--skip-github]

Called automatically by Claude Code post-write hook when files are
written to tradegent_knowledge/knowledge/
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add tradegent to path
TRADEGENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TRADEGENT_DIR))

# Load .env
from dotenv import load_dotenv
load_dotenv(TRADEGENT_DIR / ".env")


def ingest_to_rag(file_path: Path) -> dict:
    """Embed document in RAG (pgvector)."""
    try:
        from rag.embed import embed_document
        result = embed_document(str(file_path))
        return {
            "success": True,
            "doc_id": result.doc_id,
            "chunks": result.chunk_count,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def ingest_to_graph(file_path: Path) -> dict:
    """Extract entities to Graph (Neo4j)."""
    try:
        from graph.extract import extract_document
        result = extract_document(str(file_path))
        return {
            "success": True,
            "entities": len(result.entities),
            "relations": len(result.relations),
            "committed": result.committed,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_relative_knowledge_path(file_path: Path) -> str | None:
    """Get path relative to knowledge repo root."""
    # Find tradegent_knowledge in path
    parts = file_path.parts
    try:
        idx = parts.index("tradegent_knowledge")
        return "/".join(parts[idx + 1:])
    except ValueError:
        return None


def main():
    parser = argparse.ArgumentParser(description="Ingest document to knowledge base")
    parser.add_argument("file_path", help="Path to document to ingest")
    parser.add_argument("--skip-github", action="store_true", help="Skip GitHub push")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    file_path = Path(args.file_path).resolve()

    # Validate file exists
    if not file_path.exists():
        result = {"success": False, "error": f"File not found: {file_path}"}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Check if it's a knowledge file
    rel_path = get_relative_knowledge_path(file_path)
    if not rel_path or not rel_path.startswith("knowledge/"):
        result = {"success": False, "error": "Not a knowledge file", "path": str(file_path)}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Skipping non-knowledge file: {file_path}")
        sys.exit(0)

    # Only process YAML files
    if file_path.suffix not in [".yaml", ".yml"]:
        result = {"success": False, "error": "Not a YAML file"}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"Skipping non-YAML file: {file_path}")
        sys.exit(0)

    results = {
        "file": str(file_path),
        "relative_path": rel_path,
        "rag": None,
        "graph": None,
    }

    # RAG embedding
    print(f"Embedding in RAG: {file_path.name}...", file=sys.stderr)
    results["rag"] = ingest_to_rag(file_path)

    # Graph extraction
    print(f"Extracting to Graph: {file_path.name}...", file=sys.stderr)
    results["graph"] = ingest_to_graph(file_path)

    # Summary
    rag_status = "✓" if results["rag"]["success"] else "✗"
    graph_status = "✓" if results["graph"]["success"] else "✗"

    summary = f"Ingested {file_path.name}: RAG {rag_status}, Graph {graph_status}"

    if args.json:
        results["summary"] = summary
        print(json.dumps(results, indent=2))
    else:
        print(summary)
        if results["rag"]["success"]:
            print(f"  RAG: {results['rag']['chunks']} chunks")
        else:
            print(f"  RAG error: {results['rag']['error']}", file=sys.stderr)
        if results["graph"]["success"]:
            print(f"  Graph: {results['graph']['entities']} entities, {results['graph']['relations']} relations")
        else:
            print(f"  Graph error: {results['graph']['error']}", file=sys.stderr)

    # Exit with error if both failed
    if not results["rag"]["success"] and not results["graph"]["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
