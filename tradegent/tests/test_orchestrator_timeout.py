"""Timeout helper behavior tests for orchestrator 4-phase pipeline."""

from __future__ import annotations

import importlib
import sys
import time
import types


def _load_timeout_helper():
    """Import orchestrator lazily with minimal dependency stubs for this unit test."""
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
    return module._run_with_timeout


def test_run_with_timeout_returns_quickly_on_timeout() -> None:
    run_with_timeout = _load_timeout_helper()

    def slow_fn() -> str:
        time.sleep(0.30)
        return "done"

    started = time.perf_counter()
    result, error = run_with_timeout(slow_fn, 0.05, "test-timeout")
    elapsed = time.perf_counter() - started

    assert result is None
    assert error == "Timeout after 0.05s"
    # Should return near timeout window, not block for full function duration.
    assert elapsed < 0.20


def test_run_with_timeout_returns_result_on_success() -> None:
    run_with_timeout = _load_timeout_helper()
    result, error = run_with_timeout(lambda: "ok", 1, "test-success")

    assert result == "ok"
    assert error is None


def test_run_with_timeout_returns_error_on_exception() -> None:
    run_with_timeout = _load_timeout_helper()

    def boom() -> None:
        raise RuntimeError("boom")

    result, error = run_with_timeout(boom, 1, "test-error")

    assert result is None
    assert error == "boom"
