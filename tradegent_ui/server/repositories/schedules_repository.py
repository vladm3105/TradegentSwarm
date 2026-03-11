"""Schedule repository with all SQL operations for schedule management."""

from __future__ import annotations

from typing import cast
from typing import Any

from psycopg import sql

from ..database import get_db_connection


ALLOWED_UPDATE_FIELDS = {
    "is_enabled",
    "frequency",
    "time_of_day",
    "day_of_week",
    "interval_minutes",
}


def list_schedules() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, name, task_type, frequency,
                    is_enabled, time_of_day, day_of_week, interval_minutes,
                    next_run_at, last_run_at, last_run_status,
                    fail_count, consecutive_fails
                FROM nexus.schedules
                ORDER BY next_run_at ASC NULLS LAST
                """
            )
            return cast(list[dict[str, Any]], cur.fetchall())


def get_schedule(schedule_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, name, task_type, frequency,
                    is_enabled, time_of_day, day_of_week, interval_minutes,
                    next_run_at, last_run_at, last_run_status,
                    fail_count, consecutive_fails
                FROM nexus.schedules
                WHERE id = %s
                """,
                (schedule_id,),
            )
            return cast(dict[str, Any] | None, cur.fetchone())


def update_schedule(schedule_id: int, updates: dict[str, Any]) -> bool:
    filtered = {k: v for k, v in updates.items() if k in ALLOWED_UPDATE_FIELDS}
    if not filtered:
        return False

    assignments = []
    values: list[Any] = []
    for key, value in filtered.items():
        assignments.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
        values.append(value)

    values.append(schedule_id)

    query = sql.SQL(
        """
        UPDATE nexus.schedules
        SET {assignments}, updated_at = NOW()
        WHERE id = %s
        RETURNING id
        """
    ).format(assignments=sql.SQL(", ").join(assignments))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(values))
            row = cur.fetchone()
            conn.commit()

    return row is not None


def trigger_schedule_now(schedule_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.schedules
                SET next_run_at = NOW(), updated_at = NOW()
                WHERE id = %s AND is_enabled = true
                RETURNING id, name
                """,
                (schedule_id,),
            )
            row = cur.fetchone()
            conn.commit()

    return cast(dict[str, Any] | None, row)


def get_schedule_identity(schedule_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, task_type FROM nexus.schedules WHERE id = %s",
                (schedule_id,),
            )
            return cast(dict[str, Any] | None, cur.fetchone())


def get_run_history(task_type: str, limit: int) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, started_at, completed_at, status,
                    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds,
                    raw_output
                FROM nexus.run_history
                WHERE task_type = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (task_type, limit),
            )
            return cast(list[dict[str, Any]], cur.fetchall())
