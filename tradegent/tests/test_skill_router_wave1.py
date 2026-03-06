"""Tests for Wave 1 SkillRouter plan contracts."""

from __future__ import annotations

import re

from adk_runtime.skill_router import SkillRouter


_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_skill_router_returns_stock_analysis_wave1_plan() -> None:
    router = SkillRouter()

    plan = router.resolve({"intent": "analysis", "analysis_type": "stock"})

    assert plan.skill_name == "stock-analysis"
    assert _SEMVER_RE.fullmatch(plan.skill_version)
    assert plan.phases == [
        "retrieval",
        "draft",
        "critique",
        "repair",
        "risk_gate",
        "validate",
        "summarize",
    ]
    assert "stock_v27" in plan.validators


def test_skill_router_returns_earnings_analysis_wave1_plan() -> None:
    router = SkillRouter()

    plan = router.resolve({"intent": "analysis", "analysis_type": "earnings"})

    assert plan.skill_name == "earnings-analysis"
    assert _SEMVER_RE.fullmatch(plan.skill_version)
    assert "earnings_v26" in plan.validators
    assert "risk_gate" in plan.phases


def test_skill_router_returns_scan_and_watchlist_wave1_plans() -> None:
    router = SkillRouter()

    scan_plan = router.resolve({"intent": "scan", "analysis_type": "stock"})
    watchlist_plan = router.resolve({"intent": "watchlist", "analysis_type": "stock"})

    assert scan_plan.skill_name == "scan"
    assert _SEMVER_RE.fullmatch(scan_plan.skill_version)
    assert scan_plan.phases == ["retrieval", "draft", "validate", "summarize"]
    assert scan_plan.retry_policy["max_retries"] == 1

    assert watchlist_plan.skill_name == "watchlist"
    assert _SEMVER_RE.fullmatch(watchlist_plan.skill_version)
    assert watchlist_plan.phases == ["retrieval", "draft", "validate", "summarize"]
    assert watchlist_plan.retry_policy["max_retries"] == 1


def test_skill_router_uses_fallback_for_non_wave1_intent() -> None:
    router = SkillRouter()

    plan = router.resolve({"intent": "journal", "analysis_type": "stock"})

    assert plan.skill_name == "journal"
    assert plan.skill_version == "1.0.0"
    assert plan.validators == ["schema"]
