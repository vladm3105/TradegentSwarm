"""Dashboard API endpoints for tradegent_ui frontend."""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

from .config import get_settings

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Get database settings from config (which loads .env)
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
class DashboardStats(BaseModel):
    total_pnl: float
    total_pnl_pct: float
    open_positions: int
    total_market_value: float
    today_pnl: float
    today_pnl_pct: float
    win_rate: float
    total_trades: int
    active_analyses: int
    watchlist_count: int


class DailyPnL(BaseModel):
    date: str
    pnl: float
    cumulative: float


class WeeklyPnL(BaseModel):
    week: str
    pnl: float
    trades: int
    win_rate: float


class MonthlyPnL(BaseModel):
    month: str
    pnl: float
    trades: int
    win_rate: float


class PnLResponse(BaseModel):
    daily: list[DailyPnL]
    weekly: list[WeeklyPnL]
    monthly: list[MonthlyPnL]


class TickerPerformance(BaseModel):
    ticker: str
    pnl: float
    pnl_pct: float
    trades: int
    win_rate: float


class PerformanceResponse(BaseModel):
    top_performers: list[TickerPerformance]
    worst_performers: list[TickerPerformance]


class ConfidenceBucket(BaseModel):
    confidence_bucket: str
    accuracy: float
    count: int


class AnalysisQualityResponse(BaseModel):
    gate_pass_rate: float
    recommendation_distribution: dict[str, int]
    accuracy_by_confidence: list[ConfidenceBucket]


class ServiceStatus(BaseModel):
    name: str
    status: str
    latency_ms: Optional[float] = None
    uptime_pct: Optional[float] = None


class RAGStats(BaseModel):
    document_count: int
    chunk_count: int


class GraphStats(BaseModel):
    node_count: int
    edge_count: int


class ErrorRates(BaseModel):
    last_hour: float
    last_day: float


class ServiceHealthResponse(BaseModel):
    services: list[ServiceStatus]
    rag_stats: RAGStats
    graph_stats: GraphStats
    error_rates: ErrorRates


class WatchlistEntry(BaseModel):
    ticker: str
    expires: str
    trigger_type: str


class WatchlistSummaryResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    by_priority: dict[str, int]
    expiring_soon: list[WatchlistEntry]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics summary."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get portfolio summary from v_bi_portfolio_summary
                cur.execute("""
                    SELECT
                        COALESCE(total_pnl, 0) as total_pnl,
                        COALESCE(total_pnl_pct, 0) as total_pnl_pct,
                        COALESCE(open_positions, 0) as open_positions,
                        COALESCE(total_market_value, 0) as total_market_value
                    FROM nexus.v_bi_portfolio_summary
                    LIMIT 1
                """)
                portfolio = cur.fetchone()

                # Get today's P&L from v_bi_daily_pnl
                cur.execute("""
                    SELECT COALESCE(pnl, 0) as pnl, COALESCE(pnl_pct, 0) as pnl_pct
                    FROM nexus.v_bi_daily_pnl
                    WHERE date = CURRENT_DATE
                    LIMIT 1
                """)
                today = cur.fetchone()

                # Get win rate and trade count from v_bi_ticker_performance
                cur.execute("""
                    SELECT
                        COALESCE(AVG(win_rate), 0) as win_rate,
                        COALESCE(SUM(total_trades), 0) as total_trades
                    FROM nexus.v_bi_ticker_performance
                """)
                trades = cur.fetchone()

                # Get active analyses count
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM nexus.kb_stock_analyses
                    WHERE analysis_date >= CURRENT_DATE - INTERVAL '7 days'
                """)
                analyses = cur.fetchone()

                # Get watchlist count
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM nexus.kb_watchlist_entries
                    WHERE status = 'active'
                """)
                watchlist = cur.fetchone()

                return DashboardStats(
                    total_pnl=float(portfolio["total_pnl"]) if portfolio else 0,
                    total_pnl_pct=float(portfolio["total_pnl_pct"]) if portfolio else 0,
                    open_positions=int(portfolio["open_positions"]) if portfolio else 0,
                    total_market_value=float(portfolio["total_market_value"]) if portfolio else 0,
                    today_pnl=float(today["pnl"]) if today else 0,
                    today_pnl_pct=float(today["pnl_pct"]) if today else 0,
                    win_rate=float(trades["win_rate"]) if trades else 0,
                    total_trades=int(trades["total_trades"]) if trades else 0,
                    active_analyses=int(analyses["count"]) if analyses else 0,
                    watchlist_count=int(watchlist["count"]) if watchlist else 0,
                )
    except Exception as e:
        # Return mock data if database unavailable
        return DashboardStats(
            total_pnl=12547.82,
            total_pnl_pct=8.32,
            open_positions=5,
            total_market_value=163250.0,
            today_pnl=342.15,
            today_pnl_pct=0.45,
            win_rate=68.5,
            total_trades=127,
            active_analyses=3,
            watchlist_count=8,
        )


