"""Stock-analysis skill-native adapter (initial implementation)."""

from __future__ import annotations

from typing import Any

from ..contracts import SkillExecutionPlan
from ..subagent_invoker import SubagentInvoker

from .base import SkillAdapterContext
from .contracts import load_phase_prompt_specs, validate_skill_phase_outputs


class StockAnalysisAdapter:
    """Run stock-analysis phases with adapter-owned orchestration entry point."""

    skill_name = "stock-analysis"

    def __init__(self, *, subagents: SubagentInvoker) -> None:
        self._subagents = subagents
        self._prompt_specs = load_phase_prompt_specs(self.skill_name)

    def run(self, ctx: SkillAdapterContext) -> dict[str, Any]:
        payload = _build_phase_input(ctx, prompt_specs=self._prompt_specs)
        outputs = self._subagents.run(ctx.plan, payload)
        _inject_market_data_defaults(outputs=outputs, retrieval_context=ctx.retrieval_context)
        violations = validate_skill_phase_outputs(skill_name=self.skill_name, outputs=outputs)
        if violations:
            outputs["adapter_contract"] = {
                "status": "violations",
                "violations": violations,
            }
        else:
            outputs["adapter_contract"] = {
                "status": "ok",
                "violations": [],
            }
        return outputs


def _build_phase_input(ctx: SkillAdapterContext, *, prompt_specs: dict[str, str]) -> dict[str, Any]:
    request = ctx.request
    return {
        "context": ctx.retrieval_context,
        "ticker": request.get("ticker"),
        "analysis_type": request.get("analysis_type"),
        "intent": request.get("intent"),
        "skill_name": _skill_name(ctx.plan),
        "phase_prompt_specs": prompt_specs,
    }


def _skill_name(plan: SkillExecutionPlan) -> str:
    return str(getattr(plan, "skill_name", "") or "stock-analysis")


def _inject_market_data_defaults(*, outputs: dict[str, Any], retrieval_context: dict[str, Any]) -> None:
    """Ensure stock draft payload contains authoritative live data_quality fields."""
    if not isinstance(outputs, dict):
        return

    draft = outputs.get("draft")
    if not isinstance(draft, dict):
        return
    payload = draft.get("payload")
    if not isinstance(payload, dict):
        return

    context_obj: dict[str, Any] | None = None
    if isinstance(retrieval_context, dict):
        direct_context = retrieval_context.get("context")
        if isinstance(direct_context, dict):
            context_obj = direct_context
        payload_wrapper = retrieval_context.get("payload")
        if context_obj is None and isinstance(payload_wrapper, dict):
            nested_context = payload_wrapper.get("context")
            if isinstance(nested_context, dict):
                context_obj = nested_context
    if not isinstance(context_obj, dict):
        return
    market_data = context_obj.get("market_data")
    if not isinstance(market_data, dict):
        return

    dq = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}

    live_source = market_data.get("price_data_source")
    if isinstance(live_source, str) and live_source.strip().lower() in {"ib_gateway", "ib_mcp"}:
        dq["price_data_source"] = live_source.strip().lower()

    live_ts = market_data.get("quote_timestamp")
    if isinstance(live_ts, str) and live_ts.strip():
        dq["quote_timestamp"] = live_ts.strip()

    live_close = market_data.get("prior_close")
    if isinstance(live_close, (int, float)) and float(live_close) > 0:
        dq["prior_close"] = float(live_close)

    live_verified = market_data.get("price_data_verified")
    if isinstance(live_verified, bool):
        dq["price_data_verified"] = live_verified

    payload["data_quality"] = dq

    live_price = market_data.get("current_price")
    if isinstance(live_price, (int, float)) and float(live_price) > 0:
        payload["current_price"] = float(live_price)
