"""Integration-style tests for alerts routes with service layer wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import UserClaims, get_current_user
from tradegent_ui.server.routes.alerts import router as alerts_router
from tradegent_ui.server.routes import alerts as alerts_route_module


def _fake_user() -> UserClaims:
    return UserClaims(
        sub="test-user",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        permissions=["manage:alerts"],
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(alerts_router)
    app.dependency_overrides[get_current_user] = _fake_user
    return app


def test_list_alerts_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        alerts_route_module.alerts_service,
        "list_alerts",
        lambda user_id, active_only: [
            {
                "id": 1,
                "alert_type": "price",
                "ticker": "NVDA",
                "condition": {"operator": "above", "value": 900, "value_type": "price"},
                "is_active": True,
                "is_triggered": False,
                "triggered_at": None,
                "created_at": "2026-03-11T10:00:00",
            }
        ],
    )

    client = TestClient(_build_app())
    response = client.get("/api/alerts/")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["ticker"] == "NVDA"


def test_toggle_alert_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        alerts_route_module.alerts_service,
        "toggle_alert",
        lambda alert_id, user_id: {"success": True, "is_active": False},
    )

    client = TestClient(_build_app())
    response = client.patch("/api/alerts/5/toggle")

    assert response.status_code == 200
    assert response.json() == {"success": True, "is_active": False}
