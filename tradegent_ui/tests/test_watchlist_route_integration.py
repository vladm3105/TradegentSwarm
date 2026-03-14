"""Integration-style tests for watchlist routes with service layer wiring."""

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.routes.watchlist import router as watchlist_router
from tradegent_ui.server.routes import watchlist as watchlist_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(watchlist_router)
    return app


def test_list_watchlists_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        watchlist_route_module.watchlist_service,
        "list_watchlists",
        lambda: [
            {
                "id": 1,
                "name": "Manual List",
                "description": None,
                "source_type": "manual",
                "source_ref": None,
                "color": "#3b82f6",
                "is_default": False,
                "is_pinned": False,
                "total_entries": 0,
                "active_entries": 0,
                "created_at": None,
                "updated_at": None,
            }
        ],
    )

    client = TestClient(_build_app())
    response = client.get("/api/watchlists")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["watchlists"]) == 1
    assert payload["watchlists"][0]["name"] == "Manual List"


def test_watchlist_stats_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        watchlist_route_module.watchlist_service,
        "get_watchlist_stats",
        lambda watchlist_id: {
            "total": 3,
            "active": 2,
            "triggered": 1,
            "expired": 0,
            "invalidated": 0,
            "by_priority": {"high": 1, "medium": 1},
        },
    )

    client = TestClient(_build_app())
    response = client.get("/api/watchlist/stats")

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_create_watchlist_entry_route_uses_service(monkeypatch) -> None:
    now = datetime.now()

    monkeypatch.setattr(
        watchlist_route_module.watchlist_service,
        "create_watchlist_entry",
        lambda **kwargs: {
            "id": 11,
            "watchlist_id": kwargs.get("watchlist_id"),
            "watchlist_name": "All Entries",
            "watchlist_source_type": "auto",
            "watchlist_color": "#3b82f6",
            "ticker": kwargs["ticker"],
            "entry_trigger": kwargs["entry_trigger"],
            "entry_price": kwargs.get("entry_price"),
            "invalidation": kwargs.get("invalidation"),
            "invalidation_price": kwargs.get("invalidation_price"),
            "expires_at": kwargs.get("expires_at"),
            "priority": kwargs.get("priority", "medium"),
            "status": "active",
            "source": kwargs.get("source"),
            "source_analysis": kwargs.get("source_analysis"),
            "notes": kwargs.get("notes"),
            "created_at": now,
            "last_analysis_at": None,
            "days_until_expiry": None,
        },
    )

    client = TestClient(_build_app())
    response = client.post(
        "/api/watchlist",
        json={
            "watchlist_id": 1,
            "ticker": "NVDA",
            "entry_trigger": "Price above 950",
            "priority": "high",
            "notes": "Momentum setup",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 11
    assert payload["ticker"] == "NVDA"
    assert payload["entry_trigger"] == "Price above 950"
    assert payload["priority"] == "high"
