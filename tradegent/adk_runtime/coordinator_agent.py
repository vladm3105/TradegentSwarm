"""Coordinator agent skeleton for ADK orchestration."""

from __future__ import annotations

import json
import os
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, cast

import yaml  # type: ignore[import-untyped]

from .contracts import RequestEnvelope, ResponseEnvelope
from .earnings_contract import validate_earnings_v26_contract
from .mcp_tool_bus import MCPToolBus
from .policy_gate import PolicyGate
from .run_state_store import RunStateStore
from .skill_router import SkillRouter
from .skills import (
    SkillAdapterContext,
    allow_adapter_for_request,
    get_skill_adapter,
    run_skill_adapter,
)
from .subagent_invoker import SubagentInvoker
from .validators import validate_request_envelope, validate_response_envelope
from .versioning import ensure_compatible_contract_version

CURRENT_CONTRACT_VERSION = "1.0.0"
_KNOWLEDGE_FAILURE_DIR = Path("/opt/data/tradegent_swarm/tradegent_knowledge/knowledge/analysis/failures")

# USD per 1M tokens for known benchmark models (input, output).
_TOKEN_PRICING_PER_M: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "openai/gpt-4o": (5.00, 15.00),
    "openrouter/openai/gpt-4o-mini": (0.15, 0.60),
    "openrouter/openai/gpt-4.1-mini": (0.40, 1.60),
    "openrouter/openai/gpt-4o": (5.00, 15.00),
}


