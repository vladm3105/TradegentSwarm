"""Tests for MCPToolBus pluggable workflow handlers."""

from __future__ import annotations

from adk_runtime.mcp_tool_bus import MCPToolBus


class _Calls:
    def __init__(self) -> None:
        self.count = 0


def test_mcp_tool_bus_uses_registered_handler() -> None:
    calls = _Calls()

    def handler(input_payload: dict, timeout: int) -> dict:
        calls.count += 1
        return {
            "success": True,
            "handler": "custom",
            "payload": input_payload,
            "timeout": timeout,
        }

    bus = MCPToolBus(workflow_handlers={"graph_context": handler})
    result = bus.call("graph_context", {"ticker": "NVDA"}, timeout=12)

    assert result["status"] == "ok"
    assert result["payload"]["handler"] == "custom"
    assert result["payload"]["payload"]["ticker"] == "NVDA"
    assert result["payload"]["timeout"] == 12
    assert calls.count == 1


def test_mcp_tool_bus_handler_failure_honors_retry_and_returns_error() -> None:
    calls = _Calls()

    def flaky(_input_payload: dict, _timeout: int) -> dict:
        calls.count += 1
        return {"success": False, "error": "backend_down"}

    bus = MCPToolBus(max_retries=1, circuit_threshold=5, workflow_handlers={"rag_context": flaky})
    result = bus.call("rag_context", {"ticker": "AAPL"}, timeout=10)

    assert result["status"] == "error"
    assert result["error"] == "backend_down"
    # initial attempt + 1 retry
    assert calls.count == 2
