#!/usr/bin/env python3
"""Execute a non-destructive rollback drill for run-state migrations.

The drill runs rollback SQL inside a transaction, verifies expected temporary drop
state, then rolls back and verifies pre-drill table existence is restored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_layer import NexusDB


_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"
_ROLLBACK_SEQUENCE = [
    "rollback_022_run_dedup_and_side_effects.sql",
    "rollback_021_run_state_store.sql",
]
_TARGET_TABLES = [
    "nexus.run_request_dedup",
    "nexus.run_side_effect_markers",
    "nexus.run_state_events",
    "nexus.run_state_runs",
]


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _table_exists(db: NexusDB, table_name: str) -> bool:
    with db.conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) AS reg", [table_name])
        row = cur.fetchone()
    if not isinstance(row, dict):
        return False
    return row.get("reg") is not None


def _snapshot_table_state(db: NexusDB) -> dict[str, bool]:
    return {name: _table_exists(db, name) for name in _TARGET_TABLES}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run non-destructive run-state rollback drill")
    parser.add_argument(
        "--emit-json",
        action="store_true",
        help="Print machine-readable summary JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    missing = [name for name in _ROLLBACK_SEQUENCE if not (_MIGRATIONS_DIR / name).exists()]
    if missing:
        print(f"ERROR: Missing rollback SQL files: {missing}")
        return 2

    summary: dict[str, object] = {
        "rollback_sequence": list(_ROLLBACK_SEQUENCE),
        "status": "failed",
    }

    with NexusDB() as db:
        before = _snapshot_table_state(db)
        summary["before"] = before

        try:
            with db.conn.cursor() as cur:
                for file_name in _ROLLBACK_SEQUENCE:
                    cur.execute(_read_sql(_MIGRATIONS_DIR / file_name))

            dropped_state = _snapshot_table_state(db)
            summary["during_tx"] = dropped_state

            # During transaction, all target tables should be absent after rollback SQL.
            for exists in dropped_state.values():
                if exists:
                    raise RuntimeError("Rollback drill validation failed: expected all target tables dropped in tx")

            db.conn.rollback()
            after = _snapshot_table_state(db)
            summary["after_rollback"] = after

            if after != before:
                raise RuntimeError("Rollback drill validation failed: post-rollback table state mismatch")

            summary["status"] = "passed"
        except Exception as exc:
            db.conn.rollback()
            summary["error"] = str(exc)
            if args.emit_json:
                print(json.dumps(summary, sort_keys=True))
            else:
                print(f"ERROR: {exc}")
            return 1

    if args.emit_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("Rollback drill PASSED")
        print(f"Before: {summary['before']}")
        print(f"During TX: {summary['during_tx']}")
        print(f"After rollback: {summary['after_rollback']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
