"""Skill routing skeleton for ADK orchestration."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re

import yaml  # type: ignore[import-untyped]

from .contracts import RequestEnvelope, SkillExecutionPlan


_TEMPLATE_SKILL_ALIAS = {
    "scan": "market-scanning",
}

_VERSIONED_TEMPLATE_RE = re.compile(r"^template\.v(?P<version>\d+\.\d+)\.yaml$")


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


def _version_major_minor(raw_version: object) -> str | None:
    """Normalize version token to major.minor for template selection."""
    if isinstance(raw_version, int):
        return f"{raw_version}.0"
    if isinstance(raw_version, float):
        major = int(raw_version)
        minor = int(round((raw_version - major) * 10))
        return f"{major}.{minor}"
    if isinstance(raw_version, str):
        token = raw_version.strip()
        match = re.fullmatch(r"(\d+)\.(\d+)(?:\.\d+)?", token)
        if match:
            return f"{match.group(1)}.{match.group(2)}"
    return None


def _env_key_for_skill(skill_name: str) -> str:
    normalized = skill_name.replace("-", "_").upper()
    return f"ADK_TEMPLATE_VERSION_{normalized}"


def _requested_template_version(skill_name: str) -> str | None:
    """Resolve requested template major.minor from env.

    Priority:
    1. ADK_TEMPLATE_VERSION_<SKILL_NAME>
    2. ADK_TEMPLATE_VERSION (global)
    """
    per_skill_raw = os.getenv(_env_key_for_skill(skill_name), "").strip()
    if per_skill_raw:
        return _version_major_minor(per_skill_raw)

    global_raw = os.getenv("ADK_TEMPLATE_VERSION", "").strip()
    if global_raw:
        return _version_major_minor(global_raw)

    return None


def _template_major_minor(path: Path) -> str | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        return None
    return _version_major_minor(meta.get("version"))


def _select_template_file(skill_name: str) -> Path:
    """Select the active template file for a skill.

    Resolution order:
    1. Highest semantic version from template.vX.Y.yaml files
    2. Legacy template.yaml fallback
    """
    repo_root = Path(__file__).resolve().parents[2]
    template_skill = _TEMPLATE_SKILL_ALIAS.get(skill_name, skill_name)
    skill_dir = repo_root / "tradegent_knowledge" / "skills" / template_skill

    if not skill_dir.exists():
        return skill_dir / "template.yaml"

    requested = _requested_template_version(skill_name)
    legacy_template = skill_dir / "template.yaml"

    if requested:
        pinned_versioned = skill_dir / f"template.v{requested}.yaml"
        if pinned_versioned.exists():
            return pinned_versioned

        # Backward-compatible path: allow template.yaml to satisfy pinned version.
        if legacy_template.exists() and _template_major_minor(legacy_template) == requested:
            return legacy_template

    candidates: list[tuple[tuple[int, int], Path]] = []
    for path in skill_dir.glob("template.v*.yaml"):
        match = _VERSIONED_TEMPLATE_RE.match(path.name)
        if not match:
            continue
        major, minor = match.group("version").split(".")
        candidates.append(((int(major), int(minor)), path))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    return legacy_template


def _template_skill_version(skill_name: str) -> str:
    template_path = _select_template_file(skill_name)
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


@lru_cache(maxsize=8)
def _build_wave1_skill_plans(
    global_pin: str,
    stock_pin: str,
    earnings_pin: str,
    scan_pin: str,
    watchlist_pin: str,
) -> dict[str, SkillExecutionPlan]:
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


def _wave1_plan_cache_key() -> tuple[str, str, str, str, str]:
    return (
        os.getenv("ADK_TEMPLATE_VERSION", "").strip(),
        os.getenv("ADK_TEMPLATE_VERSION_STOCK_ANALYSIS", "").strip(),
        os.getenv("ADK_TEMPLATE_VERSION_EARNINGS_ANALYSIS", "").strip(),
        os.getenv("ADK_TEMPLATE_VERSION_SCAN", "").strip(),
        os.getenv("ADK_TEMPLATE_VERSION_WATCHLIST", "").strip(),
    )


class SkillRouter:
    """Resolve request intent to a normalized skill execution plan."""

    def resolve(self, request: RequestEnvelope) -> SkillExecutionPlan:
        intent = request.get("intent", "analysis")
        analysis_type = request.get("analysis_type", "stock")
        skill_name = self._resolve_skill_name(intent, analysis_type)
        plans = _build_wave1_skill_plans(*_wave1_plan_cache_key())
        plan = plans.get(skill_name)
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