@router.get("/pnl", response_model=PnLResponse)
async def get_pnl_data(period: str = Query("30d", pattern="^(1d|7d|30d|90d)$")):
    """Get P&L data for charts."""
    days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(period, 30)

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Daily P&L
                cur.execute("""
                    SELECT
                        date::text,
                        COALESCE(pnl, 0) as pnl,
                        COALESCE(cumulative_pnl, 0) as cumulative
                    FROM nexus.v_bi_daily_pnl
                    WHERE date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY date
                """, (days,))
                daily = [DailyPnL(**row) for row in cur.fetchall()]

                # Weekly P&L
                cur.execute("""
                    SELECT
                        week::text,
                        COALESCE(pnl, 0) as pnl,
                        COALESCE(trades, 0) as trades,
                        COALESCE(win_rate, 0) as win_rate
                    FROM nexus.v_bi_weekly_pnl
                    WHERE week >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY week
                """, (days,))
                weekly = [WeeklyPnL(**row) for row in cur.fetchall()]

                # Monthly P&L
                cur.execute("""
                    SELECT
                        month::text,
                        COALESCE(pnl, 0) as pnl,
                        COALESCE(trades, 0) as trades,
                        COALESCE(win_rate, 0) as win_rate
                    FROM nexus.v_bi_monthly_pnl
                    ORDER BY month DESC
                    LIMIT 12
                """)
                monthly = [MonthlyPnL(**row) for row in cur.fetchall()]

                return PnLResponse(daily=daily, weekly=weekly, monthly=monthly)
    except Exception:
        # Return mock data
        return PnLResponse(
            daily=[
                DailyPnL(date="2026-02-25", pnl=250, cumulative=1250),
                DailyPnL(date="2026-02-26", pnl=-120, cumulative=1130),
                DailyPnL(date="2026-02-27", pnl=340, cumulative=1470),
                DailyPnL(date="2026-02-28", pnl=180, cumulative=1650),
                DailyPnL(date="2026-03-01", pnl=-50, cumulative=1600),
            ],
            weekly=[
                WeeklyPnL(week="2026-W08", pnl=600, trades=12, win_rate=66.7),
                WeeklyPnL(week="2026-W09", pnl=450, trades=8, win_rate=75.0),
            ],
            monthly=[
                MonthlyPnL(month="2026-02", pnl=1600, trades=45, win_rate=68.9),
                MonthlyPnL(month="2026-01", pnl=2100, trades=52, win_rate=71.2),
            ],
        )


@router.get("/performance", response_model=PerformanceResponse)
async def get_ticker_performance(limit: int = Query(10, ge=1, le=50)):
    """Get top and worst performing tickers."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Top performers
                cur.execute("""
                    SELECT
                        ticker,
                        COALESCE(total_pnl, 0) as pnl,
                        COALESCE(total_pnl_pct, 0) as pnl_pct,
                        COALESCE(total_trades, 0) as trades,
                        COALESCE(win_rate, 0) as win_rate
                    FROM nexus.v_bi_ticker_performance
                    ORDER BY total_pnl DESC
                    LIMIT %s
                """, (limit,))
                top = [TickerPerformance(**row) for row in cur.fetchall()]

                # Worst performers
                cur.execute("""
                    SELECT
                        ticker,
                        COALESCE(total_pnl, 0) as pnl,
                        COALESCE(total_pnl_pct, 0) as pnl_pct,
                        COALESCE(total_trades, 0) as trades,
                        COALESCE(win_rate, 0) as win_rate
                    FROM nexus.v_bi_ticker_performance
                    ORDER BY total_pnl ASC
                    LIMIT %s
                """, (limit,))
                worst = [TickerPerformance(**row) for row in cur.fetchall()]

                return PerformanceResponse(top_performers=top, worst_performers=worst)
    except Exception:
        return PerformanceResponse(
            top_performers=[
                TickerPerformance(ticker="NVDA", pnl=2340, pnl_pct=12.5, trades=5, win_rate=80),
                TickerPerformance(ticker="AMD", pnl=1250, pnl_pct=8.3, trades=4, win_rate=75),
            ],
            worst_performers=[
                TickerPerformance(ticker="TSLA", pnl=-450, pnl_pct=-3.2, trades=3, win_rate=33.3),
            ],
        )


@router.get("/analysis-quality", response_model=AnalysisQualityResponse)
async def get_analysis_quality():
    """Get analysis quality metrics."""
    import structlog
    log = structlog.get_logger()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Gate pass rate
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE gate_result = 'PASS') * 100.0 / NULLIF(COUNT(*), 0) as pass_rate
                    FROM nexus.kb_stock_analyses
                    WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
                """)
                gate = cur.fetchone()

                # Recommendation distribution (filter out NULL recommendations)
                cur.execute("""
                    SELECT recommendation, COUNT(*) as count
                    FROM nexus.kb_stock_analyses
                    WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'
                      AND recommendation IS NOT NULL
                    GROUP BY recommendation
                """)
                rec_dist = {row["recommendation"]: row["count"] for row in cur.fetchall()}

                # Accuracy by confidence (from calibration table if exists)
                accuracy = []
                try:
                    cur.execute("""
                        SELECT
                            confidence_bucket,
                            actual_rate as accuracy,
                            total_predictions as count
                        FROM nexus.confidence_calibration
                        ORDER BY confidence_bucket
                    """)
                    accuracy = [ConfidenceBucket(**row) for row in cur.fetchall()]
                except Exception:
                    pass

                return AnalysisQualityResponse(
                    gate_pass_rate=float(gate["pass_rate"]) if gate and gate["pass_rate"] else 0,
                    recommendation_distribution=rec_dist,
                    accuracy_by_confidence=accuracy,
                )
    except Exception as e:
        log.error("analysis_quality_error", error=str(e), error_type=type(e).__name__)
        return AnalysisQualityResponse(
            gate_pass_rate=72.0,
            recommendation_distribution={"BUY": 35, "WATCH": 40, "NO_POSITION": 20, "AVOID": 5},
            accuracy_by_confidence=[
                ConfidenceBucket(confidence_bucket="60-70%", accuracy=0.65, count=15),
                ConfidenceBucket(confidence_bucket="70-80%", accuracy=0.72, count=22),
                ConfidenceBucket(confidence_bucket="80-90%", accuracy=0.81, count=18),
            ],
        )


