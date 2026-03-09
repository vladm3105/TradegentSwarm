Critique the draft earnings analysis for missing v2.6 requirements, weak scenario logic, and gate inconsistency.
Return structured issues and corrected payload keys.

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
    """Return contract violations for phase outputs.

    This validator is intentionally strict on shape but shallow on semantics,
    leaving domain-depth checks to schema validation and quality gates.
    """
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
                for key in ("summary", "recommendation", "alert_levels"):
                    if key not in payload:
                        violations.append(f"stock_draft_missing_{key}")
            elif skill_name == "earnings-analysis":
                for key in ("summary", "scoring", "do_nothing_gate"):
                    if key not in payload:
                        violations.append(f"earnings_draft_missing_{key}")

    return sorted(set(violations))
