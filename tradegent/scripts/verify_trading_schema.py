#!/usr/bin/env python3
"""
Verify trading schema is properly applied.

Usage:
    cd tradegent
    python scripts/verify_trading_schema.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def verify_schema():
    """Verify all required trading tables and columns exist."""
    from db_layer import NexusDB

    required_tables = {
        "trades": [
            "id", "ticker", "entry_date", "entry_price", "entry_size",
            "entry_type", "status", "current_size", "exit_date", "exit_price",
            "exit_reason", "pnl_dollars", "pnl_pct", "thesis", "source_analysis",
            "review_status", "review_path", "order_id", "ib_order_status",
            "created_at", "updated_at"
        ],
        "watchlist": [
            "id", "ticker", "entry_trigger", "entry_price", "invalidation",
            "invalidation_price", "expires_at", "priority", "status",
            "source", "source_analysis", "notes", "created_at", "updated_at"
        ],
        "task_queue": [
            "id", "task_type", "ticker", "analysis_type", "prompt",
            "priority", "status", "cooldown_key", "cooldown_until",
            "started_at", "completed_at", "error_message", "created_at"
        ],
    }

    errors = []
    warnings = []

    with NexusDB() as db:
        for table, expected_columns in required_tables.items():
            # Check table exists
            with db.conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = 'nexus' AND table_name = %s
                    )
                """, [table])
                exists = cur.fetchone()["exists"]

            if not exists:
                errors.append(f"Table nexus.{table} does not exist")
                continue

            # Check columns
            with db.conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'nexus' AND table_name = %s
                """, [table])
                actual_columns = {row["column_name"] for row in cur.fetchall()}

            missing = set(expected_columns) - actual_columns
            if missing:
                for col in missing:
                    if col in ("order_id", "ib_order_status", "partial_fills", "avg_fill_price", "direction"):
                        warnings.append(f"nexus.{table}.{col} missing (order tracking column)")
                    else:
                        errors.append(f"nexus.{table}.{col} missing")

        # Check required indexes
        required_indexes = [
            ("trades", "idx_trades_ticker"),
            ("trades", "idx_trades_status"),
            ("trades", "idx_trades_open"),
            ("watchlist", "idx_watchlist_ticker"),
            ("watchlist", "idx_watchlist_active"),
            ("task_queue", "idx_task_queue_pending"),
        ]

        for table, index in required_indexes:
            with db.conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE schemaname = 'nexus'
                          AND tablename = %s
                          AND indexname = %s
                    )
                """, [table, index])
                exists = cur.fetchone()["exists"]

            if not exists:
                warnings.append(f"Index {index} on nexus.{table} missing")

        # Check triggers
        for table in ["trades", "watchlist"]:
            with db.conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.triggers
                        WHERE event_object_schema = 'nexus'
                          AND event_object_table = %s
                          AND trigger_name = %s
                    )
                """, [table, f"{table}_updated_at"])
                exists = cur.fetchone()["exists"]

            if not exists:
                warnings.append(f"Trigger {table}_updated_at missing")

    # Report results
    print("=" * 60)
    print("Trading Schema Verification")
    print("=" * 60)

    if errors:
        print(f"\n❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   - {e}")

    if warnings:
        print(f"\n⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"   - {w}")

    if not errors and not warnings:
        print("\n✅ All tables, columns, indexes, and triggers verified!")
        print("\nTable row counts:")
        with NexusDB() as db:
            for table in required_tables:
                with db.conn.cursor() as cur:
                    cur.execute(f"SELECT COUNT(*) as cnt FROM nexus.{table}")
                    count = cur.fetchone()["cnt"]
                print(f"   nexus.{table}: {count} rows")

    print("\n" + "=" * 60)

    if errors:
        print("\nTo fix: python scripts/apply_migration.py 003")
        return False

    return True


if __name__ == "__main__":
    success = verify_schema()
    sys.exit(0 if success else 1)
