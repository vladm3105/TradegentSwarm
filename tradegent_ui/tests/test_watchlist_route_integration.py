"""Integration-style tests for watchlist routes with service layer wiring."""

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
