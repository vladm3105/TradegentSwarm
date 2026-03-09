"""Tests for stock market-data hard gates in ADK side effects."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.side_effects import write_analysis_yaml


def _cleanup(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def test_market_data_gate_blocks_when_required_fields_missing(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")

    result = write_analysis_yaml(
        run_id="run-mdg-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 410.0,
                    "data_quality": {
                        "price_data_source": "manual",
                    },
                },
            }
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    assert "Stock market data gate failed" in str(result.get("error", ""))
    reason_codes = result.get("reason_codes")
    assert isinstance(reason_codes, list)
    assert "market_data_source_not_allowed" in reason_codes
    assert "quote_timestamp_missing" in reason_codes
    assert "prior_close_missing" in reason_codes


def test_market_data_gate_passes_with_valid_ib_data(monkeypatch) -> None:
    now = datetime.now()
    quote_ts = (now - timedelta(seconds=20)).isoformat()

    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_STALENESS_SEC", "120")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_DEVIATION_PCT", "20")

    result = write_analysis_yaml(
        run_id="run-mdg-2",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 412.0,
                    "data_quality": {
                        "price_data_source": "ib_gateway",
                        "quote_timestamp": quote_ts,
                        "prior_close": 405.0,
                        "price_data_verified": True,
                    },
                    "summary": {
                        "narrative": "Validated market data and live context support this setup with bounded downside controls."
                    },
                },
            }
        },
    )

    assert result["success"] is True
    file_path = str(result.get("file_path", ""))
    assert file_path
    _cleanup(file_path)


def test_market_data_gate_non_blocking_writes_degraded_metadata(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_BLOCKING", "false")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")

    result = write_analysis_yaml(
        run_id="run-mdg-3",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 410.0,
                    "data_quality": {
                        "price_data_source": "manual",
                    },
                },
            }
        },
    )

    assert result["success"] is True
    file_path = str(result.get("file_path", ""))
    assert file_path

    doc = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert doc.get("_meta", {}).get("status") == "degraded"
    adk_runtime = doc.get("adk_runtime", {})
    assert isinstance(adk_runtime, dict)
    assert adk_runtime.get("degraded") is True
    assert "market_data_source_not_allowed" in adk_runtime.get("degraded_reasons", [])

    _cleanup(file_path)


def test_stock_write_path_does_not_default_source_to_manual(monkeypatch) -> None:
    monkeypatch.delenv("ADK_MARKET_DATA_GATES_ENABLED", raising=False)

    result = write_analysis_yaml(
        run_id="run-mdg-4",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 412.0,
                    "summary": {
                        "narrative": "Concrete setup text without placeholder wording and with valid actionable levels."
                    },
                },
            }
        },
    )

    assert result["success"] is True
    file_path = str(result.get("file_path", ""))
    doc = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert doc.get("data_quality", {}).get("price_data_source") in {"", None}

    _cleanup(file_path)


def test_market_data_gate_handles_timezone_aware_quote_timestamp(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_STALENESS_SEC", "120")

    result = write_analysis_yaml(
        run_id="run-mdg-5",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 412.0,
                    "data_quality": {
                        "price_data_source": "ib_gateway",
                        "quote_timestamp": "2026-03-08T16:49:40Z",
                        "prior_close": 405.0,
                        "price_data_verified": True,
                    },
                    "summary": {
                        "narrative": "Timezone-aware timestamp regression coverage with valid market data fields."
                    },
                },
            }
        },
    )

    # Main assertion: no runtime exception in datetime arithmetic path.
    assert isinstance(result, dict)
    if result.get("success") is True:
        _cleanup(str(result.get("file_path", "")))


def test_runtime_context_market_data_overrides_stale_payload(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_STALENESS_SEC", "120")

    now = datetime.now().isoformat()
    result = write_analysis_yaml(
        run_id="run-mdg-6",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "_runtime_context": {
                "market_data": {
                    "current_price": 413.0,
                    "prior_close": 405.0,
                    "quote_timestamp": now,
                    "price_data_source": "ib_mcp",
                    "price_data_verified": True,
                }
            },
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 150.0,
                    "data_quality": {
                        "price_data_source": "ib_mcp",
                        "quote_timestamp": "2023-09-01T12:00:00Z",
                        "prior_close": 120.0,
                    },
                    "summary": {
                        "narrative": "Runtime context market data should override stale model payload values."
                    },
                },
            },
        },
    )

    assert result.get("success") is True
    file_path = str(result.get("file_path", ""))
    doc = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    assert doc.get("current_price") == 413.0
    assert doc.get("data_quality", {}).get("prior_close") == 405.0
    assert doc.get("data_quality", {}).get("price_data_source") == "ib_mcp"

    _cleanup(file_path)


def test_market_data_gate_blocks_when_ib_source_unverified(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")

    result = write_analysis_yaml(
        run_id="run-mdg-7",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 412.0,
                    "data_quality": {
                        "price_data_source": "ib_mcp",
                        "price_data_verified": False,
                        "quote_timestamp": datetime.now().isoformat(),
                        "prior_close": 405.0,
                    },
                    "summary": {
                        "narrative": "Unverified IB source should be blocked under strict market-data gating."
                    },
                },
            }
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    reason_codes = result.get("reason_codes")
    assert isinstance(reason_codes, list)
    assert "price_unverified" in reason_codes


def test_market_data_gate_blocks_when_key_levels_are_price_outliers(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_KEY_LEVEL_DEVIATION_PCT", "40")

    result = write_analysis_yaml(
        run_id="run-mdg-8",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 410.68,
                    "data_quality": {
                        "price_data_source": "ib_mcp",
                        "price_data_verified": True,
                        "quote_timestamp": datetime.now().isoformat(),
                        "prior_close": 410.68,
                    },
                    "summary": {
                        "narrative": "Outlier key levels should be blocked under strict market-data quality rules.",
                        "key_levels": {
                            "entry": 155.0,
                            "stop": 145.0,
                            "target_1": 165.0,
                        },
                    },
                },
            }
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    reason_codes = result.get("reason_codes")
    assert isinstance(reason_codes, list)
    assert "key_level_sanity_failed" in reason_codes


def test_runtime_market_data_normalizes_outlier_key_levels(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_KEY_LEVEL_DEVIATION_PCT", "40")

    result = write_analysis_yaml(
        run_id="run-mdg-9",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "_runtime_context": {
                "market_data": {
                    "current_price": 410.68,
                    "prior_close": 410.68,
                    "quote_timestamp": datetime.now().isoformat(),
                    "price_data_source": "ib_mcp",
                    "price_data_verified": True,
                }
            },
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 410.68,
                    "data_quality": {
                        "price_data_source": "ib_mcp",
                        "price_data_verified": True,
                        "quote_timestamp": datetime.now().isoformat(),
                        "prior_close": 410.68,
                    },
                    "summary": {
                        "narrative": "Runtime context should normalize stale model key levels.",
                        "key_levels": {
                            "entry": 155.0,
                            "stop": 145.0,
                            "target_1": 165.0,
                        },
                    },
                    "alert_levels": {
                        "price_alerts": [
                            {
                                "price": 150.0,
                                "tag": "20-day MA",
                                "significance": "Outlier alert should be normalized using runtime context.",
                            }
                        ]
                    },
                },
            },
        },
    )

    assert result.get("success") is True
    file_path = str(result.get("file_path", ""))
    doc = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    levels = doc.get("summary", {}).get("key_levels", {})
    assert levels.get("entry") == 410.68
    assert levels.get("stop") == 394.25
    assert levels.get("target_1") == 443.53
    alert_price = doc.get("alert_levels", {}).get("price_alerts", [{}])[0].get("price")
    assert alert_price == 408.63
    alert_source_value = (
        doc.get("alert_levels", {})
        .get("price_alerts", [{}])[0]
        .get("derivation", {})
        .get("source_value")
    )
    assert alert_source_value == 408.63

    _cleanup(file_path)


def test_market_data_gate_blocks_when_alert_price_is_outlier(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_ALLOWED_SOURCES", "ib_gateway,ib_mcp")
    monkeypatch.setenv("ADK_MARKET_DATA_MAX_KEY_LEVEL_DEVIATION_PCT", "40")

    result = write_analysis_yaml(
        run_id="run-mdg-10",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 410.68,
                    "data_quality": {
                        "price_data_source": "ib_mcp",
                        "price_data_verified": True,
                        "quote_timestamp": datetime.now().isoformat(),
                        "prior_close": 410.68,
                    },
                    "summary": {
                        "narrative": "Alert outlier should be blocked under strict market-data quality rules.",
                        "key_levels": {
                            "entry": 410.68,
                            "stop": 394.25,
                            "target_1": 443.53,
                        },
                    },
                    "alert_levels": {
                        "price_alerts": [
                            {
                                "price": 150.0,
                                "tag": "20-day MA",
                                "significance": "Outlier alert level.",
                            }
                        ]
                    },
                },
            }
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    reason_codes = result.get("reason_codes")
    assert isinstance(reason_codes, list)
    assert "alert_level_sanity_failed" in reason_codes
