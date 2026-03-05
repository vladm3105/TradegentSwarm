"""Notification routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import structlog

from ..auth import get_current_user, UserClaims
from ..database import get_db_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    id: int
    type: str
    severity: str
    title: str
    message: Optional[str]
    data: Optional[dict]
    is_read: bool
    created_at: datetime


class NotificationCount(BaseModel):
    total: int
    unread: int


@router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: UserClaims = Depends(get_current_user),
) -> list[NotificationResponse]:
    """List user notifications."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if unread_only:
                cur.execute("""
                    SELECT * FROM nexus.notifications
                    WHERE user_id = %s AND is_read = false
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user.sub, limit))
            else:
                cur.execute("""
                    SELECT * FROM nexus.notifications
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user.sub, limit))
            rows = cur.fetchall()

    return [NotificationResponse(**r) for r in rows]


@router.get("/count", response_model=NotificationCount)
async def get_notification_count(
    user: UserClaims = Depends(get_current_user),
) -> NotificationCount:
    """Get notification counts."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_read = false) as unread
                FROM nexus.notifications
                WHERE user_id = %s
            """, (user.sub,))
            row = cur.fetchone()

    return NotificationCount(total=row['total'], unread=row['unread'])


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Mark notification as read."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.notifications
                SET is_read = true
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (notification_id, user.sub))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(404, "Notification not found")

    return {"success": True}


@router.post("/read-all")
async def mark_all_as_read(
    user: UserClaims = Depends(get_current_user),
):
    """Mark all notifications as read."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.notifications
                SET is_read = true
                WHERE user_id = %s AND is_read = false
            """, (user.sub,))
            conn.commit()

    return {"success": True}
