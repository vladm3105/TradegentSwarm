"""Tests for the ADK semantic validator (IPLAN-005 Phase B)."""

from __future__ import annotations

from pathlib import Path

from adk_runtime.semantic_validator import (
    validate_earnings_document_semantics,
    validate_stock_document_semantics,
)
from adk_runtime.side_effects import write_analysis_yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _earnings_doc(overrides: dict | None = None) -> dict:
    """Minimal passing earnings document for semantic checks."""
    base = {
        "current_price": 150.0,
        "summary": {
            "narrative": (
                "NVDA trades at $150, 8% implied move, 65% beat probability. "
                "Target $165 with stop $142. EV 7.2%, R:R 2.5:1."
            ),
        },
        "scenarios": {
            "strong_beat": {"probability": 0.2, "move_pct": 5.0},
            "modest_beat": {"probability": 0.3, "move_pct": 2.5},
            "modest_miss": {"probability": 0.3, "move_pct": -2.5},
            "strong_miss": {"probability": 0.2, "move_pct": -5.0},
        },
        "do_nothing_gate": {
            "gate_result": "PASS",
            "ev_actual": 7.2,
            "confidence_actual": 65.0,
            "rr_actual": 2.5,
        },
        "news_age_check": {
            "items": [
                {"news_item": "NVDA Q4 earnings beat consensus by 15% – valid catalyst", "age_weeks": 0}
            ]
        },
    }
    if overrides:
        base.update(overrides)
    return base


