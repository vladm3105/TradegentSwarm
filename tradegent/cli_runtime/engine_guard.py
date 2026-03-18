"""Engine selection and runtime guardrails for CLI/orchestrator execution."""

from __future__ import annotations

import os
from typing import Any

SUPPORTED_AGENT_ENGINES = {"adk"}


def coerce_bool(value: Any) -> bool:
    """Normalize mixed settings value types to bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def validate_agent_engine() -> str:
    """Validate runtime engine configuration and required dependencies."""
    engine = os.getenv("AGENT_ENGINE", "adk").strip().lower()

    if engine not in SUPPORTED_AGENT_ENGINES:
        raise RuntimeError(
            f"Unsupported AGENT_ENGINE='{engine}'. Allowed: {sorted(SUPPORTED_AGENT_ENGINES)}"
        )

    if engine == "adk":
        try:
            import google.adk  # noqa: F401
        except Exception as exc:
            raise RuntimeError(
                "AGENT_ENGINE=adk requires Google ADK. "
                "Install with: pip install '.[adk]'"
            ) from exc

    return engine
