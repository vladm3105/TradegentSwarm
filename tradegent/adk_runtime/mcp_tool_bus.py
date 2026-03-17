"""MCP tool bus skeleton with normalized envelopes."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
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
        self._context_cache_ttl_sec = float(
            os.getenv("MCP_TOOLBUS_CONTEXT_CACHE_TTL_SEC", "30") or 30
        )
        self._context_cache: dict[str, dict[str, Any]] = {}

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
        last_failure_payload: dict[str, Any] | None = None
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

                if isinstance(result, dict):
                    last_failure_payload = result
                last_error = str(result.get("error", "tool_error"))
                raise RuntimeError(last_error)
            except Exception as exc:
                last_error = str(exc)
                self._record_failure(tool_name)

        error_payload: dict[str, Any] = {
            "tool_name": tool_name,
            "error": last_error,
            "attempts": attempts,
        }
        if isinstance(last_failure_payload, dict):
            error_payload["failure_payload"] = last_failure_payload

        return {
            "status": "error",
            "payload": error_payload,
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
                enforce_stock_quality_gate=bool(input_payload.get("enforce_stock_quality_gate", False)),
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

        cache_key = f"{analysis_type}:{ticker}"
        now = float(self._time())

        if not ticker:
            return {
                "success": True,
                "context": {
                    "request": request,
                    "source": None,
                    "latest_document": None,
                    "market_data": None,
                    "warnings": ["ticker_missing"],
                    "cache_hit": False,
                },
            }

        market_data = self._fetch_live_market_data(ticker)

        cached = self._context_cache.get(cache_key)
        if cached is not None:
            cached_until = float(cached.get("expires_at", 0.0) or 0.0)
            source_path = cached.get("source")
            source_mtime_ns = cached.get("source_mtime_ns")
            if (
                cached_until >= now
                and isinstance(source_path, str)
                and source_path
                and isinstance(source_mtime_ns, int)
            ):
                source_file = Path(source_path)
                if source_file.exists():
                    current_mtime_ns = source_file.stat().st_mtime_ns
                    if current_mtime_ns == source_mtime_ns:
                        return {
                            "success": True,
                            "context": {
                                "request": request,
                                "source": source_path,
                                "latest_document": cached.get("latest_document"),
                                "market_data": market_data,
                                "warnings": [],
                                "cache_hit": True,
                            },
                        }

        pattern = f"{ticker}_*.yaml"
        candidates = [p for p in search_dir.glob(pattern) if p.is_file()]
        active_only = os.getenv("ADK_CONTEXT_ACTIVE_ONLY", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        include_non_active = not active_only
        if active_only:
            candidates = [p for p in candidates if self._is_active_analysis_artifact(p)]
        if not candidates:
            return {
                "success": True,
                "context": {
                    "request": request,
                    "source": None,
                    "latest_document": None,
                    "market_data": market_data,
                    "warnings": ["no_prior_document" if include_non_active else "no_active_document"],
                    "cache_hit": False,
                },
            }

        # Filenames follow TICKER_YYYYMMDDTHHMM.yaml, so lexical max is newest.
        latest = max(candidates, key=lambda p: p.name)
        try:
            latest_doc = yaml.safe_load(latest.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to parse context file {latest}: {exc}",
            }

        self._context_cache[cache_key] = {
            "source": str(latest),
            "source_mtime_ns": latest.stat().st_mtime_ns,
            "latest_document": latest_doc,
            "expires_at": now + max(self._context_cache_ttl_sec, 0.0),
        }

        return {
            "success": True,
            "context": {
                "request": request,
                "source": str(latest),
                "latest_document": latest_doc,
                "market_data": market_data,
                "warnings": [],
                "cache_hit": False,
            },
        }

    @staticmethod
    def _is_active_analysis_artifact(file_path: Path) -> bool:
        try:
            document = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        if not isinstance(document, dict):
            return False
        meta = document.get("_meta")
        if not isinstance(meta, dict):
            return False
        return str(meta.get("status", "")).strip().lower() == "active"

    def _fetch_live_market_data(self, ticker: str) -> dict[str, Any] | None:
        """Best-effort live quote snapshot for downstream stock data-quality guards."""
        try:
            from ib_client import get_ib_client

            client = get_ib_client()
            quote = client.get_stock_price(ticker)
            if not isinstance(quote, dict):
                return None

            def _num(*keys: str) -> float | None:
                for key in keys:
                    value = quote.get(key)
                    if isinstance(value, (int, float)) and float(value) > 0:
                        return float(value)
                return None

            last = _num("last", "price", "market_price")
            close = _num("close", "prior_close", "previous_close")

            if last is None or close is None:
                try:
                    batch = client.get_quotes_batch([ticker])
                    quote_obj = batch.get(ticker) if isinstance(batch, dict) else None
                    if quote_obj is not None:
                        batch_last = getattr(quote_obj, "last", None)
                        batch_close = getattr(quote_obj, "close", None)
                        if last is None and isinstance(batch_last, (int, float)) and float(batch_last) > 0:
                            last = float(batch_last)
                        if close is None and isinstance(batch_close, (int, float)) and float(batch_close) > 0:
                            close = float(batch_close)
                except Exception:
                    pass

            if close is None:
                try:
                    hist = client.get_historical_data(
                        ticker,
                        duration="2 D",
                        bar_size="1 day",
                        what_to_show="TRADES",
                    )
                    if isinstance(hist, dict):
                        bars = hist.get("bars")
                    elif isinstance(hist, list):
                        bars = hist
                    else:
                        bars = None

                    if isinstance(bars, list) and bars:
                        last_bar = bars[-1]
                        if isinstance(last_bar, dict):
                            for key in ("close", "c"):
                                value = last_bar.get(key)
                                if isinstance(value, (int, float)) and float(value) > 0:
                                    close = float(value)
                                    break
                except Exception:
                    pass

            snapshot: dict[str, Any] = {
                "ticker": ticker,
                "quote_timestamp": datetime.now(timezone.utc).isoformat(),
                "price_data_source": "ib_mcp",
                "price_data_verified": False,
            }
            if last is not None:
                snapshot["current_price"] = last
            elif close is not None:
                snapshot["current_price"] = close
            if isinstance(close, (int, float)) and float(close) > 0:
                snapshot["prior_close"] = float(close)
            if "current_price" in snapshot or "prior_close" in snapshot:
                snapshot["price_data_verified"] = True
            return snapshot
        except Exception:
            return None
