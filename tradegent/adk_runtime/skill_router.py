"""Skill routing skeleton for ADK orchestration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from .contracts import RequestEnvelope, SkillExecutionPlan


_TEMPLATE_SKILL_ALIAS = {
    "scan": "market-scanning",
}


def _version_to_semver(raw_version: object) -> str:
    if isinstance(raw_version, int):
        return f"{raw_version}.0.0"
    if isinstance(raw_version, float):
        major = int(raw_version)
        minor = int(round((raw_version - major) * 10))
        return f"{major}.{minor}.0"
    if isinstance(raw_version, str):
        token = raw_version.strip()
        if token.count(".") == 2:
            return token
        if token.count(".") == 1:
            return f"{token}.0"
        if token.isdigit():
            return f"{token}.0.0"
    return "1.0.0"


@lru_cache(maxsize=16)
def _template_skill_version(skill_name: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    template_skill = _TEMPLATE_SKILL_ALIAS.get(skill_name, skill_name)
    template_path = repo_root / "tradegent_knowledge" / "skills" / template_skill / "template.yaml"
    if not template_path.exists():
        return "1.0.0"

    try:
        data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    except Exception:
        return "1.0.0"

    if not isinstance(data, dict):
        return "1.0.0"
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        return "1.0.0"

    return _version_to_semver(meta.get("version"))


def _build_wave1_skill_plans() -> dict[str, SkillExecutionPlan]:
    return {
    "stock-analysis": SkillExecutionPlan(
        skill_name="stock-analysis",
        skill_version=_template_skill_version("stock-analysis"),
        phases=["retrieval", "draft", "critique", "repair", "risk_gate", "validate", "summarize"],
        validators=["schema", "stock_v27", "gate"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 2},
    ),
    "earnings-analysis": SkillExecutionPlan(
        skill_name="earnings-analysis",
        skill_version=_template_skill_version("earnings-analysis"),
        phases=["retrieval", "draft", "critique", "repair", "risk_gate", "validate", "summarize"],
        validators=["schema", "earnings_v26", "gate"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 2},
    ),
    "scan": SkillExecutionPlan(
        skill_name="scan",
        skill_version=_template_skill_version("scan"),
        phases=["retrieval", "draft", "validate", "summarize"],
        validators=["schema", "scan_contract"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 1},
    ),
    "watchlist": SkillExecutionPlan(
        skill_name="watchlist",
        skill_version=_template_skill_version("watchlist"),
        phases=["retrieval", "draft", "validate", "summarize"],
        validators=["schema", "watchlist_contract"],
        allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
        retry_policy={"max_retries": 1},
    ),
    }


_WAVE1_SKILL_PLANS: dict[str, SkillExecutionPlan] = _build_wave1_skill_plans()


class SkillRouter:
    """Resolve request intent to a normalized skill execution plan."""

    def resolve(self, request: RequestEnvelope) -> SkillExecutionPlan:
        intent = request.get("intent", "analysis")
        analysis_type = request.get("analysis_type", "stock")
        skill_name = self._resolve_skill_name(intent, analysis_type)
        plan = _WAVE1_SKILL_PLANS.get(skill_name)
        if plan is not None:
            return plan

        # Fallback plan for non-wave-1 skills during migration.
        return SkillExecutionPlan(
            skill_name=skill_name,
            skill_version="1.0.0",
            phases=["retrieval", "draft", "validate", "summarize"],
            validators=["schema"],
            allowed_tools=["context_retrieval", "write_yaml", "trigger_ingest"],
            retry_policy={"max_retries": 1},
        )

    @staticmethod
    def _resolve_skill_name(intent: str, analysis_type: str) -> str:
        analysis_token = str(analysis_type).strip().lower()
        if intent == "analysis" and analysis_token == "earnings":
            return "earnings-analysis"
        if intent == "analysis":
            return "stock-analysis"
        return intent
