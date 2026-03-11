"""Integration-style tests for sessions routes with service wiring."""

from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import get_current_user, UserClaims
from tradegent_ui.server.routes.sessions import router as sessions_router
from tradegent_ui.server.routes import sessions as sessions_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(sessions_router)
    fake_user = UserClaims(sub="auth0|u1", email="user@example.com", roles=["admin"])
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return app


def test_list_sessions_route_delegates(monkeypatch):
    """GET /api/sessions/list delegates to sessions_service."""
    monkeypatch.setattr(
        sessions_route_module.sessions_service,
        "list_sessions",
        lambda limit, offset, include_archived, user: {
            "sessions": [
                {
                    "id": 1,
                    "session_id": "s-1",
                    "title": "First",
                    "message_count": 1,
                    "created_at": datetime(2026, 3, 11, 10, 0, 0),
                    "updated_at": datetime(2026, 3, 11, 10, 5, 0),
                    "is_archived": False,
                }
            ],
            "total": 1,
        },
    )

    client = TestClient(_build_app())
    resp = client.get("/api/sessions/list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["sessions"][0]["session_id"] == "s-1"


def test_create_session_route_delegates(monkeypatch):
    """POST /api/sessions/create delegates to sessions_service."""
    monkeypatch.setattr(
        sessions_route_module.sessions_service,
        "create_session",
        lambda title, user: {
            "id": 2,
            "session_id": "s-2",
            "title": title,
            "created_at": "2026-03-11T10:00:00",
            "updated_at": "2026-03-11T10:00:01",
        },
    )

    client = TestClient(_build_app())
    resp = client.post("/api/sessions/create", json={"title": "New Session"})
    assert resp.status_code == 200
    assert resp.json()["session_id"] == "s-2"
