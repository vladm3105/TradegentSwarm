"""Migration artifact tests for run-state rollback coverage."""

from __future__ import annotations

from pathlib import Path


_MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db" / "migrations"


def _read(name: str) -> str:
    return (_MIGRATIONS_DIR / name).read_text(encoding="utf-8")


def test_run_state_migrations_have_matching_rollback_files() -> None:
    for forward, rollback in (
        ("021_run_state_store.sql", "rollback_021_run_state_store.sql"),
        ("022_run_dedup_and_side_effects.sql", "rollback_022_run_dedup_and_side_effects.sql"),
    ):
        assert (_MIGRATIONS_DIR / forward).exists(), f"Missing forward migration: {forward}"
        assert (_MIGRATIONS_DIR / rollback).exists(), f"Missing rollback migration: {rollback}"


def test_rollback_021_drops_run_state_tables_in_safe_order() -> None:
    sql = _read("rollback_021_run_state_store.sql")

    assert "DROP TABLE IF EXISTS nexus.run_state_events;" in sql
    assert "DROP TABLE IF EXISTS nexus.run_state_runs;" in sql
    assert sql.find("run_state_events") < sql.find("run_state_runs")


def test_rollback_022_drops_dedup_and_side_effect_tables() -> None:
    sql = _read("rollback_022_run_dedup_and_side_effects.sql")

    assert "DROP TABLE IF EXISTS nexus.run_side_effect_markers;" in sql
    assert "DROP TABLE IF EXISTS nexus.run_request_dedup;" in sql
