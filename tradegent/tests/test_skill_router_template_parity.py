"""Template parity tests for Wave 1 skill versions.

These tests ensure SkillRouter skill_version tracks the source-of-truth
versions defined in tradegent_knowledge skill templates.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from adk_runtime.contracts import RequestEnvelope
from adk_runtime.skill_router import SkillRouter, _select_template_file


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
    router = SkillRouter()

    cases: list[tuple[RequestEnvelope, str]] = [
        (
            {"intent": "analysis", "analysis_type": "stock"},
            "stock-analysis",
        ),
        (
            {"intent": "analysis", "analysis_type": "earnings"},
            "earnings-analysis",
        ),
        (
            {"intent": "watchlist", "analysis_type": "stock"},
            "watchlist",
        ),
        (
            {"intent": "scan", "analysis_type": "stock"},
            "scan",
        ),
    ]

    for request, skill_name in cases:
        plan = router.resolve(request)
        template_path = _select_template_file(skill_name)
        assert template_path.exists(), f"Missing template: {template_path}"
        assert plan.skill_version == _expected_semver_from_template(template_path)


def test_select_template_file_prefers_latest_versioned_stock_template() -> None:
    selected = _select_template_file("stock-analysis")
    assert selected.name == "template.v2.8.yaml"


def test_select_template_file_prefers_latest_versioned_earnings_template() -> None:
    selected = _select_template_file("earnings-analysis")
    assert selected.name == "template.v2.8.yaml"


@pytest.mark.usefixtures("monkeypatch")
def test_select_template_file_honors_earnings_pin_to_legacy_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADK_TEMPLATE_VERSION_EARNINGS_ANALYSIS", "2.6")
    selected = _select_template_file("earnings-analysis")
    assert selected.name == "template.yaml"


@pytest.mark.usefixtures("monkeypatch")
def test_select_template_file_honors_global_pin_for_earnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADK_TEMPLATE_VERSION", "2.8")
    selected = _select_template_file("earnings-analysis")
    assert selected.name == "template.v2.8.yaml"
