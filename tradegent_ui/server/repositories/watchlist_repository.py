"""Watchlist repository with SQL operations for watchlist endpoints."""

from __future__ import annotations

from typing import Any, Optional, cast

from psycopg import sql

from ..database import get_db_connection


def _build_entry_filters(
    status: Optional[str],
    priority: Optional[str],
    watchlist_id: Optional[int],
) -> tuple[str, list[Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if status and status != "all":
        conditions.append("w.status = %s")
        params.append(status)

    if priority:
        conditions.append("w.priority = %s")
        params.append(priority)

    if watchlist_id is not None:
        conditions.append("w.watchlist_id = %s")
        params.append(watchlist_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def list_watchlists() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    wl.id,
                    wl.name,
                    wl.description,
                    wl.source_type,
                    wl.source_ref,
                    wl.color,
                    wl.is_default,
                    wl.is_pinned,
                    wl.created_at,
                    wl.updated_at,
                    COUNT(w.id) AS total_entries,
                    COUNT(*) FILTER (WHERE w.status = 'active') AS active_entries
                FROM nexus.watchlists wl
                LEFT JOIN nexus.watchlist w ON w.watchlist_id = wl.id
                GROUP BY wl.id
                ORDER BY wl.is_pinned DESC, wl.is_default DESC, wl.name ASC
                """
            )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def watchlist_name_exists(name: str, exclude_id: int | None = None) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if exclude_id is None:
                cur.execute(
                    "SELECT 1 FROM nexus.watchlists WHERE lower(name) = lower(%s) LIMIT 1",
                    (name,),
                )
            else:
                cur.execute(
                    """
                    SELECT 1
                    FROM nexus.watchlists
                    WHERE lower(name) = lower(%s) AND id <> %s
                    LIMIT 1
                    """,
                    (name, exclude_id),
                )
            row = cur.fetchone()
    return row is not None


def create_watchlist(name: str, description: str | None, color: str | None, is_pinned: bool) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.watchlists (name, description, source_type, color, is_pinned)
                VALUES (%s, %s, 'manual', %s, %s)
                RETURNING id, name, description, source_type, source_ref, color,
                          is_default, is_pinned, created_at, updated_at
                """,
                (name, description, color, is_pinned),
            )
            row = cur.fetchone()
        conn.commit()
    result = cast(dict[str, Any], row)
    result["total_entries"] = 0
    result["active_entries"] = 0
    return result


def update_watchlist(watchlist_id: int, updates: dict[str, Any]) -> dict[str, Any] | None:
    if not updates:
        return None

    allowed_fields = {"name", "description", "color", "is_pinned"}
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    if not filtered:
        return None

    assignments = []
    values: list[Any] = []
    for key, value in filtered.items():
        assignments.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
        values.append(value)

    values.append(watchlist_id)

    query = sql.SQL(
        """
        UPDATE nexus.watchlists
        SET {assignments}, updated_at = now()
        WHERE id = %s
        RETURNING *
        """
    ).format(assignments=sql.SQL(", ").join(assignments))

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(values))
            updated = cur.fetchone()
            if not updated:
                conn.commit()
                return None

            cur.execute(
                """
                SELECT
                    COUNT(*) AS total_entries,
                    COUNT(*) FILTER (WHERE status = 'active') AS active_entries
                FROM nexus.watchlist
                WHERE watchlist_id = %s
                """,
                (watchlist_id,),
            )
            counts = cur.fetchone()
        conn.commit()

    result = cast(dict[str, Any], updated)
    result.update(cast(dict[str, Any], counts))
    return result


def get_watchlist_metadata(watchlist_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, source_type, is_default FROM nexus.watchlists WHERE id = %s",
                (watchlist_id,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any] | None, row)


def get_watchlist_entry_count(watchlist_id: int) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM nexus.watchlist WHERE watchlist_id = %s",
                (watchlist_id,),
            )
            row = cur.fetchone()
    return int(row["cnt"])


def delete_watchlist(watchlist_id: int) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nexus.watchlists WHERE id = %s", (watchlist_id,))
        conn.commit()


