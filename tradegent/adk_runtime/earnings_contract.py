"""Earnings analysis v2.6 contract checks used during ADK migration.

This module intentionally validates a narrow, high-signal subset of fields that
must stay stable during Track H migration.
"""

from __future__ import annotations

from typing import Any


_REQUIRED_SCENARIOS = {"strong_beat", "modest_beat", "modest_miss", "strong_miss"}
_REQUIRED_SCORING_FIELDS = {
    "catalyst_score",
    "technical_score",
    "fundamental_score",
    "sentiment_score",
}


def validate_earnings_v26_contract(doc: dict[str, Any]) -> list[str]:
    """Return a list of contract violations for earnings-analysis outputs."""
    errors: list[str] = []

    meta = doc.get("_meta")
    if not isinstance(meta, dict):
        errors.append("Missing _meta")
    else:
        if meta.get("type") != "earnings-analysis":
            errors.append("_meta.type must be 'earnings-analysis'")
        try:
            version = float(meta.get("version", 0))
        except (TypeError, ValueError):
            version = 0
        if version < 2.6:
            errors.append("_meta.version must be >= 2.6")

    scoring = doc.get("scoring")
    if not isinstance(scoring, dict):
        errors.append("Missing scoring section")
    else:
        missing_scoring = _REQUIRED_SCORING_FIELDS - set(scoring.keys())
        if missing_scoring:
            errors.append(f"scoring missing fields: {sorted(missing_scoring)}")

    if not isinstance(doc.get("do_nothing_gate"), dict):
        errors.append("Missing root do_nothing_gate section")

    preparation = doc.get("preparation")
    if not isinstance(preparation, dict):
        errors.append("Missing preparation section")
    else:
        implied_move = preparation.get("implied_move")
        if not isinstance(implied_move, dict):
            errors.append("Missing preparation.implied_move section")

    scenarios = doc.get("scenarios")
    if not isinstance(scenarios, dict):
        errors.append("Missing scenarios section")
    else:
        missing = _REQUIRED_SCENARIOS - set(scenarios.keys())
        if missing:
            errors.append(f"scenarios missing required names: {sorted(missing)}")

    for section_name in ("bull_case_analysis", "base_case_analysis", "bear_case_analysis"):
        section = doc.get(section_name)
        if not isinstance(section, dict):
            errors.append(f"Missing {section_name} section")
            continue
        arguments = section.get("arguments", [])
        if not isinstance(arguments, list) or len(arguments) < 3:
            errors.append(f"{section_name}.arguments must contain at least 3 items")

    return errors
