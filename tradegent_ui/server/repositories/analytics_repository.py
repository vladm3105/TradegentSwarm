"""Analytics repository with SQL operations for analytics endpoints."""

from __future__ import annotations

from typing import Any, cast

from ..database import get_db_connection


def get_performance_stats(days: int | None) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if days is None:
                cur.execute(
                    """
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
                    WHERE status = 'closed'
                    """
                )
            else:
                cur.execute(
                    """
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
                    WHERE status = 'closed'
                      AND exit_date >= NOW() - (%s * INTERVAL '1 day')
                    """,
                    (days,),
                )
            row = cur.fetchone()
    return cast(dict[str, Any], row)


def get_equity_curve_rows(days: int | None) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if days is None:
                cur.execute(
                    """
                    SELECT
                        DATE(exit_date) as trade_date,
                        SUM(pnl_dollars) as daily_pnl
                    FROM nexus.kb_trade_journals
                    WHERE status = 'closed'
                      AND exit_date IS NOT NULL
                    GROUP BY DATE(exit_date)
                    ORDER BY trade_date
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT
                        DATE(exit_date) as trade_date,
                        SUM(pnl_dollars) as daily_pnl
                    FROM nexus.kb_trade_journals
                    WHERE status = 'closed'
                      AND exit_date IS NOT NULL
                      AND exit_date >= NOW() - (%s * INTERVAL '1 day')
                    GROUP BY DATE(exit_date)
                    ORDER BY trade_date
                    """,
                    (days,),
                )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def get_win_rate_by_setup_rows() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                """
            )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def get_daily_trade_stats(date_str: str) -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                """,
                (date_str,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any], row)


def get_daily_order_stats(date_str: str) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) as submitted,
                    COUNT(*) FILTER (WHERE status = 'filled') as filled,
                    COUNT(*) FILTER (WHERE status IN ('cancelled', 'api_cancelled')) as cancelled,
                    COUNT(*) FILTER (WHERE status = 'rejected') as rejected
                FROM nexus.order_history
                WHERE DATE(created_at) = %s
                """,
                (date_str,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any] | None, row)


def get_daily_alert_stats(date_str: str) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE is_triggered = TRUE) as triggered,
                    COUNT(*) FILTER (WHERE is_triggered = TRUE AND alert_type = 'stop') as stop_losses_hit,
                    COUNT(*) FILTER (WHERE is_triggered = TRUE AND alert_type = 'target') as targets_hit
                FROM nexus.alerts
                WHERE DATE(triggered_at) = %s OR DATE(created_at) = %s
                """,
                (date_str, date_str),
            )
            row = cur.fetchone()
    return cast(dict[str, Any] | None, row)


def get_circuit_breaker_state() -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT value
                FROM nexus.settings
                WHERE section = 'safety' AND key = 'circuit_breaker_triggered'
                """
            )
            row = cur.fetchone()
    return bool(row and row["value"] in ('"true"', 'true', True))


def get_daily_api_error_count(date_str: str) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) as error_count
                FROM nexus.run_history
                WHERE DATE(started_at) = %s AND status = 'failed'
                """,
                (date_str,),
            )
            row = cur.fetchone()
    return int(row["error_count"] if row else 0)
