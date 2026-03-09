"""Skill-native adapter contracts for ADK runtime orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from adk_runtime.contracts import RequestEnvelope, SkillExecutionPlan


@dataclass(slots=True)
class SkillAdapterContext:
    """Execution context passed to skill adapters."""

    run_id: str
    request: RequestEnvelope
    plan: SkillExecutionPlan
    retrieval_context: dict[str, Any]


class SkillAdapter(Protocol):
    """Protocol for skill-native adapter implementations."""

    skill_name: str

    def run(self, ctx: SkillAdapterContext) -> dict[str, Any]:
        """Execute adapter flow and return phase-keyed payload compatible with side effects."""
        ...
