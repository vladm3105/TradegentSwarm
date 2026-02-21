#!/usr/bin/env python3
"""Bulk index all knowledge documents to RAG + Graph.

Usage:
    python scripts/index_knowledge_base.py [--rag-only] [--graph-only] [--force]
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "tradegent"))

# Load environment variables from .env
env_file = project_root / "tradegent" / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def index_document(file_path: Path, rag: bool = True, graph: bool = True, force: bool = False) -> dict:
    """Index a single document to RAG and/or Graph."""
    result = {
        "file": str(file_path),
        "rag": None,
        "graph": None,
        "errors": [],
    }

    # RAG embedding
    if rag:
        try:
            from rag.embed import embed_document
            rag_result = embed_document(str(file_path), force=force)
            if rag_result.error_message == "unchanged":
                result["rag"] = {"status": "unchanged", "chunks": rag_result.chunk_count}
            else:
                result["rag"] = {"status": "indexed", "chunks": rag_result.chunk_count}
        except Exception as e:
            result["errors"].append(f"RAG: {e}")

    # Graph extraction
    if graph:
        try:
            from graph.extract import extract_document
            graph_result = extract_document(str(file_path))
            result["graph"] = {
                "status": "indexed" if graph_result.committed else "failed",
                "entities": len(graph_result.entities),
                "relations": len(graph_result.relations),
            }
            if graph_result.error_message:
                result["errors"].append(f"Graph: {graph_result.error_message}")
        except Exception as e:
            result["errors"].append(f"Graph: {e}")

    return result


def find_documents(knowledge_dir: Path) -> list[Path]:
    """Find all indexable YAML documents."""
    yaml_files = []

    # Patterns to include (real documents, not templates/configs)
    include_patterns = [
        "analysis/**/*.yaml",
        "trades/**/*.yaml",
        "reviews/**/*.yaml",
        "watchlist/**/*.yaml",
        "learnings/**/*.yaml",
        "strategies/*.yaml",
    ]

    for pattern in include_patterns:
        yaml_files.extend(knowledge_dir.glob(pattern))

    # Filter out templates and non-documents
    filtered = []
    for f in yaml_files:
        name = f.name.lower()
        # Skip templates
        if "template" in name:
            continue
        # Skip README files
        if name == "readme.yaml":
            continue
        filtered.append(f)

    return sorted(filtered)


def index_all(
    rag: bool = True,
    graph: bool = True,
    force: bool = False,
) -> dict:
    """Index all knowledge documents."""
    knowledge_dir = project_root / "tradegent_knowledge" / "knowledge"

    if not knowledge_dir.exists():
        print(f"Knowledge directory not found: {knowledge_dir}")
        return {"success": 0, "failed": 0, "unchanged": 0, "errors": []}

    yaml_files = find_documents(knowledge_dir)

    print(f"Found {len(yaml_files)} documents to index")
    print(f"Mode: RAG={rag}, Graph={graph}, Force={force}")
    print("-" * 60)

    results = {"success": 0, "failed": 0, "unchanged": 0, "errors": []}
    start_time = time.time()

    for i, file_path in enumerate(yaml_files, 1):
        rel_path = file_path.relative_to(knowledge_dir)
        print(f"[{i}/{len(yaml_files)}] {rel_path}...", end=" ", flush=True)

        result = index_document(file_path, rag=rag, graph=graph, force=force)

        if result["errors"]:
            print(f"ERRORS: {result['errors']}")
            results["failed"] += 1
            results["errors"].append(result)
        elif result.get("rag", {}).get("status") == "unchanged":
            print("unchanged")
            results["unchanged"] += 1
        else:
            parts = []
            if result.get("rag"):
                parts.append(f"RAG: {result['rag'].get('chunks', 0)} chunks")
            if result.get("graph"):
                parts.append(f"Graph: {result['graph'].get('entities', 0)} entities")
            print(f"OK ({', '.join(parts)})")
            results["success"] += 1

    duration = time.time() - start_time

    print("-" * 60)
    print(f"=== Summary ===")
    print(f"Success:   {results['success']}")
    print(f"Unchanged: {results['unchanged']}")
    print(f"Failed:    {results['failed']}")
    print(f"Duration:  {duration:.1f}s")

    if results["errors"]:
        print(f"\nErrors:")
        for err in results["errors"]:
            print(f"  - {err['file']}: {err['errors']}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Index knowledge documents to RAG and Graph")
    parser.add_argument("--rag-only", action="store_true", help="Only index to RAG (skip Graph)")
    parser.add_argument("--graph-only", action="store_true", help="Only index to Graph (skip RAG)")
    parser.add_argument("--force", action="store_true", help="Force re-indexing even if unchanged")
    args = parser.parse_args()

    rag = not args.graph_only
    graph = not args.rag_only

    index_all(rag=rag, graph=graph, force=args.force)


if __name__ == "__main__":
    main()
