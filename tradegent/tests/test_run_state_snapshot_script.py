"""Tests for run_state snapshot export script helpers."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_run_state_snapshot import _write_jsonl, parse_args


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.since_hours == 24
    assert args.limit == 5000
    assert args.output is None


def test_write_jsonl_writes_manifest_then_rows(tmp_path: Path) -> None:
    out = tmp_path / "snapshot.jsonl"
    rows = [
        {"id": 10, "run_id": "r1", "phase": "p1"},
        {"id": 11, "run_id": "r1", "phase": "p2"},
    ]

    manifest = _write_jsonl(out, rows, since_hours=6, limit=100)
    assert manifest["event_count"] == 2
    assert manifest["min_event_id"] == 10
    assert manifest["max_event_id"] == 11
    assert isinstance(manifest["sha256"], str)
    assert len(manifest["sha256"]) == 64

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    first = json.loads(lines[0])
    second = json.loads(lines[1])
    third = json.loads(lines[2])

    assert first["kind"] == "run_state_events_snapshot_manifest"
    assert second["id"] == 10
    assert third["id"] == 11
