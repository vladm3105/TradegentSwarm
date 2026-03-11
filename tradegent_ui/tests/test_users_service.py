"""Unit tests for users_service business logic."""

import pytest
from fastapi import HTTPException

from tradegent_ui.server.auth import UserClaims


def _user() -> UserClaims:
    return UserClaims(
        sub="auth0|u1",
        email="user@example.com",
        roles=["admin"],
        permissions=["read", "write"],
    )


@pytest.mark.asyncio
async def test_update_ib_account_rejects_invalid_mode():
    """update_ib_account returns 400 on invalid trading mode."""
    from tradegent_ui.server.services import users_service

    class Req:
        ib_account_id = "DU123"
        ib_trading_mode = "demo"
        ib_gateway_port = 4002

    with pytest.raises(HTTPException) as exc_info:
        await users_service.update_ib_account(Req(), None, _user())
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_list_api_keys_returns_empty_when_no_user(monkeypatch):
    """list_api_keys returns [] when auth subject has no DB user id."""
    from tradegent_ui.server.services import users_service

    async def _no_user(_sub):
        return None

    monkeypatch.setattr(users_service, "get_db_user_id", _no_user)
    result = await users_service.list_api_keys(_user())
    assert result == []


@pytest.mark.asyncio
async def test_revoke_session_404_when_not_found(monkeypatch):
    """revoke_session raises 404 when target session does not exist."""
    from tradegent_ui.server.services import users_service

    async def _user_id(_sub):
        return 1

    monkeypatch.setattr(users_service, "get_db_user_id", _user_id)
    monkeypatch.setattr(users_service.users_repository, "revoke_session", lambda sid, uid: False)

    with pytest.raises(HTTPException) as exc_info:
        await users_service.revoke_session(42, _user())
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_sessions_maps_rows(monkeypatch):
    """list_sessions maps repository rows to serializable payload."""
    from tradegent_ui.server.services import users_service
    from datetime import datetime

    async def _user_id(_sub):
        return 1

    monkeypatch.setattr(users_service, "get_db_user_id", _user_id)
    monkeypatch.setattr(
        users_service.users_repository,
        "list_user_sessions",
        lambda uid: [
            {
                "id": 9,
                "device_info": {"browser": "x"},
                "ip_address": "127.0.0.1",
                "last_active_at": datetime(2026, 3, 11, 11, 0, 0),
                "created_at": datetime(2026, 3, 10, 9, 0, 0),
            }
        ],
    )

    result = await users_service.list_sessions(_user())
    assert result[0]["id"] == 9
    assert result[0]["last_active_at"].startswith("2026-03-11")
