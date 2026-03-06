"""Tests for run-state rollback drill script metadata and argument parsing."""

from __future__ import annotations

from scripts.run_state_rollback_drill import _ROLLBACK_SEQUENCE, _TARGET_TABLES, parse_args


def test_rollback_sequence_is_expected_order() -> None:
    assert _ROLLBACK_SEQUENCE == [
        "rollback_022_run_dedup_and_side_effects.sql",
        "rollback_021_run_state_store.sql",
    ]


def test_target_tables_cover_run_state_and_dedup() -> None:
    assert "nexus.run_request_dedup" in _TARGET_TABLES
    assert "nexus.run_side_effect_markers" in _TARGET_TABLES
    assert "nexus.run_state_events" in _TARGET_TABLES
    assert "nexus.run_state_runs" in _TARGET_TABLES


def test_parse_args_emit_json_flag() -> None:
    args = parse_args(["--emit-json"])
    assert args.emit_json is True
