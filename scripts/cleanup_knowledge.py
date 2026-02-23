#!/usr/bin/env python3
"""
Knowledge Base Cleanup Tool

Manage and delete documents from RAG (pgvector) and Graph (Neo4j).

Usage:
    python scripts/cleanup_knowledge.py list                    # List all documents
    python scripts/cleanup_knowledge.py list --ticker DOCU      # List docs for ticker
    python scripts/cleanup_knowledge.py list --older-than 7     # List docs older than 7 days
    python scripts/cleanup_knowledge.py delete DOC_ID           # Delete specific doc
    python scripts/cleanup_knowledge.py delete --ticker DOCU --keep-latest 1  # Keep only latest
    python scripts/cleanup_knowledge.py delete --older-than 30  # Delete docs older than 30 days
    python scripts/cleanup_knowledge.py stats                   # Show statistics
"""

import sys
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tradegent"))

import psycopg
from rag.embed import get_database_url, delete_document
from rag.search import get_rag_stats
from graph.layer import TradingGraph


def list_documents(ticker: str | None = None, older_than_days: int | None = None) -> list[dict]:
    """List RAG documents with optional filters."""
    with psycopg.connect(get_database_url()) as conn:
        with conn.cursor() as cur:
            query = """
                SELECT doc_id, doc_type, ticker, file_path, embed_version, created_at
                FROM nexus.rag_documents
                WHERE 1=1
            """
            params = []

            if ticker:
                query += " AND ticker = %s"
                params.append(ticker.upper())

            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                query += " AND created_at < %s"
                params.append(cutoff)

            query += " ORDER BY created_at DESC"

            cur.execute(query, params)
            rows = cur.fetchall()

    return [
        {
            "doc_id": row[0],
            "doc_type": row[1],
            "ticker": row[2],
            "file_path": row[3],
            "version": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]


def delete_from_graph(doc_id: str) -> int:
    """Delete entities associated with a document from the graph."""
    try:
        graph = TradingGraph()
        graph.connect()

        # Delete Document node and its relationships
        with graph._driver.session(database=graph.database) as session:
            result = session.run(
                """
                MATCH (d:Document {doc_id: $doc_id})
                OPTIONAL MATCH (d)-[r]-()
                WITH d, count(r) as rel_count
                DETACH DELETE d
                RETURN rel_count
                """,
                doc_id=doc_id
            )
            record = result.single()
            deleted = record["rel_count"] if record else 0

        graph.close()
        return deleted
    except Exception as e:
        print(f"  Graph delete error: {e}")
        return 0


def delete_doc(doc_id: str, dry_run: bool = False) -> bool:
    """Delete document from both RAG and Graph."""
    if dry_run:
        print(f"  [DRY RUN] Would delete: {doc_id}")
        return True

    # Delete from RAG
    rag_deleted = delete_document(doc_id)
    if rag_deleted:
        print(f"  RAG: Deleted {doc_id}")
    else:
        print(f"  RAG: Not found {doc_id}")

    # Delete from Graph
    graph_deleted = delete_from_graph(doc_id)
    print(f"  Graph: Removed {graph_deleted} relationships for {doc_id}")

    return rag_deleted


def delete_by_ticker(ticker: str, keep_latest: int = 1, dry_run: bool = False) -> int:
    """Delete old documents for a ticker, keeping the N most recent."""
    docs = list_documents(ticker=ticker)

    if len(docs) <= keep_latest:
        print(f"Ticker {ticker}: Only {len(docs)} docs, keeping all (threshold: {keep_latest})")
        return 0

    to_delete = docs[keep_latest:]  # Skip the most recent N
    deleted = 0

    print(f"Ticker {ticker}: Deleting {len(to_delete)} old docs (keeping {keep_latest} latest)")
    for doc in to_delete:
        if delete_doc(doc["doc_id"], dry_run=dry_run):
            deleted += 1

    return deleted


def delete_older_than(days: int, dry_run: bool = False) -> int:
    """Delete documents older than N days."""
    docs = list_documents(older_than_days=days)

    if not docs:
        print(f"No documents older than {days} days")
        return 0

    print(f"Deleting {len(docs)} documents older than {days} days")
    deleted = 0

    for doc in docs:
        if delete_doc(doc["doc_id"], dry_run=dry_run):
            deleted += 1

    return deleted


def show_stats():
    """Show RAG and Graph statistics."""
    # RAG stats
    rag_stats = get_rag_stats()
    print("\n=== RAG Statistics ===")
    print(f"Documents: {rag_stats.document_count}")
    print(f"Chunks: {rag_stats.chunk_count}")

    # Graph stats
    try:
        graph = TradingGraph()
        graph.connect()
        graph_stats = graph.get_stats()
        print("\n=== Graph Statistics ===")
        print(f"Total Nodes: {sum(graph_stats.node_counts.values())}")
        for label, count in sorted(graph_stats.node_counts.items()):
            print(f"  {label}: {count}")
        print(f"Total Edges: {sum(graph_stats.edge_counts.values())}")
        graph.close()
    except Exception as e:
        print(f"\nGraph error: {e}")

    # Document breakdown by ticker
    docs = list_documents()
    print("\n=== Documents by Ticker ===")
    ticker_counts = {}
    for doc in docs:
        t = doc["ticker"] or "unknown"
        ticker_counts[t] = ticker_counts.get(t, 0) + 1

    for ticker, count in sorted(ticker_counts.items(), key=lambda x: -x[1]):
        print(f"  {ticker}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Knowledge Base Cleanup Tool")
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # List command
    list_parser = subparsers.add_parser("list", help="List documents")
    list_parser.add_argument("--ticker", help="Filter by ticker")
    list_parser.add_argument("--older-than", type=int, help="Filter by age in days")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete documents")
    delete_parser.add_argument("doc_id", nargs="?", help="Document ID to delete")
    delete_parser.add_argument("--ticker", help="Delete old docs for ticker")
    delete_parser.add_argument("--keep-latest", type=int, default=1, help="Keep N latest (with --ticker)")
    delete_parser.add_argument("--older-than", type=int, help="Delete docs older than N days")
    delete_parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")

    # Stats command
    subparsers.add_parser("stats", help="Show statistics")

    args = parser.parse_args()

    if args.command == "list":
        docs = list_documents(ticker=args.ticker, older_than_days=args.older_than)
        print(f"\n{'DOC_ID':<45} | {'TYPE':<15} | {'TICKER':<6} | {'VERSION':<8} | CREATED")
        print("-" * 100)
        for doc in docs:
            created = doc["created_at"].strftime("%Y-%m-%d %H:%M") if doc["created_at"] else "N/A"
            version = doc["version"] or "N/A"
            ticker = doc["ticker"] or "N/A"
            print(f"{doc['doc_id']:<45} | {doc['doc_type']:<15} | {ticker:<6} | {version:<8} | {created}")
        print(f"\nTotal: {len(docs)} documents")

    elif args.command == "delete":
        if args.doc_id:
            # Delete specific document
            delete_doc(args.doc_id, dry_run=args.dry_run)
        elif args.ticker:
            # Delete old docs for ticker
            deleted = delete_by_ticker(args.ticker, keep_latest=args.keep_latest, dry_run=args.dry_run)
            print(f"\nDeleted {deleted} documents")
        elif args.older_than:
            # Delete old docs
            deleted = delete_older_than(args.older_than, dry_run=args.dry_run)
            print(f"\nDeleted {deleted} documents")
        else:
            print("Specify doc_id, --ticker, or --older-than")
            sys.exit(1)

    elif args.command == "stats":
        show_stats()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
