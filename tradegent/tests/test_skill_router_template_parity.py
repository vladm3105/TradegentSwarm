"""Template parity tests for Wave 1 skill versions.

These tests ensure SkillRouter skill_version tracks the source-of-truth
versions defined in tradegent_knowledge skill templates.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

from adk_runtime.contracts import RequestEnvelope
from adk_runtime.skill_router import SkillRouter


def _expected_semver_from_template(template_path: Path) -> str:
    data = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    raw = data["_meta"]["version"]

    if isinstance(raw, int):
        return f"{raw}.0.0"
    if isinstance(raw, float):
        major = int(raw)
        minor = int(round((raw - major) * 10))
        return f"{major}.{minor}.0"
    token = str(raw).strip()
    if token.count(".") == 2:
        return token
    if token.count(".") == 1:
        return f"{token}.0"
    return f"{token}.0.0"


def test_skill_router_wave1_versions_match_templates() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    router = SkillRouter()

    cases: list[tuple[RequestEnvelope, Path]] = [
        (
            {"intent": "analysis", "analysis_type": "stock"},
            repo_root / "tradegent_knowledge" / "skills" / "stock-analysis" / "template.yaml",
        ),
        (
            {"intent": "analysis", "analysis_type": "earnings"},
            repo_root / "tradegent_knowledge" / "skills" / "earnings-analysis" / "template.yaml",
        ),
        (
            {"intent": "watchlist", "analysis_type": "stock"},
            repo_root / "tradegent_knowledge" / "skills" / "watchlist" / "template.yaml",
        ),
        (
            {"intent": "scan", "analysis_type": "stock"},
            repo_root / "tradegent_knowledge" / "skills" / "market-scanning" / "template.yaml",
        ),
    ]

    for request, template_path in cases:
        plan = router.resolve(request)
        assert template_path.exists(), f"Missing template: {template_path}"
        assert plan.skill_version == _expected_semver_from_template(template_path)
