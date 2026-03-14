"""Run state persistence skeleton for ADK orchestration."""

from __future__ import annotations

import logging
from hashlib import sha256
import json
from typing import Any

try:
    from tradegent.db_layer import NexusDB
except ImportError:  # run directly from tradegent/ dir
    from db_layer import NexusDB  # type: ignore[no-redef]


_ALLOWED_TRANSITIONS = {
    "requested": {"planned"},
    "planned": {"retrieval_done"},
    "retrieval_done": {"draft_done"},
    "draft_done": {"critique_done", "validated"},
    "critique_done": {"validated"},
    "validated": {"completed", "failed", "blocked"},
}

log = logging.getLogger("tradegent.adk_runtime.run_state_store")


class RunStateStore:
    """Run-state store with DB persistence and in-memory fallback."""

    def __init__(self, db: NexusDB | None = None, *, use_db: bool = True) -> None:
        self._db = db
        self._db_enabled = use_db
        self._db_failed = False
        self._states: dict[str, str] = {}
        self._events: list[dict[str, Any]] = []
        self._dedup: dict[str, dict[str, Any]] = {}
        self._side_effect_markers: set[tuple[str, str, str]] = set()

    @staticmethod
    def build_dedup_key(request: dict[str, Any], routing_policy_version: str = "1.0.0") -> str:
        """Build stable dedup key from canonical request identity fields."""
        base = {
            "intent": request.get("intent"),
            "ticker": request.get("ticker"),
            "analysis_type": request.get("analysis_type"),
            "idempotency_key": request.get("idempotency_key"),
            "routing_policy_version": routing_policy_version,
        }
        canonical = json.dumps(base, sort_keys=True, separators=(",", ":"))
        return sha256(canonical.encode("utf-8")).hexdigest()

    def _ensure_db(self) -> bool:
        if not self._db_enabled or self._db_failed:
            return False

        if self._db is None:
            self._db = NexusDB()

        try:
            if getattr(self._db, "_conn", None) is None and hasattr(self._db, "connect"):
                self._db.connect()
            return True
        except Exception as exc:
            self._db_failed = True
            log.warning("run_state_store.db_unavailable_fallback_memory: error=%s", str(exc))
            return False

    def init_run(
        self,
        run_id: str,
        *,
        parent_run_id: str | None = None,
        intent: str | None = None,
        ticker: str | None = None,
        analysis_type: str | None = None,
        contract_version: str | None = None,
        routing_policy_version: str | None = None,
        effective_config_hash: str | None = None,
    ) -> None:
        self._states[run_id] = "requested"

        if not self._ensure_db():
            return

        try:
            assert self._db is not None
            self._db.create_run_state_run(
                run_id,
                status="requested",
                parent_run_id=parent_run_id,
                intent=intent,
                ticker=ticker,
                analysis_type=analysis_type,
                contract_version=contract_version,
                routing_policy_version=routing_policy_version,
                effective_config_hash=effective_config_hash,
            )
        except Exception as exc:
            self._db_failed = True
            log.warning(
                "run_state_store.create_run_failed_fallback_memory: run_id=%s error=%s",
                run_id,
                str(exc),
            )

    def transition(
        self,
        run_id: str,
        to_state: str,
        phase: str,
        *,
        event_type: str = "state_transition",
        event_payload: dict[str, Any] | None = None,
        policy_decisions: list[dict[str, Any]] | None = None,
    ) -> None:
        from_state = self._states.get(run_id)
        if from_state is None:
            raise ValueError(f"Unknown run_id: {run_id}")
        if to_state not in _ALLOWED_TRANSITIONS.get(from_state, set()):
            raise ValueError(f"Invalid transition {from_state}->{to_state}")
        self._states[run_id] = to_state
        self._events.append(
            {
                "run_id": run_id,
                "from_state": from_state,
                "to_state": to_state,
                "phase": phase,
                "event_type": event_type,
                "event_payload": event_payload,
                "policy_decisions": policy_decisions,
            }
        )

        if not self._ensure_db():
            return

        try:
            assert self._db is not None
            self._db.append_run_state_event(
                run_id,
                from_state=from_state,
                to_state=to_state,
                phase=phase,
                event_type=event_type,
                event_payload=event_payload,
                policy_decisions=policy_decisions,
            )
        except Exception as exc:
            self._db_failed = True
            log.warning(
                "run_state_store.append_event_failed_fallback_memory: run_id=%s from=%s to=%s error=%s",
                run_id,
                from_state,
                to_state,
                str(exc),
            )

    def current_state(self, run_id: str) -> str:
        return self._states[run_id]

    def claim_or_get_dedup(self, dedup_key: str, run_id: str) -> tuple[bool, dict[str, Any] | None]:
        """Claim dedup key for a new run or return existing dedup record."""
        existing = self._dedup.get(dedup_key)
        if existing is not None:
            return False, existing

        if not self._ensure_db():
            self._dedup[dedup_key] = {"run_id": run_id, "status": "in_progress", "response_json": None}
            return True, None

        try:
            assert self._db is not None
            db_existing = self._db.get_run_dedup(dedup_key)
            if db_existing is not None:
                return False, db_existing

            # Ensure FK target exists before dedup claim insert.
            self._db.create_run_state_run(run_id, status="requested")

            claimed = self._db.claim_run_dedup(dedup_key, run_id)
            if claimed:
                return True, None

            db_existing = self._db.get_run_dedup(dedup_key)
            return False, db_existing
        except Exception as exc:
            self._db_failed = True
            log.warning("run_state_store.dedup_claim_failed_fallback_memory: error=%s", str(exc))
            self._dedup[dedup_key] = {"run_id": run_id, "status": "in_progress", "response_json": None}
            return True, None

    def finalize_dedup(self, dedup_key: str, status: str, response: dict[str, Any]) -> None:
        """Persist dedup result for replay-safe response reuse."""
        self._dedup[dedup_key] = {"run_id": response.get("run_id"), "status": status, "response_json": response}

        if not self._ensure_db():
            return

        try:
            assert self._db is not None
            self._db.finalize_run_dedup(dedup_key, status=status, response=response)
        except Exception as exc:
            self._db_failed = True
            log.warning("run_state_store.dedup_finalize_failed_fallback_memory: error=%s", str(exc))

    def claim_side_effect_marker(self, run_id: str, phase: str, marker_key: str) -> bool:
        """Claim side-effect marker to prevent duplicate effect execution on replay."""
        marker = (run_id, phase, marker_key)
        if marker in self._side_effect_markers:
            return False

        if not self._ensure_db():
            self._side_effect_markers.add(marker)
            return True

        try:
            assert self._db is not None
            inserted = self._db.claim_run_side_effect_marker(run_id, phase, marker_key)
            if inserted:
                self._side_effect_markers.add(marker)
            return inserted
        except Exception as exc:
            self._db_failed = True
            log.warning("run_state_store.side_effect_claim_failed_fallback_memory: error=%s", str(exc))
            self._side_effect_markers.add(marker)
            return True