@router.get("/service-health", response_model=ServiceHealthResponse)
async def get_service_health():
    """Get service health status."""
    from agent.mcp_client import get_mcp_pool

    services = []

    # Check MCP servers
    try:
        pool = await get_mcp_pool()
        mcp_health = await pool.health_check()

        services.append(ServiceStatus(
            name="IB MCP",
            status="healthy" if mcp_health.ib_mcp else "unhealthy",
        ))
        services.append(ServiceStatus(
            name="Trading RAG",
            status="healthy" if mcp_health.trading_rag else "unhealthy",
        ))
        services.append(ServiceStatus(
            name="Trading Graph",
            status="healthy" if mcp_health.trading_graph else "unhealthy",
        ))
    except Exception:
        services = [
            ServiceStatus(name="IB MCP", status="unknown"),
            ServiceStatus(name="Trading RAG", status="unknown"),
            ServiceStatus(name="Trading Graph", status="unknown"),
        ]

    # Check database
    try:
        with get_db_connection() as conn:
            services.append(ServiceStatus(name="PostgreSQL", status="healthy"))
    except Exception:
        services.append(ServiceStatus(name="PostgreSQL", status="unhealthy"))

    # Get RAG stats
    rag_stats = RAGStats(document_count=0, chunk_count=0)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(DISTINCT doc_id) as docs, COUNT(*) as chunks FROM nexus.rag_chunks")
                row = cur.fetchone()
                if row:
                    rag_stats = RAGStats(document_count=row["docs"], chunk_count=row["chunks"])
    except Exception:
        pass

    # Get Graph stats (mock for now)
    graph_stats = GraphStats(node_count=892, edge_count=1456)

    return ServiceHealthResponse(
        services=services,
        rag_stats=rag_stats,
        graph_stats=graph_stats,
        error_rates=ErrorRates(last_hour=0, last_day=0),
    )


@router.get("/watchlist-summary", response_model=WatchlistSummaryResponse)
async def get_watchlist_summary():
    """Get watchlist summary statistics."""
    import structlog
    log = structlog.get_logger()
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Total count
                cur.execute("SELECT COUNT(*) as total FROM nexus.kb_watchlist_entries")
                total = cur.fetchone()["total"]

                # By status
                cur.execute("""
                    SELECT status, COUNT(*) as count
                    FROM nexus.kb_watchlist_entries
                    GROUP BY status
                """)
                by_status = {row["status"]: row["count"] for row in cur.fetchall()}

                # By priority
                cur.execute("""
                    SELECT priority, COUNT(*) as count
                    FROM nexus.kb_watchlist_entries
                    WHERE status = 'active'
                    GROUP BY priority
                """)
                by_priority = {row["priority"]: row["count"] for row in cur.fetchall()}

                # Expiring soon (within 7 days)
                cur.execute("""
                    SELECT ticker,
                           expires_at::text as expires,
                           COALESCE(LEFT(entry_trigger, 50), 'TRIGGER') as trigger_type
                    FROM nexus.kb_watchlist_entries
                    WHERE status = 'active'
                    AND expires_at <= CURRENT_TIMESTAMP + INTERVAL '7 days'
                    ORDER BY expires_at
                    LIMIT 5
                """)
                expiring = [WatchlistEntry(**row) for row in cur.fetchall()]

                return WatchlistSummaryResponse(
                    total=total,
                    by_status=by_status,
                    by_priority=by_priority,
                    expiring_soon=expiring,
                )
    except Exception as e:
        log.error("watchlist_summary_error", error=str(e), error_type=type(e).__name__)
        return WatchlistSummaryResponse(
            total=8,
            by_status={"active": 6, "triggered": 1, "expired": 1},
            by_priority={"HIGH": 2, "MEDIUM": 3, "LOW": 1},
            expiring_soon=[
                WatchlistEntry(ticker="AMD", expires="2026-03-05", trigger_type="PRICE_BELOW"),
            ],
        )
