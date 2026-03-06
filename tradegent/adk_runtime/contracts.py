"""Core ADK orchestration contracts (initial skeleton)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict


class RequestEnvelope(TypedDict, total=False):
    contract_version: str
    intent: str
    ticker: str
    analysis_type: str
    constraints: dict[str, Any]
    trace_id: str
    client_request_id: str
    idempotency_key: str


class PolicyDecision(TypedDict, total=False):
    decision: Literal["allow", "deny", "defer"]
    checkpoint_id: str
    reason_code: str
    reason_detail: str
    policy_bundle_version: str
    evaluated_at: str
    enforcement_mode: Literal["hard_block", "soft_warn"]


class ResponseEnvelope(TypedDict, total=False):
    contract_version: str
    run_id: str
    status: Literal["completed", "failed", "blocked", "in_progress"]
    recommendation: str
    gate_result: str
    artifacts: dict[str, Any]
    telemetry: dict[str, Any]
    policy_decisions: list[PolicyDecision]
    dedup_hit: bool


@dataclass(slots=True)
class SkillExecutionPlan:
    skill_name: str
    skill_version: str
    phases: list[str]
    validators: list[str]
    allowed_tools: list[str]
    retry_policy: dict[str, Any]
