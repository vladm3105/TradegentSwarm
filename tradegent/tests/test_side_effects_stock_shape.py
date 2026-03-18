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
    assert isinstance(data.get("rationale"), str)
    assert data["rationale"].strip()

    runtime = data.get("adk_runtime")
    assert isinstance(runtime, dict)
    assert "payload" not in runtime
    assert "payload_keys" in runtime

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


def test_write_stock_analysis_yaml_uses_decision_probability_confidence() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-confidence-fallback-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "recommendation": {"action": "WATCH"},
            "decision": {"confidence_pct": 73},
            "probability": {"confidence_pct": 68},
            "summary": {
                "narrative": (
                    "Confidence fallback test narrative with sufficient detail to ensure "
                    "the output remains valid under strict schema checks."
                )
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["recommendation"]["confidence"] == 73
    assert data["do_nothing_gate"]["confidence_actual"] == 73

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_derives_confidence_from_scores() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-confidence-scores-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "recommendation": {"action": "WATCH"},
            "catalyst": {"catalyst_score": 7},
            "market_environment": {"environment_score": 6},
            "technical": {"technical_score": 5},
            "fundamentals": {"fundamental_score": 7},
            "sentiment": {"sentiment_score": 6},
            "summary": {
                "narrative": (
                    "Confidence score-derivation test narrative with enough detail to satisfy "
                    "schema expectations and keep generated structure stable."
                )
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["recommendation"]["confidence"] == 62
    assert data["do_nothing_gate"]["confidence_actual"] == 62

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


def test_write_stock_analysis_yaml_rejects_placeholder_output_when_llm_present() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-quality-gate-fail-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "llm": {"content": '{"summary": {"narrative": "placeholder narrative"}}'},
            }
        },
    )

    assert result["success"] is False
    assert "quality gate" in str(result.get("error", "")).lower()
    issues = result.get("quality_issues")
    assert isinstance(issues, list)
    assert any("current_price" in issue for issue in issues)


