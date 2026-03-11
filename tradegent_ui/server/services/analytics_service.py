"""Business logic service for analytics endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..repositories import analytics_repository


PERIOD_TO_DAYS = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "1y": 365,
    "all": None,
}


def _days_for_period(period: str) -> int | None:
    return PERIOD_TO_DAYS[period]


def get_performance_stats(period: str) -> dict[str, Any]:
    row = analytics_repository.get_performance_stats(_days_for_period(period))

    total_trades = row["total_trades"] or 0
    winning_trades = row["winning_trades"] or 0
    losing_trades = row["losing_trades"] or 0

    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    avg_win = float(row["avg_win"] or 0)
    avg_loss = float(row["avg_loss"] or 0)
    total_wins = float(row["total_wins"] or 0)
    total_losses = float(row["total_losses"] or 0)
    total_pnl = float(row["total_pnl"] or 0)

    profit_factor = (total_wins / total_losses) if total_losses > 0 else float("inf") if total_wins > 0 else 0
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else 999.99,
        "expectancy": round(expectancy, 2),
        "max_drawdown": 0.0,
        "sharpe_ratio": None,
        "total_pnl": round(total_pnl, 2),
        "total_return_pct": 0.0,
    }


def get_equity_curve(period: str) -> list[dict[str, Any]]:
    rows = analytics_repository.get_equity_curve_rows(_days_for_period(period))

    cumulative = 0.0
    initial_equity = 100000.0
    curve: list[dict[str, Any]] = []

    for row in rows:
        daily_pnl = float(row["daily_pnl"] or 0)
        cumulative += daily_pnl
        curve.append(
            {
                "date": row["trade_date"].isoformat(),
                "equity": initial_equity + cumulative,
                "pnl": round(daily_pnl, 2),
                "cumulative_pnl": round(cumulative, 2),
            }
        )

    return curve


def get_win_rate_by_setup() -> list[dict[str, Any]]:
    rows = analytics_repository.get_win_rate_by_setup_rows()
    return [
        {
            "setup_type": row["setup_type"],
            "total_trades": row["total"],
            "wins": row["wins"],
            "win_rate": round((row["wins"] / row["total"] * 100) if row["total"] else 0, 1),
            "avg_pnl": round(float(row["avg_pnl"]), 2),
            "total_pnl": round(float(row["total_pnl"]), 2),
        }
        for row in rows
    ]


def get_daily_summary(date_str: str | None) -> dict[str, Any]:
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    trade_row = analytics_repository.get_daily_trade_stats(date_str)
    order_row = analytics_repository.get_daily_order_stats(date_str)
    alert_row = analytics_repository.get_daily_alert_stats(date_str)
    cb_triggered = analytics_repository.get_circuit_breaker_state()
    api_errors = analytics_repository.get_daily_api_error_count(date_str)

    total_trades = trade_row["total_trades"] or 0
    winning_trades = trade_row["winning_trades"] or 0
    gross_pnl = float(trade_row["gross_pnl"] or 0)
    fees = float(trade_row["fees"] or 0)

    return {
        "date": date_str,
        "trading": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": trade_row["losing_trades"] or 0,
            "win_rate": round((winning_trades / total_trades * 100) if total_trades else 0, 1),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(gross_pnl - fees, 2),
            "fees": round(fees, 2),
            "largest_win": round(float(trade_row["largest_win"] or 0), 2),
            "largest_loss": round(float(trade_row["largest_loss"] or 0), 2),
        },
        "orders": {
            "submitted": order_row["submitted"] if order_row and order_row["submitted"] else 0,
            "filled": order_row["filled"] if order_row and order_row["filled"] else 0,
            "cancelled": order_row["cancelled"] if order_row and order_row["cancelled"] else 0,
            "rejected": order_row["rejected"] if order_row and order_row["rejected"] else 0,
        },
        "alerts": {
            "triggered": alert_row["triggered"] if alert_row and alert_row["triggered"] else 0,
            "stop_losses_hit": alert_row["stop_losses_hit"] if alert_row and alert_row["stop_losses_hit"] else 0,
            "targets_hit": alert_row["targets_hit"] if alert_row and alert_row["targets_hit"] else 0,
        },
        "system": {
            "circuit_breaker_triggered": cb_triggered,
            "max_drawdown_reached": 0.0,
            "api_errors": api_errors,
        },
    }
