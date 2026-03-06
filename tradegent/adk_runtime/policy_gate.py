"""Policy gate skeleton for ADK orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import PolicyDecision


class PolicyGate:
    """Evaluate policy checkpoints and return normalized decisions."""

    def evaluate(self, checkpoint_id: str, context: dict[str, Any]) -> PolicyDecision:
        bundle_version = str(context.get("policy_bundle_version", "1.0.0"))
        expected_bundle_version = str(context.get("expected_policy_bundle_version", bundle_version))

        # Contract drift on policy bundle can be either deferred (soft) or denied (hard).
        if bundle_version != expected_bundle_version:
            if bool(context.get("defer_on_bundle_mismatch", False)):
                return self._decision(
                    checkpoint_id,
                    decision="defer",
                    policy_bundle_version=bundle_version,
                    reason_code="POLICY_BUNDLE_MISMATCH",
                    reason_detail=(
                        f"policy_bundle_version={bundle_version} expected={expected_bundle_version}"
                    ),
                    enforcement_mode="soft_warn",
                )
            return self._decision(
                checkpoint_id,
                decision="deny",
                policy_bundle_version=bundle_version,
                reason_code="POLICY_BUNDLE_MISMATCH",
                reason_detail=f"policy_bundle_version={bundle_version} expected={expected_bundle_version}",
                enforcement_mode="hard_block",
            )

        dry_run_mode = bool(context.get("dry_run_mode", False))
        execution_requested = self._is_execution_checkpoint(checkpoint_id) or bool(
            context.get("execution_requested", False)
        )
        if execution_requested and dry_run_mode:
            return self._decision(
                checkpoint_id,
                decision="deny",
                policy_bundle_version=bundle_version,
                reason_code="DRY_RUN_EXECUTION_BLOCKED",
                reason_detail="Execution is not allowed while dry_run_mode=true",
                enforcement_mode="hard_block",
            )

        if execution_requested:
            stock_state = str(context.get("stock_state", "analysis")).strip().lower()
            if stock_state not in {"paper", "live"}:
                return self._decision(
                    checkpoint_id,
                    decision="deny",
                    policy_bundle_version=bundle_version,
                    reason_code="STOCK_STATE_NOT_EXECUTABLE",
                    reason_detail=f"stock_state={stock_state}",
                    enforcement_mode="hard_block",
                )

            execution_mode = str(context.get("execution_mode", "paper")).strip().lower()
            if execution_mode == "live":
                return self._decision(
                    checkpoint_id,
                    decision="deny",
                    policy_bundle_version=bundle_version,
                    reason_code="LIVE_EXECUTION_DISABLED",
                    reason_detail="Live execution remains disabled by policy",
                    enforcement_mode="hard_block",
                )

        model_alias = context.get("model_alias")
        model_denylist = context.get("model_denylist", [])
        if model_alias and isinstance(model_denylist, list) and str(model_alias) in {
            str(m) for m in model_denylist
        }:
            return self._decision(
                checkpoint_id,
                decision="deny",
                policy_bundle_version=bundle_version,
                reason_code="MODEL_DENYLIST_VIOLATION",
                reason_detail=f"model_alias={model_alias}",
                enforcement_mode="hard_block",
            )

        tool_name = context.get("tool_name")
        tool_denylist = context.get("tool_denylist", [])
        if tool_name and isinstance(tool_denylist, list) and str(tool_name) in {
            str(t) for t in tool_denylist
        }:
            return self._decision(
                checkpoint_id,
                decision="deny",
                policy_bundle_version=bundle_version,
                reason_code="TOOL_DENYLIST_VIOLATION",
                reason_detail=f"tool_name={tool_name}",
                enforcement_mode="hard_block",
            )

        budget_spent = float(context.get("budget_spent_usd", 0.0) or 0.0)
        budget_cap = float(context.get("budget_cap_usd", 0.0) or 0.0)
        if budget_cap > 0 and budget_spent > budget_cap:
            return self._decision(
                checkpoint_id,
                decision="deny",
                policy_bundle_version=bundle_version,
                reason_code="BUDGET_CAP_EXCEEDED",
                reason_detail=f"budget_spent_usd={budget_spent:.4f} budget_cap_usd={budget_cap:.4f}",
                enforcement_mode="hard_block",
            )

        return self._decision(
            checkpoint_id,
            decision="allow",
            policy_bundle_version=bundle_version,
        )

    @staticmethod
    def _is_execution_checkpoint(checkpoint_id: str) -> bool:
        token = checkpoint_id.strip().lower()
        return token in {"pre_execution", "execution", "order_execution"}

    @staticmethod
    def _decision(
        checkpoint_id: str,
        *,
        decision: str,
        policy_bundle_version: str,
        reason_code: str | None = None,
        reason_detail: str | None = None,
        enforcement_mode: str | None = None,
    ) -> PolicyDecision:
        payload: PolicyDecision = {
            "decision": decision,  # type: ignore[typeddict-item]
            "checkpoint_id": checkpoint_id,
            "policy_bundle_version": policy_bundle_version,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }
        if reason_code is not None:
            payload["reason_code"] = reason_code
        if reason_detail is not None:
            payload["reason_detail"] = reason_detail
        if enforcement_mode is not None:
            payload["enforcement_mode"] = enforcement_mode  # type: ignore[typeddict-item]
        return payload
