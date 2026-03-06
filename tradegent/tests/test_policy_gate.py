"""PolicyGate reason-code and enforcement semantics tests (Track D)."""

from adk_runtime.policy_gate import PolicyGate
from adk_runtime.validators import validate_policy_decision


def test_policy_gate_allows_when_no_violations() -> None:
    gate = PolicyGate()
    decision = gate.evaluate("post_validation", {})

    assert decision.get("decision") == "allow"
    validate_policy_decision(decision)


def test_policy_gate_denies_dry_run_execution() -> None:
    gate = PolicyGate()
    decision = gate.evaluate("pre_execution", {"dry_run_mode": True})

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "DRY_RUN_EXECUTION_BLOCKED"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_denies_non_executable_stock_state() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "pre_execution",
        {
            "dry_run_mode": False,
            "stock_state": "analysis",
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "STOCK_STATE_NOT_EXECUTABLE"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_denies_live_execution_mode() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "pre_execution",
        {
            "dry_run_mode": False,
            "stock_state": "paper",
            "execution_mode": "live",
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "LIVE_EXECUTION_DISABLED"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_denies_model_denylist_violation() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "post_validation",
        {
            "model_alias": "reasoning_premium",
            "model_denylist": ["reasoning_premium"],
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "MODEL_DENYLIST_VIOLATION"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_denies_tool_denylist_violation() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "post_validation",
        {
            "tool_name": "place_order",
            "tool_denylist": ["place_order"],
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "TOOL_DENYLIST_VIOLATION"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_denies_budget_cap_exceeded() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "post_validation",
        {
            "budget_spent_usd": 5.01,
            "budget_cap_usd": 5.00,
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "BUDGET_CAP_EXCEEDED"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)


def test_policy_gate_defers_policy_bundle_mismatch_when_enabled() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "post_validation",
        {
            "policy_bundle_version": "2.0.0",
            "expected_policy_bundle_version": "1.0.0",
            "defer_on_bundle_mismatch": True,
        },
    )

    assert decision.get("decision") == "defer"
    assert decision.get("reason_code") == "POLICY_BUNDLE_MISMATCH"
    assert decision.get("enforcement_mode") == "soft_warn"
    validate_policy_decision(decision)


def test_policy_gate_denies_policy_bundle_mismatch_by_default() -> None:
    gate = PolicyGate()
    decision = gate.evaluate(
        "post_validation",
        {
            "policy_bundle_version": "2.0.0",
            "expected_policy_bundle_version": "1.0.0",
        },
    )

    assert decision.get("decision") == "deny"
    assert decision.get("reason_code") == "POLICY_BUNDLE_MISMATCH"
    assert decision.get("enforcement_mode") == "hard_block"
    validate_policy_decision(decision)
