"""Semantic validation of analysis documents before active classification.

Phase B of IPLAN-005: blocking semantic checks applied after schema validation
and before persistence as an active artifact.

Validator functions take a pre-built document dict and return a tuple of
(issues: list[str], reason_codes: list[str]).  Empty issues list means pass.

Deterministic validator order (matches IPLAN-005 Phase B spec):
  1. Data completeness     — handled in side_effects.py
  2. Schema validation     — handled in earnings_contract.py / scripts/validate_analysis.py
  3. Semantic validation   — THIS module (numeric evidence, catalyst, logic consistency)
  4. Logic-consistency     — included here (EV/confidence/R:R vs gate result)
  5. Guardrail validation  — cost/latency (future)
  6. Final classification  — coordinator_agent.py
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PLACEHOLDER_MARKERS = (
    "placeholder",
    "migration",
    "runtime generated draft",
    "draft analysis",
    "pending live enrichment",
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _text_content(value: Any) -> str:
    """Flatten a section value to plain text for evidence counting."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return "\n".join(_text_content(item) for item in value if item is not None)
    if isinstance(value, dict):
        return "\n".join(_text_content(v) for v in value.values())
    return ""


def _contains_placeholder(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _count_numeric_tokens(text: str) -> int:
    """Count tokens that look like meaningful numbers (prices, percentages, counts)."""
    import re

    # Match numbers with optional %, $, x suffixes: 12.5%, $410, 3.2x, 8 etc.
    tokens = re.findall(r"[-+]?\d+(?:\.\d+)?(?:%|\$|x|\b)", text)
    # Filter: exclude year-like 4-digit integers standing alone (e.g. 2024, 2026)
    filtered = [t for t in tokens if not (len(t) == 4 and t.isdigit())]
    return len(filtered)


# ---------------------------------------------------------------------------
# Analysis-type-agnostic checks
# ---------------------------------------------------------------------------


def _check_narrative_evidence_density(
    doc: dict[str, Any],
    *,
    min_numeric_tokens: int = 3,
) -> tuple[list[str], list[str]]:
    """Verify the summary narrative carries at least a minimum number of numeric tokens.

    A summary with fewer than *min_numeric_tokens* distinct numbers is considered
    evidence-poor and classified as a soft/hard fail depending on caller policy.
    """
    issues: list[str] = []
    reason_codes: list[str] = []

    summary = _as_dict(doc.get("summary"))
    narrative_raw = summary.get("narrative") or ""
    if not isinstance(narrative_raw, str):
        narrative_raw = _text_content(narrative_raw)

    if _contains_placeholder(narrative_raw):
        # Placeholder language is already caught by the quality checks; skip
        # numeric-density check for placeholder texts to avoid double-counting.
        return issues, reason_codes

    numeric_count = _count_numeric_tokens(narrative_raw)
    if numeric_count < min_numeric_tokens:
        issues.append(
            f"summary.narrative contains only {numeric_count} numeric token(s); "
            f"minimum {min_numeric_tokens} required for evidence density"
        )
        reason_codes.append("evidence_density_low")

    return issues, reason_codes


def _check_catalyst_count(
    doc: dict[str, Any],
    *,
    min_catalysts: int = 1,
) -> tuple[list[str], list[str]]:
    """Verify the document contains at least *min_catalysts* non-placeholder catalysts.

    Looks for catalysts in common section slots used by both stock and earnings docs.
    """
    issues: list[str] = []
    reason_codes: list[str] = []

    catalyst_texts: list[str] = []

    # Earnings: news_age_check.items[].news_item
    news = _as_dict(doc.get("news_age_check"))
    for item in _as_list(news.get("items")):
        item_dict = _as_dict(item)
        text = _text_content(item_dict.get("news_item"))
        if text:
            catalyst_texts.append(text)

    # Stock: catalysts section (list or dict)
    catalysts_raw = doc.get("catalysts") or doc.get("catalyst_factors")
    if isinstance(catalysts_raw, list):
        for item in catalysts_raw:
            text = _text_content(item)
            if text:
                catalyst_texts.append(text)
    elif isinstance(catalysts_raw, dict):
        for v in catalysts_raw.values():
            text = _text_content(v)
            if text:
                catalyst_texts.append(text)

    # Filter out placeholder catalysts.
    real_catalysts = [t for t in catalyst_texts if not _contains_placeholder(t)]

    if len(real_catalysts) < min_catalysts:
        issues.append(
            f"document contains {len(real_catalysts)} non-placeholder catalyst(s); "
            f"minimum {min_catalysts} required"
        )
        reason_codes.append("catalyst_count_insufficient")

    return issues, reason_codes


# ---------------------------------------------------------------------------
# Earnings-specific semantic checks
# ---------------------------------------------------------------------------


def _check_earnings_gate_logic_consistency(
    doc: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Verify gate result is logically consistent with EV/confidence/R:R values.

    Hard-fail conditions (IPLAN-005 Phase B):
    - Gate result is PASS but none of the three numeric conditions (EV>5%,
      confidence>60%, R:R>2:1) are met.
    - Gate result is FAIL but all three numeric conditions are met.
    """
    issues: list[str] = []
    reason_codes: list[str] = []

    gate = _as_dict(doc.get("do_nothing_gate"))
    gate_result = gate.get("gate_result")
    if not isinstance(gate_result, str):
        return issues, reason_codes

    gate_result = gate_result.strip().upper()

    ev_actual = _number_or_none(gate.get("ev_actual")) or 0.0
    confidence_actual = _number_or_none(gate.get("confidence_actual")) or 0.0
    rr_actual = _number_or_none(gate.get("rr_actual")) or 0.0

    ev_passes = ev_actual > 5.0
    confidence_passes = confidence_actual > 60.0
    rr_passes = rr_actual > 2.0

    passes_count = sum([ev_passes, confidence_passes, rr_passes])

    if gate_result == "PASS" and passes_count == 0:
        issues.append(
            "gate_result=PASS but EV, confidence, and R:R all fail thresholds "
            f"(ev={ev_actual:.1f}%, conf={confidence_actual:.0f}%, rr={rr_actual:.2f})"
        )
        reason_codes.append("gate_result_logic_inconsistent")

    if gate_result == "FAIL" and passes_count == 3:
        issues.append(
            "gate_result=FAIL but EV, confidence, and R:R all pass thresholds "
            f"(ev={ev_actual:.1f}%, conf={confidence_actual:.0f}%, rr={rr_actual:.2f})"
        )
        reason_codes.append("gate_result_logic_inconsistent")

    return issues, reason_codes


def _check_earnings_scenario_consistency(
    doc: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Verify scenario probability sum and individual scenario presence.

    Duplicate of the check in side_effects._earnings_quality_issues but exposed
    here so the semantic validator can be invoked independently of side_effects.
    """
    issues: list[str] = []
    reason_codes: list[str] = []

    scenarios = _as_dict(doc.get("scenarios"))
    required = ("strong_beat", "modest_beat", "modest_miss", "strong_miss")
    probability_sum = 0.0
    scenario_count = 0

    for key in required:
        item = _as_dict(scenarios.get(key))
        prob = _number_or_none(item.get("probability")) or 0.0
        if prob <= 0:
            issues.append(f"scenarios.{key}.probability must be > 0")
            reason_codes.append(f"scenario_probability_missing_{key}")
        else:
            probability_sum += prob
            scenario_count += 1

    if scenario_count == len(required) and abs(probability_sum - 1.0) > 0.02:
        issues.append(
            f"scenario probability sum must be ~1.0 (found {probability_sum:.4f})"
        )
        reason_codes.append("scenario_probability_sum_invalid")

    return issues, reason_codes


# ---------------------------------------------------------------------------
# Stock-specific semantic checks
# ---------------------------------------------------------------------------


def _check_stock_gate_logic_consistency(
    doc: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Verify gate/decision result is consistent with numeric gate values for stock analyses."""
    issues: list[str] = []
    reason_codes: list[str] = []

    gate_info = _as_dict(doc.get("adk_runtime"))
    # Look for gate info under summary.do_nothing_gate (stock v2.7) or directly.
    gate = _as_dict(doc.get("do_nothing_gate"))
    if not gate:
        summary = _as_dict(doc.get("summary"))
        gate = _as_dict(summary.get("do_nothing_gate"))

    gate_result = gate.get("gate_result")
    if not isinstance(gate_result, str):
        return issues, reason_codes

    gate_result = gate_result.strip().upper()
    ev_actual = _number_or_none(gate.get("ev_actual")) or 0.0
    confidence_actual = _number_or_none(gate.get("confidence_actual")) or 0.0
    rr_actual = _number_or_none(gate.get("rr_actual")) or 0.0

    ev_passes = ev_actual > 5.0
    confidence_passes = confidence_actual > 60.0
    rr_passes = rr_actual > 2.0
    passes_count = sum([ev_passes, confidence_passes, rr_passes])

    if gate_result == "PASS" and passes_count == 0:
        issues.append(
            "gate_result=PASS but EV, confidence, and R:R all fail thresholds "
            f"(ev={ev_actual:.1f}%, conf={confidence_actual:.0f}%, rr={rr_actual:.2f})"
        )
        reason_codes.append("gate_result_logic_inconsistent")

    if gate_result == "FAIL" and passes_count == 3:
        issues.append(
            "gate_result=FAIL but EV, confidence, and R:R all pass thresholds "
            f"(ev={ev_actual:.1f}%, conf={confidence_actual:.0f}%, rr={rr_actual:.2f})"
        )
        reason_codes.append("gate_result_logic_inconsistent")

    return issues, reason_codes


# ---------------------------------------------------------------------------
# Unified entry points
# ---------------------------------------------------------------------------

_EARNINGS_HARD_FAIL_CODES = frozenset(
    {
        "scenario_probability_sum_invalid",
        "gate_result_logic_inconsistent",
    }
)

_STOCK_HARD_FAIL_CODES = frozenset(
    {
        "gate_result_logic_inconsistent",
    }
)


def validate_earnings_document_semantics(
    doc: dict[str, Any],
) -> tuple[list[str], list[str], bool]:
    """Run all semantic checks for an earnings-analysis document.

    Returns:
        issues: human-readable failure descriptions
        reason_codes: machine-readable codes (deduplicated, sorted)
        hard_fail: True if any hard-fail condition is triggered
    """
    all_issues: list[str] = []
    all_codes: list[str] = []

    for checker in (
        _check_narrative_evidence_density,
        _check_catalyst_count,
        _check_earnings_scenario_consistency,
        _check_earnings_gate_logic_consistency,
    ):
        issues, codes = checker(doc)
        all_issues.extend(issues)
        all_codes.extend(codes)

    deduped_codes = sorted(set(all_codes))
    hard_fail = any(code in _EARNINGS_HARD_FAIL_CODES for code in deduped_codes)
    return all_issues, deduped_codes, hard_fail


def validate_stock_document_semantics(
    doc: dict[str, Any],
) -> tuple[list[str], list[str], bool]:
    """Run all semantic checks for a stock-analysis document.

    Returns:
        issues: human-readable failure descriptions
        reason_codes: machine-readable codes (deduplicated, sorted)
        hard_fail: True if any hard-fail condition is triggered
    """
    all_issues: list[str] = []
    all_codes: list[str] = []

    for checker in (
        _check_narrative_evidence_density,
        _check_catalyst_count,
        _check_stock_gate_logic_consistency,
    ):
        issues, codes = checker(doc)
        all_issues.extend(issues)
        all_codes.extend(codes)

    deduped_codes = sorted(set(all_codes))
    hard_fail = any(code in _STOCK_HARD_FAIL_CODES for code in deduped_codes)
    return all_issues, deduped_codes, hard_fail
