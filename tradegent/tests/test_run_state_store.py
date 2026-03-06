"""Tests for RunStateStore DB persistence behavior and fallback."""

from __future__ import annotations

import uuid

from adk_runtime.run_state_store import RunStateStore


class FakeRunStateDB:
    """In-memory fake DB adapter for run state persistence tests."""

    def __init__(self) -> None:
        self.runs: list[dict] = []
        self.events: list[dict] = []

    def create_run_state_run(self, run_id: str, status: str = "requested", **kwargs) -> bool:
        self.runs.append({"run_id": run_id, "status": status, **kwargs})
        return True

    def append_run_state_event(self, run_id: str, **kwargs) -> int:
        self.events.append({"run_id": run_id, **kwargs})
        return len(self.events)


class FailingRunStateDB:
    """Fake DB adapter that fails on write calls to trigger fallback."""

    def create_run_state_run(self, run_id: str, status: str = "requested", **kwargs) -> bool:
        raise RuntimeError("db unavailable")

    def append_run_state_event(self, run_id: str, **kwargs) -> int:
        raise RuntimeError("db unavailable")


def test_run_state_store_persists_run_and_events_when_db_available() -> None:
    fake_db = FakeRunStateDB()
    store = RunStateStore(db=fake_db, use_db=True)
    run_id = str(uuid.uuid4())

    store.init_run(run_id, intent="analysis", ticker="NVDA", analysis_type="stock")
    store.transition(run_id, "planned", phase="plan")

    assert store.current_state(run_id) == "planned"
    assert len(fake_db.runs) == 1
    assert fake_db.runs[0]["run_id"] == run_id
    assert len(fake_db.events) == 1
    assert fake_db.events[0]["from_state"] == "requested"
    assert fake_db.events[0]["to_state"] == "planned"


def test_run_state_store_falls_back_to_memory_when_db_fails() -> None:
    store = RunStateStore(db=FailingRunStateDB(), use_db=True)
    run_id = str(uuid.uuid4())

    store.init_run(run_id)
    store.transition(run_id, "planned", phase="plan")

    assert store.current_state(run_id) == "planned"


def test_run_state_store_rejects_invalid_transition() -> None:
    store = RunStateStore(use_db=False)
    run_id = str(uuid.uuid4())

    store.init_run(run_id)

    try:
        store.transition(run_id, "validated", phase="validate")
        assert False, "Expected invalid transition to raise"
    except ValueError as exc:
        assert "Invalid transition requested->validated" in str(exc)


def test_run_state_store_dedup_claim_and_finalize_memory_mode() -> None:
    store = RunStateStore(use_db=False)
    run_id = str(uuid.uuid4())
    request = {
        "intent": "analysis",
        "ticker": "NVDA",
        "analysis_type": "stock",
        "idempotency_key": "req-123",
    }

    dedup_key = store.build_dedup_key(request)
    claimed, existing = store.claim_or_get_dedup(dedup_key, run_id)
    assert claimed is True
    assert existing is None

    response = {
        "contract_version": "1.0.0",
        "run_id": run_id,
        "status": "completed",
        "policy_decisions": [
            {
                "decision": "allow",
                "checkpoint_id": "post_validation",
                "policy_bundle_version": "1.0.0",
                "evaluated_at": "2026-03-05T00:00:00+00:00",
            }
        ],
    }
    store.finalize_dedup(dedup_key, "completed", response)

    claimed_again, existing_again = store.claim_or_get_dedup(dedup_key, str(uuid.uuid4()))
    assert claimed_again is False
    assert existing_again is not None
    assert existing_again["status"] == "completed"


def test_run_state_store_side_effect_marker_is_idempotent() -> None:
    store = RunStateStore(use_db=False)
    run_id = str(uuid.uuid4())

    first = store.claim_side_effect_marker(run_id, "draft", "subagent_invocation")
    second = store.claim_side_effect_marker(run_id, "draft", "subagent_invocation")

    assert first is True
    assert second is False
