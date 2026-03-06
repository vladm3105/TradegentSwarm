"""Focused checks for phase1 tool allowlist configuration defaults."""

from __future__ import annotations

import importlib
import sys
import types


def _load_settings_class():
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
    return module.Settings


class _FakeDB:
    def get_all_settings(self):
        return {}


def test_phase1_tools_default_is_narrower() -> None:
    Settings = _load_settings_class()
    cfg = Settings(_FakeDB())

    assert cfg.allowed_tools_phase1_analysis == "mcp__ib-mcp__*"
    assert cfg.phase1_timeout == 480


def test_phase1_tools_can_be_overridden() -> None:
    Settings = _load_settings_class()

    class _DBWithOverride:
        def get_all_settings(self):
            return {
                "allowed_tools_phase1_analysis": "mcp__ib-mcp__*",
                "phase1_timeout_seconds": 240,
            }

    cfg = Settings(_DBWithOverride())
    assert cfg.allowed_tools_phase1_analysis == "mcp__ib-mcp__*"
    assert cfg.phase1_timeout == 240
