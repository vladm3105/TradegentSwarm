"""Skill-native adapter registry and rollout gates."""

from __future__ import annotations

import hashlib
import os
from typing import Any

from ..contracts import RequestEnvelope
from ..subagent_invoker import SubagentInvoker

from .base import SkillAdapter, SkillAdapterContext
from .earnings_analysis_adapter import EarningsAnalysisAdapter
from .stock_analysis_adapter import StockAnalysisAdapter


def get_skill_adapter(*, skill_name: str, subagents: SubagentInvoker) -> SkillAdapter | None:
    """Return adapter instance when skill-native mode is enabled for the skill."""
    if _is_kill_switch_enabled():
        return None

    if skill_name == "stock-analysis":
        if not _is_enabled("ADK_SKILL_NATIVE_STOCK_ENABLED"):
            return None
        return StockAnalysisAdapter(subagents=subagents)

    if skill_name == "earnings-analysis":
        if not _is_enabled("ADK_SKILL_NATIVE_EARNINGS_ENABLED"):
            return None
        return EarningsAnalysisAdapter(subagents=subagents)

    return None


def allow_adapter_for_request(*, request: RequestEnvelope, run_id: str) -> bool:
    """Canary gate for skill-native execution.

    Uses deterministic hashing so repeated runs are stable across processes.
    """
    if _is_kill_switch_enabled():
        return False

    percent = _read_canary_percent()
    if percent <= 0:
        return False
    if percent >= 100:
        return True

    token = _canary_token(request=request, run_id=run_id)
    bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % 100
    return bucket < percent


def run_skill_adapter(*, adapter: SkillAdapter, ctx: SkillAdapterContext) -> dict[str, Any]:
    """Execute adapter and normalize null-ish returns."""
    result = adapter.run(ctx)
    return result if isinstance(result, dict) else {}


def _is_enabled(name: str) -> bool:
    raw = os.getenv(name, "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _read_canary_percent() -> int:
    raw = os.getenv("ADK_SKILL_NATIVE_CANARY_PERCENT", "0").strip()
    try:
        value = int(raw)
    except ValueError:
        return 0
    bounded = max(0, min(100, value))

    if _is_enabled("ADK_SKILL_NATIVE_CANARY_STAGE_ENFORCED"):
        allowed = {0, 10, 25, 50, 100}
        if bounded not in allowed:
            raise RuntimeError(
                "ADK_SKILL_NATIVE_CANARY_PERCENT must be one of {0,10,25,50,100} when "
                "ADK_SKILL_NATIVE_CANARY_STAGE_ENFORCED=true"
            )

    return bounded


def _canary_token(*, request: RequestEnvelope, run_id: str) -> str:
    ticker = str(request.get("ticker", "") or "")
    intent = str(request.get("intent", "") or "")
    analysis_type = str(request.get("analysis_type", "") or "")
    client_request_id = str(request.get("client_request_id", "") or "")
    idempotency_key = str(request.get("idempotency_key", "") or "")
    stable_id = idempotency_key or client_request_id or run_id
    return "|".join([ticker, intent, analysis_type, stable_id])


def _is_kill_switch_enabled() -> bool:
    return _is_enabled("ADK_SKILL_NATIVE_KILL_SWITCH")
