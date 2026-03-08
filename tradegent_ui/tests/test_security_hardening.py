"""Security hardening regression tests for Tradegent UI server auth flows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from tradegent_ui.server import auth as auth_module
from tradegent_ui.server.auth import (
    _extract_websocket_token_from_subprotocol,
    validate_token,
    validate_websocket_token,
)
from tradegent_ui.server.routes import auth as auth_routes
from tradegent_ui.server.routes.auth import SyncUserRequest, sync_user


class _FakeWebSocket:
    """Minimal websocket stub used by auth unit tests."""

    def __init__(self, subprotocols: list[str] | None = None, query_token: str | None = None):
        self.scope = {"subprotocols": subprotocols or []}
        self.query_params = {}
        if query_token is not None:
            self.query_params["token"] = query_token


@pytest.mark.asyncio
async def test_demo_token_rejected_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Demo-token auth must be disabled unless explicitly enabled."""

    settings = SimpleNamespace(
        allow_demo_tokens=False,
        app_env="development",
        auth0_configured=False,
        admin_email="admin@example.com",
        admin_name="Admin",
        demo_email="demo@example.com",
        jwt_secret="x" * 32,
        jwt_algorithm="HS256",
    )
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)

    with pytest.raises(HTTPException) as exc_info:
        await validate_token("demo-token-admin")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_demo_token_allowed_only_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Demo-token auth should work only in explicit dev/test mode."""

    settings = SimpleNamespace(
        allow_demo_tokens=True,
        app_env="development",
        auth0_configured=False,
        admin_email="admin@example.com",
        admin_name="Admin",
        demo_email="demo@example.com",
        jwt_secret="x" * 32,
        jwt_algorithm="HS256",
    )
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)

    claims = await validate_token("demo-token-admin")

    assert claims.sub == "builtin|admin"
    assert "admin" in claims.roles


def test_websocket_subprotocol_bearer_pair_extracts_token() -> None:
    ws = _FakeWebSocket(subprotocols=["bearer", "abc123"])
    token, selected = _extract_websocket_token_from_subprotocol(ws)
    assert token == "abc123"
    assert selected == "bearer"


@pytest.mark.asyncio
async def test_websocket_query_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Query-string token transport must be rejected."""

    ws = _FakeWebSocket(subprotocols=[], query_token="should-not-be-used")

    async def _fake_validate(_: str):
        raise AssertionError("validate_token should not be called for query tokens")

    monkeypatch.setattr(auth_module, "validate_token", _fake_validate)

    user, selected = await validate_websocket_token(ws)
    assert user is None
    assert selected is None


@pytest.mark.asyncio
async def test_sync_user_uses_authenticated_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync route must ignore client-supplied role injection and trust authenticated claims."""

    captured: dict = {}

    async def _fake_sync_user_from_auth0(claims, *, sync_roles: bool = False):
        captured["sub"] = claims.sub
        captured["email"] = claims.email
        captured["roles"] = claims.roles
        captured["sync_roles"] = sync_roles
        return 42

    async def _fake_log_login(*args, **kwargs):
        return None

    async def _fake_log_action(*args, **kwargs):
        return None

    monkeypatch.setattr(auth_routes, "sync_user_from_auth0", _fake_sync_user_from_auth0)
    monkeypatch.setattr(auth_routes, "log_login", _fake_log_login)
    monkeypatch.setattr(auth_routes, "log_action", _fake_log_action)

    req = Request({"type": "http", "method": "POST", "path": "/api/auth/sync-user", "headers": []})
    user = auth_module.UserClaims(
        sub="auth0|abc",
        email="user@example.com",
        name="User",
        picture=None,
        roles=["trader"],
        permissions=[],
        email_verified=True,
    )
    payload = SyncUserRequest(
        sub="auth0|abc",
        email="user@example.com",
        name="Mallory",
        picture=None,
        email_verified=True,
    )

    result = await sync_user(payload, req, user)

    assert result["success"] is True
    assert captured["sub"] == "auth0|abc"
    assert captured["email"] == "user@example.com"
    assert captured["roles"] == []
    assert captured["sync_roles"] is False


@pytest.mark.asyncio
async def test_sync_user_rejects_mismatched_subject() -> None:
    """Sync route must reject attempts to sync a different principal."""

    req = Request({"type": "http", "method": "POST", "path": "/api/auth/sync-user", "headers": []})
    user = auth_module.UserClaims(
        sub="auth0|abc",
        email="user@example.com",
        roles=["trader"],
        permissions=[],
    )
    payload = SyncUserRequest(sub="auth0|evil")

    with pytest.raises(HTTPException) as exc_info:
        await sync_user(payload, req, user)

    assert exc_info.value.status_code == 403
