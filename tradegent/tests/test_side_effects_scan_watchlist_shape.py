"""Tests for scan/watchlist side-effect document shaping and output paths."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.side_effects import write_analysis_yaml


def test_write_watchlist_yaml_has_required_sections_and_path() -> None:
    result = write_analysis_yaml(
        run_id="run-watchlist-1",
        ticker="PLTR",
        analysis_type="stock",
        skill_name="watchlist",
        payload={"priority": "high", "current_price": 22.5},
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    assert "tradegent_knowledge/knowledge/watchlist" in str(file_path)

    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    assert data["_meta"]["type"] == "watchlist"
    assert data["_meta"]["version"] == 2.1
    for key in (
        "ticker",
        "priority",
        "source",
        "thesis",
        "conviction",
        "analysis_quality",
        "entry_trigger",
        "alternative_entries",
        "invalidation",
        "key_levels",
        "events",
        "monitoring_log",
        "resolution",
    ):
        assert key in data, f"missing {key}"

    file_path.unlink(missing_ok=True)


def test_write_scan_yaml_has_required_sections_and_path() -> None:
    result = write_analysis_yaml(
        run_id="run-scan-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="scan",
        payload={
            "scanner_name": "premarket-gap",
            "scan_summary": {"scored_candidates": 1, "watchlist_count": 1},
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    assert "tradegent_knowledge/knowledge/scanners/runs" in str(file_path)

    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    assert data["_meta"]["type"] == "scanner_run"
    assert data["_meta"]["version"] == 1
    for key in (
        "scanner",
        "market_context",
        "scan_summary",
        "candidates",
        "actions_taken",
        "execution",
        "next_steps",
    ):
        assert key in data, f"missing {key}"

    assert isinstance(data["candidates"], list)
    assert len(data["candidates"]) >= 1
    assert data["candidates"][0]["ticker"] == "NVDA"

    file_path.unlink(missing_ok=True)
