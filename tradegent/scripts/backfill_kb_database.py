#!/usr/bin/env python3
"""Backfill existing YAML files into knowledge base database tables.

Usage:
    python scripts/backfill_kb_database.py --all
    python scripts/backfill_kb_database.py --stock --earnings
    python scripts/backfill_kb_database.py --dry-run --all
"""

import argparse
import logging
import sys
from pathlib import Path

# Add tradegent to path
TRADEGENT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(TRADEGENT_DIR))

from dotenv import load_dotenv
load_dotenv(TRADEGENT_DIR / ".env")

from scripts.ingest import ingest_to_database

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
log = logging.getLogger(__name__)

# Knowledge base root
KNOWLEDGE_BASE = TRADEGENT_DIR.parent / "tradegent_knowledge" / "knowledge"


def backfill_directory(directory: Path, pattern: str = "*.yaml", dry_run: bool = False) -> dict:
    """Backfill all YAML files in a directory."""
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "errors": []}

    if not directory.exists():
        log.warning(f"Directory not found: {directory}")
        return stats

    files = list(directory.rglob(pattern))
    log.info(f"Found {len(files)} files in {directory.relative_to(KNOWLEDGE_BASE.parent)}")

    for file_path in files:
        # Skip template files
        if "template" in file_path.name.lower() or file_path.name.startswith("_"):
            log.debug(f"Skipping template: {file_path.name}")
            continue

        stats["total"] += 1

        if dry_run:
            log.info(f"[DRY RUN] Would ingest: {file_path.name}")
            continue

        try:
            result = ingest_to_database(file_path)
            if result["success"]:
                stats["success"] += 1
                log.info(f"  {result['table']}: {file_path.name}")
            elif result.get("skipped"):
                stats["skipped"] += 1
                log.debug(f"  Skipped: {file_path.name} ({result.get('error', 'unknown type')})")
            else:
                stats["failed"] += 1
                log.warning(f"  {file_path.name}: {result.get('error', 'unknown error')}")
                stats["errors"].append(f"{file_path.name}: {result.get('error')}")
        except Exception as e:
            stats["failed"] += 1
            log.error(f"  {file_path.name}: {e}")
            stats["errors"].append(f"{file_path.name}: {e}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Backfill KB database from existing YAML files"
    )
    parser.add_argument("--all", action="store_true", help="Backfill all directories")
    parser.add_argument("--stock", action="store_true", help="Backfill stock analyses")
    parser.add_argument("--earnings", action="store_true", help="Backfill earnings analyses")
    parser.add_argument("--research", action="store_true", help="Backfill research analyses")
    parser.add_argument("--profiles", action="store_true", help="Backfill ticker profiles")
    parser.add_argument("--trades", action="store_true", help="Backfill trade journals")
    parser.add_argument("--watchlist", action="store_true", help="Backfill watchlist")
    parser.add_argument("--reviews", action="store_true", help="Backfill reviews")
    parser.add_argument("--learnings", action="store_true", help="Backfill learnings")
    parser.add_argument("--strategies", action="store_true", help="Backfill strategies")
    parser.add_argument("--scanners", action="store_true", help="Backfill scanner configs")
    parser.add_argument("--dry-run", action="store_true", help="List files without ingesting")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.all:
        args.stock = args.earnings = args.research = args.profiles = True
        args.trades = args.watchlist = args.reviews = args.learnings = True
        args.strategies = args.scanners = True

    # Check if any option selected
    any_selected = any([
        args.stock, args.earnings, args.research, args.profiles,
        args.trades, args.watchlist, args.reviews, args.learnings,
        args.strategies, args.scanners
    ])
    if not any_selected:
        parser.print_help()
        print("\nError: At least one category must be specified (or --all)")
        sys.exit(1)

    total_stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    if args.dry_run:
        log.info("=== DRY RUN MODE ===\n")

    if args.stock:
        log.info("=== Backfilling Stock Analyses ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "analysis" / "stock", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.earnings:
        log.info("\n=== Backfilling Earnings Analyses ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "analysis" / "earnings", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.research:
        log.info("\n=== Backfilling Research Analyses ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "analysis" / "research", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.profiles:
        log.info("\n=== Backfilling Ticker Profiles ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "analysis" / "ticker-profiles", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.trades:
        log.info("\n=== Backfilling Trade Journals ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "trades", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.watchlist:
        log.info("\n=== Backfilling Watchlist ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "watchlist", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.reviews:
        log.info("\n=== Backfilling Reviews ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "reviews", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.learnings:
        log.info("\n=== Backfilling Learnings ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "learnings", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.strategies:
        log.info("\n=== Backfilling Strategies ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "strategies", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    if args.scanners:
        log.info("\n=== Backfilling Scanner Configs ===")
        stats = backfill_directory(KNOWLEDGE_BASE / "scanners", dry_run=args.dry_run)
        for k in total_stats:
            total_stats[k] += stats.get(k, 0)

    # Summary
    log.info("\n" + "=" * 40)
    log.info("SUMMARY")
    log.info("=" * 40)
    log.info(f"Total files:  {total_stats['total']}")
    log.info(f"Success:      {total_stats['success']}")
    log.info(f"Failed:       {total_stats['failed']}")
    log.info(f"Skipped:      {total_stats['skipped']}")

    if total_stats["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
