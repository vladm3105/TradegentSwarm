"""Sub-agent invocation skeleton for ADK runtime."""

from __future__ import annotations

import asyncio
import json
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

_STOCK_TOP_LEVEL_KEYS = {
    "ticker",
    "current_price",
    "market_environment",
    "summary",
    "bull_case_analysis",
    "bear_case_analysis",
    "recommendation",
    "alert_levels",
    "liquidity_analysis",
    "sentiment",
}

_EARNINGS_TOP_LEVEL_KEYS = {
    "ticker",
    "summary",
    "scoring",
    "do_nothing_gate",
    "scenarios",
    "preparation",
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
                phase_output = self._run_phase(plan, phase, payload)
                self._validate_phase_output(phase, phase_output)
                outputs[phase] = phase_output
        return outputs

    def _run_phase(self, plan: SkillExecutionPlan, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
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

        llm_result = self._invoke_llm_phase(role_alias, plan, phase, payload)
        parsed_payload = self._parse_json_payload(llm_result.get("content"))
        phase_payload = self._normalize_phase_payload(plan, parsed_payload) or payload
        return {
            "status": "ok",
            "payload": phase_payload,
            "llm": {
                "content": llm_result.get("content", ""),
                "model_alias": llm_result.get("model_alias", role_alias),
                "model": llm_result.get("model", routed_model),
                "provider": llm_result.get("provider", self._provider_from_model(routed_model)),
                "input_tokens": int(llm_result.get("input_tokens", 0)),
                "output_tokens": int(llm_result.get("output_tokens", 0)),
            },
        }

    def _invoke_llm_phase(
        self,
        role_alias: str,
        plan: SkillExecutionPlan,
        phase: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        prompt_payload = self._build_prompt_payload(plan, phase, payload)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a structured sub-agent. Return exactly one JSON object only. "
                    "No markdown, no explanations."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, sort_keys=True),
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
    def _parse_json_payload(raw: Any) -> dict[str, Any] | None:
        if not isinstance(raw, str) or not raw.strip():
            return None

        text = raw.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed

        if "```" in text:
            for block in text.split("```"):
                candidate = block.strip()
                if not candidate:
                    continue
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed

        decoder = json.JSONDecoder()
        for idx, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    @staticmethod
    def _normalize_phase_payload(
        plan: SkillExecutionPlan,
        payload: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None

        skill_name = str(getattr(plan, "skill_name", "") or "")
        allowed_keys = _STOCK_TOP_LEVEL_KEYS if skill_name == "stock-analysis" else _EARNINGS_TOP_LEVEL_KEYS

        def _extract(candidate: Any) -> dict[str, Any] | None:
            if not isinstance(candidate, dict):
                return None
            if any(key in candidate for key in allowed_keys):
                return candidate
            return None

        direct = _extract(payload)
        if direct is not None:
            return direct

        for key in ("analysis", "result", "output", "data"):
            nested = _extract(payload.get(key))
            if nested is not None:
                return nested

        return None

    @staticmethod
    def _build_prompt_payload(plan: SkillExecutionPlan, phase: str, payload: dict[str, Any]) -> dict[str, Any]:
        context = payload.get("context")
        latest_document: dict[str, Any] | None = None
        request_context: dict[str, Any] | None = None
        if isinstance(context, dict):
            nested_payload = context.get("payload")
            if isinstance(nested_payload, dict):
                nested_context = nested_payload.get("context")
                if isinstance(nested_context, dict):
                    request_context = nested_context.get("request") if isinstance(nested_context.get("request"), dict) else None
                    latest_document = (
                        nested_context.get("latest_document")
                        if isinstance(nested_context.get("latest_document"), dict)
                        else None
                    )

        schema_hint: dict[str, Any]
        output_contract: dict[str, Any]
        if str(getattr(plan, "skill_name", "")) == "stock-analysis":
            schema_hint = {
                "current_price": "number (> 0)",
                "summary.thesis": "string (>= 120 chars, no placeholders)",
                "summary.key_levels.entry": "number (> 0)",
                "summary.key_levels.stop": "number (> 0)",
                "summary.key_levels.target_1": "number (> 0)",
                "alert_levels.price_alerts[0].price": "number (> 0)",
                "alert_levels.price_alerts[0].significance": "string (>= 120 chars)",
            }
            output_contract = {
                "top_level_required": sorted(_STOCK_TOP_LEVEL_KEYS),
                "forbidden_top_level": ["task", "phase", "schema_hint", "source_context"],
                "rules": [
                    "Return a single JSON object representing final stock analysis only.",
                    "Do not include the prompt envelope or schema metadata in the output.",
                    "Do not use placeholder wording like 'runtime generated draft analysis'.",
                    "All numeric trading levels must be > 0.",
                ],
            }
        elif str(getattr(plan, "skill_name", "")) == "earnings-analysis":
            schema_hint = {
                "summary": {
                    "thesis": "string",
                    "confidence": "number 0-100",
                },
                "scoring": "object",
                "do_nothing_gate": "object",
            }
            output_contract = {
                "top_level_required": sorted(_EARNINGS_TOP_LEVEL_KEYS),
                "forbidden_top_level": ["task", "phase", "schema_hint", "source_context"],
                "rules": [
                    "Return a single JSON object representing final earnings analysis only.",
                    "Do not include the prompt envelope or schema metadata in the output.",
                ],
            }
        else:
            schema_hint = {"result": "object"}
            output_contract = {
                "top_level_required": ["result"],
                "rules": ["Return a single JSON object only."],
            }

        reference_context: dict[str, Any] | None = latest_document
        if isinstance(reference_context, dict) and "summary" in reference_context:
            summary = reference_context.get("summary")
            if isinstance(summary, dict):
                thesis = str(summary.get("thesis", "")).lower()
                if "runtime generated draft analysis" in thesis or "placeholder" in thesis:
                    reference_context = None

        return {
            "task": "Generate structured analysis JSON for downstream YAML rendering.",
            "phase": phase,
            "skill_name": getattr(plan, "skill_name", None),
            "ticker": payload.get("ticker") or (request_context or {}).get("ticker"),
            "analysis_type": payload.get("analysis_type") or (request_context or {}).get("analysis_type"),
            "intent": payload.get("intent") or (request_context or {}).get("intent"),
            "schema_hint": schema_hint,
            "output_contract": output_contract,
            "source_context": reference_context,
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
