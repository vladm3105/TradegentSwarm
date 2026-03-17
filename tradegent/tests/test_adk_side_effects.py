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


def test_mcp_tool_bus_write_yaml_enforced_stock_quality_gate_blocks_placeholder() -> None:
    bus = MCPToolBus()

    write_result = bus.call(
        "write_yaml",
        {
            "run_id": "run-test-quality-gate-1",
            "ticker": "NVDA",
            "analysis_type": "stock",
            "skill_name": "stock-analysis",
            "enforce_stock_quality_gate": True,
            "payload": {"draft": {"status": "ok", "payload": {}}},
        },
    )

    assert write_result["status"] == "error"
    payload = write_result.get("payload", {})
    assert isinstance(payload, dict)
    assert "Stock analysis quality gate failed" in str(payload.get("error", ""))
    failure_payload = payload.get("failure_payload")
    assert isinstance(failure_payload, dict)
    assert isinstance(failure_payload.get("quality_issues"), list)


def test_earnings_data_completeness_gate_blocks_in_legacy_mode(monkeypatch) -> None:
    """Earnings data gate fires (legacy block) when required fields are zero/missing."""
    monkeypatch.setenv("ADK_EARNINGS_QUALITY_GATES_ENABLED", "true")
    # ADK_NON_ACTIVE_PERSISTENCE_ENABLED defaults to false (legacy mode).

    result = write_analysis_yaml(
        run_id="run-earnings-gate-legacy-1",
        ticker="NVDA",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={"draft": {"status": "ok"}},
    )

    # Legacy mode: data gate returns hard-block with success=False.
    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    assert "Earnings data completeness gate failed" in str(result.get("error", ""))
    reason_codes = result.get("reason_codes", [])
    assert isinstance(reason_codes, list)
    # At minimum, consensus_eps and implied_move are always 0 in the builder defaults.
    assert any("missing_" in code for code in reason_codes), reason_codes

    declined_path = Path(str(result.get("declined_file_path", "")))
    if declined_path.exists():
        declined_path.unlink(missing_ok=True)


def test_earnings_data_completeness_gate_returns_non_active_artifact(monkeypatch) -> None:
    """Earnings data gate with non-active mode persists artifact and returns success=True."""
    monkeypatch.setenv("ADK_EARNINGS_QUALITY_GATES_ENABLED", "true")
    monkeypatch.setenv("ADK_NON_ACTIVE_PERSISTENCE_ENABLED", "true")

    result = write_analysis_yaml(
        run_id="run-earnings-gate-nonactive-1",
        ticker="AAPL",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={"draft": {"status": "ok"}},
    )

    # Non-active mode: gate returns success=True with inactive status.
    assert result["success"] is True
    assert result.get("analysis_status") == "inactive_data_unavailable"
    failure_metadata = result.get("failure_metadata")
    assert isinstance(failure_metadata, dict)
    assert failure_metadata.get("failure_code") == "DATA_INCOMPLETE"
    assert isinstance(failure_metadata.get("failed_checks"), list)
    assert len(failure_metadata["failed_checks"]) > 0

    artifact_path = Path(str(result.get("file_path", "")))
    if artifact_path.exists():
        artifact_path.unlink(missing_ok=True)


def test_earnings_gate_disabled_by_default_write_succeeds() -> None:
    """No quality gate env vars → earnings write succeeds regardless of data gaps."""
    result = write_analysis_yaml(
        run_id="run-earnings-default-1",
        ticker="MSFT",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={"draft": {"status": "ok"}},
    )

    assert result["success"] is True
    file_path = Path(result["file_path"])
    assert file_path.exists()
    Path(file_path).unlink(missing_ok=True)


def test_earnings_quality_gate_blocks_placeholder_content(monkeypatch) -> None:
    """Quality gate fires on placeholder narrative when data completeness gate passes."""
    monkeypatch.setenv("ADK_EARNINGS_QUALITY_GATES_ENABLED", "true")
    # Pass real preparation values so data completeness gate does NOT fire.
    # The document builder still emits placeholder summary/scenario language,
    # which _earnings_quality_issues() detects.
    result = write_analysis_yaml(
        run_id="run-earnings-quality-1",
        ticker="NVDA",
        analysis_type="earnings",
        skill_name="earnings-analysis",
        payload={
            "current_price": 900.0,
            "preparation": {
                "current_estimates": {"consensus_eps": 1.5, "consensus_revenue_b": 5.0},
                "implied_move": {"percentage": 8.0},
            },
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    assert "Earnings analysis quality gate failed" in str(result.get("error", ""))
    reason_codes = result.get("reason_codes", [])
    assert isinstance(reason_codes, list)
    assert len(reason_codes) > 0

    declined_path = Path(str(result.get("declined_file_path", "")))
    if declined_path.exists():
        declined_path.unlink(missing_ok=True)


def test_critique_score_gate_blocks_when_scores_below_threshold(monkeypatch) -> None:
    """Phase D: critique score gate blocks active classification for low section scores."""
    monkeypatch.setenv("ADK_CRITIQUE_SCORE_GATE_ENABLED", "true")
    monkeypatch.setenv("ADK_CRITIQUE_SECTION_MIN_SCORE", "7.0")

    result = write_analysis_yaml(
        run_id="run-critique-gate-low-1",
        ticker="MSFT",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 8.0,
                        "consistency": 6.5,
                        "actionability": 8.0,
                    }
                },
            },
        },
    )

    assert result["success"] is False
    assert result.get("status") == "blocked_quality"
    assert "Critique score gate failed" in str(result.get("error", ""))
    codes = result.get("reason_codes", [])
    assert isinstance(codes, list)
    assert any(str(code).startswith("critique_score_below_threshold_") for code in codes)

    declined_path = Path(str(result.get("declined_file_path", "")))
    if declined_path.exists():
        declined_path.unlink(missing_ok=True)


