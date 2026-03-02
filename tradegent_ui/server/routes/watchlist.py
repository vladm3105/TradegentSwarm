"""
Watchlist API endpoints.
Serves watchlist data from the watchlist table.
"""

import logging
from typing import Optional
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])
log = logging.getLogger(__name__)

_settings = get_settings()

DB_CONFIG = {
    "host": _settings.pg_host,
    "port": _settings.pg_port,
    "user": _settings.pg_user,
    "password": _settings.pg_pass,
    "dbname": _settings.pg_db,
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


# Response models
class WatchlistEntry(BaseModel):
    """Watchlist entry summary."""
    id: int
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
    by_priority: dict


class WatchlistListResponse(BaseModel):
    """Response for watchlist list."""
    entries: list[WatchlistEntry]
    total: int
    stats: WatchlistStats


@router.get("/list", response_model=WatchlistListResponse)
async def list_watchlist(
    status: Optional[str] = Query(None, pattern="^(active|triggered|expired|invalidated|all)$"),
    priority: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List watchlist entries with optional filtering."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build where clause
                conditions = []
                params = []

                if status and status != "all":
                    conditions.append("status = %s")
                    params.append(status)

                if priority:
                    conditions.append("priority = %s")
                    params.append(priority)

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Get total count
                cur.execute(f"SELECT COUNT(*) as cnt FROM nexus.watchlist {where_clause}", params)
                total = cur.fetchone()["cnt"]

                # Get entries
                cur.execute(f"""
                    SELECT
                        id,
                        ticker,
                        entry_trigger,
                        entry_price,
                        invalidation,
                        invalidation_price,
                        expires_at,
                        priority,
                        status,
                        source,
                        source_analysis,
                        notes,
                        created_at,
                        CASE
                            WHEN expires_at IS NOT NULL THEN
                                EXTRACT(DAY FROM expires_at - CURRENT_TIMESTAMP)::int
                            ELSE NULL
                        END as days_until_expiry
                    FROM nexus.watchlist
                    {where_clause}
                    ORDER BY
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'medium' THEN 2
                            WHEN 'low' THEN 3
                            ELSE 4
                        END,
                        created_at DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])

                rows = cur.fetchall()
                entries = []
                for row in rows:
                    entries.append(WatchlistEntry(
                        id=row["id"],
                        ticker=row["ticker"],
                        entry_trigger=row["entry_trigger"],
                        entry_price=float(row["entry_price"]) if row["entry_price"] else None,
                        invalidation=row["invalidation"],
                        invalidation_price=float(row["invalidation_price"]) if row["invalidation_price"] else None,
                        expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
                        priority=row["priority"] or "medium",
                        status=row["status"],
                        source=row["source"],
                        source_analysis=row["source_analysis"],
                        notes=row["notes"],
                        created_at=row["created_at"].isoformat() if row["created_at"] else "",
                        days_until_expiry=row["days_until_expiry"],
                    ))

                # Get stats
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        COUNT(*) FILTER (WHERE status = 'triggered') as triggered,
                        COUNT(*) FILTER (WHERE status = 'expired') as expired,
                        COUNT(*) FILTER (WHERE status = 'invalidated') as invalidated
                    FROM nexus.watchlist
                """)
                stats_row = cur.fetchone()

                # Get by priority (active only)
                cur.execute("""
                    SELECT priority, COUNT(*) as count
                    FROM nexus.watchlist
                    WHERE status = 'active'
                    GROUP BY priority
                """)
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
        log.error(f"Failed to list watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{entry_id}", response_model=WatchlistEntry)
async def get_watchlist_detail(entry_id: int):
    """Get watchlist entry detail by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, ticker, entry_trigger, entry_price, invalidation,
                        invalidation_price, expires_at, priority, status,
                        source, source_analysis, notes, created_at,
                        CASE
                            WHEN expires_at IS NOT NULL THEN
                                EXTRACT(DAY FROM expires_at - CURRENT_TIMESTAMP)::int
                            ELSE NULL
                        END as days_until_expiry
                    FROM nexus.watchlist
                    WHERE id = %s
                """, (entry_id,))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Watchlist entry not found")

                return WatchlistEntry(
                    id=row["id"],
                    ticker=row["ticker"],
                    entry_trigger=row["entry_trigger"],
                    entry_price=float(row["entry_price"]) if row["entry_price"] else None,
                    invalidation=row["invalidation"],
                    invalidation_price=float(row["invalidation_price"]) if row["invalidation_price"] else None,
                    expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
                    priority=row["priority"] or "medium",
                    status=row["status"],
                    source=row["source"],
                    source_analysis=row["source_analysis"],
                    notes=row["notes"],
                    created_at=row["created_at"].isoformat() if row["created_at"] else "",
                    days_until_expiry=row["days_until_expiry"],
                )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get watchlist detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=WatchlistStats)
async def get_watchlist_stats():
    """Get watchlist statistics."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        COUNT(*) FILTER (WHERE status = 'triggered') as triggered,
                        COUNT(*) FILTER (WHERE status = 'expired') as expired,
                        COUNT(*) FILTER (WHERE status = 'invalidated') as invalidated
                    FROM nexus.watchlist
                """)
                stats_row = cur.fetchone()

                # Get by priority (active only)
                cur.execute("""
                    SELECT priority, COUNT(*) as count
                    FROM nexus.watchlist
                    WHERE status = 'active'
                    GROUP BY priority
                """)
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
