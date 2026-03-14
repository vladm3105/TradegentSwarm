"""Business logic service for watchlist endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException

from ..repositories import watchlist_repository


SOURCE_TYPE_ORDER = {
    "manual": 1,
    "scanner": 2,
    "auto": 3,
}


def list_watchlists() -> list[dict[str, Any]]:
    rows = watchlist_repository.list_watchlists()
    rows.sort(
        key=lambda row: (
            not bool(row["is_pinned"]),
            not bool(row["is_default"]),
            SOURCE_TYPE_ORDER.get(str(row["source_type"]), 99),
            str(row["name"]).lower(),
        )
    )
    return rows


def create_watchlist(name: str, description: str | None, color: str | None, is_pinned: bool) -> dict[str, Any]:
    normalized_name = name.strip()
    if watchlist_repository.watchlist_name_exists(normalized_name):
        raise HTTPException(status_code=409, detail="Watchlist name already exists")
    return watchlist_repository.create_watchlist(
        name=normalized_name,
        description=description,
        color=color,
        is_pinned=is_pinned,
    )


def create_watchlist_entry(
    watchlist_id: int | None,
    ticker: str,
    entry_trigger: str,
    entry_price: float | None,
    invalidation: str | None,
    invalidation_price: float | None,
    expires_at: datetime | None,
    priority: str,
    source: str | None,
    source_analysis: str | None,
    notes: str | None,
) -> dict[str, Any]:
    normalized_ticker = ticker.strip().upper()
    normalized_trigger = entry_trigger.strip()

    if not normalized_ticker:
        raise HTTPException(status_code=400, detail="Ticker is required")
    if len(normalized_ticker) > 10:
        raise HTTPException(status_code=400, detail="Ticker too long")
    if not normalized_trigger:
        raise HTTPException(status_code=400, detail="Entry trigger is required")

    normalized_priority = priority.strip().lower()
    if normalized_priority not in {"high", "medium", "low"}:
        raise HTTPException(status_code=400, detail="Priority must be high, medium, or low")

    created = watchlist_repository.create_watchlist_entry(
        {
            "watchlist_id": watchlist_id,
            "ticker": normalized_ticker,
            "entry_trigger": normalized_trigger,
            "entry_price": entry_price,
            "invalidation": invalidation,
            "invalidation_price": invalidation_price,
            "expires_at": expires_at,
            "priority": normalized_priority,
            "source": source,
            "source_analysis": source_analysis,
            "notes": notes,
        }
    )

    if not created:
        raise HTTPException(status_code=500, detail="Failed to create watchlist entry")

    return created


def update_watchlist(watchlist_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    if "name" in updates and updates["name"] is not None:
        updates["name"] = str(updates["name"]).strip()
        if watchlist_repository.watchlist_name_exists(updates["name"], exclude_id=watchlist_id):
            raise HTTPException(status_code=409, detail="Watchlist name already exists")

    result = watchlist_repository.update_watchlist(watchlist_id=watchlist_id, updates=updates)
    if not result:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return result


def delete_watchlist(watchlist_id: int) -> dict[str, Any]:
    watchlist = watchlist_repository.get_watchlist_metadata(watchlist_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    if watchlist["is_default"]:
        raise HTTPException(status_code=422, detail="Default watchlist cannot be deleted")
    if watchlist["source_type"] != "manual":
        raise HTTPException(status_code=422, detail="Only manual watchlists can be deleted")

    entry_count = watchlist_repository.get_watchlist_entry_count(watchlist_id)
    if entry_count > 0:
        raise HTTPException(status_code=422, detail="Only empty watchlists can be deleted")

    watchlist_repository.delete_watchlist(watchlist_id)
    return {"deleted": True}


def list_watchlist_entries(
    status: Optional[str],
    priority: Optional[str],
    watchlist_id: Optional[int],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    total, entries, stats_row, by_priority = watchlist_repository.list_watchlist_entries(
        status=status,
        priority=priority,
        watchlist_id=watchlist_id,
        limit=limit,
        offset=offset,
    )
    return {
        "entries": entries,
        "total": total,
        "stats": {
            "total": stats_row["total"],
            "active": stats_row["active"],
            "triggered": stats_row["triggered"],
            "expired": stats_row["expired"],
            "invalidated": stats_row["invalidated"],
            "by_priority": by_priority,
        },
    }


def get_watchlist_entry(entry_id: int) -> dict[str, Any]:
    row = watchlist_repository.get_watchlist_entry(entry_id)
    if not row:
        raise HTTPException(status_code=404, detail="Watchlist entry not found")
    return row


def get_watchlist_stats(watchlist_id: Optional[int]) -> dict[str, Any]:
    stats_row, by_priority = watchlist_repository.get_watchlist_stats(watchlist_id)
    return {
        "total": stats_row["total"],
        "active": stats_row["active"],
        "triggered": stats_row["triggered"],
        "expired": stats_row["expired"],
        "invalidated": stats_row["invalidated"],
        "by_priority": by_priority,
    }
