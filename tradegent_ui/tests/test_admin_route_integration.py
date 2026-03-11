"""Integration tests for admin routes with service delegation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import UserClaims, get_current_user
from tradegent_ui.server.routes.admin import router as admin_router
from tradegent_ui.server.routes import admin as admin_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_current_user] = lambda: UserClaims(
        sub="auth0|admin", email="admin@example.com", roles=["admin"]
    )
    return app


def test_list_users_route_delegates(monkeypatch):
    async def _list_users(page, limit, search):
        return {
            "users": [
                {
                    "id": 1,
                    "auth0_sub": "auth0|u1",
                    "email": "u@example.com",
                    "name": "U",
                    "picture": None,
                    "is_active": True,
                    "is_admin": False,
                    "roles": ["viewer"],
                    "last_login_at": None,
                    "created_at": "2026-03-11T10:00:00",
                }
            ],
            "total": 1,
            "page": 1,
            "limit": 20,
        }

    monkeypatch.setattr(admin_route_module.admin_service, "list_users", _list_users)

    client = TestClient(_build_app())
    resp = client.get("/api/admin/users")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_permissions_route_delegates(monkeypatch):
    async def _list_permissions():
        return [{"code": "users:read", "resource_type": "users", "action": "read"}]

    monkeypatch.setattr(admin_route_module.admin_service, "list_permissions", _list_permissions)

    client = TestClient(_build_app())
    resp = client.get("/api/admin/permissions")
    assert resp.status_code == 200
    assert resp.json()[0]["code"] == "users:read"
