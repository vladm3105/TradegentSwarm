"""Alerts repository with SQL operations for alert endpoints."""

from __future__ import annotations

from typing import Any, cast

from ..database import get_db_connection


def list_alerts(user_id: str, active_only: bool) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if active_only:
                cur.execute(
                    """
                    SELECT * FROM nexus.alerts
                    WHERE user_id = %s AND is_active = true
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM nexus.alerts
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def create_alert(user_id: str, alert_type: str, ticker: str | None, condition_json: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.alerts (user_id, alert_type, ticker, condition)
                VALUES (%s, %s, %s, %s::jsonb)
                RETURNING *
                """,
                (user_id, alert_type, ticker, condition_json),
            )
            row = cur.fetchone()
            conn.commit()
    return cast(dict[str, Any], row)


def delete_alert(alert_id: int, user_id: str) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM nexus.alerts
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (alert_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return row is not None


def toggle_alert(alert_id: int, user_id: str) -> bool | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.alerts
                SET is_active = NOT is_active, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING is_active
                """,
                (alert_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return cast(bool | None, row["is_active"] if row else None)
