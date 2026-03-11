"""Alert management routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime
import structlog

from ..auth import get_current_user, UserClaims
from ..services import alerts_service

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertCondition(BaseModel):
    operator: Literal['above', 'below', 'crosses']
    value: float
    value_type: Literal['price', 'pct_change', 'absolute'] = 'price'


class CreateAlertRequest(BaseModel):
    alert_type: Literal['price', 'pnl', 'stop', 'target', 'expiration', 'system']
    ticker: Optional[str] = None
    condition: AlertCondition


class AlertResponse(BaseModel):
    id: int
    alert_type: str
    ticker: Optional[str]
    condition: dict
    is_active: bool
    is_triggered: bool
    triggered_at: Optional[datetime]
    created_at: datetime


@router.get("/", response_model=list[AlertResponse])
async def list_alerts(
    active_only: bool = True,
    user: UserClaims = Depends(get_current_user),
) -> list[AlertResponse]:
    """List user alerts."""
    rows = alerts_service.list_alerts(user_id=user.sub, active_only=active_only)

    return [AlertResponse(
        id=r['id'],
        alert_type=r['alert_type'],
        ticker=r['ticker'],
        condition=r['condition'],
        is_active=r['is_active'],
        is_triggered=r['is_triggered'],
        triggered_at=r['triggered_at'],
        created_at=r['created_at'],
    ) for r in rows]


@router.post("/", response_model=AlertResponse)
async def create_alert(
    body: CreateAlertRequest,
    user: UserClaims = Depends(get_current_user),
) -> AlertResponse:
    """Create a new alert."""
    row = alerts_service.create_alert(
        user_id=user.sub,
        alert_type=body.alert_type,
        ticker=body.ticker,
        condition=body.condition.model_dump(),
    )

    log.info("alert.created", alert_id=row['id'], alert_type=body.alert_type, ticker=body.ticker)

    return AlertResponse(
        id=row['id'],
        alert_type=row['alert_type'],
        ticker=row['ticker'],
        condition=row['condition'],
        is_active=row['is_active'],
        is_triggered=row['is_triggered'],
        triggered_at=row['triggered_at'],
        created_at=row['created_at'],
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Delete an alert."""
    result = alerts_service.delete_alert(alert_id=alert_id, user_id=user.sub)

    log.info("alert.deleted", alert_id=alert_id)
    return result


@router.patch("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Toggle alert active status."""
    return alerts_service.toggle_alert(alert_id=alert_id, user_id=user.sub)
