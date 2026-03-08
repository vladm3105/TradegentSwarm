"""Tests for ADK request/response envelope validation."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from adk_runtime.coordinator_agent import CoordinatorAgent
from adk_runtime.contracts import RequestEnvelope
from adk_runtime.mcp_tool_bus import MCPToolBus
from adk_runtime.policy_gate import PolicyGate
from adk_runtime.run_state_store import RunStateStore
from adk_runtime.skill_router import SkillRouter
from adk_runtime.subagent_invoker import SubagentInvoker
from adk_runtime.validators import (
    EnvelopeValidationError,
    validate_policy_decision,
    validate_request_envelope,
    validate_response_envelope,
)


@pytest.fixture(autouse=True)
def _disable_benchmark_metrics_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADK_BENCHMARK_METRICS_ENABLED", "false")


class TrackingToolBus(MCPToolBus):
    """Track tool invocations for side-effect assertions."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, tool_name: str, input_payload: dict[str, object], timeout: int = 30) -> dict[str, object]:
        self.calls.append(tool_name)
        return {
            "status": "ok",
            "payload": {"tool_name": tool_name, "input": input_payload, "timeout": timeout},
            "error": None,
            "latency_ms": 0,
        }


class MarkerBlockingRunStateStore(RunStateStore):
    """Reject mutable side-effect markers to simulate replay-safe skip."""

    def claim_side_effect_marker(self, run_id: str, phase: str, marker_key: str) -> bool:
        if phase in {"persist", "index"}:
            return False
        return super().claim_side_effect_marker(run_id, phase, marker_key)


class OrderedCallRunStateStore(RunStateStore):
    """Capture init/dedup method order for coordinator call-sequencing tests."""

    def __init__(self) -> None:
        super().__init__(use_db=False)
        self.calls: list[str] = []

    def init_run(self, run_id: str, **kwargs: object) -> None:
        self.calls.append("init_run")
        super().init_run(run_id, **kwargs)

    def claim_or_get_dedup(self, dedup_key: str, run_id: str) -> tuple[bool, dict[str, object] | None]:
        self.calls.append("claim_or_get_dedup")
        return super().claim_or_get_dedup(dedup_key, run_id)


def _valid_request() -> RequestEnvelope:
    return {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "NVDA",
        "analysis_type": "stock",
        "idempotency_key": "req-123",
    }


def _build_coordinator() -> CoordinatorAgent:
    return CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=MCPToolBus(),
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )


def test_validate_request_envelope_accepts_valid_analysis_request() -> None:
    validate_request_envelope(_valid_request())


def test_validate_request_envelope_rejects_missing_idempotency_key() -> None:
    payload = _valid_request()
    payload.pop("idempotency_key")
    with pytest.raises(EnvelopeValidationError, match="idempotency_key"):
        validate_request_envelope(payload)


def test_validate_request_envelope_rejects_analysis_without_ticker() -> None:
    payload = _valid_request()
    payload.pop("ticker")
    with pytest.raises(EnvelopeValidationError, match="ticker"):
        validate_request_envelope(payload)


def test_validate_policy_decision_rejects_defer_without_reason_code() -> None:
    with pytest.raises(EnvelopeValidationError, match="reason_code"):
        validate_policy_decision(
            {
                "decision": "defer",
                "checkpoint_id": "post_validation",
                "policy_bundle_version": "1.0.0",
                "evaluated_at": "2026-03-05T00:00:00+00:00",
                "enforcement_mode": "soft_warn",
            }
        )


def test_validate_response_envelope_rejects_invalid_status() -> None:
    payload: dict[str, object] = {
        "contract_version": "1.0.0",
        "run_id": "0f4f8665-10f6-48de-ae35-08f7707f0bf5",
        "status": "ok",
        "policy_decisions": [
            {
                "decision": "allow",
                "checkpoint_id": "post_validation",
                "policy_bundle_version": "1.0.0",
                "evaluated_at": "2026-03-05T00:00:00+00:00",
            }
        ],
    }
    with pytest.raises(EnvelopeValidationError, match="Unsupported status"):
        validate_response_envelope(payload)


def test_coordinator_validates_and_returns_contract_valid_response() -> None:
    coordinator = _build_coordinator()
    response = coordinator.handle(_valid_request())

    assert response.get("status") in {"completed", "blocked"}
    assert response.get("contract_version") == "1.0.0"


def test_coordinator_rejects_invalid_intent_before_execution() -> None:
    coordinator = _build_coordinator()
    bad_request = _valid_request()
    bad_request["intent"] = "unsupported"

    with pytest.raises(EnvelopeValidationError, match="Unsupported intent"):
        coordinator.handle(bad_request)


def test_coordinator_returns_dedup_hit_for_duplicate_request() -> None:
    coordinator = _build_coordinator()
    request = _valid_request()

    first = coordinator.handle(request)
    second = coordinator.handle(request)

    assert second.get("dedup_hit") is True
    assert second.get("run_id") == first.get("run_id")


