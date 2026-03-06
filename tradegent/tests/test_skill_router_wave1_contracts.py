"""Contract tests for Wave 1 SkillRouter plans.

These lock exact phase/validator/tool profiles to prevent silent drift.
"""

from __future__ import annotations

from adk_runtime.skill_router import SkillRouter


def test_wave1_plan_contracts_are_stable() -> None:
    router = SkillRouter()

    cases = {
        ("analysis", "stock"): {
            "skill": "stock-analysis",
            "phases": ["retrieval", "draft", "critique", "repair", "risk_gate", "validate", "summarize"],
            "validators": ["schema", "stock_v27", "gate"],
            "retries": 2,
        },
        ("analysis", "earnings"): {
            "skill": "earnings-analysis",
            "phases": ["retrieval", "draft", "critique", "repair", "risk_gate", "validate", "summarize"],
            "validators": ["schema", "earnings_v26", "gate"],
            "retries": 2,
        },
        ("scan", "stock"): {
            "skill": "scan",
            "phases": ["retrieval", "draft", "validate", "summarize"],
            "validators": ["schema", "scan_contract"],
            "retries": 1,
        },
        ("watchlist", "stock"): {
            "skill": "watchlist",
            "phases": ["retrieval", "draft", "validate", "summarize"],
            "validators": ["schema", "watchlist_contract"],
            "retries": 1,
        },
    }

    for (intent, analysis_type), expected in cases.items():
        plan = router.resolve({"intent": intent, "analysis_type": analysis_type})
        assert plan.skill_name == expected["skill"]
        assert plan.phases == expected["phases"]
        assert plan.validators == expected["validators"]
        assert plan.allowed_tools == ["context_retrieval", "write_yaml", "trigger_ingest"]
        assert plan.retry_policy["max_retries"] == expected["retries"]
