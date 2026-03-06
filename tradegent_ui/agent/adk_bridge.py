"""Bridge from tradegent_ui agents to Tradegent ADK Coordinator envelopes."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any, TYPE_CHECKING, cast

import yaml  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from tradegent.adk_runtime.contracts import RequestEnvelope, ResponseEnvelope


def _normalize_analysis_type(analysis_type: str) -> str:
    token = (analysis_type or "stock").strip().lower()
    return "earnings" if token.startswith("earn") else "stock"


def _build_idempotency_key(
    *,
    session_id: str,
    ticker: str,
    analysis_type: str,
    query: str,
) -> str:
    base = "|".join(
        [
            session_id.strip().lower(),
            ticker.strip().upper(),
            _normalize_analysis_type(analysis_type),
            query.strip().lower(),
        ]
    )
    return sha256(base.encode("utf-8")).hexdigest()


def _extract_yaml_file_path(response_artifacts: dict[str, Any]) -> str | None:
    yaml_write = response_artifacts.get("yaml_write")
    if not isinstance(yaml_write, dict):
        return None

    payload = yaml_write.get("payload")
    if not isinstance(payload, dict):
        return None

    file_path = payload.get("file_path")
    return file_path if isinstance(file_path, str) and file_path else None


def _extract_debug_metadata(response: "ResponseEnvelope", *, ui_bridge_latency_ms: float) -> dict[str, Any]:
    telemetry = response.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}

    llm = telemetry.get("llm")
    if not isinstance(llm, dict):
        llm = {}

    providers = telemetry.get("providers")
    models = telemetry.get("models")
    if not isinstance(providers, list):
        providers = []
    if not isinstance(models, list):
        models = []

    return {
        "run_id": response.get("run_id"),
        "status": response.get("status"),
        "provider": providers[0] if providers else None,
        "providers": providers,
        "model": models[0] if models else None,
        "models": models,
        "input_tokens": int(llm.get("input_tokens_total", 0) or 0),
        "output_tokens": int(llm.get("output_tokens_total", 0) or 0),
        "cost_usd": llm.get("estimated_cost_usd"),
        "latency_ms": int(telemetry.get("duration_ms", 0) or 0),
        "ui_bridge_latency_ms": round(float(ui_bridge_latency_ms), 2),
        "policy_decisions": response.get("policy_decisions", []),
    }


def _build_request_envelope(
    *,
    session_id: str,
    query: str,
    ticker: str,
    analysis_type: str,
    contract_version: str = "1.0.0",
) -> dict[str, Any]:
    normalized_type = _normalize_analysis_type(analysis_type)
    return {
        "contract_version": contract_version,
        "intent": "analysis",
        "ticker": ticker.strip().upper(),
        "analysis_type": normalized_type,
        "idempotency_key": _build_idempotency_key(
            session_id=session_id,
            ticker=ticker,
            analysis_type=normalized_type,
            query=query,
        ),
    }


def run_adk_analysis_from_ui(
    *,
    session_id: str,
    query: str,
    ticker: str,
    analysis_type: str,
    contract_version: str = "1.0.0",
) -> dict[str, Any]:
    """Run analysis via ADK Coordinator and return UI-friendly result payload."""
    import time

    started = time.perf_counter()
    from tradegent.adk_runtime.coordinator_agent import CoordinatorAgent
    from tradegent.adk_runtime.mcp_tool_bus import MCPToolBus
    from tradegent.adk_runtime.policy_gate import PolicyGate
    from tradegent.adk_runtime.run_state_store import RunStateStore
    from tradegent.adk_runtime.skill_router import SkillRouter
    from tradegent.adk_runtime.subagent_invoker import SubagentInvoker

    request = cast(
        "RequestEnvelope",
        _build_request_envelope(
        session_id=session_id,
        query=query,
        ticker=ticker,
        analysis_type=analysis_type,
        contract_version=contract_version,
        ),
    )

    coordinator = CoordinatorAgent(
        router=SkillRouter(),
        tool_bus=MCPToolBus(),
        subagents=SubagentInvoker(),
        policy_gate=PolicyGate(),
        state_store=RunStateStore(),
    )
    response = coordinator.handle(request)
    bridge_duration_ms = (time.perf_counter() - started) * 1000

    artifacts = response.get("artifacts", {}) if isinstance(response, dict) else {}
    if not isinstance(artifacts, dict):
        artifacts = {}

    result: dict[str, Any] = {
        "status": response.get("status", "failed"),
        "ticker": ticker.strip().upper(),
        "analysis_type": _normalize_analysis_type(analysis_type),
        "run_id": response.get("run_id"),
        "policy_decisions": response.get("policy_decisions", []),
        "artifacts": artifacts,
        "telemetry": response.get("telemetry", {}),
    }
    result["debug_metadata"] = _extract_debug_metadata(response, ui_bridge_latency_ms=bridge_duration_ms)

    file_path = _extract_yaml_file_path(artifacts)
    if file_path:
        result["file_path"] = file_path
        path = Path(file_path)
        if path.exists():
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            except Exception:
                doc = None

            if isinstance(doc, dict):
                gate = doc.get("do_nothing_gate")
                if isinstance(gate, dict):
                    result["gate_result"] = gate.get("gate_result")

                recommendation = doc.get("recommendation")
                if isinstance(recommendation, dict):
                    result["recommendation"] = recommendation.get("action")

                decision = doc.get("decision")
                if isinstance(decision, dict) and "recommendation" in decision:
                    result["recommendation"] = decision.get("recommendation")

    return result
