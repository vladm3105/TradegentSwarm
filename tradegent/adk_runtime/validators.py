"""Request/response envelope validation for ADK runtime contracts."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from .contracts import PolicyDecision, RequestEnvelope, ResponseEnvelope
from .versioning import parse_semver

ALLOWED_INTENTS = {"analysis", "scan", "watchlist", "journal", "validation"}
ALLOWED_STATUSES = {"completed", "failed", "blocked", "in_progress"}
ALLOWED_POLICY_DECISIONS = {"allow", "deny", "defer"}
ALLOWED_ENFORCEMENT_MODES = {"hard_block", "soft_warn"}


class EnvelopeValidationError(RuntimeError):
    """Raised when a request/response envelope violates runtime contract."""


def _require_non_empty_string(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeValidationError(f"Invalid or missing '{key}'")
    return value.strip()


def validate_request_envelope(request: Mapping[str, object] | RequestEnvelope) -> None:
    """Validate minimum request contract required by CoordinatorAgent."""
    if not isinstance(request, dict):
        raise EnvelopeValidationError("Request must be a mapping")

    if "contract_version" in request:
        parse_semver(_require_non_empty_string(request, "contract_version"))

    intent = _require_non_empty_string(request, "intent")
    if intent not in ALLOWED_INTENTS:
        raise EnvelopeValidationError(
            f"Unsupported intent '{intent}'. Allowed: {sorted(ALLOWED_INTENTS)}"
        )

    _require_non_empty_string(request, "idempotency_key")

    if intent == "analysis":
        _require_non_empty_string(request, "analysis_type")
        _require_non_empty_string(request, "ticker")

    constraints = request.get("constraints")
    if constraints is not None and not isinstance(constraints, dict):
        raise EnvelopeValidationError("'constraints' must be an object when provided")


def validate_policy_decision(decision: Mapping[str, object] | PolicyDecision) -> None:
    """Validate policy decision payload shape and semantic rules."""
    if not isinstance(decision, dict):
        raise EnvelopeValidationError("Policy decision must be a mapping")

    verdict = _require_non_empty_string(decision, "decision")
    if verdict not in ALLOWED_POLICY_DECISIONS:
        raise EnvelopeValidationError(
            f"Unsupported policy decision '{verdict}'. Allowed: {sorted(ALLOWED_POLICY_DECISIONS)}"
        )

    _require_non_empty_string(decision, "checkpoint_id")
    _require_non_empty_string(decision, "policy_bundle_version")
    _require_non_empty_string(decision, "evaluated_at")

    if verdict in {"deny", "defer"}:
        _require_non_empty_string(decision, "reason_code")
        mode = _require_non_empty_string(decision, "enforcement_mode")
        if mode not in ALLOWED_ENFORCEMENT_MODES:
            raise EnvelopeValidationError(
                f"Unsupported enforcement_mode '{mode}'. Allowed: {sorted(ALLOWED_ENFORCEMENT_MODES)}"
            )


def validate_response_envelope(response: Mapping[str, object] | ResponseEnvelope) -> None:
    """Validate response envelope contract returned by CoordinatorAgent."""
    if not isinstance(response, dict):
        raise EnvelopeValidationError("Response must be a mapping")

    parse_semver(_require_non_empty_string(response, "contract_version"))

    run_id = _require_non_empty_string(response, "run_id")
    try:
        UUID(run_id)
    except ValueError as exc:
        raise EnvelopeValidationError("'run_id' must be a valid UUID") from exc

    status = _require_non_empty_string(response, "status")
    if status not in ALLOWED_STATUSES:
        raise EnvelopeValidationError(
            f"Unsupported status '{status}'. Allowed: {sorted(ALLOWED_STATUSES)}"
        )

    policy_decisions = response.get("policy_decisions")
    if not isinstance(policy_decisions, list) or not policy_decisions:
        raise EnvelopeValidationError("'policy_decisions' must be a non-empty array")

    for decision in policy_decisions:
        validate_policy_decision(decision)
