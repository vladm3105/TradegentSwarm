"""Tests for stock/earnings side-effect document shaping."""

from __future__ import annotations

import json
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.side_effects import write_analysis_yaml


_STOCK_REQUIRED_SECTIONS = [
    "_meta",
    "ticker",
    "current_price",
    "data_quality",
    "news_age_check",
    "catalyst",
    "market_environment",
    "threat_assessment",
    "technical",
    "fundamentals",
    "sentiment",
    "comparable_companies",
    "liquidity_analysis",
    "scenarios",
    "bull_case_analysis",
    "bear_case_analysis",
    "bias_check",
    "do_nothing_gate",
    "falsification",
    "recommendation",
    "summary",
]


def test_write_stock_analysis_yaml_has_validator_critical_structure() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-shape-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={"draft": {"status": "ok"}},
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    for section in _STOCK_REQUIRED_SECTIONS:
        assert section in data, f"Missing required section: {section}"

    peers = data["comparable_companies"]["peers"]
    assert len(peers) >= 3
    assert all("ticker" in p and "pe_forward" in p for p in peers)

    bull_args = data["bull_case_analysis"]["arguments"]
    bear_args = data["bear_case_analysis"]["arguments"]
    assert len(bull_args) >= 3
    assert len(bear_args) >= 3

    alerts = data["alert_levels"]["price_alerts"]
    assert alerts and isinstance(alerts[0].get("derivation"), dict)
    assert len(str(alerts[0].get("significance", ""))) >= 100

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_has_scoring_and_gate_fields() -> None:
    result = write_analysis_yaml(
        run_id="run-earn-shape-1",
        ticker="AAPL",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={"draft": {"status": "ok"}},
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["_meta"]["type"] == "earnings-analysis"
    assert data["_meta"]["version"] == 2.6
    for section in (
        "data_quality",
        "post_mortem",
        "historical_moves",
        "news_age_check",
        "preparation",
        "customer_demand",
        "technical",
        "sentiment",
        "scenarios",
        "probability",
        "bull_case_analysis",
        "base_case_analysis",
        "bear_case_analysis",
        "bias_check",
        "scoring",
        "do_nothing_gate",
        "decision",
        "summary",
        "meta_learning",
    ):
        assert section in data, f"Missing section: {section}"

    assert set(data["scoring"].keys()) >= {
        "catalyst_score",
        "technical_score",
        "fundamental_score",
        "sentiment_score",
    }
    assert "do_nothing_gate" in data
    assert len(data["bull_case_analysis"]["arguments"]) >= 3
    assert len(data["base_case_analysis"]["arguments"]) >= 3
    assert len(data["bear_case_analysis"]["arguments"]) >= 3

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_applies_payload_overrides() -> None:
    result = write_analysis_yaml(
        run_id="run-earn-shape-override-1",
        ticker="MSFT",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "current_price": 412.34,
            "earnings_time": "BMO",
            "days_to_earnings": 4,
            "decision": {
                "recommendation": "WATCH",
                "confidence_pct": 67,
                "rationale": "Contract-safe payload override test.",
                "key_insight": "Directional edge remains limited pre-event.",
            },
            "scoring": {
                "catalyst_score": 7,
                "technical_score": 6,
                "fundamental_score": 5,
                "sentiment_score": 4,
                "weighted_total": 5.6,
            },
            "do_nothing_gate": {
                "ev_actual": 6.1,
                "confidence_actual": 67,
                "rr_actual": 2.4,
                "gates_passed": 4,
                "gate_result": "PASS",
            },
            "summary": {"narrative": "Structured summary override from payload."},
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["current_price"] == 412.34
    assert data["earnings_time"] == "BMO"
    assert data["days_to_earnings"] == 4
    assert data["decision"]["recommendation"] == "WATCH"
    assert data["decision"]["confidence_pct"] == 67
    assert data["scoring"]["catalyst_score"] == 7
    assert data["scoring"]["weighted_total"] == 5.6
    assert data["do_nothing_gate"]["gates_passed"] == 4
    assert data["summary"]["narrative"] == "Structured summary override from payload."

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_applies_llm_content_json_overrides() -> None:
    llm_overrides = {
        "scenarios": {
            "strong_beat": {"probability": 0.35, "move_pct": 7.2, "description": "Upside surprise"},
            "probability_check": 1.0,
            "expected_value": 1.4,
            "ev_calculation": "llm-derived",
        },
        "probability": {
            "base_rate": 0.55,
            "adjustments": {
                "customer_demand": 0.04,
                "estimate_revisions": 0.01,
                "sentiment_contrarian": -0.02,
                "technical": 0.03,
                "expectations": -0.01,
            },
            "final_probability": {
                "p_beat": 0.58,
                "p_miss": 0.42,
                "p_significant_beat": 0.24,
                "p_significant_miss": 0.17,
            },
            "confidence": "high",
            "confidence_pct": 71,
        },
        "alert_levels": {
            "price_alerts": [
                {
                    "price": 410.0,
                    "direction": "below",
                    "significance": "Support break",
                    "action_if_triggered": "Re-evaluate",
                }
            ],
            "event_alerts": [{"event": "Guide update", "date": "2026-03-10", "action": "Review"}],
            "post_earnings_review": "2026-03-11",
        },
    }

    result = write_analysis_yaml(
        run_id="run-earn-shape-llm-override-1",
        ticker="AMZN",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {},
                "llm": {"content": json.dumps(llm_overrides)},
            }
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["scenarios"]["strong_beat"]["probability"] == 0.35
    assert data["scenarios"]["strong_beat"]["move_pct"] == 7.2
    assert data["scenarios"]["ev_calculation"] == "llm-derived"
    assert data["probability"]["base_rate"] == 0.55
    assert data["probability"]["final_probability"]["p_beat"] == 0.58
    assert data["probability"]["confidence"] == "high"
    assert data["probability"]["confidence_pct"] == 71
    assert data["alert_levels"]["price_alerts"][0]["price"] == 410.0
    assert data["alert_levels"]["event_alerts"][0]["event"] == "Guide update"
    assert data["alert_levels"]["post_earnings_review"] == "2026-03-11"

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_prefers_direct_payload_over_llm_content() -> None:
    llm_overrides = {
        "decision": {"recommendation": "NEUTRAL", "confidence_pct": 51},
        "summary": {"narrative": "Narrative from LLM content."},
    }

    result = write_analysis_yaml(
        run_id="run-earn-shape-precedence-1",
        ticker="META",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "decision": {
                "recommendation": "WATCH",
                "confidence_pct": 68,
                "rationale": "Direct payload precedence.",
                "key_insight": "Direct payload key insight.",
            },
            "summary": {"narrative": "Narrative from direct payload."},
            "draft": {
                "status": "ok",
                "payload": {},
                "llm": {"content": json.dumps(llm_overrides)},
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["decision"]["recommendation"] == "WATCH"
    assert data["decision"]["confidence_pct"] == 68
    assert data["summary"]["narrative"] == "Narrative from direct payload."

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_applies_case_analysis_overrides() -> None:
    result = write_analysis_yaml(
        run_id="run-earn-case-override-1",
        ticker="NFLX",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "bull_case_analysis": {
                "strength": 8,
                "arguments": [{"argument": "a"}, {"argument": "b"}, {"argument": "c"}],
                "summary": "Bull summary override",
                "strongest_argument": "Argument a",
                "conditions_where_bull_wins": "If guide expands",
            },
            "base_case_analysis": {
                "strength": 6,
                "arguments": [{"argument": "d"}, {"argument": "e"}, {"argument": "f"}],
                "summary": "Base summary override",
                "trading_implications": "Smaller size",
            },
            "bear_case_analysis": {
                "strength": 7,
                "arguments": [{"argument": "g"}, {"argument": "h"}, {"argument": "i"}],
                "summary": "Bear summary override",
                "strength_interpretation": "Elevated downside",
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["bull_case_analysis"]["strength"] == 8
    assert data["bull_case_analysis"]["summary"] == "Bull summary override"
    assert data["base_case_analysis"]["strength"] == 6
    assert data["base_case_analysis"]["trading_implications"] == "Smaller size"
    assert data["bear_case_analysis"]["strength"] == 7
    assert data["bear_case_analysis"]["strength_interpretation"] == "Elevated downside"

    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_case_analysis_arguments_keep_minimum_three() -> None:
    result = write_analysis_yaml(
        run_id="run-earn-case-minargs-1",
        ticker="ORCL",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "bull_case_analysis": {
                "arguments": [{"argument": "only one"}],
            }
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert len(data["bull_case_analysis"]["arguments"]) >= 3

    file_path.unlink(missing_ok=True)
