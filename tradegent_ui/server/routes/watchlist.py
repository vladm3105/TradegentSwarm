"""Watchlist API endpoints for named watchlists and watch entries."""

import logging
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import get_settings

router = APIRouter(tags=["watchlist"])
log = logging.getLogger(__name__)

_settings = get_settings()

DB_CONFIG = {
    "host": _settings.pg_host,
    "port": _settings.pg_port,
    "user": _settings.pg_user,
    "password": _settings.pg_pass,
    "dbname": _settings.pg_db,
}


SOURCE_TYPE_ORDER = {
    "manual": 1,
    "scanner": 2,
    "auto": 3,
}


def get_db_connection():
    """Get database connection."""
    return psycopg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
        row_factory=dict_row,
    )


def build_entry_filters(
    status: Optional[str],
    priority: Optional[str],
    watchlist_id: Optional[int],
) -> tuple[str, list[Any]]:
    """Build SQL where clause for watchlist entry filters."""
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


class WatchlistSummary(BaseModel):
    """Named watchlist container."""
    id: int
    name: str
    description: Optional[str] = None
    source_type: str
    source_ref: Optional[str] = None
    color: Optional[str] = None
    is_default: bool
    is_pinned: bool
    total_entries: int
    active_entries: int
    created_at: str
    updated_at: str


class WatchlistsResponse(BaseModel):
    """Named watchlists response."""
    watchlists: list[WatchlistSummary]


class CreateWatchlistRequest(BaseModel):
    """Create a manual watchlist."""
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(default="#3b82f6", pattern="^#[0-9A-Fa-f]{6}$")
    is_pinned: bool = False


