"""Skill-native adapter output contracts and prompt-spec loader helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PHASES = ("draft", "critique", "repair", "risk_gate", "summarize")


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
                dq = payload.get("data_quality") if isinstance(payload.get("data_quality"), dict) else {}
                for key in ("price_data_source", "quote_timestamp", "prior_close"):
                    if key not in dq:
                        violations.append(f"stock_draft_missing_data_quality_{key}")
            elif skill_name == "earnings-analysis":
                for key in ("summary", "scoring", "do_nothing_gate"):
                    if key not in payload:
                        violations.append(f"earnings_draft_missing_{key}")

    return sorted(set(violations))