def test_critique_score_gate_allows_when_all_scores_meet_threshold(monkeypatch) -> None:
    """Phase D: critique score gate allows persistence when all section scores meet threshold."""
    monkeypatch.setenv("ADK_CRITIQUE_SCORE_GATE_ENABLED", "true")
    monkeypatch.setenv("ADK_CRITIQUE_SECTION_MIN_SCORE", "7.0")

    result = write_analysis_yaml(
        run_id="run-critique-gate-pass-1",
        ticker="AMZN",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 8.0,
                        "consistency": 7.1,
                        "actionability": 7.0,
                    }
                },
            },
        },
    )

    assert result["success"] is True
    assert result.get("analysis_status") == "active"

    file_path = Path(str(result.get("file_path", "")))
    if file_path.exists():
        file_path.unlink(missing_ok=True)


def test_critique_score_gate_non_active_mode_persists_inactive_artifact(monkeypatch) -> None:
    """11.4 matrix: enabled+non-active mode persists inactive artifact (not hard block)."""
    monkeypatch.setenv("ADK_CRITIQUE_SCORE_GATE_ENABLED", "true")
    monkeypatch.setenv("ADK_NON_ACTIVE_PERSISTENCE_ENABLED", "true")
    monkeypatch.setenv("ADK_CRITIQUE_SECTION_MIN_SCORE", "7.0")

    result = write_analysis_yaml(
        run_id="run-critique-gate-nonactive-1",
        ticker="META",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {"summary": {"narrative": "has data 1 2 3"}}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 6.9,
                        "consistency": 8.2,
                        "actionability": 8.0,
                    },
                    "failed_sections": ["evidence"],
                    "failed_section_reasons": {"evidence": "insufficient numeric support"},
                },
            },
            "repair": {"status": "ok", "payload": {"notes": "repair attempted"}},
        },
    )

    assert result["success"] is True
    assert result.get("analysis_status") == "inactive_quality_failed"
    failure_metadata = result.get("failure_metadata")
    assert isinstance(failure_metadata, dict)
    assert failure_metadata.get("failure_code") == "PLACEHOLDER_CONTENT"

    artifact_path = Path(str(result.get("file_path", "")))
    if artifact_path.exists():
        artifact_path.unlink(missing_ok=True)


def test_critique_score_gate_disabled_default_path_allows_low_scores(monkeypatch) -> None:
    """11.4 matrix: disabled default path does not block low critique scores."""
    monkeypatch.delenv("ADK_CRITIQUE_SCORE_GATE_ENABLED", raising=False)
    monkeypatch.delenv("ADK_NON_ACTIVE_PERSISTENCE_ENABLED", raising=False)

    result = write_analysis_yaml(
        run_id="run-critique-gate-disabled-1",
        ticker="NFLX",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 2.0,
                        "consistency": 2.0,
                        "actionability": 2.0,
                    }
                },
            },
            "repair": {"status": "ok", "payload": {"notes": "not required when disabled"}},
        },
    )

    assert result["success"] is True
    assert result.get("analysis_status") == "active"

    file_path = Path(str(result.get("file_path", "")))
    if file_path.exists():
        file_path.unlink(missing_ok=True)


def test_draft_critique_repair_flow_blocks_then_allows_with_score_semantics(monkeypatch) -> None:
    """11.1 criterion: draft->critique->repair flow exhibits score-based block/pass semantics."""
    monkeypatch.setenv("ADK_CRITIQUE_SCORE_GATE_ENABLED", "true")
    monkeypatch.setenv("ADK_CRITIQUE_SECTION_MIN_SCORE", "7.0")

    blocked = write_analysis_yaml(
        run_id="run-flow-blocked-1",
        ticker="CRM",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {"summary": {"narrative": "initial draft 100 200"}}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 6.0,
                        "consistency": 8.0,
                        "actionability": 8.0,
                    },
                    "failed_sections": ["evidence"],
                    "failed_section_reasons": {"evidence": "missing numeric derivations"},
                },
            },
            "repair": {
                "status": "ok",
                "payload": {
                    "summary": {"narrative": "repair attempted but critique still below threshold"}
                },
            },
        },
    )
    assert blocked["success"] is False
    assert blocked.get("status") == "blocked_quality"

    blocked_path = Path(str(blocked.get("declined_file_path", "")))
    if blocked_path.exists():
        blocked_path.unlink(missing_ok=True)

    allowed = write_analysis_yaml(
        run_id="run-flow-allowed-1",
        ticker="CRM",
        analysis_type="stock",
        skill_name="stock-analysis",
        payload={
            "draft": {"status": "ok", "payload": {"summary": {"narrative": "draft with 3 5 8"}}},
            "critique": {
                "status": "ok",
                "payload": {
                    "section_scores": {
                        "evidence": 7.1,
                        "consistency": 8.0,
                        "actionability": 8.0,
                    }
                },
            },
            "repair": {
                "status": "ok",
                "payload": {
                    "summary": {"narrative": "fixed with clear numeric support 7 8 9"}
                },
            },
        },
    )
    assert allowed["success"] is True
    assert allowed.get("analysis_status") == "active"

    allowed_path = Path(str(allowed.get("file_path", "")))
    if allowed_path.exists():
        allowed_path.unlink(missing_ok=True)
