"""Unit tests for tool usage telemetry extraction helpers in orchestrator."""

from __future__ import annotations

import importlib
import sys
import types


def _load_extract_helper():
    sys.modules.pop("orchestrator", None)

    if "shared.observability" not in sys.modules:
        shared_obs = types.ModuleType("shared.observability")
        shared_obs.setup_logging = lambda *args, **kwargs: None
        sys.modules["shared.observability"] = shared_obs

    if "structlog" not in sys.modules:
        structlog_stub = types.ModuleType("structlog")
        structlog_stub.get_logger = lambda *args, **kwargs: types.SimpleNamespace(
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            debug=lambda *a, **k: None,
        )
        sys.modules["structlog"] = structlog_stub

    module = importlib.import_module("orchestrator")
    return module._extract_tool_usage_counts


def test_extract_tool_usage_counts_mcp_and_websearch() -> None:
    extract = _load_extract_helper()
    text = (
        "Used mcp__ib-mcp__get_stock_price and mcp__ib-mcp__get_stock_price again. "
        "Fallback was WebSearch."
    )

    counts = extract(text)

    assert counts["mcp__ib-mcp__get_stock_price"] == 2
    assert counts["WebSearch"] == 1


def test_extract_tool_usage_counts_empty_when_no_mentions() -> None:
    extract = _load_extract_helper()
    counts = extract("No tool calls were listed in this output.")

    assert counts == {}
