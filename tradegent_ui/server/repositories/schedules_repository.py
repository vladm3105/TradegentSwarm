"""Schedule repository with all SQL operations for schedule management."""

from __future__ import annotations

from typing import cast
from typing import Any

from psycopg import sql

from ..database import get_db_connection


ALLOWED_UPDATE_FIELDS = {
    "name",
    "task_type",
    "is_enabled",
    "frequency",
    "time_of_day",
    "day_of_week",
    "interval_minutes",
}


def create_schedule(data: dict[str, Any]) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.schedules (
                    name,
                    task_type,
                    frequency,
                    is_enabled,
                    time_of_day,
                    day_of_week,
                    interval_minutes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["name"],
                    data["task_type"],
                    data["frequency"],
                    data.get("is_enabled", True),
                    data.get("time_of_day"),
                    data.get("day_of_week"),
                    data.get("interval_minutes"),
                ),
            )
            row = cur.fetchone()
            conn.commit()

    return cast(int, row["id"])


def list_schedules() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.task_type,
                    s.frequency,
                    s.is_enabled,
                    s.time_of_day,
                    s.day_of_week,
                    s.interval_minutes,
                    s.next_run_at,
                    s.last_run_at,
                    s.last_run_status,
                    s.fail_count,
                    s.consecutive_fails,
                    ar.active_started_at,
                    CASE
                        WHEN ar.active_started_at IS NOT NULL THEN COALESCE(ss.current_task, s.task_type)
                        ELSE NULL
                    END AS active_task_label,
                    CASE
                        WHEN ar.active_started_at IS NOT NULL THEN ss.last_heartbeat
                        ELSE NULL
                    END AS active_heartbeat_at
                FROM nexus.schedules AS s
                LEFT JOIN LATERAL (
                    SELECT rh.started_at AS active_started_at
                    FROM nexus.run_history AS rh
                    WHERE rh.schedule_id = s.id
                      AND rh.status = 'running'
                    ORDER BY rh.started_at DESC
                    LIMIT 1
                ) AS ar ON TRUE
                LEFT JOIN nexus.service_status AS ss
                    ON ss.id = 1
                ORDER BY s.next_run_at ASC NULLS LAST
                """
            )
            return cast(list[dict[str, Any]], cur.fetchall())


def get_schedule(schedule_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.name,
                    s.task_type,
                    s.frequency,
                    s.is_enabled,
                    s.time_of_day,
                    s.day_of_week,
                    s.interval_minutes,
                    s.next_run_at,
                    s.last_run_at,
                    s.last_run_status,
                    s.fail_count,
                    s.consecutive_fails,
                    ar.active_started_at,
                    CASE
                        WHEN ar.active_started_at IS NOT NULL THEN COALESCE(ss.current_task, s.task_type)
                        ELSE NULL
                    END AS active_task_label,
                    CASE
                        WHEN ar.active_started_at IS NOT NULL THEN ss.last_heartbeat
                        ELSE NULL
                    END AS active_heartbeat_at
                FROM nexus.schedules AS s
                LEFT JOIN LATERAL (
                    SELECT rh.started_at AS active_started_at
                    FROM nexus.run_history AS rh
                    WHERE rh.schedule_id = s.id
                      AND rh.status = 'running'
                    ORDER BY rh.started_at DESC
                    LIMIT 1
                ) AS ar ON TRUE
                LEFT JOIN nexus.service_status AS ss
                    ON ss.id = 1
                WHERE s.id = %s
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
