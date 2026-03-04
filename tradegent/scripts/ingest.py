#!/usr/bin/env python3
"""Auto-ingest script for knowledge base documents.

Ingestion Priority (optimized for UI delivery time):
    1. Database (PostgreSQL kb_* tables) - fastest, needed by UI immediately
    2. RAG embedding (pgvector) - semantic search
    3. Graph extraction (Neo4j) - entity relationships

Usage:
    python ingest.py <file_path> [--skip-github] [--skip-db]

Called automatically by Claude Code post-write hook when files are
written to tradegent_knowledge/knowledge/

Exit Codes:
    0 - Success (all operations passed or intentionally skipped)
    1 - Complete failure (all operations failed)
    2 - Partial failure (some operations failed)
    3 - Input validation error (file not found, not YAML, not knowledge file)
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml

# Add tradegent to path
TRADEGENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TRADEGENT_DIR))

# Load .env
from dotenv import load_dotenv
load_dotenv(TRADEGENT_DIR / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s]: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("tradegent.ingest")


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


def ingest_to_database(file_path: Path) -> dict:
    """Insert document into knowledge base database tables."""
    try:
        # Load YAML with explicit error handling
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            log.error(f"Invalid YAML in {file_path.name}: {e}")
            return {"success": False, "error": f"Invalid YAML syntax: {e}"}

        if data is None:
            return {"success": False, "error": "Empty YAML file"}

        # Get document type from _meta
        meta = data.get("_meta", {})
        doc_type = meta.get("type", "unknown")
        log.debug(f"Processing {file_path.name} as {doc_type}")

        # Import db_layer
        from db_layer import NexusDB
        db = NexusDB()
        db.connect()

        try:
            record_id = None
            table = None

            if doc_type == "stock-analysis":
                record_id = db.upsert_kb_stock_analysis(str(file_path), data)
                table = "kb_stock_analyses"
            elif doc_type == "earnings-analysis":
                record_id = db.upsert_kb_earnings_analysis(str(file_path), data)
                table = "kb_earnings_analyses"
            elif doc_type == "research-analysis":
                record_id = db.upsert_kb_research_analysis(str(file_path), data)
                table = "kb_research_analyses"
            elif doc_type == "ticker-profile":
                record_id = db.upsert_kb_ticker_profile(str(file_path), data)
                table = "kb_ticker_profiles"
            elif doc_type == "trade-journal":
                record_id = db.upsert_kb_trade_journal(str(file_path), data)
                table = "kb_trade_journals"
            elif doc_type == "watchlist":
                record_id = db.upsert_kb_watchlist_entry(str(file_path), data)
                table = "kb_watchlist_entries"
            elif doc_type in ("post-trade-review", "post-earnings-review", "report-validation"):
                record_id = db.upsert_kb_review(str(file_path), data)
                table = "kb_reviews"
            elif doc_type == "learning":
                record_id = db.upsert_kb_learning(str(file_path), data)
                table = "kb_learnings"
            elif doc_type == "strategy":
                record_id = db.upsert_kb_strategy(str(file_path), data)
                table = "kb_strategies"
            elif doc_type == "scanner-config":
                record_id = db.upsert_kb_scanner_config(str(file_path), data)
                table = "kb_scanner_configs"
            elif doc_type == "scanner-run":
                # Scanner execution results
                record_id = db.upsert_kb_scanner_run(data)
                table = "kb_scanner_runs"
            else:
                return {"success": False, "error": f"Unknown doc_type: {doc_type}", "skipped": True}

            # Post-processing: Extract earnings results from post-earnings-review
            if doc_type == "post-earnings-review" and record_id:
                earnings_result = extract_earnings_result_from_review(data, record_id)
                if earnings_result:
                    try:
                        er_id = db.upsert_kb_earnings_result(
                            ticker=earnings_result["ticker"],
                            earnings_date=earnings_result["earnings_date"],
                            data=earnings_result,
                            source_review_id=record_id
                        )
                        log.info(f"Extracted earnings result (id={er_id}) from review (id={record_id})")
                    except Exception as e:
                        log.warning(f"Failed to extract earnings result from review: {e}")

            return {
                "success": True,
                "table": table,
                "record_id": record_id,
                "doc_type": doc_type,
            }
        finally:
            db.close()

    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_earnings_result_from_review(data: dict, review_id: int) -> dict | None:
    """Extract earnings result data from a post-earnings-review document.

    Args:
        data: The post-earnings-review YAML data
        review_id: The ID of the review record in kb_reviews

    Returns:
        Extracted earnings result dict or None if insufficient data
    """
    meta = data.get("_meta", {})
    ticker = meta.get("ticker") or data.get("ticker")

    # Get earnings date from multiple possible sources
    earnings_date = (
        data.get("earnings_release", {}).get("date")
        or data.get("earnings_date")
        or meta.get("earnings_date")
    )

    if not ticker or not earnings_date:
        log.debug(f"Cannot extract earnings result: missing ticker or date")
        return None

    # Extract actual results from the review
    actual = data.get("actual_results", data.get("actual", {}))
    forecast = data.get("forecast_comparison", data.get("forecast", {}))
    accuracy = data.get("accuracy_assessment", data.get("accuracy", {}))
    reaction = data.get("stock_reaction", data.get("reaction", {}))

    # Build earnings result record
    result = {
        "ticker": ticker,
        "earnings_date": earnings_date,
        "source_review_id": review_id,
        # Actual EPS
        "actual_eps": actual.get("eps") or actual.get("actual_eps"),
        "consensus_eps": forecast.get("consensus_eps") or forecast.get("expected_eps"),
        "eps_surprise": actual.get("eps_surprise") or actual.get("surprise"),
        "eps_surprise_pct": actual.get("eps_surprise_pct"),
        # Actual Revenue
        "actual_revenue": actual.get("revenue") or actual.get("actual_revenue"),
        "consensus_revenue": forecast.get("consensus_revenue"),
        "revenue_surprise_pct": actual.get("revenue_surprise_pct"),
        # Guidance
        "guidance_direction": actual.get("guidance", {}).get("direction") or actual.get("guidance_direction"),
        "guidance_vs_consensus": actual.get("guidance", {}).get("vs_consensus"),
        # Reaction
        "reaction_1d_pct": reaction.get("day_1_pct") or reaction.get("1d_pct"),
        "reaction_3d_pct": reaction.get("day_3_pct") or reaction.get("3d_pct"),
        "reaction_5d_pct": reaction.get("day_5_pct") or reaction.get("5d_pct"),
        "price_at_release": reaction.get("price_at_release"),
        "price_after_1d": reaction.get("price_after_1d"),
        # Forecast accuracy
        "forecast_accuracy_score": accuracy.get("overall_score") or accuracy.get("score"),
        "p_beat_predicted": forecast.get("p_beat") or forecast.get("predicted_p_beat"),
        "beat_occurred": actual.get("beat") if isinstance(actual.get("beat"), bool) else None,
    }

    # Only return if we have meaningful data
    if result.get("actual_eps") is not None or result.get("actual_revenue") is not None:
        return result

    log.debug(f"No actual results found in post-earnings-review for {ticker}")
    return None


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
    parser.add_argument("--skip-db", action="store_true", help="Skip database insert")
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
        "db": None,
        "rag": None,
        "graph": None,
    }

    # Priority 1: Database insert (fastest, needed by UI immediately)
    if not args.skip_db:
        print(f"[1/3] Database: {file_path.name}...", file=sys.stderr)
        results["db"] = ingest_to_database(file_path)
    else:
        results["db"] = {"success": False, "skipped": True}

    # Priority 2: RAG embedding (for semantic search)
    print(f"[2/3] RAG: {file_path.name}...", file=sys.stderr)
    results["rag"] = ingest_to_rag(file_path)

    # Priority 3: Graph extraction (for entity relationships)
    print(f"[3/3] Graph: {file_path.name}...", file=sys.stderr)
    results["graph"] = ingest_to_graph(file_path)

    # Summary
    db_status = "✓" if results["db"]["success"] else ("⊘" if results["db"].get("skipped") else "✗")
    rag_status = "✓" if results["rag"]["success"] else "✗"
    graph_status = "✓" if results["graph"]["success"] else "✗"

    summary = f"Ingested {file_path.name}: DB {db_status}, RAG {rag_status}, Graph {graph_status}"

    if args.json:
        results["summary"] = summary
        print(json.dumps(results, indent=2))
    else:
        print(summary)
        # DB first (priority 1)
        if results["db"]["success"]:
            print(f"  DB: {results['db']['table']} (id={results['db']['record_id']})")
        elif not results["db"].get("skipped"):
            print(f"  DB error: {results['db'].get('error', 'unknown')}", file=sys.stderr)
        # RAG second (priority 2)
        if results["rag"]["success"]:
            print(f"  RAG: {results['rag']['chunks']} chunks")
        else:
            print(f"  RAG error: {results['rag']['error']}", file=sys.stderr)
        # Graph third (priority 3)
        if results["graph"]["success"]:
            print(f"  Graph: {results['graph']['entities']} entities, {results['graph']['relations']} relations")
        else:
            print(f"  Graph error: {results['graph']['error']}", file=sys.stderr)

    # Determine exit code based on results
    rag_ok = results["rag"]["success"]
    graph_ok = results["graph"]["success"]
    db_ok = results["db"]["success"] or results["db"].get("skipped")

    if rag_ok and graph_ok and db_ok:
        sys.exit(0)  # Full success
    elif not rag_ok and not graph_ok and not db_ok:
        sys.exit(1)  # Complete failure
    else:
        sys.exit(2)  # Partial failure


if __name__ == "__main__":
    main()