class CoordinatorAgent:
    """Orchestrate request lifecycle via router, tool bus, sub-agents, policy, and state store."""

    def __init__(
        self,
        router: SkillRouter,
        tool_bus: MCPToolBus,
        subagents: SubagentInvoker,
        policy_gate: PolicyGate,
        state_store: RunStateStore,
    ) -> None:
        self.router = router
        self.tool_bus = tool_bus
        self.subagents = subagents
        self.policy_gate = policy_gate
        self.state_store = state_store

    def handle(self, request: RequestEnvelope) -> ResponseEnvelope:
        started = time.perf_counter()
        validate_request_envelope(request)
        request_contract_version = request.get("contract_version", CURRENT_CONTRACT_VERSION)
        ensure_compatible_contract_version(request_contract_version, CURRENT_CONTRACT_VERSION)

        run_id = str(uuid.uuid4())
        self.state_store.init_run(
            run_id,
            intent=request.get("intent"),
            ticker=request.get("ticker"),
            analysis_type=request.get("analysis_type"),
            contract_version=request_contract_version,
            routing_policy_version="1.0.0",
        )

        dedup_key = self.state_store.build_dedup_key(dict(request), routing_policy_version="1.0.0")
        claimed, existing = self.state_store.claim_or_get_dedup(dedup_key, run_id)
        if not claimed and existing is not None:
            snapshot = existing.get("response_json") if isinstance(existing, dict) else None
            if isinstance(snapshot, dict):
                snapshot["dedup_hit"] = True
                validate_response_envelope(snapshot)
                return cast(ResponseEnvelope, snapshot)

            in_progress_response: ResponseEnvelope = {
                "contract_version": request_contract_version,
                "run_id": str(existing.get("run_id", run_id)),
                "status": "in_progress",
                "artifacts": {},
                "telemetry": {},
                "policy_decisions": [
                    {
                        "decision": "allow",
                        "checkpoint_id": "dedup_in_progress",
                        "policy_bundle_version": "1.0.0",
                        "evaluated_at": "2026-03-05T00:00:00+00:00",
                    }
                ],
                "dedup_hit": True,
            }
            validate_response_envelope(in_progress_response)
            return in_progress_response

        self.state_store.transition(run_id, "planned", phase="plan")

        plan = self.router.resolve(request)
        context = self.tool_bus.call("context_retrieval", {"request": request})
        self.state_store.transition(run_id, "retrieval_done", phase="retrieval")

        phase_input = {
            "context": context,
            "ticker": request.get("ticker"),
            "analysis_type": request.get("analysis_type"),
            "intent": request.get("intent"),
            "skill_name": getattr(plan, "skill_name", None),
        }

        if not self.state_store.claim_side_effect_marker(run_id, "draft", "subagent_invocation"):
            subagent_outputs = {}
        else:
            skill_name = str(getattr(plan, "skill_name", "") or "")
            adapter = get_skill_adapter(skill_name=skill_name, subagents=self.subagents)
            use_adapter = adapter is not None and allow_adapter_for_request(
                request=request,
                run_id=run_id,
            )

            if use_adapter:
                subagent_outputs = run_skill_adapter(
                    adapter=adapter,
                    ctx=SkillAdapterContext(
                        run_id=run_id,
                        request=request,
                        plan=plan,
                        retrieval_context=context,
                    ),
                )
            else:
                subagent_outputs = self.subagents.run(plan, phase_input)

        self.state_store.transition(run_id, "draft_done", phase="draft")
        if "critique" in plan.phases:
            self.state_store.transition(run_id, "critique_done", phase="critique")
        self.state_store.transition(run_id, "validated", phase="validate")

        decision = self.policy_gate.evaluate("post_validation", {"outputs": subagent_outputs})
        final_state: Literal["completed", "blocked", "failed"] = (
            "completed" if decision.get("decision") == "allow" else "blocked"
        )

        artifacts: dict[str, Any] = {}
        if final_state == "completed":
            artifacts = self._run_mutable_side_effects(
                run_id=run_id,
                request=request,
                plan=plan,
                retrieval_context=context,
                subagent_outputs=subagent_outputs,
            )
            artifact_status = artifacts.get("analysis_artifact_status")
            if isinstance(artifact_status, str) and artifact_status.startswith("inactive_"):
                final_state = "failed"
            validation = artifacts.get("contract_validation")
            if isinstance(validation, dict) and validation.get("status") == "error":
                final_state = "failed"

        self.state_store.transition(
            run_id,
            final_state,
            phase="finalize",
            policy_decisions=[dict(decision)],
        )

        response: ResponseEnvelope = {
            "contract_version": request_contract_version,
            "run_id": run_id,
            "status": final_state,
            "artifacts": artifacts,
            "telemetry": self._build_telemetry(
                context_result=context,
                subagent_outputs=subagent_outputs,
                artifacts=artifacts,
                duration_ms=int((time.perf_counter() - started) * 1000),
            ),
            "policy_decisions": [decision],
        }
        validate_response_envelope(response)
        self._append_benchmark_telemetry_record(
            run_id=run_id,
            request=request,
            response=response,
        )
        self.state_store.finalize_dedup(dedup_key, final_state, dict(response))
        return response

    @staticmethod
    def _append_benchmark_telemetry_record(
        *,
        run_id: str,
        request: RequestEnvelope,
        response: ResponseEnvelope,
    ) -> None:
        """Append one benchmark-consumable telemetry row per run (best effort)."""
        if os.getenv("ADK_BENCHMARK_METRICS_ENABLED", "true").lower() in {
            "0",
            "false",
            "no",
        }:
            return

        default_path = Path(__file__).resolve().parents[1] / "logs" / "adk_benchmark_metrics.jsonl"
        configured_path = os.getenv("ADK_BENCHMARK_METRICS_PATH", "").strip()
        target = Path(configured_path) if configured_path else default_path

        telemetry = response.get("telemetry")
        llm = telemetry.get("llm") if isinstance(telemetry, dict) else {}
        if not isinstance(llm, dict):
            llm = {}

        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "status": response.get("status"),
            "intent": request.get("intent"),
            "ticker": request.get("ticker"),
            "analysis_type": request.get("analysis_type"),
            "duration_ms": telemetry.get("duration_ms") if isinstance(telemetry, dict) else None,
            "context_latency_ms": (
                telemetry.get("context_latency_ms") if isinstance(telemetry, dict) else None
            ),
            "side_effect_latency_ms": (
                telemetry.get("side_effect_latency_ms") if isinstance(telemetry, dict) else None
            ),
            "providers": telemetry.get("providers") if isinstance(telemetry, dict) else [],
            "models": telemetry.get("models") if isinstance(telemetry, dict) else [],
            "input_tokens_total": llm.get("input_tokens_total"),
            "output_tokens_total": llm.get("output_tokens_total"),
            "estimated_cost_usd": llm.get("estimated_cost_usd"),
        }

        # Quality gate telemetry: capture artifact classification and failure details
        # for placeholder-rate and validation-fail-rate KPI tracking.
        artifacts_dict = response.get("artifacts")
        if isinstance(artifacts_dict, dict):
            artifact_status = artifacts_dict.get("analysis_artifact_status")
            if isinstance(artifact_status, str):
                record["analysis_artifact_status"] = artifact_status
                record["artifact_inactive"] = artifact_status.startswith("inactive_")
            gate_report = artifacts_dict.get("quality_gate_report")
            if isinstance(gate_report, dict):
                record["quality_failure_code"] = gate_report.get("failure_code")
                record["quality_failed_checks"] = gate_report.get("failed_checks")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception:
            # Telemetry persistence failures must not affect user-facing orchestration.
            return

    def _run_mutable_side_effects(
        self,
        *,
        run_id: str,
        request: RequestEnvelope,
        plan: Any,
        retrieval_context: dict[str, Any],
        subagent_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute mutable operations with marker-based replay protection."""
        artifacts: dict[str, Any] = {}
        contract_valid = True
        write_success = False
        yaml_file_path: str | None = None

        if self.state_store.claim_side_effect_marker(run_id, "persist", "write_yaml"):
            yaml_result = self.tool_bus.call(
                "write_yaml",
                {
                    "run_id": run_id,
                    "ticker": request.get("ticker"),
                    "analysis_type": request.get("analysis_type"),
                    "skill_name": getattr(plan, "skill_name", None),
                    "enforce_stock_quality_gate": str(request.get("analysis_type", "")).lower()
                    == "stock",
                    "payload": {
                        "_runtime_context": (
                            retrieval_context.get("payload", {}).get("context")
                            if isinstance(retrieval_context, dict)
                            else {}
                        ),
                        **subagent_outputs,
                    },
                },
            )
            artifacts["yaml_write"] = yaml_result

            write_success = str(yaml_result.get("status", "")).lower() == "ok"
            yaml_payload = yaml_result.get("payload") if isinstance(yaml_result, dict) else None
            if isinstance(yaml_payload, dict):
                yaml_file_path = yaml_payload.get("file_path") if isinstance(yaml_payload.get("file_path"), str) else None
                analysis_status = yaml_payload.get("analysis_status")
                if isinstance(analysis_status, str) and analysis_status:
                    artifacts["analysis_artifact_status"] = analysis_status

                failure_metadata = yaml_payload.get("failure_metadata")
                if isinstance(failure_metadata, dict):
                    artifacts["quality_gate_report"] = {
                        "failure_code": failure_metadata.get("failure_code"),
                        "failed_checks": failure_metadata.get("failed_checks", []),
                        "missing_fields": failure_metadata.get("missing_fields", []),
                        "retry_eligible": failure_metadata.get("retry_eligible", True),
                        "retry_after": failure_metadata.get("retry_after"),
                        "validator_version": failure_metadata.get("validator_version", "adk_quality_gate_v1"),
                    }

            # Validate earnings artifacts before ingest to prevent indexing invalid payloads.
            skill_name = str(getattr(plan, "skill_name", "") or "")
            if write_success and skill_name == "earnings-analysis":
                validation = self._validate_written_earnings_yaml(yaml_result)
                artifacts["contract_validation"] = validation
                contract_valid = validation.get("status") == "ok"
                if not contract_valid and isinstance(validation.get("errors"), list):
                    schema_failure = self._persist_schema_failure_envelope(
                        run_id=run_id,
                        request=request,
                        plan=plan,
                        yaml_result=yaml_result,
                        errors=[str(item) for item in validation.get("errors", [])],
                    )
                    artifacts["schema_failure_envelope"] = schema_failure
                    artifacts["analysis_artifact_status"] = "inactive_schema_failed"
                    artifacts["quality_gate_report"] = {
                        "failure_code": "SCHEMA_INVALID",
                        "failed_checks": [str(item) for item in validation.get("errors", [])],
                        "missing_fields": [],
                        "retry_eligible": True,
                        "retry_after": None,
                        "validator_version": "earnings_v26_contract_v1",
                    }

        if write_success and contract_valid and self.state_store.claim_side_effect_marker(run_id, "index", "trigger_ingest"):
            ingest_result = self.tool_bus.call(
                "trigger_ingest",
                {
                    "run_id": run_id,
                    "ticker": request.get("ticker"),
                    "analysis_type": request.get("analysis_type"),
                    "file_path": yaml_file_path,
                },
            )
            artifacts["ingest"] = ingest_result

        return artifacts

    @staticmethod
    def _persist_schema_failure_envelope(
        *,
        run_id: str,
        request: RequestEnvelope,
        plan: Any,
        yaml_result: dict[str, Any],
        errors: list[str],
    ) -> dict[str, Any]:
        payload = yaml_result.get("payload") if isinstance(yaml_result, dict) else None
        yaml_path = payload.get("file_path") if isinstance(payload, dict) else None
        target_file = Path(str(yaml_path)) if isinstance(yaml_path, str) and yaml_path else None

        raw_excerpt = ""
        if target_file is not None and target_file.exists():
            try:
                raw_excerpt = target_file.read_text(encoding="utf-8")[:8000]
                target_file.unlink(missing_ok=True)
            except Exception:
                pass

        _KNOWLEDGE_FAILURE_DIR.mkdir(parents=True, exist_ok=True)
        ticker = str(request.get("ticker", "UNKNOWN") or "UNKNOWN").upper()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        envelope_path = _KNOWLEDGE_FAILURE_DIR / f"{ticker}_{stamp}_schema_failure.yaml"
        envelope = {
            "_meta": {
                "id": f"{ticker}_{stamp}_schema_failure",
                "type": "analysis-failure-envelope",
                "version": "1.0",
                "status": "inactive_schema_failed",
                "created": datetime.now(timezone.utc).isoformat(),
                "run_id": run_id,
                "source": "adk_runtime",
                "skill": str(getattr(plan, "skill_name", "") or ""),
            },
            "ticker": ticker,
            "analysis_type": str(request.get("analysis_type", "")),
            "failure": {
                "failure_code": "SCHEMA_INVALID",
                "failed_checks": errors,
                "missing_fields": [],
                "retry_eligible": True,
                "retry_after": None,
                "validator_version": "earnings_v26_contract_v1",
            },
            "raw_output_excerpt": raw_excerpt,
            "raw_output_ref": str(target_file) if target_file is not None else None,
        }
        envelope_path.write_text(yaml.safe_dump(envelope, sort_keys=False), encoding="utf-8")
        return {
            "status": "ok",
            "file_path": str(envelope_path),
            "relative_path": str(envelope_path.relative_to(Path("/opt/data/tradegent_swarm"))),
        }

    @staticmethod
    def _validate_written_earnings_yaml(yaml_result: dict[str, Any]) -> dict[str, Any]:
        payload = yaml_result.get("payload") if isinstance(yaml_result, dict) else None
        if not isinstance(payload, dict):
            return {"status": "skipped", "reason": "yaml_result_payload_missing"}

        file_path = payload.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            return {"status": "skipped", "reason": "yaml_file_path_missing"}

        target = Path(file_path)
        if not target.exists():
            return {"status": "error", "errors": [f"earnings_yaml_not_found:{file_path}"]}

        try:
            doc = yaml.safe_load(target.read_text(encoding="utf-8"))
        except Exception as exc:
            return {"status": "error", "errors": [f"earnings_yaml_parse_error:{exc}"]}

        if not isinstance(doc, dict):
            return {"status": "error", "errors": ["earnings_yaml_not_mapping"]}

        errors = validate_earnings_v26_contract(doc)
        if errors:
            return {"status": "error", "errors": errors}

        return {"status": "ok", "errors": []}

    @staticmethod
    def _build_telemetry(
        *,
        context_result: dict[str, Any],
        subagent_outputs: dict[str, Any],
        artifacts: dict[str, Any],
        duration_ms: int,
    ) -> dict[str, Any]:
        """Build normalized telemetry snapshot for UI and observability pipelines."""
        phase_telemetry: list[dict[str, Any]] = []
        providers: set[str] = set()
        models: set[str] = set()
        input_tokens_total = 0
        output_tokens_total = 0

        for phase, output in subagent_outputs.items():
            if not isinstance(output, dict):
                continue

            item: dict[str, Any] = {"phase": phase}
            llm = output.get("llm")
            routing = output.get("routing")

            if isinstance(llm, dict):
                provider = llm.get("provider")
                model = llm.get("model")
                model_alias = llm.get("model_alias")
                item.update(
                    {
                        "provider": provider,
                        "model": model,
                        "model_alias": model_alias,
                        "input_tokens": int(llm.get("input_tokens", 0) or 0),
                        "output_tokens": int(llm.get("output_tokens", 0) or 0),
                    }
                )
                item["estimated_cost_usd"] = CoordinatorAgent._estimate_phase_cost_usd(item)
                input_tokens_total += item["input_tokens"]
                output_tokens_total += item["output_tokens"]
                if isinstance(provider, str) and provider:
                    providers.add(provider)
                if isinstance(model, str) and model:
                    models.add(model)
            elif isinstance(routing, dict):
                provider = routing.get("provider")
                model = routing.get("model")
                item.update(
                    {
                        "provider": provider,
                        "model": model,
                        "model_alias": routing.get("role_alias"),
                        "input_tokens": 0,
                        "output_tokens": 0,
                    }
                )
                if isinstance(provider, str) and provider:
                    providers.add(provider)
                if isinstance(model, str) and model:
                    models.add(model)
            else:
                continue

            phase_telemetry.append(item)

        estimated_cost_usd = CoordinatorAgent._estimate_total_cost_usd(phase_telemetry)

        context_latency_ms = 0
        if isinstance(context_result, dict):
            context_latency_ms = int(context_result.get("latency_ms", 0) or 0)

        side_effect_latency_ms = 0
        for key in ("yaml_write", "ingest"):
            entry = artifacts.get(key)
            if isinstance(entry, dict):
                side_effect_latency_ms += int(entry.get("latency_ms", 0) or 0)

        return {
            "duration_ms": max(duration_ms, 0),
            "context_latency_ms": max(context_latency_ms, 0),
            "side_effect_latency_ms": max(side_effect_latency_ms, 0),
            "llm": {
                "input_tokens_total": input_tokens_total,
                "output_tokens_total": output_tokens_total,
                "estimated_cost_usd": estimated_cost_usd,
            },
            "providers": sorted(providers),
            "models": sorted(models),
            "phases": phase_telemetry,
        }

    @staticmethod
    def _estimate_phase_cost_usd(phase: dict[str, Any]) -> float | None:
        model = str(phase.get("model") or "").strip()
        if not model:
            return None

        pricing = _TOKEN_PRICING_PER_M.get(model)
        if pricing is None:
            return None

        input_tokens = int(phase.get("input_tokens", 0) or 0)
        output_tokens = int(phase.get("output_tokens", 0) or 0)
        input_rate_per_m, output_rate_per_m = pricing
        return (input_tokens * input_rate_per_m / 1_000_000.0) + (
            output_tokens * output_rate_per_m / 1_000_000.0
        )

    @staticmethod
    def _estimate_total_cost_usd(phases: list[dict[str, Any]]) -> float | None:
        costs: list[float] = []
        for phase in phases:
            cost = phase.get("estimated_cost_usd")
            if isinstance(cost, (int, float)):
                costs.append(float(cost))
        if not costs:
            return None
        return sum(costs)
