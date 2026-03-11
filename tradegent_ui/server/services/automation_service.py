"""Automation service — business logic for trading mode and circuit-breaker control."""
from fastapi import HTTPException

from ..repositories import automation_repository


def get_automation_status() -> dict:
    """Return current automation status assembled from settings."""
    settings = automation_repository.get_automation_settings()
    return {
        "mode": settings.get("trading_mode", "dry_run"),
        "auto_execute": settings.get("auto_execute_enabled", "false") == "true",
        "is_paused": settings.get("trading_paused", "false") == "true",
        "circuit_breaker_triggered": settings.get("circuit_breaker_triggered", "false") == "true",
        "circuit_breaker_triggered_at": settings.get("circuit_breaker_triggered_at"),
    }


def set_trading_mode(mode: str, confirm: bool) -> dict:
    """Validate and apply trading mode change.

    Raises HTTPException(400) when live mode is requested without confirm=True.
    """
    if mode == "live" and not confirm:
        raise HTTPException(400, "Live trading requires explicit confirmation")

    auto_execute = "true" if mode in ("paper", "live") else "false"
    dry_run = "true" if mode == "dry_run" else "false"
    automation_repository.set_trading_mode(mode, auto_execute, dry_run)
    return {"success": True, "mode": mode, "auto_execute": auto_execute}


def pause_trading() -> dict:
    """Pause all automated trading."""
    automation_repository.set_trading_paused(True)
    return {"success": True, "paused": True}


def resume_trading(circuit_breaker) -> dict:
    """Resume automated trading.

    Raises HTTPException(400) if the circuit breaker is still triggered.
    """
    if circuit_breaker.is_triggered:
        raise HTTPException(
            400,
            "Cannot resume: Circuit breaker is triggered. Reset required.",
        )
    automation_repository.set_trading_paused(False)
    return {"success": True, "paused": False}


def get_circuit_breaker_settings() -> dict:
    """Return circuit-breaker settings as a plain dict."""
    settings = automation_repository.get_circuit_breaker_settings()
    return {
        "enabled": settings.get("circuit_breaker_enabled", "true") == "true",
        "max_daily_loss": float(settings.get("max_daily_loss", "1000")),
        "max_daily_loss_pct": float(settings.get("max_daily_loss_pct", "5")),
    }


def update_circuit_breaker_settings(
    enabled: bool,
    max_daily_loss: float,
    max_daily_loss_pct: float,
) -> dict:
    """Persist circuit-breaker setting updates."""
    automation_repository.update_circuit_breaker_settings(
        enabled, max_daily_loss, max_daily_loss_pct
    )
    return {"success": True}
