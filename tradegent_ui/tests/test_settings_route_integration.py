"""Integration tests for settings routes with service delegation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import get_current_user, UserClaims
from tradegent_ui.server.routes.settings import router as settings_router
from tradegent_ui.server.routes import settings as settings_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(settings_router)
    app.dependency_overrides[get_current_user] = lambda: UserClaims(
        sub="auth0|admin", email="admin@example.com", roles=["admin"]
    )
    return app


def test_restart_route_delegates_userid_lookup(monkeypatch):
    monkeypatch.setattr(settings_route_module.settings_service, "get_user_id", lambda sub: 1)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(settings_route_module, "log_action", _noop)

    client = TestClient(_build_app())
    resp = client.post("/api/settings/restart-server")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
