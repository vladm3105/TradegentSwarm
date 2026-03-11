"""Integration-style tests for notifications routes with service layer wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import UserClaims, get_current_user
from tradegent_ui.server.routes.notifications import router as notifications_router
from tradegent_ui.server.routes import notifications as notifications_route_module


def _fake_user() -> UserClaims:
    return UserClaims(
        sub="test-user",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        permissions=["read:notifications"],
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(notifications_router)
    app.dependency_overrides[get_current_user] = _fake_user
    return app


def test_list_notifications_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications_route_module.notifications_service,
        "list_notifications",
        lambda user_id, unread_only, limit: [
            {
                "id": 1,
                "type": "system",
                "severity": "info",
                "title": "Test",
                "message": "ok",
                "data": {},
                "is_read": False,
                "created_at": "2026-03-11T10:00:00",
            }
        ],
    )

    client = TestClient(_build_app())
    response = client.get("/api/notifications/")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_count_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        notifications_route_module.notifications_service,
        "get_notification_count",
        lambda user_id: {"total": 4, "unread": 1},
    )

    client = TestClient(_build_app())
    response = client.get("/api/notifications/count")

    assert response.status_code == 200
    assert response.json() == {"total": 4, "unread": 1}
