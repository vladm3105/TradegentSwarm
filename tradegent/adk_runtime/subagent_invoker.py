"""Sub-agent invocation skeleton for ADK runtime."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from .contracts import SkillExecutionPlan
try:
    from tradegent.llm_gateway import LiteLLMGatewayClient
except ImportError:  # pragma: no cover - fallback for local test/import context
    from llm_gateway import LiteLLMGatewayClient


_PHASE_ROLE_ALIAS = {
    "draft": "reasoning_standard",
    "critique": "critic_model",
    "repair": "reasoning_standard",
    "risk_gate": "reasoning_premium",
    "summarize": "summarizer_fast",
}


class SubagentOutputValidationError(RuntimeError):
    """Raised when a sub-agent phase output violates runtime contract."""


class SubagentInvoker:
    """Execute enabled sub-agent phases and return structured outputs."""

    def __init__(
        self,
        gateway: LiteLLMGatewayClient | None = None,
        *,
        enable_litellm: bool | None = None,
    ) -> None:
        if enable_litellm is None:
            enable_litellm = os.getenv("ADK_SUBAGENT_LLM_ENABLED", "false").strip().lower() == "true"
        self.enable_litellm = enable_litellm
        self.gateway = gateway or LiteLLMGatewayClient.from_env()

    def run(self, plan: SkillExecutionPlan, payload: dict[str, Any]) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for phase in plan.phases:
            if phase in {"draft", "critique", "repair", "risk_gate", "summarize"}:
                phase_output = self._run_phase(phase, payload)
                self._validate_phase_output(phase, phase_output)
                outputs[phase] = phase_output
        return outputs

    def _run_phase(self, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        role_alias = _PHASE_ROLE_ALIAS.get(phase, "summarizer_fast")
        candidates = self.gateway.get_route_candidates(role_alias)
        routed_model = candidates[0] if candidates else "unknown"

        # Default behavior remains local/non-LLM unless explicitly enabled.
        if not self.enable_litellm:
            return {
                "status": "ok",
                "payload": payload,
                "routing": {
                    "role_alias": role_alias,
                    "model": routed_model,
                    "provider": self._provider_from_model(routed_model),
                },
            }

        llm_result = self._invoke_llm_phase(role_alias, phase, payload)
        return {
            "status": "ok",
            "payload": payload,
            "llm": {
                "content": llm_result.get("content", ""),
                "model_alias": llm_result.get("model_alias", role_alias),
                "model": llm_result.get("model", routed_model),
                "provider": llm_result.get("provider", self._provider_from_model(routed_model)),
                "input_tokens": int(llm_result.get("input_tokens", 0)),
                "output_tokens": int(llm_result.get("output_tokens", 0)),
            },
        }

    def _invoke_llm_phase(self, role_alias: str, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Keep prompt minimal and deterministic for migration phase.
        messages = [
            {
                "role": "system",
                "content": "You are a structured sub-agent. Return concise JSON.",
            },
            {
                "role": "user",
                "content": f"phase={phase}; payload_keys={sorted(payload.keys())}",
            },
        ]

        async def _call() -> dict[str, Any]:
            res = await self.gateway.chat_json(role_alias=role_alias, messages=messages, temperature=0.1)
            return {
                "content": res.content,
                "model_alias": res.model_alias,
                "model": res.model,
                "provider": res.provider,
                "input_tokens": res.input_tokens,
                "output_tokens": res.output_tokens,
            }

        try:
            # Safe in the current sync orchestrator path.
            return asyncio.run(_call())
        except RuntimeError:
            # If an event loop is already active, avoid nested-loop failure and return route metadata.
            candidates = self.gateway.get_route_candidates(role_alias)
            routed_model = candidates[0] if candidates else "unknown"
            return {
                "content": "",
                "model_alias": role_alias,
                "model": routed_model,
                "provider": self._provider_from_model(routed_model),
                "input_tokens": 0,
                "output_tokens": 0,
            }

    @staticmethod
    def _provider_from_model(model: str) -> str:
        if "/" in model:
            return model.split("/", 1)[0]
        return "unknown"

    @staticmethod
    def _validate_phase_output(phase: str, output: dict[str, Any]) -> None:
        if not isinstance(output, dict):
            raise SubagentOutputValidationError(f"phase={phase}: output must be object")

        status = output.get("status")
        if status != "ok":
            raise SubagentOutputValidationError(f"phase={phase}: status must be 'ok'")

        if not isinstance(output.get("payload"), dict):
            raise SubagentOutputValidationError(f"phase={phase}: payload must be object")

        has_routing = isinstance(output.get("routing"), dict)
        has_llm = isinstance(output.get("llm"), dict)
        if has_routing == has_llm:
            raise SubagentOutputValidationError(
                f"phase={phase}: exactly one of 'routing' or 'llm' is required"
            )

        if has_routing:
            routing = output["routing"]
            if not isinstance(routing.get("role_alias"), str) or not routing.get("role_alias"):
                raise SubagentOutputValidationError(f"phase={phase}: routing.role_alias required")
            if not isinstance(routing.get("model"), str) or not routing.get("model"):
                raise SubagentOutputValidationError(f"phase={phase}: routing.model required")
            if not isinstance(routing.get("provider"), str) or not routing.get("provider"):
                raise SubagentOutputValidationError(f"phase={phase}: routing.provider required")

        if has_llm:
            llm = output["llm"]
            required_text_fields = ("model_alias", "model", "provider")
            for key in required_text_fields:
                if not isinstance(llm.get(key), str) or not llm.get(key):
                    raise SubagentOutputValidationError(f"phase={phase}: llm.{key} required")
            for key in ("input_tokens", "output_tokens"):
                value = llm.get(key)
                if not isinstance(value, int) or value < 0:
                    raise SubagentOutputValidationError(f"phase={phase}: llm.{key} must be non-negative int")
