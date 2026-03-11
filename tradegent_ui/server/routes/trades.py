"""
Trades API endpoints.
Serves trade journal data from the trades table.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..services import trades_service

router = APIRouter(prefix="/api/trades", tags=["trades"])
log = logging.getLogger(__name__)


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
        result = trades_service.list_trades(status=status, ticker=ticker, limit=limit, offset=offset)
        return TradeListResponse(
            trades=[TradeSummary(**trade) for trade in result["trades"]],
            total=result["total"],
            stats=TradeStats(**result["stats"]),
        )

    except Exception as e:
        log.error(f"Failed to list trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{trade_id}", response_model=TradeDetailResponse)
async def get_trade_detail(trade_id: int):
    """Get full trade detail by ID."""
    try:
        result = trades_service.get_trade_detail(trade_id)
        return TradeDetailResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get trade detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=TradeStats)
async def get_trade_stats():
    """Get overall trade statistics."""
    try:
        row = trades_service.get_trade_stats()
        return TradeStats(**row)

    except Exception as e:
        log.error(f"Failed to get trade stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
