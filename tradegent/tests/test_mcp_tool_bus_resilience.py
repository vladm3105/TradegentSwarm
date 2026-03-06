"""Resilience tests for MCPToolBus retry and circuit-breaker behavior."""

from __future__ import annotations

from adk_runtime.mcp_tool_bus import MCPToolBus


class FlakyBus(MCPToolBus):
    def __init__(self) -> None:
        super().__init__(max_retries=1, circuit_threshold=10, circuit_cooldown_sec=30)
        self.calls = 0

    def _dispatch_tool(self, tool_name: str, input_payload: dict, timeout: int) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient_failure")
        return {"success": True, "ok": True}


class AlwaysFailBus(MCPToolBus):
    def __init__(self) -> None:
        self.now = 1000.0
        super().__init__(max_retries=0, circuit_threshold=2, circuit_cooldown_sec=60, time_fn=self._time)
        self.calls = 0

    def _time(self) -> float:
        return self.now

    def _dispatch_tool(self, tool_name: str, input_payload: dict, timeout: int) -> dict:
        self.calls += 1
        raise RuntimeError("hard_failure")


def test_mcp_tool_bus_retries_then_succeeds() -> None:
    bus = FlakyBus()

    result = bus.call("context_retrieval", {"request": {}}, timeout=30)

    assert result["status"] == "ok"
    assert bus.calls == 2


def test_mcp_tool_bus_opens_circuit_after_threshold() -> None:
    bus = AlwaysFailBus()

    first = bus.call("context_retrieval", {"request": {}}, timeout=30)
    second = bus.call("context_retrieval", {"request": {}}, timeout=30)
    third = bus.call("context_retrieval", {"request": {}}, timeout=30)

    assert first["status"] == "error"
    assert second["status"] == "error"
    assert third["status"] == "error"
    assert third["error"] == "CIRCUIT_OPEN"
    # Third call should not dispatch due to open circuit.
    assert bus.calls == 2