def test_coordinator_initializes_run_before_dedup_claim() -> None:
    state_store = OrderedCallRunStateStore()
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=MCPToolBus(),
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=state_store,
    )

    coordinator.handle(_valid_request())

    assert state_store.calls.index("init_run") < state_store.calls.index("claim_or_get_dedup")


def test_coordinator_executes_mutable_side_effects_once_per_completed_run() -> None:
    tool_bus = TrackingToolBus()
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )

    response = coordinator.handle(_valid_request())

    assert response.get("status") == "completed"
    assert "yaml_write" in response.get("artifacts", {})
    assert "ingest" in response.get("artifacts", {})
    assert tool_bus.calls.count("write_yaml") == 1
    assert tool_bus.calls.count("trigger_ingest") == 1


def test_coordinator_skips_mutable_side_effects_when_markers_already_claimed() -> None:
    tool_bus = TrackingToolBus()
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=MarkerBlockingRunStateStore(use_db=False),
    )

    response = coordinator.handle(_valid_request())

    assert response.get("status") == "completed"
    assert response.get("artifacts", {}) == {}
    assert "write_yaml" not in tool_bus.calls
    assert "trigger_ingest" not in tool_bus.calls


class EarningsContractToolBus(MCPToolBus):
    """Tool bus test double that writes controlled earnings artifacts."""

    def __init__(self, *, file_path: Path, doc: dict[str, object]) -> None:
        self.calls: list[str] = []
        self.file_path = file_path
        self.doc = doc

    def call(self, tool_name: str, input_payload: dict[str, object], timeout: int = 30) -> dict[str, object]:
        self.calls.append(tool_name)
        if tool_name == "context_retrieval":
            return {"status": "ok", "payload": {"context": {"request": input_payload.get("request")}}, "error": None, "latency_ms": 0}

        if tool_name == "write_yaml":
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_path.write_text(yaml.safe_dump(self.doc, sort_keys=False), encoding="utf-8")
            return {
                "status": "ok",
                "payload": {"success": True, "file_path": str(self.file_path)},
                "error": None,
                "latency_ms": 0,
            }

        if tool_name == "trigger_ingest":
            return {"status": "ok", "payload": {"success": True}, "error": None, "latency_ms": 0}

        return {
            "status": "ok",
            "payload": {"tool_name": tool_name, "input": input_payload, "timeout": timeout},
            "error": None,
            "latency_ms": 0,
        }


def _valid_earnings_contract_doc() -> dict[str, object]:
    return {
        "_meta": {"type": "earnings-analysis", "version": 2.6},
        "scoring": {
            "catalyst_score": 5,
            "technical_score": 5,
            "fundamental_score": 5,
            "sentiment_score": 5,
        },
        "do_nothing_gate": {"gate_result": "PASS"},
        "preparation": {"implied_move": {"percentage": 0.0}},
        "scenarios": {
            "strong_beat": {},
            "modest_beat": {},
            "modest_miss": {},
            "strong_miss": {},
        },
        "bull_case_analysis": {"arguments": [{}, {}, {}]},
        "base_case_analysis": {"arguments": [{}, {}, {}]},
        "bear_case_analysis": {"arguments": [{}, {}, {}]},
    }


def test_coordinator_fails_earnings_run_when_contract_invalid_and_skips_ingest(tmp_path: Path) -> None:
    invalid_doc = {
        "_meta": {"type": "earnings-analysis", "version": 2.6},
        "scenarios": {"strong_beat": {}, "modest_beat": {}},
    }
    tool_bus = EarningsContractToolBus(file_path=tmp_path / "bad_earnings.yaml", doc=invalid_doc)
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )
    request: RequestEnvelope = {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "AAPL",
        "analysis_type": "earnings",
        "idempotency_key": "earn-invalid-1",
    }

    response = coordinator.handle(request)

    assert response.get("status") == "failed"
    artifacts = response.get("artifacts", {})
    assert isinstance(artifacts, dict)
    assert "contract_validation" in artifacts
    validation = artifacts["contract_validation"]
    assert isinstance(validation, dict)
    assert validation.get("status") == "error"
    assert "write_yaml" in tool_bus.calls
    assert "trigger_ingest" not in tool_bus.calls


def test_coordinator_completes_earnings_run_when_contract_valid(tmp_path: Path) -> None:
    tool_bus = EarningsContractToolBus(
        file_path=tmp_path / "ok_earnings.yaml",
        doc=_valid_earnings_contract_doc(),
    )
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )
    request: RequestEnvelope = {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "MSFT",
        "analysis_type": "earnings",
        "idempotency_key": "earn-valid-1",
    }

    response = coordinator.handle(request)

    assert response.get("status") == "completed"
    artifacts = response.get("artifacts", {})
    assert isinstance(artifacts, dict)
    validation = artifacts.get("contract_validation")
    assert isinstance(validation, dict)
    assert validation.get("status") == "ok"
    assert "write_yaml" in tool_bus.calls
    assert "trigger_ingest" in tool_bus.calls


