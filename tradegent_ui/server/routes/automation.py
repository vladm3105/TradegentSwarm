"""Automation control routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal
import structlog

from ..auth import get_current_user, UserClaims
from ..database import get_db_connection
from ..services.circuit_breaker import get_circuit_breaker

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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key, value FROM nexus.settings
                WHERE section IN ('trading', 'safety')
            """)
            rows = cur.fetchall()
            settings = {r['key']: r['value'] for r in rows}

    return TradingModeResponse(
        mode=settings.get('trading_mode', 'dry_run'),
        auto_execute=settings.get('auto_execute_enabled', 'false') == 'true',
        is_paused=settings.get('trading_paused', 'false') == 'true',
        circuit_breaker_triggered=settings.get('circuit_breaker_triggered', 'false') == 'true',
        circuit_breaker_triggered_at=settings.get('circuit_breaker_triggered_at'),
    )


@router.post("/mode")
async def set_trading_mode(
    body: TradingModeRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Set trading mode."""
    if body.mode == 'live' and not body.confirm:
        raise HTTPException(400, "Live trading requires explicit confirmation")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Set trading mode
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_mode'
            """, (body.mode,))

            # Set auto_execute based on mode
            auto_execute = 'true' if body.mode in ('paper', 'live') else 'false'
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'auto_execute_enabled'
            """, (auto_execute,))

            # Set dry_run_mode (inverse of trading)
            dry_run = 'true' if body.mode == 'dry_run' else 'false'
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'dry_run_mode'
            """, (dry_run,))

            conn.commit()

    log.warning(
        "trading_mode.changed",
        user=user.email,
        new_mode=body.mode,
        auto_execute=auto_execute,
    )

    return {"success": True, "mode": body.mode}


@router.post("/pause")
async def pause_trading(
    user: UserClaims = Depends(get_current_user),
):
    """Pause all automated trading."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings
                SET value = 'true', updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_paused'
            """)
            cur.execute("""
                UPDATE nexus.settings
                SET value = NOW()::text, updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_paused_at'
            """)
            conn.commit()

    log.warning("trading.paused", user=user.email)
    return {"success": True, "paused": True}


@router.post("/resume")
async def resume_trading(
    user: UserClaims = Depends(get_current_user),
):
    """Resume automated trading."""
    # Check circuit breaker
    cb = get_circuit_breaker()
    if cb.is_triggered:
        raise HTTPException(400, "Cannot resume: Circuit breaker is triggered. Reset required.")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings
                SET value = 'false', updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_paused'
            """)
            conn.commit()

    log.warning("trading.resumed", user=user.email)
    return {"success": True, "paused": False}


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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key, value FROM nexus.settings
                WHERE section = 'safety'
            """)
            rows = cur.fetchall()
            settings = {r['key']: r['value'] for r in rows}

    return CircuitBreakerSettings(
        enabled=settings.get('circuit_breaker_enabled', 'true') == 'true',
        max_daily_loss=float(settings.get('max_daily_loss', '1000')),
        max_daily_loss_pct=float(settings.get('max_daily_loss_pct', '5')),
    )


@router.put("/circuit-breaker/settings")
async def update_circuit_breaker_settings(
    body: CircuitBreakerSettings,
    user: UserClaims = Depends(get_current_user),
):
    """Update circuit breaker settings."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'circuit_breaker_enabled'
            """, (str(body.enabled).lower(),))
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'max_daily_loss'
            """, (str(body.max_daily_loss),))
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'max_daily_loss_pct'
            """, (str(body.max_daily_loss_pct),))
            conn.commit()

    log.info("circuit_breaker.settings_updated", user=user.email)
    return {"success": True}
