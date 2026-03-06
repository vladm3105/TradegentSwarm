"""MCP tool bus skeleton with normalized envelopes."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .side_effects import trigger_ingest, write_analysis_yaml


class MCPToolBus:
    """Normalize MCP request/response envelopes for tool access."""

    def __init__(
        self,
        *,
        max_retries: int | None = None,
        circuit_threshold: int | None = None,
        circuit_cooldown_sec: int | None = None,
        time_fn: Any | None = None,
        knowledge_root: Path | None = None,
        workflow_handlers: dict[str, Any] | None = None,
    ) -> None:
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(os.getenv("MCP_TOOLBUS_MAX_RETRIES", "1") or 1)
        )
        self.circuit_threshold = (
            circuit_threshold
            if circuit_threshold is not None
            else int(os.getenv("MCP_TOOLBUS_CIRCUIT_THRESHOLD", "3") or 3)
        )
        self.circuit_cooldown_sec = (
            circuit_cooldown_sec
            if circuit_cooldown_sec is not None
            else int(os.getenv("MCP_TOOLBUS_CIRCUIT_COOLDOWN_SEC", "30") or 30)
        )
        self._time = time_fn or time.time
        self._failures: dict[str, int] = {}
        self._circuit_open_until: dict[str, float] = {}
        self._knowledge_root = knowledge_root or Path(
            "/opt/data/tradegent_swarm/tradegent_knowledge/knowledge"
        )
        self._workflow_handlers: dict[str, Any] = dict(workflow_handlers or {})

    def register_handler(self, tool_name: str, handler: Any) -> None:
        """Register/replace runtime handler for a tool workflow."""
        self._workflow_handlers[tool_name] = handler

    def call(self, tool_name: str, input_payload: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
        started = time.time()
        open_until = self._circuit_open_until.get(tool_name)
        now = float(self._time())
        if open_until is not None and now < open_until:
            return {
                "status": "error",
                "payload": {
                    "tool_name": tool_name,
                    "error": "CIRCUIT_OPEN",
                    "circuit_open_until": open_until,
                },
                "error": "CIRCUIT_OPEN",
                "latency_ms": int((time.time() - started) * 1000),
            }

        attempts = self.max_retries + 1
        last_error: str | None = None
        for _attempt in range(1, attempts + 1):
            try:
                result = self._dispatch_tool(tool_name, input_payload, timeout)
                if result.get("success"):
                    self._failures[tool_name] = 0
                    self._circuit_open_until.pop(tool_name, None)
                    return {
                        "status": "ok",
                        "payload": result,
                        "error": None,
                        "latency_ms": int((time.time() - started) * 1000),
                    }

                last_error = str(result.get("error", "tool_error"))
                raise RuntimeError(last_error)
            except Exception as exc:
                last_error = str(exc)
                self._record_failure(tool_name)

        return {
            "status": "error",
            "payload": {
                "tool_name": tool_name,
                "error": last_error,
                "attempts": attempts,
            },
            "error": last_error,
            "latency_ms": int((time.time() - started) * 1000),
        }

    def _dispatch_tool(self, tool_name: str, input_payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        # External handlers allow progressive migration to real MCP workflows
        # while preserving bus-level retry/circuit behavior.
        handler = self._workflow_handlers.get(tool_name)
        if handler is not None:
            result = handler(input_payload, timeout)
            if isinstance(result, dict):
                return result
            return {"success": False, "error": f"invalid_handler_result:{type(result).__name__}"}

        if tool_name == "context_retrieval":
            return self._context_retrieval_workflow(input_payload)

        if tool_name == "write_yaml":
            return write_analysis_yaml(
                run_id=str(input_payload.get("run_id", "")),
                ticker=str(input_payload.get("ticker", "")),
                analysis_type=str(input_payload.get("analysis_type", "stock")),
                skill_name=(
                    str(input_payload.get("skill_name"))
                    if input_payload.get("skill_name") is not None
                    else None
                ),
                payload=input_payload.get("payload", {}) if isinstance(input_payload.get("payload"), dict) else {},
            )

        if tool_name == "trigger_ingest":
            return trigger_ingest(str(input_payload.get("file_path", "")))

        # Placeholder for non-side-effect MCP calls during migration.
        return {"success": True, "tool_name": tool_name, "input": input_payload, "timeout": timeout}

    def _record_failure(self, tool_name: str) -> None:
        count = int(self._failures.get(tool_name, 0)) + 1
        self._failures[tool_name] = count
        if count >= self.circuit_threshold:
            self._circuit_open_until[tool_name] = float(self._time()) + float(self.circuit_cooldown_sec)

    def _context_retrieval_workflow(self, input_payload: dict[str, Any]) -> dict[str, Any]:
        """File-backed context retrieval using latest YAML artifact for ticker/type."""
        request = input_payload.get("request", {})
        if not isinstance(request, dict):
            request = {}

        ticker = str(request.get("ticker", "")).strip().upper()
        analysis_type = str(request.get("analysis_type", "stock")).strip().lower()

        if analysis_type == "earnings":
            search_dir = self._knowledge_root / "analysis" / "earnings"
        else:
            search_dir = self._knowledge_root / "analysis" / "stock"

        if not ticker:
            return {
                "success": True,
                "context": {
                    "request": request,
                    "source": None,
                    "latest_document": None,
                    "warnings": ["ticker_missing"],
                },
            }

        pattern = f"{ticker}_*.yaml"
        candidates = sorted(search_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            return {
                "success": True,
                "context": {
                    "request": request,
                    "source": None,
                    "latest_document": None,
                    "warnings": ["no_prior_document"],
                },
            }

        latest = candidates[0]
        try:
            latest_doc = yaml.safe_load(latest.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to parse context file {latest}: {exc}",
            }

        return {
            "success": True,
            "context": {
                "request": request,
                "source": str(latest),
                "latest_document": latest_doc,
                "warnings": [],
            },
        }
