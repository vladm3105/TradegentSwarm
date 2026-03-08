"""Tests for SubagentInvoker LiteLLM routing and output validation."""

from __future__ import annotations

import pytest

from adk_runtime.contracts import SkillExecutionPlan
from adk_runtime.subagent_invoker import SubagentInvoker, SubagentOutputValidationError


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_route_candidates(self, role_alias: str) -> list[str]:
        if role_alias == "critic_model":
            return ["openrouter/critic-a", "openai/gpt-4o-mini"]
        return ["openai/gpt-4o-mini"]

    async def chat_json(
        self,
        *,
        role_alias: str,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
    ):
        _ = messages
        _ = temperature
        self.calls.append(role_alias)

        class _Resp:
            content = '{"ok": true}'
            model_alias = role_alias
            model = "openai/gpt-4o-mini"
            provider = "openai"
            input_tokens = 10
            output_tokens = 4

        return _Resp()


def _plan() -> SkillExecutionPlan:
    return SkillExecutionPlan(
        skill_name="stock-analysis",
        skill_version="1.0.0",
        phases=["draft", "critique", "summarize"],
        validators=["schema"],
        allowed_tools=[],
        retry_policy={"max_retries": 2},
    )


def test_subagent_invoker_reports_route_metadata_when_litellm_disabled() -> None:
    invoker = SubagentInvoker(gateway=FakeGateway(), enable_litellm=False)  # type: ignore[arg-type]

    outputs = invoker.run(_plan(), {"context": {"a": 1}})

    assert outputs["draft"]["status"] == "ok"
    assert outputs["draft"]["routing"]["role_alias"] == "reasoning_standard"
    assert outputs["draft"]["routing"]["model"] == "openai/gpt-4o-mini"
    assert outputs["critique"]["routing"]["role_alias"] == "critic_model"
    assert outputs["critique"]["routing"]["model"] == "openrouter/critic-a"


def test_subagent_invoker_calls_gateway_when_litellm_enabled() -> None:
    gateway = FakeGateway()
    invoker = SubagentInvoker(gateway=gateway, enable_litellm=True)  # type: ignore[arg-type]

    outputs = invoker.run(_plan(), {"context": {"a": 1}})

    assert gateway.calls == ["reasoning_standard", "critic_model", "summarizer_fast"]
    assert outputs["critique"]["llm"]["model_alias"] == "critic_model"
    assert outputs["critique"]["llm"]["model"] == "openai/gpt-4o-mini"


def test_subagent_invoker_invalid_routing_output_raises() -> None:
    class BadInvoker(SubagentInvoker):
        def _run_phase(
            self,
            plan: SkillExecutionPlan,
            phase: str,
            payload: dict[str, object],
        ) -> dict[str, object]:
            _ = plan
            _ = phase
            return {
                "status": "ok",
                "payload": payload,
                "routing": {
                    "role_alias": "",
                    "model": "gpt-5-mini",
                    "provider": "openai",
                },
            }

    invoker = BadInvoker(gateway=FakeGateway(), enable_litellm=False)  # type: ignore[arg-type]

    with pytest.raises(SubagentOutputValidationError):
        invoker.run(_plan(), {"ticker": "AAPL"})


def test_subagent_invoker_invalid_llm_output_raises() -> None:
    class BadInvoker(SubagentInvoker):
        def _run_phase(
            self,
            plan: SkillExecutionPlan,
            phase: str,
            payload: dict[str, object],
        ) -> dict[str, object]:
            _ = plan
            _ = phase
            return {
                "status": "ok",
                "payload": payload,
                "llm": {
                    "content": "ok",
                    "model_alias": "summarizer_fast",
                    "model": "",
                    "provider": "openai",
                    "input_tokens": -1,
                    "output_tokens": 2,
                },
            }

    invoker = BadInvoker(gateway=FakeGateway(), enable_litellm=True)  # type: ignore[arg-type]

    with pytest.raises(SubagentOutputValidationError):
        invoker.run(_plan(), {"ticker": "AAPL"})


def test_subagent_invoker_promotes_llm_json_to_payload() -> None:
    class StructuredGateway(FakeGateway):
        async def chat_json(
            self,
            *,
            role_alias: str,
            messages: list[dict[str, str]],
            temperature: float = 0.1,
        ):
            _ = messages
            _ = temperature
            self.calls.append(role_alias)

            class _Resp:
                content = (
                    '{"current_price": 123.45, "summary": {"thesis": "Long-form thesis text with concrete setup details and no placeholders."}}'
                )
                model_alias = role_alias
                model = "openai/gpt-4o-mini"
                provider = "openai"
                input_tokens = 20
                output_tokens = 12

            return _Resp()

    gateway = StructuredGateway()
    invoker = SubagentInvoker(gateway=gateway, enable_litellm=True)  # type: ignore[arg-type]

    outputs = invoker.run(_plan(), {"ticker": "AAPL", "analysis_type": "stock"})

    assert outputs["draft"]["payload"]["current_price"] == 123.45
    assert "thesis" in outputs["draft"]["payload"]["summary"]


def test_subagent_invoker_extracts_nested_analysis_payload() -> None:
    class WrappedGateway(FakeGateway):
        async def chat_json(
            self,
            *,
            role_alias: str,
            messages: list[dict[str, str]],
            temperature: float = 0.1,
        ):
            _ = messages
            _ = temperature
            self.calls.append(role_alias)

            class _Resp:
                content = (
                    '{"task": "ignored", "analysis": {"current_price": 222.0, "summary": {"thesis": "Concrete thesis with enough detail to avoid placeholders and provide trading context."}, "alert_levels": {"price_alerts": [{"price": 221.0, "condition": "below", "significance": "Detailed significant alert description that exceeds minimum length and provides actionable monitoring context."}]}}}'
                )
                model_alias = role_alias
                model = "openai/gpt-4o-mini"
                provider = "openai"
                input_tokens = 22
                output_tokens = 13

            return _Resp()

    gateway = WrappedGateway()
    invoker = SubagentInvoker(gateway=gateway, enable_litellm=True)  # type: ignore[arg-type]

    outputs = invoker.run(_plan(), {"ticker": "AAPL", "analysis_type": "stock"})

    assert outputs["draft"]["payload"]["current_price"] == 222.0
    assert "analysis" not in outputs["draft"]["payload"]
