#!/usr/bin/env python3
"""Export append-only run-state event snapshots for audit and rollback safety.

This script writes a JSONL snapshot containing:
1) a manifest row with query scope and checksum metadata
2) one row per event in nexus.run_state_events ordered by id ascending
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

sys.path.insert(0, str(Path(__file__).parent.parent))

from db_layer import NexusDB


def _default_output_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(__file__).resolve().parents[2] / "tmp" / f"run_state_events_snapshot_{ts}.jsonl"


def _iter_events(
    db: NexusDB,
    *,
    since_hours: int,
    limit: int,
) -> list[dict[str, Any]]:
    query = """
        SELECT
            e.id,
            e.run_id,
            e.from_state,
            e.to_state,
            e.phase,
            e.event_type,
            e.event_payload_json,
            e.policy_decisions_json,
            e.created_at,
            r.intent,
            r.ticker,
            r.analysis_type,
            r.status AS run_status,
            r.contract_version
        FROM nexus.run_state_events e
        LEFT JOIN nexus.run_state_runs r ON r.run_id = e.run_id
        WHERE e.created_at >= (now() - (%s * INTERVAL '1 hour'))
        ORDER BY e.id ASC
        LIMIT %s
    """

    with db.conn.cursor() as cur:
        cur.execute(query, [since_hours, limit])
        rows = cur.fetchall()
    return [dict(row) for row in rows]


def _write_jsonl(path: Path, rows: list[dict[str, Any]], *, since_hours: int, limit: int) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    min_id: int | None = None
    max_id: int | None = None

    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            if isinstance(row.get("id"), int):
                event_id = int(row["id"])
                min_id = event_id if min_id is None else min(min_id, event_id)
                max_id = event_id if max_id is None else max(max_id, event_id)

            encoded = _encode_row(row)
            digest.update(encoded.encode("utf-8"))
            fp.write(encoded + "\n")

    manifest = {
        "kind": "run_state_events_snapshot_manifest",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "since_hours": since_hours,
        "limit": limit,
        "event_count": len(rows),
        "min_event_id": min_id,
        "max_event_id": max_id,
        "sha256": digest.hexdigest(),
    }

    # Prepend manifest by rewriting once; snapshot files are expected to be small enough for this.
    payload_lines = path.read_text(encoding="utf-8").splitlines()
    with path.open("w", encoding="utf-8") as fp:
        fp.write(json.dumps(manifest, sort_keys=True, default=_json_default) + "\n")
        for line in payload_lines:
            fp.write(line + "\n")

    return manifest


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _encode_row(row: dict[str, Any]) -> str:
    return json.dumps(row, sort_keys=True, default=_json_default)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export run_state_events append-only snapshot")
    parser.add_argument("--since-hours", type=int, default=24, help="Window to export from now (hours)")
    parser.add_argument("--limit", type=int, default=5000, help="Maximum events to export")
    parser.add_argument("--output", type=Path, default=None, help="Output .jsonl path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output = args.output or _default_output_path()

    if args.since_hours <= 0:
        print("ERROR: --since-hours must be > 0")
        return 2
    if args.limit <= 0:
        print("ERROR: --limit must be > 0")
        return 2

    with NexusDB() as db:
        rows = _iter_events(db, since_hours=args.since_hours, limit=args.limit)

    manifest = _write_jsonl(output, rows, since_hours=args.since_hours, limit=args.limit)
    print(
        json.dumps(
            {
                "output": str(output),
                "event_count": manifest["event_count"],
                "min_event_id": manifest["min_event_id"],
                "max_event_id": manifest["max_event_id"],
                "sha256": manifest["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
