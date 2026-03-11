"""Business logic service for notifications endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..repositories import notifications_repository


def list_notifications(user_id: str, unread_only: bool, limit: int) -> list[dict[str, Any]]:
    return notifications_repository.list_notifications(user_id=user_id, unread_only=unread_only, limit=limit)


def get_notification_count(user_id: str) -> dict[str, int]:
    row = notifications_repository.get_notification_count(user_id=user_id)
    return {"total": int(row["total"]), "unread": int(row["unread"])}


def mark_as_read(notification_id: int, user_id: str) -> dict[str, Any]:
    updated = notifications_repository.mark_as_read(notification_id=notification_id, user_id=user_id)
    if not updated:
        raise HTTPException(404, "Notification not found")
    return {"success": True}


def mark_all_as_read(user_id: str) -> dict[str, Any]:
    notifications_repository.mark_all_as_read(user_id=user_id)
    return {"success": True}
