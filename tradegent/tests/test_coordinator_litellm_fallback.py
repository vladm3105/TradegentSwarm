"""Coordinator-level LiteLLM fallback behavior tests."""

from __future__ import annotations

from typing import Any

from adk_runtime.contracts import RequestEnvelope
from adk_runtime.coordinator_agent import CoordinatorAgent
from adk_runtime.mcp_tool_bus import MCPToolBus
from adk_runtime.policy_gate import PolicyGate
from adk_runtime.run_state_store import RunStateStore
from adk_runtime.skill_router import SkillRouter
from adk_runtime.subagent_invoker import SubagentInvoker
from llm_gateway.client import LiteLLMGatewayClient


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class _FakeResponse:
    def __init__(self, *, content: str, response_id: str = "resp-fallback") -> None:
        self.id = response_id
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage(prompt_tokens=12, completion_tokens=6)


class _NoopSideEffectToolBus(MCPToolBus):
    """Avoid file writes/ingest in this integration test while preserving flow."""

    def call(self, tool_name: str, input_payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        if tool_name in {"write_yaml", "trigger_ingest"}:
            return {
                "status": "ok",
                "payload": {"success": True, "tool_name": tool_name},
                "error": None,
                "latency_ms": 0,
            }
        return super().call(tool_name, input_payload, timeout)


def _request() -> RequestEnvelope:
    return {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "NVDA",
        "analysis_type": "stock",
        "idempotency_key": "coord-fallback-1",
    }


def test_coordinator_uses_litellm_fallback_chain(monkeypatch) -> None:
    calls: list[str] = []

    async def _fake_acompletion(**kwargs):
        model = kwargs["model"]
        calls.append(model)
        if model == "openrouter/fail-model":
            raise RuntimeError("simulated provider outage")
        return _FakeResponse(content='{"ok": true}')

    import llm_gateway.client as client_mod

    monkeypatch.setattr(client_mod.litellm, "acompletion", _fake_acompletion)

    gateway = LiteLLMGatewayClient(
        routes={
            "reasoning_standard": ["openrouter/fail-model", "openai/gpt-4o-mini"],
            "summarizer_fast": ["openai/gpt-4o-mini"],
            "reasoning_premium": ["openai/gpt-4o"],
            "extraction_fast": ["openai/gpt-4o-mini"],
            "critic_model": ["openai/gpt-4o-mini"],
        },
        timeout=10.0,
        max_retries=0,
    )

    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=_NoopSideEffectToolBus(),
        subagents=SubagentInvoker(gateway=gateway, enable_litellm=True),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )

    response = coordinator.handle(_request())

    # first draft attempt fails on openrouter and falls back to openai
    assert calls[0:2] == ["openrouter/fail-model", "openai/gpt-4o-mini"]
    # run completes despite first-provider failure
    assert response.get("status") == "completed"