def _stock_doc(overrides: dict | None = None) -> dict:
    """Minimal passing stock document for semantic checks."""
    base = {
        "current_price": 410.0,
        "summary": {
            "narrative": (
                "MSFT breakout above $410 resistance. Target $440, stop $398. "
                "RSI 58, volume 1.4x average. EV 6.1%, confidence 62%, R:R 2.4:1."
            ),
        },
        "do_nothing_gate": {
            "gate_result": "PASS",
            "ev_actual": 6.1,
            "confidence_actual": 62.0,
            "rr_actual": 2.4,
        },
        "catalysts": [
            "Azure cloud segment accelerating – Q2 beat by $1.2B",
            "AI copilot integration driving ARPU expansion",
        ],
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Earnings semantic validator unit tests
# ---------------------------------------------------------------------------


def test_earnings_semantics_pass_on_valid_document() -> None:
    doc = _earnings_doc()
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert issues == [], issues
    assert codes == []
    assert hard_fail is False


def test_earnings_semantics_flags_low_evidence_density() -> None:
    doc = _earnings_doc({
        "summary": {"narrative": "NVDA looks good. Buy it."},
    })
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert "evidence_density_low" in codes
    # Low evidence density is soft-fail (not in EARNINGS_HARD_FAIL_CODES).
    assert hard_fail is False


def test_earnings_semantics_flags_missing_catalyst() -> None:
    doc = _earnings_doc({"news_age_check": {"items": []}})
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert "catalyst_count_insufficient" in codes


def test_earnings_semantics_flags_invalid_scenario_probability_sum() -> None:
    doc = _earnings_doc({
        "scenarios": {
            "strong_beat": {"probability": 0.3},
            "modest_beat": {"probability": 0.3},
            "modest_miss": {"probability": 0.3},
            "strong_miss": {"probability": 0.3},  # sum = 1.2
        }
    })
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert "scenario_probability_sum_invalid" in codes
    assert hard_fail is True  # Hard-fail condition.


def test_earnings_semantics_flags_gate_pass_with_all_metrics_failing() -> None:
    doc = _earnings_doc({
        "do_nothing_gate": {
            "gate_result": "PASS",
            "ev_actual": 1.0,       # fails >5% threshold
            "confidence_actual": 40.0,  # fails >60% threshold
            "rr_actual": 1.0,       # fails >2:1 threshold
        }
    })
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert "gate_result_logic_inconsistent" in codes
    assert hard_fail is True


def test_earnings_semantics_flags_gate_fail_with_all_metrics_passing() -> None:
    doc = _earnings_doc({
        "do_nothing_gate": {
            "gate_result": "FAIL",
            "ev_actual": 8.0,
            "confidence_actual": 70.0,
            "rr_actual": 3.0,
        }
    })
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    assert "gate_result_logic_inconsistent" in codes
    assert hard_fail is True


def test_earnings_semantics_skips_placeholder_narrative_for_density_check() -> None:
    """Placeholder narratives should not trigger evidence_density_low (already caught by quality gate)."""
    doc = _earnings_doc({
        "summary": {"narrative": "This is a placeholder draft analysis pending live enrichment."},
    })
    issues, codes, hard_fail = validate_earnings_document_semantics(doc)
    # evidence_density_low must NOT appear — placeholder check skips density.
    assert "evidence_density_low" not in codes


# ---------------------------------------------------------------------------
# Stock semantic validator unit tests
# ---------------------------------------------------------------------------


def test_stock_semantics_pass_on_valid_document() -> None:
    doc = _stock_doc()
    issues, codes, hard_fail = validate_stock_document_semantics(doc)
    assert issues == [], issues
    assert hard_fail is False


def test_stock_semantics_flags_gate_inconsistency() -> None:
    doc = _stock_doc({
        "do_nothing_gate": {
            "gate_result": "PASS",
            "ev_actual": 0.5,
            "confidence_actual": 30.0,
            "rr_actual": 0.8,
        }
    })
    issues, codes, hard_fail = validate_stock_document_semantics(doc)
    assert "gate_result_logic_inconsistent" in codes
    assert hard_fail is True


# ---------------------------------------------------------------------------
# Integration: semantic validation wired into write_analysis_yaml
# ---------------------------------------------------------------------------


def test_semantic_validator_blocks_hard_fail_in_legacy_mode(monkeypatch) -> None:
    """ADK_SEMANTIC_VALIDATION_ENABLED=true: hard-fail blocks write (legacy mode)."""
    monkeypatch.setenv("ADK_SEMANTIC_VALIDATION_ENABLED", "true")

    # Payload that produces gate_result=PASS with all metrics failing → hard-fail.
    result = write_analysis_yaml(
        run_id="run-sem-legacy-1",
        ticker="NVDA",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "do_nothing_gate": {
                "gate_result": "PASS",
                "ev_actual": 0.5,
                "confidence_actual": 20.0,
                "rr_actual": 0.5,
                "gates_passed": 0,
            },
            "scenarios": {
                "strong_beat": {"probability": 0.2, "move_pct": 5.0},
                "modest_beat": {"probability": 0.3, "move_pct": 2.5},
                "modest_miss": {"probability": 0.3, "move_pct": -2.5},
                "strong_miss": {"probability": 0.2, "move_pct": -5.0},
            },
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    assert "gate_result_logic_inconsistent" in result.get("reason_codes", [])

    declined_path = Path(str(result.get("declined_file_path", "")))
    if declined_path.exists():
        declined_path.unlink(missing_ok=True)


def test_semantic_validator_returns_non_active_artifact(monkeypatch) -> None:
    """Semantic hard-fail with non-active mode returns success=True + inactive status."""
    monkeypatch.setenv("ADK_SEMANTIC_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("ADK_NON_ACTIVE_PERSISTENCE_ENABLED", "true")

    result = write_analysis_yaml(
        run_id="run-sem-nonactive-1",
        ticker="AAPL",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "do_nothing_gate": {
                "gate_result": "PASS",
                "ev_actual": 0.1,
                "confidence_actual": 10.0,
                "rr_actual": 0.1,
                "gates_passed": 0,
            },
            "scenarios": {
                "strong_beat": {"probability": 0.2, "move_pct": 5.0},
                "modest_beat": {"probability": 0.3, "move_pct": 2.5},
                "modest_miss": {"probability": 0.3, "move_pct": -2.5},
                "strong_miss": {"probability": 0.2, "move_pct": -5.0},
            },
        },
    )

    assert result["success"] is True
    assert result.get("analysis_status") == "inactive_quality_failed"
    assert result.get("failure_metadata", {}).get("failure_code") == "LOGIC_INCONSISTENT"

    artifact_path = Path(str(result.get("file_path", "")))
    if artifact_path.exists():
        artifact_path.unlink(missing_ok=True)


def test_semantic_validator_disabled_by_default_write_succeeds() -> None:
    """With no env var, semantic validation is off and write proceeds normally."""
    # No monkeypatch — defaults to disabled.
    result = write_analysis_yaml(
        run_id="run-sem-default-1",
        ticker="TSLA",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "do_nothing_gate": {
                "gate_result": "PASS",
                "ev_actual": 0.0,
                "confidence_actual": 0.0,
                "rr_actual": 0.0,
                "gates_passed": 0,
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    assert file_path.exists()
    file_path.unlink(missing_ok=True)
