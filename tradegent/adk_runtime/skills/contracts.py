"""Skill-native adapter output contracts and prompt-spec loader helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PHASES = ("draft", "critique", "repair", "risk_gate", "summarize")
_CRITIQUE_MIN_SCORE = 7.0

ANALYSIS_ACTIVE_STATUS = "active"
ANALYSIS_INACTIVE_STATUSES = (
    "inactive_quality_failed",
    "inactive_data_unavailable",
    "inactive_schema_failed",
)
ANALYSIS_FAILURE_CODES = (
    "DATA_INCOMPLETE",
    "PLACEHOLDER_CONTENT",
    "SCHEMA_INVALID",
    "LOGIC_INCONSISTENT",
    "COST_GUARDRAIL_EXCEEDED",
    "LATENCY_GUARDRAIL_EXCEEDED",
)


def load_phase_prompt_specs(skill_name: str) -> dict[str, str]:
    root = Path(__file__).resolve().parents[1] / "prompts" / skill_name
    specs: dict[str, str] = {}
    for phase in _PHASES:
        path = root / f"{phase}.md"
        if path.exists():
            specs[phase] = path.read_text(encoding="utf-8").strip()
    return specs


def validate_skill_phase_outputs(*, skill_name: str, outputs: dict[str, Any]) -> list[str]:
    """Return contract violations for phase outputs."""
    violations: list[str] = []
    if not isinstance(outputs, dict) or not outputs:
        return ["phase_outputs_missing"]

    for phase in _PHASES:
        phase_obj = outputs.get(phase)
        if not isinstance(phase_obj, dict):
            violations.append(f"{phase}_missing")
            continue
        payload = phase_obj.get("payload")
        if not isinstance(payload, dict):
            violations.append(f"{phase}_payload_missing")

    draft = outputs.get("draft")
    if isinstance(draft, dict):
        payload = draft.get("payload")
        if isinstance(payload, dict):
            if skill_name == "stock-analysis":
                for key in ("summary", "recommendation", "alert_levels", "data_quality"):
                    if key not in payload:
                        violations.append(f"stock_draft_missing_{key}")
                dq_raw = payload.get("data_quality")
                dq: dict[str, Any] = dq_raw if isinstance(dq_raw, dict) else {}
                for key in ("price_data_source", "quote_timestamp", "prior_close"):
                    if key not in dq:
                        violations.append(f"stock_draft_missing_data_quality_{key}")
            elif skill_name == "earnings-analysis":
                for key in ("summary", "scoring", "do_nothing_gate"):
                    if key not in payload:
                        violations.append(f"earnings_draft_missing_{key}")

    critique = outputs.get("critique")
    if isinstance(critique, dict):
        critique_payload = critique.get("payload")
        if isinstance(critique_payload, dict):
            section_scores_raw = critique_payload.get("section_scores")
            if section_scores_raw is None:
                violations.append("critique_payload_missing_section_scores")
            elif not isinstance(section_scores_raw, dict):
                violations.append("critique_section_scores_not_mapping")
            else:
                if not section_scores_raw:
                    violations.append("critique_section_scores_empty")

                low_score_sections: list[str] = []
                for section, score in section_scores_raw.items():
                    if not isinstance(score, (int, float)):
                        violations.append(
                            f"critique_section_score_non_numeric_{str(section).strip() or 'unknown'}"
                        )
                        continue
                    if float(score) < _CRITIQUE_MIN_SCORE:
                        low_score_sections.append(str(section))

                failed_sections_raw = critique_payload.get("failed_sections")
                if low_score_sections and not isinstance(failed_sections_raw, list):
                    violations.append("critique_missing_failed_sections")
                elif isinstance(failed_sections_raw, list):
                    failed_sections = {str(item) for item in failed_sections_raw if str(item).strip()}
                    for section in low_score_sections:
                        if section not in failed_sections:
                            violations.append(f"critique_failed_section_missing_{section}")

                failed_reasons_raw = critique_payload.get("failed_section_reasons")
                if low_score_sections and not isinstance(failed_reasons_raw, dict):
                    violations.append("critique_missing_failed_section_reasons")
                elif isinstance(failed_reasons_raw, dict):
                    for section in low_score_sections:
                        reason = failed_reasons_raw.get(section)
                        if not isinstance(reason, str) or not reason.strip():
                            violations.append(f"critique_failed_reason_missing_{section}")

    return sorted(set(violations))
