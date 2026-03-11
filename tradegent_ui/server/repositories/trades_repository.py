"""Trades repository with SQL operations for trade endpoints."""

from __future__ import annotations

from typing import Any, cast

from psycopg import sql

from ..database import get_db_connection


def _where_clause_and_params(status: str | None, ticker: str | None) -> tuple[sql.SQL, list[Any]]:
    conditions: list[sql.SQL] = []
    params: list[Any] = []

    if status and status != "all":
        conditions.append(sql.SQL("status = %s"))
        params.append(status)

    if ticker:
        conditions.append(sql.SQL("ticker = %s"))
        params.append(ticker.upper())

    if not conditions:
        return sql.SQL(""), params

    where_sql = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(conditions)
    return where_sql, params


def list_trades(status: str | None, ticker: str | None, limit: int, offset: int) -> tuple[int, list[dict[str, Any]]]:
    where_sql, where_params = _where_clause_and_params(status, ticker)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            count_query = sql.SQL("SELECT COUNT(*) as cnt FROM nexus.trades") + where_sql
            cur.execute(count_query, tuple(where_params))
            total = int(cur.fetchone()["cnt"])

            list_query = (
                sql.SQL(
                    """
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
                    """
                )
                + where_sql
                + sql.SQL(
                    """
                    ORDER BY entry_date DESC
                    LIMIT %s OFFSET %s
                    """
                )
            )
            cur.execute(list_query, tuple(where_params + [limit, offset]))
            rows = cur.fetchall()

    return total, cast(list[dict[str, Any]], rows)


def get_trade_stats() -> dict[str, Any]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                """
            )
            row = cur.fetchone()
    return cast(dict[str, Any], row)


def get_trade_detail(trade_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id, ticker, direction, entry_date, entry_price, entry_size,
                    entry_type, status, current_size, exit_date, exit_price,
                    exit_reason, pnl_dollars, pnl_pct, thesis, source_analysis,
                    source_type, review_status, stop_loss, target_price,
                    full_symbol, option_underlying, option_expiration,
                    option_strike, option_type
                FROM nexus.trades
                WHERE id = %s
                """,
                (trade_id,),
            )
            row = cur.fetchone()
    return cast(dict[str, Any] | None, row)
