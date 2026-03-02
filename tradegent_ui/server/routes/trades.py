"""
Trades API endpoints.
Serves trade journal data from the trades table.
"""

import logging
from typing import Optional
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/api/trades", tags=["trades"])
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
class TradeSummary(BaseModel):
    """Summary for trade list."""
    id: int
    ticker: str
    direction: Optional[str] = None
    entry_date: str
    entry_price: float
    entry_size: float
    status: str
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_dollars: Optional[float] = None
    pnl_pct: Optional[float] = None
    thesis: Optional[str] = None
    source_type: Optional[str] = None


class TradeStats(BaseModel):
    """Trade statistics."""
    total_trades: int
    open_trades: int
    closed_trades: int
    total_pnl: float
    win_rate: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float


class TradeListResponse(BaseModel):
    """Response for trade list."""
    trades: list[TradeSummary]
    total: int
    stats: TradeStats


class TradeDetailResponse(BaseModel):
    """Full trade detail response."""
    id: int
    ticker: str
    direction: Optional[str] = None
    entry_date: str
    entry_price: float
    entry_size: float
    entry_type: Optional[str] = None
    status: str
    current_size: Optional[float] = None
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_dollars: Optional[float] = None
    pnl_pct: Optional[float] = None
    thesis: Optional[str] = None
    source_analysis: Optional[str] = None
    source_type: Optional[str] = None
    review_status: Optional[str] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    # Option fields
    full_symbol: Optional[str] = None
    option_underlying: Optional[str] = None
    option_expiration: Optional[str] = None
    option_strike: Optional[float] = None
    option_type: Optional[str] = None