class _IntegrationToolBus(MCPToolBus):
    """Integration test bus: real YAML write + fake ingest success."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def call(self, tool_name: str, input_payload: dict[str, object], timeout: int = 30) -> dict[str, object]:
        self.calls.append(tool_name)
        if tool_name == "trigger_ingest":
            return {"status": "ok", "payload": {"success": True}, "error": None, "latency_ms": 0}
        return super().call(tool_name, input_payload, timeout)


class _StructuredSubagent:
    """Sub-agent stub returning realistic phased outputs."""

    def run(self, plan: object, payload: dict[str, object]) -> dict[str, object]:
        _ = plan
        _ = payload
        return {
            "draft": {
                "status": "ok",
                "payload": {
                    "current_price": 201.5,
                    "decision": {
                        "recommendation": "WATCH",
                        "confidence_pct": 69,
                        "rationale": "Integration-path rationale.",
                        "key_insight": "Demand improving into event.",
                    },
                    "bull_case_analysis": {
                        "strength": 8,
                        "arguments": [{"argument": "a"}, {"argument": "b"}, {"argument": "c"}],
                        "summary": "Bull case from integration payload",
                    },
                    "scenarios": {
                        "strong_beat": {"probability": 0.31, "move_pct": 6.8},
                    },
                    "probability": {
                        "base_rate": 0.54,
                        "confidence": "high",
                        "confidence_pct": 69,
                    },
                },
                "routing": {
                    "role_alias": "reasoning_standard",
                    "model": "openai/gpt-4o-mini",
                    "provider": "openai",
                },
            }
        }


class _TelemetrySubagent:
    """Sub-agent stub with explicit llm metadata for telemetry aggregation tests."""

    def run(self, plan: object, payload: dict[str, object]) -> dict[str, object]:
        _ = plan
        _ = payload
        return {
            "draft": {
                "status": "ok",
                "payload": {"current_price": 100},
                "llm": {
                    "content": "{}",
                    "model_alias": "reasoning_standard",
                    "model": "openai/gpt-4o-mini",
                    "provider": "openai",
                    "input_tokens": 11,
                    "output_tokens": 7,
                },
            },
            "critique": {
                "status": "ok",
                "payload": {"ok": True},
                "routing": {
                    "role_alias": "critic_model",
                    "model": "openai/gpt-4.1-mini",
                    "provider": "openai",
                },
            },
        }


def test_coordinator_writes_mapped_earnings_fields_from_subagent_payload() -> None:
    tool_bus = _IntegrationToolBus()
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=_StructuredSubagent(),  # type: ignore[arg-type]
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )
    request: RequestEnvelope = {
        "contract_version": "1.0.0",
        "intent": "analysis",
        "ticker": "CRM",
        "analysis_type": "earnings",
        "idempotency_key": "earn-integration-1",
    }

    response = coordinator.handle(request)

    assert response.get("status") == "completed"
    artifacts = response.get("artifacts", {})
    assert isinstance(artifacts, dict)
    yaml_write = artifacts.get("yaml_write")
    assert isinstance(yaml_write, dict)
    nested = yaml_write.get("payload")
    assert isinstance(nested, dict)
    file_path = nested.get("file_path")
    assert isinstance(file_path, str)

    path = Path(file_path)
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert doc["current_price"] == 201.5
    assert doc["decision"]["recommendation"] == "WATCH"
    assert doc["decision"]["confidence_pct"] == 69
    assert doc["bull_case_analysis"]["strength"] == 8
    assert doc["bull_case_analysis"]["summary"] == "Bull case from integration payload"
    assert doc["scenarios"]["strong_beat"]["probability"] == 0.31
    assert doc["probability"]["base_rate"] == 0.54
    assert doc["probability"]["confidence"] == "high"
    assert doc["probability"]["confidence_pct"] == 69
    assert "trigger_ingest" in tool_bus.calls

    path.unlink(missing_ok=True)


def test_coordinator_includes_aggregated_telemetry_in_response() -> None:
    tool_bus = TrackingToolBus()
    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=tool_bus,
        subagents=_TelemetrySubagent(),  # type: ignore[arg-type]
        policy_gate=PolicyGate(),
        state_store=RunStateStore(use_db=False),
    )

    response = coordinator.handle(_valid_request())

    telemetry = response.get("telemetry")
    assert isinstance(telemetry, dict)
    llm = telemetry.get("llm")
    assert isinstance(llm, dict)
    assert llm.get("input_tokens_total") == 11
    assert llm.get("output_tokens_total") == 7
    assert isinstance(llm.get("estimated_cost_usd"), float)
    assert float(llm["estimated_cost_usd"]) > 0
    assert telemetry.get("providers") == ["openai"]
    models = telemetry.get("models")
    assert isinstance(models, list)
    assert "openai/gpt-4o-mini" in models
    assert isinstance(telemetry.get("duration_ms"), int)
    assert isinstance(telemetry.get("side_effect_latency_ms"), int)
