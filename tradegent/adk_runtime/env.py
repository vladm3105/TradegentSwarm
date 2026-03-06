"""Shared runtime environment loader for agents and sub-agents."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ENV_PATH = Path("/opt/data/tradegent_swarm/tradegent/.env")
ENV_PATH_VAR = "TRADEGENT_ENV_PATH"


def load_runtime_env(env_path: Path | None = None) -> Path:
    """Load runtime environment once from the configured .env path."""
    override_path = os.getenv(ENV_PATH_VAR, "").strip()
    path = env_path or (Path(override_path) if override_path else DEFAULT_ENV_PATH)
    if path.exists():
        load_dotenv(path)
    return path
