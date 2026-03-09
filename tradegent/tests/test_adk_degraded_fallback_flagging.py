"""Dedicated degraded fallback flagging tests for stock write path."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.side_effects import write_analysis_yaml


def _cleanup(path: str) -> None:
    Path(path).unlink(missing_ok=True)


def test_degraded_flagging_present_when_non_blocking_market_gate(monkeypatch) -> None:
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_MARKET_DATA_GATES_BLOCKING", "false")

    result = write_analysis_yaml(
        run_id="run-degraded-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 100.0,
                    "data_quality": {"price_data_source": "manual"},
                },
            }
        },
    )

    assert result.get("success") is True
    file_path = str(result.get("file_path", ""))
    doc = yaml.safe_load(Path(file_path).read_text(encoding="utf-8"))

    assert doc.get("_meta", {}).get("status") == "degraded"
    assert doc.get("adk_runtime", {}).get("degraded") is True
    assert isinstance(doc.get("adk_runtime", {}).get("degraded_reasons"), list)

    _cleanup(file_path)
