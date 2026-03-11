"""Analytics and performance routes."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
import structlog

from ..auth import get_current_user, UserClaims
from ..services import analytics_service

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class PerformanceStats(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    total_pnl: float
    total_return_pct: float


class EquityCurvePoint(BaseModel):
    date: str
    equity: float
    pnl: float
    cumulative_pnl: float


class PositionHeatmapEntry(BaseModel):
    ticker: str
    sector: Optional[str]
    market_value: float
    weight_pct: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class SectorExposure(BaseModel):
    sector: str
    market_value: float
    weight_pct: float
    tickers: list[str]


@router.get("/performance", response_model=PerformanceStats)
async def get_performance_stats(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y|all)$"),
    user: UserClaims = Depends(get_current_user),
) -> PerformanceStats:
    """Get trading performance statistics."""
    return PerformanceStats(**analytics_service.get_performance_stats(period))


@router.get("/equity-curve", response_model=list[EquityCurvePoint])
async def get_equity_curve(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y|all)$"),
    user: UserClaims = Depends(get_current_user),
) -> list[EquityCurvePoint]:
    """Get equity curve data."""
    return [EquityCurvePoint(**row) for row in analytics_service.get_equity_curve(period)]


@router.get("/position-heatmap", response_model=list[PositionHeatmapEntry])
async def get_position_heatmap(
    user: UserClaims = Depends(get_current_user),
) -> list[PositionHeatmapEntry]:
    """Get current position heat map data."""
    try:
        from ..mcp_client import get_mcp_pool
        pool = await get_mcp_pool()

        result = await pool.call_ib_mcp("get_positions", {})
        if not result.success or not result.result:
            return []

        positions = result.result
        total_value = sum(abs(float(p.get('marketValue', 0))) for p in positions)

        heatmap = []
        for pos in positions:
            market_value = float(pos.get('marketValue', 0))
            unrealized_pnl = float(pos.get('unrealizedPnl', 0))
            avg_cost = float(pos.get('avgCost', 0))
            quantity = float(pos.get('quantity', 0))
            cost_basis = avg_cost * abs(quantity) if avg_cost and quantity else 0

            heatmap.append(PositionHeatmapEntry(
                ticker=pos.get('symbol', 'UNKNOWN'),
                sector=pos.get('sector'),
                market_value=round(market_value, 2),
                weight_pct=round((abs(market_value) / total_value * 100) if total_value else 0, 2),
                unrealized_pnl=round(unrealized_pnl, 2),
                unrealized_pnl_pct=round((unrealized_pnl / cost_basis * 100) if cost_basis else 0, 2),
            ))

        return sorted(heatmap, key=lambda x: abs(x.market_value), reverse=True)

    except Exception as e:
        log.error("position_heatmap.failed", error=str(e))
        return []


@router.get("/sector-exposure", response_model=list[SectorExposure])
async def get_sector_exposure(
    user: UserClaims = Depends(get_current_user),
) -> list[SectorExposure]:
    """Get sector exposure breakdown."""
    heatmap = await get_position_heatmap(user)

    # Group by sector
    sectors: dict[str, dict] = {}
    for pos in heatmap:
        sector = pos.sector or "Unknown"
        if sector not in sectors:
            sectors[sector] = {"market_value": 0.0, "tickers": []}
        sectors[sector]["market_value"] += pos.market_value
        sectors[sector]["tickers"].append(pos.ticker)

    total_value = sum(s["market_value"] for s in sectors.values())

    exposure = [
        SectorExposure(
            sector=sector,
            market_value=round(data["market_value"], 2),
            weight_pct=round((data["market_value"] / total_value * 100) if total_value else 0, 2),
            tickers=data["tickers"],
        )
        for sector, data in sectors.items()
    ]

    return sorted(exposure, key=lambda x: abs(x.market_value), reverse=True)


class PositionSizeRequest(BaseModel):
    account_size: float
    risk_per_trade_pct: float = 1.0  # Default 1%
    entry_price: float
    stop_loss_price: float


class PositionSizeResult(BaseModel):
    position_size: int
    dollar_risk: float
    risk_per_share: float
    total_cost: float
    portfolio_weight_pct: float


@router.post("/position-size", response_model=PositionSizeResult)
async def calculate_position_size(
    request: PositionSizeRequest,
    user: UserClaims = Depends(get_current_user),
) -> PositionSizeResult:
    """Calculate optimal position size based on risk parameters."""
    dollar_risk = request.account_size * (request.risk_per_trade_pct / 100)
    risk_per_share = abs(request.entry_price - request.stop_loss_price)

    if risk_per_share == 0:
        position_size = 0
    else:
        position_size = int(dollar_risk / risk_per_share)

    total_cost = position_size * request.entry_price
    portfolio_weight = (total_cost / request.account_size * 100) if request.account_size else 0

    return PositionSizeResult(
        position_size=position_size,
        dollar_risk=round(dollar_risk, 2),
        risk_per_share=round(risk_per_share, 2),
        total_cost=round(total_cost, 2),
        portfolio_weight_pct=round(portfolio_weight, 2),
    )


@router.get("/win-rate-by-setup")
async def get_win_rate_by_setup(
    user: UserClaims = Depends(get_current_user),
):
    """Get win rate breakdown by trade setup type."""
    return analytics_service.get_win_rate_by_setup()


class DailySummaryTradingStats(BaseModel):
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    gross_pnl: float
    net_pnl: float
    fees: float
    largest_win: float
    largest_loss: float


class DailySummaryOrderStats(BaseModel):
    submitted: int
    filled: int
    cancelled: int
    rejected: int


class DailySummaryAlertStats(BaseModel):
    triggered: int
    stop_losses_hit: int
    targets_hit: int


class DailySummarySystemStats(BaseModel):
    circuit_breaker_triggered: bool
    max_drawdown_reached: float
    api_errors: int


class DailySummaryResponse(BaseModel):
    date: str
    trading: DailySummaryTradingStats
    orders: DailySummaryOrderStats
    alerts: DailySummaryAlertStats
    system: DailySummarySystemStats


@router.get("/daily-summary", response_model=DailySummaryResponse)
async def get_daily_summary(
    date: str = Query(default=None, description="Date in YYYY-MM-DD format"),
    user: UserClaims = Depends(get_current_user),
) -> DailySummaryResponse:
    """Get comprehensive daily trading summary."""
    return DailySummaryResponse(**analytics_service.get_daily_summary(date))
