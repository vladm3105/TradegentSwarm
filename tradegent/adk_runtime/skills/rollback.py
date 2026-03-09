"""Rollback trigger evaluation for skill-native rollout."""

from __future__ import annotations

from typing import Any


def rollback_reasons(metrics: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    realism_pass_rate = _to_float(metrics.get("realism_pass_rate"))
    critical_defects = _to_int(metrics.get("critical_defects"))
    degraded_rate = _to_float(metrics.get("degraded_rate"))
    timeout_violations = _to_int(metrics.get("timeout_violations"))
    cost_violations = _to_int(metrics.get("cost_violations"))

    if realism_pass_rate is not None and realism_pass_rate < 95.0:
        reasons.append("realism_below_threshold")
    if critical_defects is not None and critical_defects > 0:
        reasons.append("critical_defects_detected")
    if degraded_rate is not None and degraded_rate > 5.0:
        reasons.append("degraded_rate_above_threshold")
    if timeout_violations is not None and timeout_violations > 0:
        reasons.append("timeout_violations_detected")
    if cost_violations is not None and cost_violations > 0:
        reasons.append("cost_violations_detected")

    return reasons


def should_trigger_rollback(metrics: dict[str, Any]) -> bool:
    return bool(rollback_reasons(metrics))


def _to_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
