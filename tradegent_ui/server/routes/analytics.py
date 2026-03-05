"""Analytics and performance routes."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from decimal import Decimal
import structlog

from ..auth import get_current_user, UserClaims
from ..database import get_db_connection

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
    # Calculate date range
    if period == "all":
        date_filter = ""
    else:
        days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[period]
        date_filter = f"AND exit_date >= NOW() - INTERVAL '{days} days'"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get closed trades
            cur.execute(f"""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE pnl_dollars > 0) as winning_trades,
                    COUNT(*) FILTER (WHERE pnl_dollars < 0) as losing_trades,
                    COALESCE(AVG(pnl_dollars) FILTER (WHERE pnl_dollars > 0), 0) as avg_win,
                    COALESCE(AVG(ABS(pnl_dollars)) FILTER (WHERE pnl_dollars < 0), 0) as avg_loss,
                    COALESCE(SUM(pnl_dollars) FILTER (WHERE pnl_dollars > 0), 0) as total_wins,
                    COALESCE(SUM(ABS(pnl_dollars)) FILTER (WHERE pnl_dollars < 0), 0) as total_losses,
                    COALESCE(SUM(pnl_dollars), 0) as total_pnl
                FROM nexus.kb_trade_journals
                WHERE status = 'closed' {date_filter}
            """)
            row = cur.fetchone()

    total_trades = row['total_trades'] or 0
    winning_trades = row['winning_trades'] or 0
    losing_trades = row['losing_trades'] or 0

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_win = float(row['avg_win'] or 0)
    avg_loss = float(row['avg_loss'] or 0)
    total_wins = float(row['total_wins'] or 0)
    total_losses = float(row['total_losses'] or 0)
    total_pnl = float(row['total_pnl'] or 0)

    profit_factor = (total_wins / total_losses) if total_losses > 0 else float('inf') if total_wins > 0 else 0
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

    return PerformanceStats(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=round(win_rate, 2),
        avg_win=round(avg_win, 2),
        avg_loss=round(avg_loss, 2),
        profit_factor=round(profit_factor, 2) if profit_factor != float('inf') else 999.99,
        expectancy=round(expectancy, 2),
        max_drawdown=0.0,  # TODO: Calculate from equity curve
        sharpe_ratio=None,  # TODO: Calculate from returns
        total_pnl=round(total_pnl, 2),
        total_return_pct=0.0,  # TODO: Calculate from initial capital
    )


@router.get("/equity-curve", response_model=list[EquityCurvePoint])
async def get_equity_curve(
    period: str = Query("30d", pattern="^(7d|30d|90d|1y|all)$"),
    user: UserClaims = Depends(get_current_user),
) -> list[EquityCurvePoint]:
    """Get equity curve data."""
    # Calculate date range
    if period == "all":
        date_filter = ""
    else:
        days = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}[period]
        date_filter = f"WHERE exit_date >= NOW() - INTERVAL '{days} days'"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT
                    DATE(exit_date) as trade_date,
                    SUM(pnl_dollars) as daily_pnl
                FROM nexus.kb_trade_journals
                {date_filter}
                AND status = 'closed'
                AND exit_date IS NOT NULL
                GROUP BY DATE(exit_date)
                ORDER BY trade_date
            """)
            rows = cur.fetchall()

    # Build cumulative equity curve
    cumulative = 0.0
    initial_equity = 100000.0  # Assumed starting equity
    curve = []

    for row in rows:
        daily_pnl = float(row['daily_pnl'] or 0)
        cumulative += daily_pnl
        curve.append(EquityCurvePoint(
            date=row['trade_date'].isoformat(),
            equity=initial_equity + cumulative,
            pnl=round(daily_pnl, 2),
            cumulative_pnl=round(cumulative, 2),
        ))

    return curve


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
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COALESCE(source_type, 'Unknown') as setup_type,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE pnl_dollars > 0) as wins,
                    COALESCE(AVG(pnl_dollars), 0) as avg_pnl,
                    COALESCE(SUM(pnl_dollars), 0) as total_pnl
                FROM nexus.kb_trade_journals
                WHERE status = 'closed'
                GROUP BY source_type
                ORDER BY total DESC
            """)
            rows = cur.fetchall()

    return [
        {
            "setup_type": row['setup_type'],
            "total_trades": row['total'],
            "wins": row['wins'],
            "win_rate": round((row['wins'] / row['total'] * 100) if row['total'] else 0, 1),
            "avg_pnl": round(float(row['avg_pnl']), 2),
            "total_pnl": round(float(row['total_pnl']), 2),
        }
        for row in rows
    ]


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
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Trading stats from trade journals
            cur.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    COUNT(*) FILTER (WHERE pnl_dollars > 0) as winning_trades,
                    COUNT(*) FILTER (WHERE pnl_dollars < 0) as losing_trades,
                    COALESCE(SUM(pnl_dollars), 0) as gross_pnl,
                    COALESCE(SUM(fees), 0) as fees,
                    COALESCE(MAX(pnl_dollars) FILTER (WHERE pnl_dollars > 0), 0) as largest_win,
                    COALESCE(MIN(pnl_dollars) FILTER (WHERE pnl_dollars < 0), 0) as largest_loss
                FROM nexus.kb_trade_journals
                WHERE DATE(exit_date) = %s AND status = 'closed'
            """, (date,))
            trade_row = cur.fetchone()

            # Order stats
            cur.execute("""
                SELECT
                    COUNT(*) as submitted,
                    COUNT(*) FILTER (WHERE status = 'filled') as filled,
                    COUNT(*) FILTER (WHERE status IN ('cancelled', 'api_cancelled')) as cancelled,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                FROM nexus.order_history
                WHERE DATE(created_at) = %s
            """, (date,))
            order_row = cur.fetchone()

            # Alert stats
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE is_triggered = TRUE) as triggered,
                    COUNT(*) FILTER (WHERE is_triggered = TRUE AND alert_type = 'stop') as stop_losses_hit,
                    COUNT(*) FILTER (WHERE is_triggered = TRUE AND alert_type = 'target') as targets_hit
                FROM nexus.alerts
                WHERE DATE(triggered_at) = %s OR DATE(created_at) = %s
            """, (date, date))
            alert_row = cur.fetchone()

            # System stats - circuit breaker
            cur.execute("""
                SELECT value
                FROM nexus.settings
                WHERE section = 'safety' AND key = 'circuit_breaker_triggered'
            """)
            cb_row = cur.fetchone()
            cb_triggered = cb_row and cb_row['value'] in ('"true"', 'true', True)

            # API errors count
            cur.execute("""
                SELECT COUNT(*) as error_count
                FROM nexus.run_history
                WHERE DATE(started_at) = %s AND status = 'failed'
            """, (date,))
            error_row = cur.fetchone()

    total_trades = trade_row['total_trades'] or 0
    winning_trades = trade_row['winning_trades'] or 0
    gross_pnl = float(trade_row['gross_pnl'] or 0)
    fees = float(trade_row['fees'] or 0)

    return DailySummaryResponse(
        date=date,
        trading=DailySummaryTradingStats(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=trade_row['losing_trades'] or 0,
            win_rate=round((winning_trades / total_trades * 100) if total_trades else 0, 1),
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(gross_pnl - fees, 2),
            fees=round(fees, 2),
            largest_win=round(float(trade_row['largest_win'] or 0), 2),
            largest_loss=round(float(trade_row['largest_loss'] or 0), 2),
        ),
        orders=DailySummaryOrderStats(
            submitted=order_row['submitted'] or 0 if order_row else 0,
            filled=order_row['filled'] or 0 if order_row else 0,
            cancelled=order_row['cancelled'] or 0 if order_row else 0,
            rejected=order_row['rejected'] or 0 if order_row else 0,
        ),
        alerts=DailySummaryAlertStats(
            triggered=alert_row['triggered'] or 0 if alert_row else 0,
            stop_losses_hit=alert_row['stop_losses_hit'] or 0 if alert_row else 0,
            targets_hit=alert_row['targets_hit'] or 0 if alert_row else 0,
        ),
        system=DailySummarySystemStats(
            circuit_breaker_triggered=cb_triggered,
            max_drawdown_reached=0.0,  # TODO: Track intraday drawdown
            api_errors=error_row['error_count'] or 0 if error_row else 0,
        ),
    )
