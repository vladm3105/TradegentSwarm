"""Rollback trigger logic tests for skill-native rollout."""

from __future__ import annotations

from adk_runtime.skills.rollback import rollback_reasons, should_trigger_rollback


def test_rollback_not_triggered_when_metrics_healthy() -> None:
    metrics = {
        "realism_pass_rate": 97.0,
        "critical_defects": 0,
        "degraded_rate": 2.0,
        "timeout_violations": 0,
        "cost_violations": 0,
    }
    assert should_trigger_rollback(metrics) is False
    assert rollback_reasons(metrics) == []


def test_rollback_triggered_with_multiple_failures() -> None:
    metrics = {
        "realism_pass_rate": 90.0,
        "critical_defects": 1,
        "degraded_rate": 8.0,
        "timeout_violations": 2,
        "cost_violations": 1,
    }
    reasons = rollback_reasons(metrics)
    assert should_trigger_rollback(metrics) is True
    assert "realism_below_threshold" in reasons
    assert "critical_defects_detected" in reasons
    assert "degraded_rate_above_threshold" in reasons
    assert "timeout_violations_detected" in reasons
    assert "cost_violations_detected" in reasons
