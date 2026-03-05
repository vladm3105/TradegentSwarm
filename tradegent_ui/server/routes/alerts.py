"""Alert management routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal, Optional
from datetime import datetime
import json
import structlog

from ..auth import get_current_user, UserClaims
from ..database import get_db_connection

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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if active_only:
                cur.execute("""
                    SELECT * FROM nexus.alerts
                    WHERE user_id = %s AND is_active = true
                    ORDER BY created_at DESC
                """, (user.sub,))
            else:
                cur.execute("""
                    SELECT * FROM nexus.alerts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                """, (user.sub,))
            rows = cur.fetchall()

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
    # Validate ticker required for price/stop/target alerts
    if body.alert_type in ('price', 'stop', 'target') and not body.ticker:
        raise HTTPException(400, f"{body.alert_type} alert requires a ticker")

    # Convert condition to JSON string for JSONB column
    condition_json = json.dumps(body.condition.model_dump())

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.alerts (user_id, alert_type, ticker, condition)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING *
            """, (user.sub, body.alert_type, body.ticker, condition_json))
            row = cur.fetchone()
            conn.commit()

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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM nexus.alerts
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (alert_id, user.sub))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(404, "Alert not found")

    log.info("alert.deleted", alert_id=alert_id)
    return {"success": True}


@router.patch("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Toggle alert active status."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.alerts
                SET is_active = NOT is_active, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING is_active
            """, (alert_id, user.sub))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(404, "Alert not found")

    return {"success": True, "is_active": row['is_active']}
