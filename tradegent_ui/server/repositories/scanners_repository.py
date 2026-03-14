"""Scanners repository for scanner configs and historical run results."""

from typing import Any, Optional, cast

from ..database import get_db_connection


def list_scanners(scanner_type: Optional[str], enabled_only: bool) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if scanner_type:
        conditions.append("s.instrument = %s")
        params.append(scanner_type)

    if enabled_only:
        conditions.append("s.is_enabled = true")

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            s.id,
            s.scanner_code,
            s.display_name as name,
            s.description,
            s.instrument as scanner_type,
            s.is_enabled,
            s.auto_analyze,
            s.analysis_type,
            r.started_at as last_run,
            r.status as last_run_status,
            CASE
                WHEN r.raw_output IS NOT NULL THEN
                    (r.raw_output::jsonb->>'candidates_found')::int
                ELSE 0
            END as candidates_count
        FROM nexus.ib_scanners s
        LEFT JOIN LATERAL (
            SELECT started_at, status, raw_output
            FROM nexus.run_history
            WHERE task_type = 'run_scanner'
            AND COALESCE(NULLIF(ticker, ''), raw_output::jsonb->>'scanner') = s.scanner_code
            ORDER BY started_at DESC
            LIMIT 1
        ) r ON true
        {where_clause}
        ORDER BY s.instrument, s.display_name
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def list_scanner_results(scanner_code: Optional[str], limit: int) -> list[dict[str, Any]]:
    conditions = ["task_type = 'run_scanner'"]
    params: list[Any] = []

    if scanner_code:
        conditions.append(
            "COALESCE(NULLIF(ticker, ''), raw_output::jsonb->>'scanner') = %s"
        )
        params.append(scanner_code)

    where_clause = "WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT
            id,
            COALESCE(NULLIF(ticker, ''), raw_output::jsonb->>'scanner') as scanner_code,
            started_at,
            status,
            duration_seconds,
            raw_output
        FROM nexus.run_history
        {where_clause}
        ORDER BY started_at DESC
        LIMIT %s
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params + [limit]))
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def list_latest_candidate_outputs() -> list[Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT raw_output
                FROM nexus.run_history
                WHERE task_type = 'run_scanner'
                AND status = 'completed'
                AND raw_output IS NOT NULL
                AND (raw_output::jsonb->>'candidates_found')::int > 0
                ORDER BY started_at DESC
                LIMIT 5
                """
            )
            rows = cur.fetchall()
    return [row["raw_output"] for row in rows]
