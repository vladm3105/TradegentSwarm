"""Unit tests for analytics service layer."""

from tradegent_ui.server.services import analytics_service


def test_get_performance_stats_calculates_metrics(monkeypatch) -> None:
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_performance_stats",
        lambda days: {
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
            "avg_win": 120.0,
            "avg_loss": 50.0,
            "total_wins": 720.0,
            "total_losses": 200.0,
            "total_pnl": 520.0,
        },
    )

    result = analytics_service.get_performance_stats("30d")

    assert result["total_trades"] == 10
    assert result["win_rate"] == 60.0
    assert result["profit_factor"] == 3.6
    assert result["expectancy"] == 52.0
    assert result["total_pnl"] == 520.0


def test_get_equity_curve_builds_cumulative_values(monkeypatch) -> None:
    class DummyDate:
        def __init__(self, value: str):
            self._value = value

        def isoformat(self) -> str:
            return self._value

    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_equity_curve_rows",
        lambda days: [
            {"trade_date": DummyDate("2026-03-10"), "daily_pnl": 100.0},
            {"trade_date": DummyDate("2026-03-11"), "daily_pnl": -25.0},
        ],
    )

    result = analytics_service.get_equity_curve("7d")

    assert len(result) == 2
    assert result[0]["equity"] == 100100.0
    assert result[1]["equity"] == 100075.0
    assert result[1]["cumulative_pnl"] == 75.0


def test_get_daily_summary_formats_sections(monkeypatch) -> None:
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_daily_trade_stats",
        lambda date_str: {
            "total_trades": 2,
            "winning_trades": 1,
            "losing_trades": 1,
            "gross_pnl": 80.0,
            "fees": 5.0,
            "largest_win": 120.0,
            "largest_loss": -40.0,
        },
    )
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_daily_order_stats",
        lambda date_str: {"submitted": 3, "filled": 2, "cancelled": 1, "rejected": 0},
    )
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_daily_alert_stats",
        lambda date_str: {"triggered": 4, "stop_losses_hit": 1, "targets_hit": 2},
    )
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_circuit_breaker_state",
        lambda: False,
    )
    monkeypatch.setattr(
        analytics_service.analytics_repository,
        "get_daily_api_error_count",
        lambda date_str: 1,
    )

    result = analytics_service.get_daily_summary("2026-03-11")

    assert result["date"] == "2026-03-11"
    assert result["trading"]["net_pnl"] == 75.0
    assert result["orders"]["filled"] == 2
    assert result["alerts"]["targets_hit"] == 2
    assert result["system"]["api_errors"] == 1
