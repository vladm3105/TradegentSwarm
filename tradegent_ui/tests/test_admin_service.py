"""Unit tests for admin_service logic."""

import pytest
from fastapi import HTTPException

from tradegent_ui.server.auth import UserClaims


def _admin_user() -> UserClaims:
    return UserClaims(sub="auth0|admin", email="admin@example.com", roles=["admin"])


@pytest.mark.asyncio
async def test_get_user_not_found(monkeypatch):
    from tradegent_ui.server.services import admin_service

    monkeypatch.setattr(admin_service.admin_repository, "get_user", lambda user_id: None)

    with pytest.raises(HTTPException) as exc:
        await admin_service.get_user(99)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_user_roles_invalid_role(monkeypatch):
    from tradegent_ui.server.services import admin_service

    monkeypatch.setattr(admin_service.admin_repository, "get_user_id_by_sub", lambda sub: 1)
    monkeypatch.setattr(admin_service.admin_repository, "user_exists", lambda user_id: True)
    monkeypatch.setattr(admin_service.admin_repository, "get_role_map", lambda roles: {"admin": 1})

    with pytest.raises(HTTPException) as exc:
        await admin_service.update_user_roles(2, ["admin", "bad-role"], None, _admin_user())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_list_users_shapes_payload(monkeypatch):
    from tradegent_ui.server.services import admin_service
    from datetime import datetime

    monkeypatch.setattr(
        admin_service.admin_repository,
        "list_users",
        lambda page, limit, search: (
            1,
            [
                {
                    "id": 1,
                    "auth0_sub": "auth0|x",
                    "email": "x@example.com",
                    "name": "X",
                    "picture": None,
                    "is_active": True,
                    "is_admin": False,
                    "roles": ["viewer"],
                    "last_login_at": None,
                    "created_at": datetime(2026, 3, 11, 10, 0, 0),
                }
            ],
        ),
    )

    result = await admin_service.list_users(1, 20, None)
    assert result["total"] == 1
    assert result["users"][0]["email"] == "x@example.com"


@pytest.mark.asyncio
async def test_get_audit_log_formats_ip(monkeypatch):
    from tradegent_ui.server.services import admin_service
    from datetime import datetime

    monkeypatch.setattr(
        admin_service.admin_repository,
        "list_audit_log",
        lambda user_id, action, limit, offset: [
            {
                "id": 1,
                "user_id": 1,
                "user_email": "u@example.com",
                "action": "admin.test",
                "resource_type": "user",
                "resource_id": "1",
                "details": {},
                "ip_address": "127.0.0.1",
                "created_at": datetime(2026, 3, 11, 9, 0, 0),
            }
        ],
    )

    rows = await admin_service.get_audit_log(None, None, 10, 0)
    assert rows[0]["ip_address"] == "127.0.0.1"
    assert rows[0]["created_at"].startswith("2026-03-11")