def list_watchlist_entries(
    status: Optional[str],
    priority: Optional[str],
    watchlist_id: Optional[int],
    limit: int,
    offset: int,
) -> tuple[int, list[dict[str, Any]], dict[str, Any], dict[str, int]]:
    where_clause, params = _build_entry_filters(status, priority, watchlist_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) as cnt FROM nexus.watchlist w {where_clause}",
                params,
            )
            total = int(cur.fetchone()["cnt"])

            cur.execute(
                f"""
                SELECT
                    w.id,
                    w.watchlist_id,
                    wl.name AS watchlist_name,
                    wl.source_type AS watchlist_source_type,
                    wl.color AS watchlist_color,
                    w.ticker,
                    w.entry_trigger,
                    w.entry_price,
                    w.invalidation,
                    w.invalidation_price,
                    w.expires_at,
                    w.priority,
                    w.status,
                    w.source,
                    w.source_analysis,
                    w.notes,
                    w.created_at,
                    CASE
                        WHEN w.expires_at IS NOT NULL THEN
                            EXTRACT(DAY FROM w.expires_at - CURRENT_TIMESTAMP)::int
                        ELSE NULL
                    END as days_until_expiry
                FROM nexus.watchlist w
                LEFT JOIN nexus.watchlists wl ON wl.id = w.watchlist_id
                {where_clause}
                ORDER BY
                    CASE w.priority
                        WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2
                        WHEN 'low' THEN 3
                        ELSE 4
                    END,
                    w.created_at DESC
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            entries = cast(list[dict[str, Any]], cur.fetchall())

            cur.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE w.status = 'active') as active,
                    COUNT(*) FILTER (WHERE w.status = 'triggered') as triggered,
                    COUNT(*) FILTER (WHERE w.status = 'expired') as expired,
                    COUNT(*) FILTER (WHERE w.status = 'invalidated') as invalidated
                FROM nexus.watchlist w
                {where_clause}
                """,
                params,
            )
            stats_row = cast(dict[str, Any], cur.fetchone())

            priority_conditions = ["w.status = 'active'"]
            priority_params: list[Any] = []
            if watchlist_id is not None:
                priority_conditions.append("w.watchlist_id = %s")
                priority_params.append(watchlist_id)
            priority_where = f"WHERE {' AND '.join(priority_conditions)}"

            cur.execute(
                f"""
                SELECT w.priority, COUNT(*) as count
                FROM nexus.watchlist w
                {priority_where}
                GROUP BY w.priority
                """,
                priority_params,
            )
            by_priority = {row["priority"]: row["count"] for row in cur.fetchall()}

    return total, entries, stats_row, cast(dict[str, int], by_priority)


def get_watchlist_entry(entry_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    w.id,
                    w.watchlist_id,
                    wl.name AS watchlist_name,
                    wl.source_type AS watchlist_source_type,
                    wl.color AS watchlist_color,
                    w.ticker,
                    w.entry_trigger,
                    w.entry_price,
                    w.invalidation,
                    w.invalidation_price,
                    w.expires_at,
                    w.priority,
                    w.status,
                    w.source,
                    w.source_analysis,
                    w.notes,
                    w.created_at,
                    CASE
                        WHEN w.expires_at IS NOT NULL THEN
                            EXTRACT(DAY FROM w.expires_at - CURRENT_TIMESTAMP)::int
                        ELSE NULL
                    END as days_until_expiry
                FROM nexus.watchlist w
                LEFT JOIN nexus.watchlists wl ON wl.id = w.watchlist_id
                WHERE w.id = %s
                """,
                (entry_id,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any] | None, row)


def get_watchlist_stats(watchlist_id: Optional[int]) -> tuple[dict[str, Any], dict[str, int]]:
    params: list[Any] = []
    where_clause = "WHERE watchlist_id = %s" if watchlist_id is not None else ""
    if watchlist_id is not None:
        params.append(watchlist_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'active') as active,
                    COUNT(*) FILTER (WHERE status = 'triggered') as triggered,
                    COUNT(*) FILTER (WHERE status = 'expired') as expired,
                    COUNT(*) FILTER (WHERE status = 'invalidated') as invalidated
                FROM nexus.watchlist
                {where_clause}
                """,
                params,
            )
            stats_row = cast(dict[str, Any], cur.fetchone())

            priority_params: list[Any] = []
            priority_where = "WHERE status = 'active'"
            if watchlist_id is not None:
                priority_where += " AND watchlist_id = %s"
                priority_params.append(watchlist_id)

            cur.execute(
                f"""
                SELECT priority, COUNT(*) as count
                FROM nexus.watchlist
                {priority_where}
                GROUP BY priority
                """,
                priority_params,
            )
            by_priority = {row["priority"]: row["count"] for row in cur.fetchall()}

    return stats_row, cast(dict[str, int], by_priority)