@router.get("/list", response_model=TradeListResponse)
async def list_trades(
    status: Optional[str] = Query(None, pattern="^(open|closed|cancelled|all)$"),
    ticker: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List trades with optional filtering."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build where clause
                conditions = []
                params = []

                if status and status != "all":
                    conditions.append("status = %s")
                    params.append(status)

                if ticker:
                    conditions.append("ticker = %s")
                    params.append(ticker.upper())

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Get total count
                cur.execute(f"SELECT COUNT(*) as cnt FROM nexus.trades {where_clause}", params)
                total = cur.fetchone()["cnt"]

                # Get trades
                cur.execute(f"""
                    SELECT
                        id,
                        ticker,
                        direction,
                        entry_date,
                        entry_price,
                        entry_size,
                        status,
                        exit_date,
                        exit_price,
                        pnl_dollars,
                        pnl_pct,
                        thesis,
                        source_type
                    FROM nexus.trades
                    {where_clause}
                    ORDER BY entry_date DESC
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])

                rows = cur.fetchall()
                trades = []
                for row in rows:
                    trades.append(TradeSummary(
                        id=row["id"],
                        ticker=row["ticker"],
                        direction=row["direction"],
                        entry_date=row["entry_date"].isoformat() if row["entry_date"] else "",
                        entry_price=float(row["entry_price"]) if row["entry_price"] else 0,
                        entry_size=float(row["entry_size"]) if row["entry_size"] else 0,
                        status=row["status"],
                        exit_date=row["exit_date"].isoformat() if row["exit_date"] else None,
                        exit_price=float(row["exit_price"]) if row["exit_price"] else None,
                        pnl_dollars=float(row["pnl_dollars"]) if row["pnl_dollars"] else None,
                        pnl_pct=float(row["pnl_pct"]) if row["pnl_pct"] else None,
                        thesis=row["thesis"],
                        source_type=row["source_type"],
                    ))

                # Get stats
                cur.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE status = 'open') as open_trades,
                        COUNT(*) FILTER (WHERE status = 'closed') as closed_trades,
                        COALESCE(SUM(pnl_dollars), 0) as total_pnl,
                        COALESCE(
                            COUNT(*) FILTER (WHERE pnl_dollars > 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE status = 'closed'), 0),
                            0
                        ) as win_rate,
                        COALESCE(AVG(pnl_dollars) FILTER (WHERE pnl_dollars > 0), 0) as avg_win,
                        COALESCE(AVG(pnl_dollars) FILTER (WHERE pnl_dollars < 0), 0) as avg_loss,
                        COALESCE(MAX(pnl_dollars), 0) as best_trade,
                        COALESCE(MIN(pnl_dollars), 0) as worst_trade
                    FROM nexus.trades
                """)
                stats_row = cur.fetchone()

                stats = TradeStats(
                    total_trades=stats_row["total_trades"],
                    open_trades=stats_row["open_trades"],
                    closed_trades=stats_row["closed_trades"],
                    total_pnl=float(stats_row["total_pnl"]),
                    win_rate=float(stats_row["win_rate"]),
                    avg_win=float(stats_row["avg_win"]),
                    avg_loss=float(stats_row["avg_loss"]),
                    best_trade=float(stats_row["best_trade"]),
                    worst_trade=float(stats_row["worst_trade"]),
                )

                return TradeListResponse(trades=trades, total=total, stats=stats)

    except Exception as e:
        log.error(f"Failed to list trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{trade_id}", response_model=TradeDetailResponse)
async def get_trade_detail(trade_id: int):
    """Get full trade detail by ID."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id, ticker, direction, entry_date, entry_price, entry_size,
                        entry_type, status, current_size, exit_date, exit_price,
                        exit_reason, pnl_dollars, pnl_pct, thesis, source_analysis,
                        source_type, review_status, stop_loss, target_price,
                        full_symbol, option_underlying, option_expiration,
                        option_strike, option_type
                    FROM nexus.trades
                    WHERE id = %s
                """, (trade_id,))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Trade not found")

                return TradeDetailResponse(
                    id=row["id"],
                    ticker=row["ticker"],
                    direction=row["direction"],
                    entry_date=row["entry_date"].isoformat() if row["entry_date"] else "",
                    entry_price=float(row["entry_price"]) if row["entry_price"] else 0,
                    entry_size=float(row["entry_size"]) if row["entry_size"] else 0,
                    entry_type=row["entry_type"],
                    status=row["status"],
                    current_size=float(row["current_size"]) if row["current_size"] else None,
                    exit_date=row["exit_date"].isoformat() if row["exit_date"] else None,
                    exit_price=float(row["exit_price"]) if row["exit_price"] else None,
                    exit_reason=row["exit_reason"],
                    pnl_dollars=float(row["pnl_dollars"]) if row["pnl_dollars"] else None,
                    pnl_pct=float(row["pnl_pct"]) if row["pnl_pct"] else None,
                    thesis=row["thesis"],
                    source_analysis=row["source_analysis"],
                    source_type=row["source_type"],
                    review_status=row["review_status"],
                    stop_loss=float(row["stop_loss"]) if row["stop_loss"] else None,
                    target_price=float(row["target_price"]) if row["target_price"] else None,
                    full_symbol=row["full_symbol"],
                    option_underlying=row["option_underlying"],
                    option_expiration=row["option_expiration"].isoformat() if row["option_expiration"] else None,
                    option_strike=float(row["option_strike"]) if row["option_strike"] else None,
                    option_type=row["option_type"],
                )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get trade detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=TradeStats)
async def get_trade_stats():
    """Get overall trade statistics."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total_trades,
                        COUNT(*) FILTER (WHERE status = 'open') as open_trades,
                        COUNT(*) FILTER (WHERE status = 'closed') as closed_trades,
                        COALESCE(SUM(pnl_dollars), 0) as total_pnl,
                        COALESCE(
                            COUNT(*) FILTER (WHERE pnl_dollars > 0) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE status = 'closed'), 0),
                            0
                        ) as win_rate,
                        COALESCE(AVG(pnl_dollars) FILTER (WHERE pnl_dollars > 0), 0) as avg_win,
                        COALESCE(AVG(pnl_dollars) FILTER (WHERE pnl_dollars < 0), 0) as avg_loss,
                        COALESCE(MAX(pnl_dollars), 0) as best_trade,
                        COALESCE(MIN(pnl_dollars), 0) as worst_trade
                    FROM nexus.trades
                """)
                row = cur.fetchone()

                return TradeStats(
                    total_trades=row["total_trades"],
                    open_trades=row["open_trades"],
                    closed_trades=row["closed_trades"],
                    total_pnl=float(row["total_pnl"]),
                    win_rate=float(row["win_rate"]),
                    avg_win=float(row["avg_win"]),
                    avg_loss=float(row["avg_loss"]),
                    best_trade=float(row["best_trade"]),
                    worst_trade=float(row["worst_trade"]),
                )

    except Exception as e:
        log.error(f"Failed to get trade stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