def test_write_stock_analysis_yaml_allows_non_placeholder_output_when_llm_present() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-quality-gate-pass-1",
        ticker="AAPL",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "current_price": 201.5,
            "recommendation": {"action": "BUY", "confidence": 74},
            "summary": {
                "narrative": "Constructive setup with defined invalidation and clear execution plan.",
                "key_levels": {
                    "entry": 200.0,
                    "stop": 194.0,
                    "target_1": 214.0,
                },
            },
            "alert_levels": {
                "price_alerts": [
                    {
                        "price": 199.5,
                        "tag": "20-day MA",
                        "significance": (
                            "Price reclaim above the 20-day moving average supports trend continuation "
                            "with improving breadth and acceptable downside containment under current volatility."
                        ),
                        "derivation": {
                            "methodology": "moving_average",
                            "source_field": "technical.moving_averages.ma_20d",
                            "source_value": 199.5,
                            "calculation": "direct",
                        },
                    }
                ]
            },
            "draft": {
                "status": "ok",
                "llm": {"content": '{"thesis": "live generation"}'},
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["current_price"] == 201.5
    assert data["summary"]["key_levels"]["entry"] == 200.0
    assert data["alert_levels"]["price_alerts"][0]["price"] == 199.5

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_uses_thesis_when_narrative_missing() -> None:
    thesis = (
        "Constructive setup with durable demand profile, defined downside invalidation, and "
        "clear upside objective supported by current trend structure and participation breadth."
    )
    result = write_analysis_yaml(
        run_id="run-stock-thesis-fallback-1",
        ticker="AAPL",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "current_price": 201.5,
            "recommendation": {"action": "BUY", "confidence": 74},
            "summary": {
                "thesis": thesis,
                "key_levels": {
                    "entry": 200.0,
                    "stop": 194.0,
                    "target_1": 214.0,
                },
            },
            "alert_levels": {
                "price_alerts": [
                    {
                        "price": 199.5,
                        "tag": "20-day MA",
                        "significance": (
                            "Price reclaim above the 20-day moving average supports trend continuation "
                            "with improving breadth and acceptable downside containment under current volatility."
                        ),
                        "derivation": {
                            "methodology": "moving_average",
                            "source_field": "technical.moving_averages.ma_20d",
                            "source_value": 199.5,
                            "calculation": "direct",
                        },
                    }
                ]
            },
            "draft": {
                "status": "ok",
                "llm": {"content": '{"thesis": "live generation"}'},
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["summary"]["narrative"] == thesis

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_accepts_fenced_json_llm_overrides() -> None:
        llm_content = """Analysis summary\n```json
{
    "current_price": 301.25,
    "recommendation": {"action": "WATCH", "confidence": 66},
    "summary": {
        "narrative": "Structured narrative from fenced JSON with explicit invalidation and execution conditions.",
        "key_levels": {"entry": 300.0, "stop": 292.0, "target_1": 318.0}
    },
    "alert_levels": {
        "price_alerts": [
            {
                "price": 299.5,
                "tag": "20-day MA",
                "significance": "Fenced JSON alert significance remains detailed enough to satisfy validation and support actionable monitoring conditions in production workflows.",
                "derivation": {
                    "methodology": "moving_average",
                    "source_field": "technical.moving_averages.ma_20d",
                    "source_value": 299.5,
                    "calculation": "direct"
                }
            }
        ]
    }
}
```\n"""

        result = write_analysis_yaml(
                run_id="run-stock-fenced-json-1",
                ticker="MSFT",
                analysis_type="stock",
                skill_name="stock-analysis",
                enforce_stock_quality_gate=True,
                payload={
                        "draft": {
                                "status": "ok",
                                "llm": {"content": llm_content},
                        }
                },
        )

        assert result["success"] is True
        file_path = Path(result["file_path"])
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

        assert data["current_price"] == 301.25
        assert data["summary"]["key_levels"]["entry"] == 300.0
        assert data["alert_levels"]["price_alerts"][0]["price"] == 299.5

        file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_uses_context_latest_document_when_llm_missing_fields() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-context-fallback-1",
        ticker="AAPL",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "context": {
                        "status": "ok",
                        "payload": {
                            "context": {
                                "latest_document": {
                                    "current_price": 187.42,
                                    "recommendation": {"action": "BUY", "confidence": 72},
                                    "summary": {
                                        "narrative": "Latest context narrative with concrete setup language.",
                                        "key_levels": {
                                            "entry": 186.0,
                                            "stop": 179.0,
                                            "target_1": 199.0,
                                        },
                                    },
                                    "alert_levels": {
                                        "price_alerts": [
                                            {
                                                "price": 185.5,
                                                "tag": "Context Level",
                                                "significance": (
                                                    "Context alert significance with sufficient detail for"
                                                    " gating and monitoring in production workflows."
                                                ),
                                            }
                                        ]
                                    },
                                }
                            }
                        },
                    }
                },
                "llm": {"content": "No structured json in this response"},
            }
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["current_price"] == 187.42
    assert data["summary"]["key_levels"]["entry"] == 186.0
    assert data["summary"]["key_levels"]["stop"] == 179.0
    assert data["summary"]["key_levels"]["target_1"] == 199.0
    assert data["alert_levels"]["price_alerts"][0]["price"] == 185.5

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_derives_levels_from_price_when_missing() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-derived-levels-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "context": {
                        "status": "ok",
                        "payload": {
                            "context": {
                                "latest_document": {
                                    "current_price": 250.0,
                                    "summary": {"narrative": "Context-only price fallback."},
                                }
                            }
                        },
                    }
                },
                "llm": {"content": "still no structured payload"},
            }
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["current_price"] == 250.0
    assert data["summary"]["key_levels"]["entry"] == 250.0
    assert data["summary"]["key_levels"]["stop"] == 240.0
    assert data["summary"]["key_levels"]["target_1"] == 270.0
    assert data["alert_levels"]["price_alerts"][0]["price"] == 248.75

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_preserves_rich_sections_from_context() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-rich-context-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "context": {
                        "status": "ok",
                        "payload": {
                            "context": {
                                "latest_document": {
                                    "current_price": 410.0,
                                    "data_quality": {
                                        "price_data_source": "ib_mcp",
                                        "price_data_verified": True,
                                        "quote_timestamp": "2026-03-08T20:00:00+00:00",
                                        "prior_close": 408.0,
                                    },
                                    "technical": {
                                        "moving_averages": {"ma_20d": 405.0},
                                        "momentum": {"rsi_14": 55},
                                        "technical_summary": "Context technical detail.",
                                    },
                                    "fundamentals": {
                                        "valuation": {"pe_ratio": 31.5},
                                        "growth": {"revenue_growth_yoy": 12.0},
                                    },
                                    "sentiment": {
                                        "analyst": {"total": 54},
                                        "summary": "Context sentiment detail.",
                                    },
                                    "scenarios": {
                                        "strong_bull": {"probability": 0.25},
                                        "base_bull": {"probability": 0.35},
                                        "base_bear": {"probability": 0.25},
                                        "strong_bear": {"probability": 0.15},
                                        "expected_value": 4.2,
                                    },
                                    "summary": {
                                        "narrative": "Context narrative with concrete setup details.",
                                        "key_levels": {
                                            "entry": 410.0,
                                            "stop": 398.0,
                                            "target_1": 438.0,
                                        },
                                    },
                                    "alert_levels": {
                                        "price_alerts": [
                                            {
                                                "price": 408.5,
                                                "tag": "20-day MA",
                                                "significance": "Context alert significance with enough detail to satisfy quality gating for production monitoring and execution decisions.",
                                                "derivation": {
                                                    "methodology": "moving_average",
                                                    "source_field": "technical.moving_averages.ma_20d",
                                                    "source_value": 408.5,
                                                    "calculation": "direct",
                                                },
                                            }
                                        ]
                                    },
                                }
                            }
                        },
                    }
                },
                "llm": {"content": "non-structured content"},
            }
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["technical"]["moving_averages"]["ma_20d"] == 405.0
    assert data["technical"]["momentum"]["rsi_14"] == 55
    assert data["fundamentals"]["valuation"]["pe_ratio"] == 31.5
    assert data["fundamentals"]["growth"]["revenue_growth_yoy"] == 12.0
    assert data["sentiment"]["analyst"]["total"] == 54
    assert data["scenarios"]["expected_value"] == 4.2

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_rich_overrides_prefer_payload_over_context() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-rich-override-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "technical": {
                "moving_averages": {"ma_20d": 500.0},
                "momentum": {"rsi_14": 62},
            },
            "sentiment": {
                "analyst": {"total": 61},
                "summary": "Override sentiment detail.",
            },
            "summary": {
                "narrative": "Override narrative with concrete entry and invalidation framing.",
                "key_levels": {
                    "entry": 505.0,
                    "stop": 485.0,
                    "target_1": 545.0,
                },
            },
            "alert_levels": {
                "price_alerts": [
                    {
                        "price": 502.5,
                        "tag": "20-day MA",
                        "significance": "Override alert significance with enough detail to support actionable monitoring and preserve quality requirements.",
                        "derivation": {
                            "methodology": "moving_average",
                            "source_field": "technical.moving_averages.ma_20d",
                            "source_value": 502.5,
                            "calculation": "direct",
                        },
                    }
                ]
            },
            "draft": {
                "status": "ok",
                "payload": {
                    "context": {
                        "status": "ok",
                        "payload": {
                            "context": {
                                "latest_document": {
                                    "technical": {"moving_averages": {"ma_20d": 490.0}},
                                    "sentiment": {"analyst": {"total": 40}},
                                }
                            }
                        },
                    }
                },
                "llm": {"content": '{"current_price": 506.0, "data_quality": {"price_data_source": "ib_mcp", "price_data_verified": true, "quote_timestamp": "2026-03-08T20:45:00+00:00", "prior_close": 501.0}}'},
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    assert data["technical"]["moving_averages"]["ma_20d"] == 500.0
    assert data["technical"]["momentum"]["rsi_14"] == 62
    assert data["sentiment"]["analyst"]["total"] == 61
    assert data["summary"]["key_levels"]["entry"] == 505.0

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_generates_broader_price_alert_set() -> None:
    result = write_analysis_yaml(
        run_id="run-stock-alert-breadth-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "current_price": 410.68,
            "data_quality": {
                "price_data_source": "ib_mcp",
                "price_data_verified": True,
                "quote_timestamp": "2026-03-08T21:30:00+00:00",
                "prior_close": 408.96,
            },
            "technical": {
                "moving_averages": {"ma_20d": 402.0},
                "momentum": {"rsi_14": 42},
            },
            "summary": {
                "narrative": "Alert breadth regression test with explicit levels and risk controls.",
                "key_levels": {
                    "entry": 410.68,
                    "stop": 394.25,
                    "target_1": 443.53,
                },
            },
            "alert_levels": {
                "price_alerts": [
                    {
                        "price": 408.63,
                        "tag": "20-day MA",
                        "significance": "Primary alert significance text with enough detail to satisfy gating and preserve actionable monitoring context for execution quality.",
                        "derivation": {
                            "methodology": "moving_average",
                            "source_field": "technical.moving_averages.ma_20d",
                            "source_value": 408.63,
                            "calculation": "direct",
                        },
                    }
                ]
            },
            "draft": {
                "status": "ok",
                "llm": {"content": '{"summary": {"thesis": "live output"}}'},
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))

    alerts = data["alert_levels"]["price_alerts"]
    assert isinstance(alerts, list)
    assert len(alerts) >= 3
    assert alerts[0]["price"] == 408.63
    assert alerts[0]["tag"] == "20-day MA"

    file_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_blocks_sparse_rag_coverage(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "false")
    monkeypatch.setenv("ADK_NON_ACTIVE_USE_DECLINED_DIR", "true")

    llm_content = """```json
{
    "current_price": 12.02,
    "recommendation": {"action": "WATCH", "confidence": 60},
    "summary": {
        "narrative": "Sparse output generated for quality gate regression coverage with explicit levels.",
        "key_levels": {"entry": 12.02, "stop": 11.54, "target_1": 12.98}
    },
    "alert_levels": {
        "price_alerts": [
            {
                "price": 12.0,
                "tag": "Entry Trigger",
                "significance": "Alert significance contains enough characters to pass baseline checks while remaining intentionally sparse for coverage test.",
                "derivation": {
                    "methodology": "support_resistance",
                    "source_field": "summary.key_levels.entry",
                    "source_value": 12.02,
                    "calculation": "direct"
                }
            }
        ]
    },
    "fundamentals": {"insider_activity": {"recent_buys": 0, "recent_sells": 0, "net_direction": "neutral"}},
    "sentiment": {"summary": "Neutral sentiment."}
}
```"""

    result = write_analysis_yaml(
        run_id="run-stock-sparse-rag-coverage-1",
        ticker="ZZZZ",
        analysis_type="stock",
        skill_name="stock-analysis",
        enforce_stock_quality_gate=True,
        payload={
            "draft": {"status": "ok", "llm": {"content": llm_content}},
            "critique": {"status": "ok", "llm": {"content": "critique phase"}},
            "repair": {"status": "ok", "llm": {"content": "repair phase"}},
            "risk_gate": {"status": "ok", "llm": {"content": "risk gate phase"}},
            "summarize": {"status": "ok", "llm": {"content": "summary phase"}},
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    issues = result.get("quality_issues")
    assert isinstance(issues, list)
    assert any("too sparse for RAG ingestion" in issue for issue in issues)

    declined_file_path = result.get("declined_file_path")
    assert isinstance(declined_file_path, str)
    declined_path = Path(declined_file_path)
    assert declined_path.exists()
    assert "tradegent_knowledge/knowledge/analysis/declined" in str(declined_path)

    declined_data = yaml.safe_load(declined_path.read_text(encoding="utf-8"))
    assert declined_data["_meta"]["status"] in {"declined", "inactive_quality_failed"}

    decline_reason = (declined_data.get("decline") or {}).get("reason")
    if decline_reason is None:
        decline_reason = (declined_data.get("inactive_quality_gate") or {}).get("reason")
    if decline_reason is None:
        decline_reason = (declined_data.get("non_active") or {}).get("reason")
    assert decline_reason == "stock_quality_gate_failed"

    declined_path.unlink(missing_ok=True)


def test_write_stock_analysis_yaml_blocks_empty_llm_for_adk_payload(monkeypatch) -> None:
    monkeypatch.setenv("ADK_EMPTY_LLM_BLOCK_ENABLED", "true")
    monkeypatch.setenv("ADK_CONF_GATE_FIX_ENABLED", "true")
    monkeypatch.setenv("ADK_CONF_GATE_FIX_ROLLOUT_PERCENT", "100")

    result = write_analysis_yaml(
        run_id="run-stock-empty-llm-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "_runtime_context": {"selected_engine": "adk", "entrypoint": "skill_router"},
            "draft": {"status": "ok", "llm": {"content": ""}},
            "critique": {"status": "ok", "llm": {"content": ""}},
            "repair": {"status": "ok", "llm": {"content": ""}},
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    reason_codes = result.get("reason_codes")
    assert isinstance(reason_codes, list)
    assert "empty_adk_llm_content" in reason_codes


def test_write_stock_analysis_yaml_allows_empty_llm_for_deterministic_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ADK_EMPTY_LLM_BLOCK_ENABLED", "true")
    monkeypatch.setenv("ADK_CONF_GATE_FIX_ENABLED", "true")
    monkeypatch.setenv("ADK_CONF_GATE_FIX_ROLLOUT_PERCENT", "100")
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "false")

    result = write_analysis_yaml(
        run_id="run-stock-empty-llm-carveout-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "_runtime_context": {
                "selected_engine": "adk",
                "entrypoint": "skill_router",
                "deterministic_fallback": True,
            },
            "current_price": 300.0,
            "recommendation": {"action": "WATCH", "confidence": 64},
            "summary": {
                "narrative": "Deterministic fallback produced structured output with explicit risk controls.",
                "key_levels": {"entry": 300.0, "stop": 288.0, "target_1": 324.0},
            },
            "alert_levels": {
                "price_alerts": [
                    {
                        "price": 299.0,
                        "tag": "20-day MA",
                        "significance": (
                            "Deterministic fallback alert significance includes explicit execution relevance and "
                            "risk reassessment instructions to satisfy quality checks in production workflows."
                        ),
                        "derivation": {
                            "methodology": "moving_average",
                            "source_field": "technical.moving_averages.ma_20d",
                            "source_value": 299.0,
                            "calculation": "direct",
                        },
                    }
                ]
            },
            "draft": {"status": "ok", "llm": {"content": ""}},
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    assert data["adk_runtime"]["conf_gate_fix_enabled"] is True
    file_path.unlink(missing_ok=True)


def test_write_earnings_analysis_yaml_derives_confidence_from_decision_and_probability() -> None:
    result = write_analysis_yaml(
        run_id="run-earn-confidence-derive-1",
        ticker="AMD",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "decision": {
                "recommendation": "WATCH",
                "confidence_pct": 73,
            },
            "probability": {
                "confidence_pct": 70,
            },
            "scenarios": {
                "expected_value": 6.4,
            },
            "summary": {
                "key_levels": {"entry": 120.0, "stop": 112.0, "target_1": 136.0}
            },
        },
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    gate = data["do_nothing_gate"]

    assert gate["confidence_actual"] == 73
    assert data["decision"]["confidence_pct"] == 73
    assert data["probability"]["confidence_pct"] == 70
    assert gate["ev_actual"] == 6.4
    assert gate["rr_actual"] == 2.0
    assert isinstance(gate["gates_passed"], int)

    file_path.unlink(missing_ok=True)
