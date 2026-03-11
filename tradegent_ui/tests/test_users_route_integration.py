"""Integration-style tests for users routes with service delegation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import get_current_user, UserClaims
from tradegent_ui.server.routes.users import router as users_router
from tradegent_ui.server.routes import users as users_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(users_router)
    fake_user = UserClaims(
        sub="auth0|u1",
        email="user@example.com",
        roles=["admin"],
        permissions=["read", "write"],
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return app


def test_get_ib_account_route_delegates(monkeypatch):
    """GET /api/users/me/ib-account delegates to users_service."""

    async def _get_ib_account(user):
        return {
            "ib_account_id": "DU123",
            "ib_trading_mode": "paper",
            "ib_gateway_port": 4002,
        }

    monkeypatch.setattr(users_route_module.users_service, "get_ib_account", _get_ib_account)

    client = TestClient(_build_app())
    resp = client.get("/api/users/me/ib-account")
    assert resp.status_code == 200
    assert resp.json()["ib_account_id"] == "DU123"


def test_revoke_all_sessions_route_delegates(monkeypatch):
    """DELETE /api/users/me/sessions delegates to users_service."""

    async def _revoke_all_sessions(user):
        return {"success": True, "sessions_revoked": 3}

    monkeypatch.setattr(users_route_module.users_service, "revoke_all_sessions", _revoke_all_sessions)

    client = TestClient(_build_app())
    resp = client.delete("/api/users/me/sessions")
    assert resp.status_code == 200
    assert resp.json()["sessions_revoked"] == 3
