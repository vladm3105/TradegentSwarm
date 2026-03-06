"""Tests for earnings v2.6 contract validation harness."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.earnings_contract import validate_earnings_v26_contract
from adk_runtime.side_effects import write_analysis_yaml


def test_earnings_contract_harness_accepts_generated_document() -> None:
    result = write_analysis_yaml(
        run_id="earn-contract-1",
        ticker="TSLA",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={"draft": {"status": "ok"}},
    )
    assert result["success"] is True

    file_path = Path(result["file_path"])
    doc = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    errors = validate_earnings_v26_contract(doc)
    assert errors == []

    file_path.unlink(missing_ok=True)


def test_earnings_contract_harness_reports_required_failures() -> None:
    broken_doc = {
        "_meta": {"type": "earnings-analysis", "version": 2.6},
        "scenarios": {
            "strong_beat": {},
            "modest_beat": {},
            # intentionally missing modest_miss, strong_miss
        },
        "bull_case_analysis": {"arguments": [{}]},
    }

    errors = validate_earnings_v26_contract(broken_doc)

    assert any("Missing scoring section" in e for e in errors)
    assert any("Missing root do_nothing_gate" in e for e in errors)
    assert any("Missing preparation.implied_move" in e or "Missing preparation section" in e for e in errors)
    assert any("scenarios missing required names" in e for e in errors)
    assert any("base_case_analysis" in e for e in errors)
    assert any("bear_case_analysis" in e for e in errors)
