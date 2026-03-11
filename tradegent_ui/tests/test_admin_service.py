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


@pytest.mark.asyncio
async def test_delete_user_data_success(monkeypatch):
    from tradegent_ui.server.services import admin_service

    monkeypatch.setattr(admin_service.admin_repository, "get_user_id_by_sub", lambda sub: 1)
    monkeypatch.setattr(admin_service.admin_repository, "get_user_email", lambda user_id: "u@example.com")
    monkeypatch.setattr(admin_service.admin_repository, "create_gdpr_deletion_request", lambda user_id, user_email, processed_by: 10)
    monkeypatch.setattr(
        admin_service.admin_repository,
        "execute_gdpr_deletion",
        lambda request_id, user_id, user_data_tables: ["nexus.audit_log: 1"],
    )

    result = await admin_service.delete_user_data(2, _admin_user())
    assert result["success"] is True
    assert result["tables_cleared"] == ["nexus.audit_log: 1"]


@pytest.mark.asyncio
async def test_delete_user_data_marks_failed(monkeypatch):
    from tradegent_ui.server.services import admin_service

    state = {"failed_called": False}

    monkeypatch.setattr(admin_service.admin_repository, "get_user_id_by_sub", lambda sub: 1)
    monkeypatch.setattr(admin_service.admin_repository, "get_user_email", lambda user_id: "u@example.com")
    monkeypatch.setattr(admin_service.admin_repository, "create_gdpr_deletion_request", lambda user_id, user_email, processed_by: 10)

    def _fail_delete(request_id, user_id, user_data_tables):
        raise RuntimeError("boom")

    def _mark_failed(request_id, error_message):
        state["failed_called"] = True
        assert request_id == 10
        assert "boom" in error_message

    monkeypatch.setattr(admin_service.admin_repository, "execute_gdpr_deletion", _fail_delete)
    monkeypatch.setattr(admin_service.admin_repository, "mark_gdpr_request_failed", _mark_failed)

    with pytest.raises(HTTPException) as exc:
        await admin_service.delete_user_data(2, _admin_user())

    assert exc.value.status_code == 500
    assert state["failed_called"] is True
