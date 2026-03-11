"""Integration-style tests for analytics routes with service layer wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import UserClaims, get_current_user
from tradegent_ui.server.routes.analytics import router as analytics_router
from tradegent_ui.server.routes import analytics as analytics_route_module


def _fake_user() -> UserClaims:
    return UserClaims(
        sub="test-user",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        permissions=["read:analytics"],
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(analytics_router)
    app.dependency_overrides[get_current_user] = _fake_user
    return app


def test_performance_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        analytics_route_module.analytics_service,
        "get_performance_stats",
        lambda period: {
            "total_trades": 5,
            "winning_trades": 3,
            "losing_trades": 2,
            "win_rate": 60.0,
            "avg_win": 100.0,
            "avg_loss": 50.0,
            "profit_factor": 2.0,
            "expectancy": 40.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": None,
            "total_pnl": 200.0,
            "total_return_pct": 0.0,
        },
    )

    client = TestClient(_build_app())
    response = client.get("/api/analytics/performance?period=30d")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_trades"] == 5
    assert payload["profit_factor"] == 2.0


def test_daily_summary_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        analytics_route_module.analytics_service,
        "get_daily_summary",
        lambda date: {
            "date": "2026-03-11",
            "trading": {
                "total_trades": 1,
                "winning_trades": 1,
                "losing_trades": 0,
                "win_rate": 100.0,
                "gross_pnl": 50.0,
                "net_pnl": 48.0,
                "fees": 2.0,
                "largest_win": 50.0,
                "largest_loss": 0.0,
            },
            "orders": {"submitted": 1, "filled": 1, "cancelled": 0, "rejected": 0},
            "alerts": {"triggered": 0, "stop_losses_hit": 0, "targets_hit": 0},
            "system": {
                "circuit_breaker_triggered": False,
                "max_drawdown_reached": 0.0,
                "api_errors": 0,
            },
        },
    )

    client = TestClient(_build_app())
    response = client.get("/api/analytics/daily-summary?date=2026-03-11")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trading"]["net_pnl"] == 48.0
    assert payload["system"]["api_errors"] == 0
