"""Business logic service for trade endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..repositories import trades_repository


def _to_trade_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "direction": row["direction"],
        "entry_date": row["entry_date"].isoformat() if row["entry_date"] else "",
        "entry_price": float(row["entry_price"]) if row["entry_price"] else 0,
        "entry_size": float(row["entry_size"]) if row["entry_size"] else 0,
        "status": row["status"],
        "exit_date": row["exit_date"].isoformat() if row["exit_date"] else None,
        "exit_price": float(row["exit_price"]) if row["exit_price"] else None,
        "pnl_dollars": float(row["pnl_dollars"]) if row["pnl_dollars"] else None,
        "pnl_pct": float(row["pnl_pct"]) if row["pnl_pct"] else None,
        "thesis": row["thesis"],
        "source_type": row["source_type"],
    }


def _to_trade_stats(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_trades": row["total_trades"],
        "open_trades": row["open_trades"],
        "closed_trades": row["closed_trades"],
        "total_pnl": float(row["total_pnl"]),
        "win_rate": float(row["win_rate"]),
        "avg_win": float(row["avg_win"]),
        "avg_loss": float(row["avg_loss"]),
        "best_trade": float(row["best_trade"]),
        "worst_trade": float(row["worst_trade"]),
    }


def list_trades(status: str | None, ticker: str | None, limit: int, offset: int) -> dict[str, Any]:
    total, rows = trades_repository.list_trades(status=status, ticker=ticker, limit=limit, offset=offset)
    stats_row = trades_repository.get_trade_stats()
    return {
        "trades": [_to_trade_summary(row) for row in rows],
        "total": total,
        "stats": _to_trade_stats(stats_row),
    }


def get_trade_stats() -> dict[str, Any]:
    return _to_trade_stats(trades_repository.get_trade_stats())


def get_trade_detail(trade_id: int) -> dict[str, Any]:
    row = trades_repository.get_trade_detail(trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")

    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "direction": row["direction"],
        "entry_date": row["entry_date"].isoformat() if row["entry_date"] else "",
        "entry_price": float(row["entry_price"]) if row["entry_price"] else 0,
        "entry_size": float(row["entry_size"]) if row["entry_size"] else 0,
        "entry_type": row["entry_type"],
        "status": row["status"],
        "current_size": float(row["current_size"]) if row["current_size"] else None,
        "exit_date": row["exit_date"].isoformat() if row["exit_date"] else None,
        "exit_price": float(row["exit_price"]) if row["exit_price"] else None,
        "exit_reason": row["exit_reason"],
        "pnl_dollars": float(row["pnl_dollars"]) if row["pnl_dollars"] else None,
        "pnl_pct": float(row["pnl_pct"]) if row["pnl_pct"] else None,
        "thesis": row["thesis"],
        "source_analysis": row["source_analysis"],
        "source_type": row["source_type"],
        "review_status": row["review_status"],
        "stop_loss": float(row["stop_loss"]) if row["stop_loss"] else None,
        "target_price": float(row["target_price"]) if row["target_price"] else None,
        "full_symbol": row["full_symbol"],
        "option_underlying": row["option_underlying"],
        "option_expiration": row["option_expiration"].isoformat() if row["option_expiration"] else None,
        "option_strike": float(row["option_strike"]) if row["option_strike"] else None,
        "option_type": row["option_type"],
    }
