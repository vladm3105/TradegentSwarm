"""Integration tests for auth routes with service delegation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import get_current_user, UserClaims
from tradegent_ui.server.routes.auth import router as auth_router
from tradegent_ui.server.routes import auth as auth_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_current_user] = lambda: UserClaims(
        sub="auth0|u1", email="u@example.com", roles=["viewer"], permissions=["users:read"]
    )
    return app


def test_me_route_delegates(monkeypatch):
    async def _profile(user):
        return {
            "id": 1,
            "auth0_sub": "auth0|u1",
            "email": "u@example.com",
            "name": "User",
            "picture": None,
            "roles": ["viewer"],
            "permissions": ["users:read"],
            "ib_account_id": None,
            "ib_trading_mode": None,
            "preferences": {},
            "requires_onboarding": True,
        }

    monkeypatch.setattr(auth_route_module.auth_service, "get_current_user_profile", _profile)

    client = TestClient(_build_app())
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "u@example.com"
