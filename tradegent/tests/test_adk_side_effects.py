"""Tests for ADK side-effect helpers and MCP tool bus routing."""

from __future__ import annotations

from pathlib import Path

from adk_runtime.mcp_tool_bus import MCPToolBus
from adk_runtime.side_effects import trigger_ingest, write_analysis_yaml


def test_write_analysis_yaml_creates_canonical_file() -> None:
    result = write_analysis_yaml(
        run_id="run-test-1",
        ticker="NVDA",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={"draft": {"status": "ok"}},
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    assert file_path.exists()
    assert "tradegent_knowledge/knowledge/analysis/stock" in str(file_path)

    text = file_path.read_text(encoding="utf-8")
    assert "type: stock-analysis" in text
    assert "ticker: NVDA" in text
    assert "source: adk_runtime" in text

    # Cleanup test artifact.
    file_path.unlink(missing_ok=True)


def test_trigger_ingest_returns_error_for_missing_file() -> None:
    result = trigger_ingest("/tmp/nonexistent-adk-ingest.yaml")
    assert result["success"] is False
    assert "File not found" in str(result.get("error", ""))


def test_mcp_tool_bus_write_yaml_and_ingest_missing_file() -> None:
    bus = MCPToolBus()

    write_result = bus.call(
        "write_yaml",
        {
            "run_id": "run-test-2",
            "ticker": "AAPL",
            "analysis_type": "earnings",
            "skill_name": "earnings-analysis",
            "payload": {"draft": {"status": "ok"}},
        },
    )

    assert write_result["status"] == "ok"
    nested = write_result["payload"]
    assert isinstance(nested, dict)
    path = Path(str(nested["file_path"]))
    assert path.exists()
    assert "tradegent_knowledge/knowledge/analysis/earnings" in str(path)

    ingest_result = bus.call("trigger_ingest", {"file_path": "/tmp/definitely-missing.yaml"})
    assert ingest_result["status"] == "error"

    # Cleanup test artifact.
    path.unlink(missing_ok=True)
