"""Notifications repository with SQL operations for notifications endpoints."""

from __future__ import annotations

from typing import Any, cast

from ..database import get_db_connection


def list_notifications(user_id: str, unread_only: bool, limit: int) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if unread_only:
                cur.execute(
                    """
                    SELECT * FROM nexus.notifications
                    WHERE user_id = %s AND is_read = false
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM nexus.notifications
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, limit),
                )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def get_notification_count(user_id: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE is_read = false) as unread
                FROM nexus.notifications
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any], row)


def mark_as_read(notification_id: int, user_id: str) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.notifications
                SET is_read = true
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (notification_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return row is not None


def mark_all_as_read(user_id: str) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.notifications
                SET is_read = true
                WHERE user_id = %s AND is_read = false
                """,
                (user_id,),
            )
            conn.commit()
