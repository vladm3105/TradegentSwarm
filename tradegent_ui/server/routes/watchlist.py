"""Watchlist API endpoints for named watchlists and watch entries."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services import watchlist_service

router = APIRouter(tags=["watchlist"])
log = logging.getLogger(__name__)


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
        rows = watchlist_service.list_watchlists()
        watchlists = [serialize_watchlist(dict(row)) for row in rows]
        return WatchlistsResponse(watchlists=watchlists)
    except Exception as e:
        log.error(f"Failed to list watchlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/watchlists", response_model=WatchlistSummary)
async def create_watchlist(payload: CreateWatchlistRequest):
    """Create a manual watchlist."""
    try:
        row = watchlist_service.create_watchlist(
            name=payload.name,
            description=payload.description,
            color=payload.color,
            is_pinned=payload.is_pinned,
        )
        return serialize_watchlist(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to create watchlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/api/watchlists/{watchlist_id}", response_model=WatchlistSummary)
async def update_watchlist(watchlist_id: int, payload: UpdateWatchlistRequest):
    """Update a watchlist."""
    updates = payload.model_dump(exclude_none=True)

    try:
        row = watchlist_service.update_watchlist(watchlist_id=watchlist_id, updates=updates)
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
        return watchlist_service.delete_watchlist(watchlist_id)
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
    try:
        result = watchlist_service.list_watchlist_entries(
            status=status,
            priority=priority,
            watchlist_id=watchlist_id,
            limit=limit,
            offset=offset,
        )
        entries = [serialize_entry(dict(row)) for row in result["entries"]]
        stats = WatchlistStats(**result["stats"])
        return WatchlistListResponse(entries=entries, total=result["total"], stats=stats)
    except Exception as e:
        log.error(f"Failed to list watchlist entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/watchlist/detail/{entry_id}", response_model=WatchlistEntry)
async def get_watchlist_detail(entry_id: int):
    """Get watchlist entry detail by ID."""
    try:
        row = watchlist_service.get_watchlist_entry(entry_id)
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
    try:
        stats = watchlist_service.get_watchlist_stats(watchlist_id=watchlist_id)
        return WatchlistStats(**stats)
    except Exception as e:
        log.error(f"Failed to get watchlist stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
