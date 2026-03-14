"""Regression tests for analyses normalization helper behavior."""

from __future__ import annotations

from datetime import datetime, timezone

from tradegent_ui.server import analyses


def test_extract_confidence_precedence_and_clamping() -> None:
    payload = {
        "do_nothing_gate": {"confidence_actual": "105"},
        "recommendation": {"confidence": 55},
    }

    # Gate confidence takes precedence and is clamped to [0, 100].
    assert analyses._extract_confidence(payload, row_value=42) == 100


def test_extract_confidence_falls_back_to_row_then_recommendation() -> None:
    payload = {
        "do_nothing_gate": {"confidence_actual": None},
        "recommendation": {"confidence": 61},
    }

    assert analyses._extract_confidence(payload, row_value="59") == 59
    assert analyses._extract_confidence(payload, row_value=None) == 61


def test_extract_expected_value_prefers_gate_ev_actual() -> None:
    payload = {
        "do_nothing_gate": {
            "ev_actual": "7.25",
            "expected_value_actual": "6.50",
        }
    }

    assert analyses._extract_expected_value(payload, row_value=3.0) == 7.25


def test_extract_expected_value_falls_back_to_row_value() -> None:
    payload = {"do_nothing_gate": {"ev_actual": None, "expected_value_actual": None}}

    assert analyses._extract_expected_value(payload, row_value="4.75") == 4.75


def test_row_to_summary_and_detail_prefer_yaml_gate_result_and_values() -> None:
    row = {
        "id": 101,
        "ticker": "NVDA",
        "analysis_type": "stock",
        "analysis_date": datetime(2026, 3, 12, 12, 0, tzinfo=timezone.utc),
        "schema_version": "2.7",
        "recommendation": "WATCH",
        "confidence": 12,
        "expected_value_pct": -1.0,
        "gate_result": "MARGINAL",
        "current_price": 901.12,
        "file_path": "path/to/file.yaml",
        "status": "active",
        "yaml_content": {
            "do_nothing_gate": {
                "confidence_actual": 64,
                "ev_actual": 5.5,
                "gate_result": "PASS",
            },
            "_meta": {"status": "active"},
        },
    }

    summary = analyses._row_to_summary(row)
    assert summary.confidence == 64
    assert summary.expected_value == 5.5
    assert summary.gate_result == "PASS"

    detail = analyses._row_to_detail(row)
    assert detail.confidence == 64
    assert detail.expected_value == 5.5
    assert detail.gate_result == "PASS"
    # Legacy active status should normalize to completed.
    assert detail.status == "completed"