class UpdateWatchlistRequest(BaseModel):
    """Update an existing watchlist."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, pattern="^#[0-9A-Fa-f]{6}$")
    is_pinned: Optional[bool] = None


class WatchlistEntry(BaseModel):
    """Watchlist entry summary."""
    id: int
    watchlist_id: Optional[int] = None
    watchlist_name: Optional[str] = None
    watchlist_source_type: Optional[str] = None
    watchlist_color: Optional[str] = None
    ticker: str
    entry_trigger: Optional[str] = None
    entry_price: Optional[float] = None
    invalidation: Optional[str] = None
    invalidation_price: Optional[float] = None
    expires_at: Optional[str] = None
    priority: str
    status: str
    source: Optional[str] = None
    source_analysis: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    days_until_expiry: Optional[int] = None


class WatchlistStats(BaseModel):
    """Watchlist statistics."""
    total: int
    active: int
    triggered: int
    expired: int
    invalidated: int
    by_priority: dict[str, int]


class WatchlistListResponse(BaseModel):
    """Response for watchlist list."""
    entries: list[WatchlistEntry]
    total: int
    stats: WatchlistStats


def serialize_watchlist(row: dict[str, Any]) -> WatchlistSummary:
    """Convert a database row to a watchlist summary model."""
    return WatchlistSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        color=row["color"],
        is_default=bool(row["is_default"]),
        is_pinned=bool(row["is_pinned"]),
        total_entries=row["total_entries"] or 0,
        active_entries=row["active_entries"] or 0,
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
    )


def serialize_entry(row: dict[str, Any]) -> WatchlistEntry:
    """Convert a database row to a watchlist entry model."""
    return WatchlistEntry(
        id=row["id"],
        watchlist_id=row.get("watchlist_id"),
        watchlist_name=row.get("watchlist_name"),
        watchlist_source_type=row.get("watchlist_source_type"),
        watchlist_color=row.get("watchlist_color"),
        ticker=row["ticker"],
        entry_trigger=row["entry_trigger"],
        entry_price=float(row["entry_price"]) if row["entry_price"] is not None else None,
        invalidation=row["invalidation"],
        invalidation_price=float(row["invalidation_price"]) if row["invalidation_price"] is not None else None,
        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
        priority=row["priority"] or "medium",
        status=row["status"],
        source=row["source"],
        source_analysis=row["source_analysis"],
        notes=row["notes"],
        created_at=row["created_at"].isoformat() if row["created_at"] else "",
        days_until_expiry=row["days_until_expiry"],
    )


@router.get("/api/watchlists", response_model=WatchlistsResponse)
async def list_watchlists():
    """List named watchlists with entry counts."""
    try:
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

        watchlists = [serialize_watchlist(dict(row)) for row in rows]
        watchlists.sort(
            key=lambda item: (
                not item.is_pinned,
                not item.is_default,
                SOURCE_TYPE_ORDER.get(item.source_type, 99),
                item.name.lower(),
            )
        )
        return WatchlistsResponse(watchlists=watchlists)
    except Exception as e:
        log.error(f"Failed to list watchlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/watchlists", response_model=WatchlistSummary)
async def create_watchlist(payload: CreateWatchlistRequest):
    """Create a manual watchlist."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM nexus.watchlists WHERE lower(name) = lower(%s) LIMIT 1",
                    (payload.name.strip(),),
                )
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="Watchlist name already exists")

                cur.execute(
                    """
                    INSERT INTO nexus.watchlists (name, description, source_type, color, is_pinned)
                    VALUES (%s, %s, 'manual', %s, %s)
                    RETURNING id, name, description, source_type, source_ref, color,
                              is_default, is_pinned, created_at, updated_at
                    """,
                    (payload.name.strip(), payload.description, payload.color, payload.is_pinned),
                )
                row = dict(cur.fetchone())
            conn.commit()

        row["total_entries"] = 0
        row["active_entries"] = 0
        return serialize_watchlist(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to create watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/watchlists/{watchlist_id}", response_model=WatchlistSummary)
async def update_watchlist(watchlist_id: int, payload: UpdateWatchlistRequest):
    """Update a watchlist."""
    updates: list[str] = []
    params: list[Any] = []

    if payload.name is not None:
        updates.append("name = %s")
        params.append(payload.name.strip())
    if payload.description is not None:
        updates.append("description = %s")
        params.append(payload.description)
    if payload.color is not None:
        updates.append("color = %s")
        params.append(payload.color)
    if payload.is_pinned is not None:
        updates.append("is_pinned = %s")
        params.append(payload.is_pinned)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if payload.name is not None:
                    cur.execute(
                        """
                        SELECT 1
                        FROM nexus.watchlists
                        WHERE lower(name) = lower(%s) AND id <> %s
                        LIMIT 1
                        """,
                        (payload.name.strip(), watchlist_id),
                    )
                    if cur.fetchone():
                        raise HTTPException(status_code=409, detail="Watchlist name already exists")

                params.append(watchlist_id)
                cur.execute(
                    f"UPDATE nexus.watchlists SET {', '.join(updates)}, updated_at = now() WHERE id = %s RETURNING *",
                    params,
                )
                updated = cur.fetchone()
                if not updated:
                    raise HTTPException(status_code=404, detail="Watchlist not found")

                row = dict(updated)
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
                counts = dict(cur.fetchone())
            conn.commit()

        row.update(counts)
        return serialize_watchlist(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to update watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/watchlists/{watchlist_id}")
async def delete_watchlist(watchlist_id: int):
    """Delete an empty manual watchlist."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, source_type, is_default FROM nexus.watchlists WHERE id = %s",
                    (watchlist_id,),
                )
                watchlist = cur.fetchone()
                if not watchlist:
                    raise HTTPException(status_code=404, detail="Watchlist not found")
                if watchlist["is_default"]:
                    raise HTTPException(status_code=422, detail="Default watchlist cannot be deleted")
                if watchlist["source_type"] != "manual":
                    raise HTTPException(status_code=422, detail="Only manual watchlists can be deleted")

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM nexus.watchlist WHERE watchlist_id = %s",
                    (watchlist_id,),
                )
                entry_count = cur.fetchone()["cnt"]
                if entry_count > 0:
                    raise HTTPException(status_code=422, detail="Only empty watchlists can be deleted")

                cur.execute("DELETE FROM nexus.watchlists WHERE id = %s", (watchlist_id,))
            conn.commit()
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to delete watchlist {watchlist_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/watchlist/list", response_model=WatchlistListResponse)
async def list_watchlist(
    status: Optional[str] = Query(None, pattern="^(active|triggered|expired|invalidated|all)$"),
    priority: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    watchlist_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List watchlist entries with optional filtering."""
    where_clause, params = build_entry_filters(status, priority, watchlist_id)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) as cnt FROM nexus.watchlist w {where_clause}",
                    params,
                )
                total = cur.fetchone()["cnt"]

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
                entries = [serialize_entry(dict(row)) for row in cur.fetchall()]

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
                stats_row = cur.fetchone()

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

        stats = WatchlistStats(
            total=stats_row["total"],
            active=stats_row["active"],
            triggered=stats_row["triggered"],
            expired=stats_row["expired"],
            invalidated=stats_row["invalidated"],
            by_priority=by_priority,
        )
        return WatchlistListResponse(entries=entries, total=total, stats=stats)
    except Exception as e:
        log.error(f"Failed to list watchlist entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/watchlist/detail/{entry_id}", response_model=WatchlistEntry)
async def get_watchlist_detail(entry_id: int):
    """Get watchlist entry detail by ID."""
    try:
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
                if not row:
                    raise HTTPException(status_code=404, detail="Watchlist entry not found")
                return serialize_entry(dict(row))
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get watchlist detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/watchlist/stats", response_model=WatchlistStats)
async def get_watchlist_stats(
    watchlist_id: Optional[int] = Query(None, ge=1),
):
    """Get watchlist statistics, optionally scoped to a named list."""
    _, params = build_entry_filters(None, None, watchlist_id)
    where_clause = "WHERE watchlist_id = %s" if watchlist_id is not None else ""

    try:
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
                stats_row = cur.fetchone()

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

        return WatchlistStats(
            total=stats_row["total"],
            active=stats_row["active"],
            triggered=stats_row["triggered"],
            expired=stats_row["expired"],
            invalidated=stats_row["invalidated"],
            by_priority=by_priority,
        )
    except Exception as e:
        log.error(f"Failed to get watchlist stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
