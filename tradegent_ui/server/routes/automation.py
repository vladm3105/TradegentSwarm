"""Automation control routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal
import structlog

from ..auth import get_current_user, UserClaims
from ..services.circuit_breaker import get_circuit_breaker
from ..services import automation_service

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/automation", tags=["automation"])


class TradingModeRequest(BaseModel):
    mode: Literal['dry_run', 'paper', 'live']
    confirm: bool = False  # Required for live mode


class TradingModeResponse(BaseModel):
    mode: str
    auto_execute: bool
    is_paused: bool
    circuit_breaker_triggered: bool
    circuit_breaker_triggered_at: str | None


class CircuitBreakerSettings(BaseModel):
    enabled: bool
    max_daily_loss: float
    max_daily_loss_pct: float


@router.get("/status", response_model=TradingModeResponse)
async def get_automation_status(
    user: UserClaims = Depends(get_current_user),
) -> TradingModeResponse:
    """Get current automation status."""
    data = automation_service.get_automation_status()
    return TradingModeResponse(**data)


@router.post("/mode")
async def set_trading_mode(
    body: TradingModeRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Set trading mode."""
    result = automation_service.set_trading_mode(body.mode, body.confirm)
    log.warning("trading_mode.changed", user=user.email, new_mode=body.mode)
    return result


@router.post("/pause")
async def pause_trading(
    user: UserClaims = Depends(get_current_user),
):
    """Pause all automated trading."""
    result = automation_service.pause_trading()
    log.warning("trading.paused", user=user.email)
    return result


@router.post("/resume")
async def resume_trading(
    user: UserClaims = Depends(get_current_user),
):
    """Resume automated trading."""
    cb = get_circuit_breaker()
    result = automation_service.resume_trading(cb)
    log.warning("trading.resumed", user=user.email)
    return result


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    user: UserClaims = Depends(get_current_user),
):
    """Reset circuit breaker (requires confirmation)."""
    cb = get_circuit_breaker()
    if not cb.is_triggered:
        raise HTTPException(400, "Circuit breaker is not triggered")

    await cb.reset(user.sub)

    log.warning("circuit_breaker.manual_reset", user=user.email)
    return {"success": True, "reset": True}


@router.get("/circuit-breaker/settings", response_model=CircuitBreakerSettings)
async def get_circuit_breaker_settings(
    user: UserClaims = Depends(get_current_user),
) -> CircuitBreakerSettings:
    """Get circuit breaker settings."""
    data = automation_service.get_circuit_breaker_settings()
    return CircuitBreakerSettings(**data)


@router.put("/circuit-breaker/settings")
async def update_circuit_breaker_settings(
    body: CircuitBreakerSettings,
    user: UserClaims = Depends(get_current_user),
):
    """Update circuit breaker settings."""
    result = automation_service.update_circuit_breaker_settings(
        body.enabled, body.max_daily_loss, body.max_daily_loss_pct
    )
    log.info("circuit_breaker.settings_updated", user=user.email)
    return result
