"""Tests for skill-native adapter registry and canary gates."""

from __future__ import annotations

import pytest

from adk_runtime.contracts import RequestEnvelope
from adk_runtime.skills.registry import allow_adapter_for_request, get_skill_adapter
from adk_runtime.subagent_invoker import SubagentInvoker


class _NoopGateway:
    def get_route_candidates(self, role_alias: str) -> list[str]:
        _ = role_alias
        return ["openai/gpt-4o-mini"]


def _subagents() -> SubagentInvoker:
    return SubagentInvoker(gateway=_NoopGateway(), enable_litellm=False)  # type: ignore[arg-type]


def _request() -> RequestEnvelope:
    return {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "MSFT",
        "analysis_type": "stock",
        "idempotency_key": "test-1",
        "client_request_id": "req-1",
    }


def test_registry_returns_none_when_skill_native_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_STOCK_ENABLED", "false")
    adapter = get_skill_adapter(skill_name="stock-analysis", subagents=_subagents())
    assert adapter is None


def test_registry_returns_stock_adapter_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_STOCK_ENABLED", "true")
    monkeypatch.setenv("ADK_SKILL_NATIVE_KILL_SWITCH", "false")
    adapter = get_skill_adapter(skill_name="stock-analysis", subagents=_subagents())
    assert adapter is not None
    assert getattr(adapter, "skill_name", None) == "stock-analysis"


def test_kill_switch_disables_adapter_and_canary(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_STOCK_ENABLED", "true")
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "100")
    monkeypatch.setenv("ADK_SKILL_NATIVE_KILL_SWITCH", "true")

    req = _request()
    adapter = get_skill_adapter(skill_name="stock-analysis", subagents=_subagents())
    assert adapter is None
    assert allow_adapter_for_request(request=req, run_id="run-a") is False


def test_canary_gate_honors_zero_and_full(monkeypatch) -> None:
    req = _request()

    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "0")
    assert allow_adapter_for_request(request=req, run_id="run-a") is False

    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "100")
    assert allow_adapter_for_request(request=req, run_id="run-a") is True


def test_canary_gate_is_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "37")
    req = _request()

    first = allow_adapter_for_request(request=req, run_id="run-1")
    second = allow_adapter_for_request(request=req, run_id="run-2")

    assert first == second


def test_canary_stage_enforcement_rejects_invalid_stage(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_STAGE_ENFORCED", "true")
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "37")

    with pytest.raises(RuntimeError, match="must be one of"):
        allow_adapter_for_request(request=_request(), run_id="run-stage-invalid")


def test_canary_stage_enforcement_accepts_valid_stage(monkeypatch) -> None:
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_STAGE_ENFORCED", "true")
    monkeypatch.setenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "25")

    # Should not raise for allowed stage values.
    allow_adapter_for_request(request=_request(), run_id="run-stage-valid")
