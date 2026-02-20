#!/usr/bin/env python3
"""
Sync trading knowledge documents to RAG+Graph system.
Used by GitHub Actions after validation passes.

Requires either:
1. Self-hosted runner with access to trader modules
2. RAG/Graph MCP servers running with HTTP endpoints
"""

import os
import sys
import yaml
import asyncio
from pathlib import Path
from typing import Optional

# Try to import trader modules (for self-hosted runners)
TRADER_AVAILABLE = False
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'trader'))
    from rag.embed import embed_document
    from graph.extract import extract_document as graph_extract_document
    TRADER_AVAILABLE = True
except ImportError:
    embed_document = None
    graph_extract_document = None

# Try httpx for HTTP mode
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    httpx = None
    HTTPX_AVAILABLE = False

# Configuration
RAG_MCP_URL = os.environ.get('RAG_MCP_URL', 'http://localhost:8101')
GRAPH_MCP_URL = os.environ.get('GRAPH_MCP_URL', 'http://localhost:8102')
SYNC_MODE = os.environ.get('SYNC_MODE', 'auto')  # auto, local, http, dry-run

# Document type mapping based on path
DOC_TYPE_MAP = {
    'earnings': 'earnings-analysis',
    'analysis': 'stock-analysis',
    'trades': 'trade-journal',
    'strategies': 'strategy',
    'tickers': 'ticker-profile',
    'ticker-profiles': 'ticker-profile',
    'learnings': 'learning',
    'research': 'research-analysis',
    'watchlist': 'watchlist',
    'scanners': 'scanner-config',
    'reviews': 'post-trade-review',
}


def get_doc_type_for_path(file_path: str) -> Optional[str]:
    """Determine document type based on file path."""
    path = Path(file_path)
    parts = path.parts

    for part in parts:
        part_lower = part.lower()
        if part_lower in DOC_TYPE_MAP:
            return DOC_TYPE_MAP[part_lower]

    return None


def resolve_sync_mode() -> str:
    """Determine which sync mode to use."""
    if SYNC_MODE != 'auto':
        return SYNC_MODE

    if TRADER_AVAILABLE:
        return 'local'
    elif HTTPX_AVAILABLE:
        return 'http'
    else:
        return 'dry-run'


async def sync_document_local(file_path: str) -> tuple[bool, str]:
    """Sync document using local trader modules."""
    if not TRADER_AVAILABLE:
        return False, f"✗ Local mode unavailable: trader modules not found"

    results = []

    # Embed to RAG
    try:
        result = embed_document(file_path, force=False)
        results.append(f"RAG: {result.chunk_count} chunks")
    except Exception as e:
        results.append(f"RAG error: {e}")

    # Extract to Graph
    try:
        result = graph_extract_document(file_path)
        results.append(f"Graph: {result.entity_count} entities, {result.relation_count} relations")
    except Exception as e:
        results.append(f"Graph error: {e}")

    return True, f"✓ Synced: {file_path} ({'; '.join(results)})"


async def sync_document_http(client, file_path: str) -> tuple[bool, str]:
    """Sync document using HTTP endpoints (MCP servers)."""
    results = []

    # Note: This requires MCP servers to expose HTTP endpoints
    # The FastMCP SSE transport doesn't natively support this
    # This is a placeholder for future HTTP API support

    return False, f"✗ HTTP sync not yet implemented for {file_path}"


async def sync_document_dry_run(file_path: str) -> tuple[bool, str]:
    """Dry-run mode - just log what would be synced."""
    doc_type = get_doc_type_for_path(file_path)
    return True, f"[DRY-RUN] Would sync: {file_path} (type: {doc_type})"


async def sync_document(client, file_path: str, mode: str) -> tuple[bool, str]:
    """Sync a single document using the specified mode."""
    if mode == 'local':
        return await sync_document_local(file_path)
    elif mode == 'http':
        return await sync_document_http(client, file_path)
    else:
        return await sync_document_dry_run(file_path)


async def main():
    """Sync all provided files to RAG+Graph."""
    if len(sys.argv) < 2:
        print("Usage: sync.py <file1> [file2] ...")
        print("\nEnvironment variables:")
        print("  SYNC_MODE: auto|local|http|dry-run (default: auto)")
        print("  RAG_MCP_URL: RAG MCP server URL (for http mode)")
        print("  GRAPH_MCP_URL: Graph MCP server URL (for http mode)")
        sys.exit(0)

    mode = resolve_sync_mode()
    print(f"Sync mode: {mode}")
    print(f"Trader modules available: {TRADER_AVAILABLE}")
    print()

    files = sys.argv[1:]

    # Filter to valid YAML files
    to_sync = []
    for file_path in files:
        file_path = file_path.strip()
        if not file_path:
            continue

        path = Path(file_path)
        if path.suffix not in ('.yaml', '.yml'):
            print(f"Skipped (not YAML): {file_path}")
            continue

        doc_type = get_doc_type_for_path(file_path)
        if not doc_type:
            print(f"Skipped (unknown document type): {file_path}")
            continue

        if not path.exists():
            print(f"Skipped (file not found): {file_path}")
            continue

        to_sync.append(file_path)

    if not to_sync:
        print("No documents to sync")
        sys.exit(0)

    # Sync documents
    results = []
    client = httpx.AsyncClient() if mode == 'http' and HTTPX_AVAILABLE else None

    try:
        for file_path in to_sync:
            success, message = await sync_document(client, file_path, mode)
            results.append((success, message))
            print(message)
    finally:
        if client:
            await client.aclose()

    # Summary
    total = len(results)
    passed = sum(1 for success, _ in results if success)
    failed = total - passed

    print(f"\n{'='*50}")
    print(f"Sync complete: {passed}/{total} synced")

    if mode == 'dry-run':
        print("ℹ️  Dry-run mode - no changes made")
        print("   Set SYNC_MODE=local on self-hosted runner for actual sync")
    elif failed > 0:
        print(f"⚠️  {failed} document(s) failed to sync")
    else:
        print("✅ All documents synced to RAG+Graph")

    sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())
