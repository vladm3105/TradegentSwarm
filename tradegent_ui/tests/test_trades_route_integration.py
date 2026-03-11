"""Integration-style tests for trades routes with service layer wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.routes.trades import router as trades_router
from tradegent_ui.server.routes import trades as trades_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(trades_router)
    return app


def test_list_trades_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        trades_route_module.trades_service,
        "list_trades",
        lambda status, ticker, limit, offset: {
            "trades": [
                {
                    "id": 1,
                    "ticker": "AAPL",
                    "direction": "long",
                    "entry_date": "2026-03-11T10:00:00",
                    "entry_price": 100.0,
                    "entry_size": 5.0,
                    "status": "open",
                    "exit_date": None,
                    "exit_price": None,
                    "pnl_dollars": None,
                    "pnl_pct": None,
                    "thesis": "test",
                    "source_type": "manual",
                }
            ],
            "total": 1,
            "stats": {
                "total_trades": 1,
                "open_trades": 1,
                "closed_trades": 0,
                "total_pnl": 0.0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
            },
        },
    )

    client = TestClient(_build_app())
    response = client.get("/api/trades/list")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["trades"][0]["ticker"] == "AAPL"


def test_stats_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        trades_route_module.trades_service,
        "get_trade_stats",
        lambda: {
            "total_trades": 2,
            "open_trades": 1,
            "closed_trades": 1,
            "total_pnl": 123.0,
            "win_rate": 50.0,
            "avg_win": 200.0,
            "avg_loss": -77.0,
            "best_trade": 200.0,
            "worst_trade": -77.0,
        },
    )

    client = TestClient(_build_app())
    response = client.get("/api/trades/stats")

    assert response.status_code == 200
    assert response.json()["total_trades"] == 2
