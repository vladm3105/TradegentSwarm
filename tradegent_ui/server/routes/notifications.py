"""Notification routes."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import structlog

from ..auth import get_current_user, UserClaims
from ..services import notifications_service

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
    rows = notifications_service.list_notifications(user_id=user.sub, unread_only=unread_only, limit=limit)

    return [NotificationResponse(**r) for r in rows]


@router.get("/count", response_model=NotificationCount)
async def get_notification_count(
    user: UserClaims = Depends(get_current_user),
) -> NotificationCount:
    """Get notification counts."""
    row = notifications_service.get_notification_count(user_id=user.sub)
    return NotificationCount(total=row["total"], unread=row["unread"])


@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Mark notification as read."""
    return notifications_service.mark_as_read(notification_id=notification_id, user_id=user.sub)


@router.post("/read-all")
async def mark_all_as_read(
    user: UserClaims = Depends(get_current_user),
):
    """Mark all notifications as read."""
    return notifications_service.mark_all_as_read(user_id=user.sub)
