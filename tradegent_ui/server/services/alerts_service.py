"""Business logic service for alert operations."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from ..repositories import alerts_repository


def list_alerts(user_id: str, active_only: bool) -> list[dict[str, Any]]:
    return alerts_repository.list_alerts(user_id=user_id, active_only=active_only)


def create_alert(user_id: str, alert_type: str, ticker: str | None, condition: dict[str, Any]) -> dict[str, Any]:
    if alert_type in ("price", "stop", "target") and not ticker:
        raise HTTPException(400, f"{alert_type} alert requires a ticker")

    condition_json = json.dumps(condition)
    return alerts_repository.create_alert(
        user_id=user_id,
        alert_type=alert_type,
        ticker=ticker,
        condition_json=condition_json,
    )


def delete_alert(alert_id: int, user_id: str) -> dict[str, Any]:
    deleted = alerts_repository.delete_alert(alert_id=alert_id, user_id=user_id)
    if not deleted:
        raise HTTPException(404, "Alert not found")
    return {"success": True}


def toggle_alert(alert_id: int, user_id: str) -> dict[str, Any]:
    is_active = alerts_repository.toggle_alert(alert_id=alert_id, user_id=user_id)
    if is_active is None:
        raise HTTPException(404, "Alert not found")
    return {"success": True, "is_active": is_active}
