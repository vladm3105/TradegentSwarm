"""Focused tests for orchestrator AGENT_ENGINE cutover behavior."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest


class _FakeCoordinator:
    def __init__(self, response: dict):
        self._response = response

    def handle(self, _request: dict) -> dict:
        return self._response


def _load_orchestrator_module():
    sys.modules.pop("orchestrator", None)

    if "shared.observability" not in sys.modules:
        shared_obs = types.ModuleType("shared.observability")
        shared_obs.setup_logging = lambda *args, **kwargs: None
        sys.modules["shared.observability"] = shared_obs

    if "structlog" not in sys.modules:
        structlog_stub = types.ModuleType("structlog")
        structlog_stub.get_logger = lambda *args, **kwargs: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        )
        sys.modules["structlog"] = structlog_stub

    return importlib.import_module("orchestrator")


def test_validate_agent_engine_requires_adk_when_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_orchestrator_module()

    monkeypatch.setenv("ADK_REQUIRED", "true")
    monkeypatch.setenv("AGENT_ENGINE", "legacy")

    with pytest.raises(RuntimeError, match="ADK_REQUIRED=true requires AGENT_ENGINE=adk"):
        module.validate_agent_engine()


def test_generate_analysis_output_uses_adk_without_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_orchestrator_module()

    monkeypatch.setattr("orchestrator.validate_agent_engine", lambda: "adk")
    monkeypatch.setattr(
        "orchestrator._run_adk_analysis_generation",
        lambda *args, **kwargs: "adk-output",
    )

    def _unexpected_cli(*args, **kwargs):
        raise AssertionError("call_claude_code must not be called in ADK mode")

    monkeypatch.setattr("orchestrator.call_claude_code", _unexpected_cli)

    result = module._generate_analysis_output(
        db=MagicMock(),
        ticker="NVDA",
        analysis_type=module.AnalysisType.STOCK,
        prompt="analyze",
        allowed_tools="mcp__ib-mcp__*",
        label="ANALYZE-NVDA",
    )

    assert result == "adk-output"


def test_generate_analysis_output_uses_legacy_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_orchestrator_module()

    monkeypatch.setattr("orchestrator.validate_agent_engine", lambda: "legacy")
    monkeypatch.setattr(
        "orchestrator.call_claude_code",
        lambda *args, **kwargs: "legacy-output",
    )

    result = module._generate_analysis_output(
        db=MagicMock(),
        ticker="NVDA",
        analysis_type=module.AnalysisType.STOCK,
        prompt="analyze",
        allowed_tools="mcp__ib-mcp__*",
        label="ANALYZE-NVDA",
    )

    assert result == "legacy-output"


def test_run_adk_analysis_generation_rejects_invalid_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_orchestrator_module()

    monkeypatch.setattr(
        "orchestrator._create_adk_coordinator",
        lambda _db: _FakeCoordinator({"status": "completed"}),
    )

    output = module._run_adk_analysis_generation(
        db=MagicMock(),
        ticker="NVDA",
        analysis_type=module.AnalysisType.STOCK,
        entrypoint="ANALYZE-NVDA",
        prompt="prompt",
        allowed_tools="mcp__ib-mcp__*",
    )

    assert output == ""


def test_run_adk_analysis_generation_returns_legacy_json_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_orchestrator_module()

    artifact = tmp_path / "NVDA_20260306T1200.yaml"
    artifact.write_text(
        "\n".join(
            [
                "recommendation:",
                "  action: BUY",
                "  confidence: 74",
                "do_nothing_gate:",
                "  gate_result: PASS",
                "  expected_value_actual: 9.5",
            ]
        ),
        encoding="utf-8",
    )

    valid_response = {
        "contract_version": "1.0.0",
        "run_id": "ccf44a12-89f1-4bd6-b493-0f3473d21d13",
        "status": "completed",
        "artifacts": {
            "yaml_write": {
                "payload": {
                    "file_path": str(artifact),
                }
            }
        },
        "telemetry": {},
        "policy_decisions": [
            {
                "decision": "allow",
                "checkpoint_id": "post_validation",
                "policy_bundle_version": "1.0.0",
                "evaluated_at": "2026-03-06T12:00:00+00:00",
            }
        ],
    }

    monkeypatch.setattr(
        "orchestrator._create_adk_coordinator",
        lambda _db: _FakeCoordinator(valid_response),
    )

    output = module._run_adk_analysis_generation(
        db=MagicMock(),
        ticker="NVDA",
        analysis_type=module.AnalysisType.STOCK,
        entrypoint="ANALYZE-NVDA",
        prompt="prompt",
        allowed_tools="mcp__ib-mcp__*",
    )

    parsed = module.parse_json_block(output)
    assert parsed is not None
    assert parsed["gate_passed"] is True
    assert parsed["recommendation"] == "BUY"
    assert parsed["confidence"] == 74
    assert parsed["expected_value_pct"] == 9.5
