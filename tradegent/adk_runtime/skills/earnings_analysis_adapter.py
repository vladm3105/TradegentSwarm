"""Earnings-analysis skill-native adapter (initial implementation)."""

from __future__ import annotations

from adk_runtime.contracts import SkillExecutionPlan
from adk_runtime.subagent_invoker import SubagentInvoker

from .base import SkillAdapterContext
from .contracts import load_phase_prompt_specs, validate_skill_phase_outputs


class EarningsAnalysisAdapter:
    """Run earnings-analysis phases with adapter-owned orchestration entry point."""

    skill_name = "earnings-analysis"

    def __init__(self, *, subagents: SubagentInvoker) -> None:
        self._subagents = subagents
        self._prompt_specs = load_phase_prompt_specs(self.skill_name)

    def run(self, ctx: SkillAdapterContext) -> dict[str, Any]:
        payload = _build_phase_input(ctx, prompt_specs=self._prompt_specs)
        outputs = self._subagents.run(ctx.plan, payload)
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
    return str(getattr(plan, "skill_name", "") or "earnings-analysis")
