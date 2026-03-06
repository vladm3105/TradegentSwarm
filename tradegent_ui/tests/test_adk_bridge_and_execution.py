"""Tests for ADK bridge request shaping and BaseAgent ADK execution path."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from tradegent_ui.agent.adk_bridge import (
    _build_request_envelope,
    _extract_debug_metadata,
    _extract_yaml_file_path,
    _normalize_analysis_type,
)
from tradegent_ui.agent.analysis_agent import AnalysisAgent
from tradegent_ui.agent.context_manager import ConversationContext
from tradegent_ui.agent.base_agent import BaseAgent
from tradegent_ui.agent.tool_mappings import MCPServer, ToolMapping


class _DummyAgent(BaseAgent):
    """Minimal concrete agent for testing BaseAgent internals."""

    async def process(self, query, tickers, context):  # pragma: no cover - not used in tests
        raise NotImplementedError


def test_normalize_analysis_type_variants() -> None:
    assert _normalize_analysis_type("earnings") == "earnings"
    assert _normalize_analysis_type("EARN") == "earnings"
    assert _normalize_analysis_type("stock") == "stock"
    assert _normalize_analysis_type("") == "stock"


def test_build_request_envelope_uses_canonical_fields() -> None:
    envelope = _build_request_envelope(
        session_id="Session-1",
        query="Analyze NVDA earnings",
        ticker="nvda",
        analysis_type="EARNINGS",
    )

    assert envelope["contract_version"] == "1.0.0"
    assert envelope["intent"] == "analysis"
    assert envelope["ticker"] == "NVDA"
    assert envelope["analysis_type"] == "earnings"
    assert isinstance(envelope["idempotency_key"], str)
    assert len(envelope["idempotency_key"]) == 64


def test_extract_yaml_file_path_from_artifacts() -> None:
    artifacts = {"yaml_write": {"payload": {"file_path": "/tmp/NVDA.yaml"}}}
    assert _extract_yaml_file_path(artifacts) == "/tmp/NVDA.yaml"
    assert _extract_yaml_file_path({}) is None


def test_extract_debug_metadata_from_response_telemetry() -> None:
    metadata = _extract_debug_metadata(
        {
            "run_id": "run-abc",
            "status": "completed",
            "policy_decisions": [{"decision": "allow"}],
            "telemetry": {
                "duration_ms": 321,
                "providers": ["openai"],
                "models": ["openai/gpt-4o-mini"],
                "llm": {
                    "input_tokens_total": 12,
                    "output_tokens_total": 5,
                    "estimated_cost_usd": None,
                },
            },
        },
        ui_bridge_latency_ms=12.4,
    )

    assert metadata["run_id"] == "run-abc"
    assert metadata["provider"] == "openai"
    assert metadata["model"] == "openai/gpt-4o-mini"
    assert metadata["input_tokens"] == 12
    assert metadata["output_tokens"] == 5
    assert metadata["latency_ms"] == 321
    assert metadata["ui_bridge_latency_ms"] == 12.4


def test_base_agent_routes_tradegent_analyze_to_adk_bridge(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_ENGINE", "adk")

    def _fake_run_adk_analysis_from_ui(**kwargs):
        assert kwargs["session_id"] == "session-42"
        assert kwargs["query"] == "analyze NVDA"
        assert kwargs["ticker"] == "NVDA"
        assert kwargs["analysis_type"] == "earnings"
        return {
            "status": "completed",
            "ticker": "NVDA",
            "analysis_type": "earnings",
            "run_id": "run-1",
            "artifacts": {},
        }

    monkeypatch.setattr(
        "tradegent_ui.agent.adk_bridge.run_adk_analysis_from_ui",
        _fake_run_adk_analysis_from_ui,
    )

    agent = _DummyAgent("analysis")
    mapping = ToolMapping(
        server=MCPServer.SUBPROCESS,
        mcp_tool="tradegent_analyze",
        description="test",
        params_map={},
    )

    response = asyncio.run(
        agent._execute_subprocess(
            mapping,
            {
                "ticker": "NVDA",
                "type": "earnings",
                "query": "analyze NVDA",
                "session_id": "session-42",
            },
        )
    )

    assert response.success is True
    assert response.result is not None
    assert response.result["status"] == "completed"


def test_analysis_agent_propagates_debug_metadata_from_tool_results() -> None:
    agent = AnalysisAgent()
    context = ConversationContext(session_id="session-1")

    async def _fake_execute_tool(tool_name, params):
        _ = tool_name
        _ = params

        class _Resp:
            success = True
            result = {
                "status": "completed",
                "debug_metadata": {
                    "run_id": "run-123",
                    "provider": "openai",
                    "model": "openai/gpt-4o-mini",
                    "input_tokens": 10,
                    "output_tokens": 3,
                    "latency_ms": 100,
                },
            }
            error = None

        return _Resp()

    agent.execute_tool = AsyncMock(side_effect=_fake_execute_tool)  # type: ignore[method-assign]
    agent.generate_response = AsyncMock(return_value={"text": "ok", "components": []})  # type: ignore[method-assign]

    response = asyncio.run(agent.process("analyze NVDA", ["NVDA"], context))

    assert response.success is True
    assert isinstance(response.debug_metadata, dict)
    assert response.debug_metadata["run_id"] == "run-123"
