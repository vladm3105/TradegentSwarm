"""Unit tests for sessions_service business logic."""

import pytest
from fastapi import HTTPException

from tradegent_ui.server.auth import UserClaims


def _user() -> UserClaims:
    return UserClaims(sub="auth0|u1", email="user@example.com", roles=["admin"])


def test_get_or_create_user_id_raises_for_unprovisioned_user(monkeypatch):
    """Rejects unprovisioned users instead of falling back to another account."""
    from tradegent_ui.server.services import sessions_service

    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "get_user_id_by_sub",
        lambda sub: None,
    )
    with pytest.raises(HTTPException) as exc_info:
        sessions_service.get_or_create_user_id(_user())
    assert exc_info.value.status_code == 403


def test_save_messages_raises_404_when_session_missing(monkeypatch):
    """save_messages raises 404 for unknown session."""
    from tradegent_ui.server.services import sessions_service

    monkeypatch.setattr(sessions_service, "get_or_create_user_id", lambda user: 1)
    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "get_session_db_id",
        lambda session_id, user_id: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        sessions_service.save_messages("missing", [], _user())
    assert exc_info.value.status_code == 404


def test_update_session_requires_fields(monkeypatch):
    """update_session raises 400 when no update fields provided."""
    from tradegent_ui.server.services import sessions_service

    with pytest.raises(HTTPException) as exc_info:
        sessions_service.update_session("s1", None, None, _user())
    assert exc_info.value.status_code == 400


def test_list_sessions_shapes_payload(monkeypatch):
    """list_sessions maps repository rows into response payload."""
    from tradegent_ui.server.services import sessions_service

    monkeypatch.setattr(sessions_service, "get_or_create_user_id", lambda user: 1)
    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "list_sessions",
        lambda user_id, limit, offset, include_archived: [
            {
                "id": 11,
                "session_id": "s-11",
                "title": "One",
                "message_count": 2,
                "created_at": "c",
                "updated_at": "u",
                "is_archived": False,
            }
        ],
    )
    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "count_sessions",
        lambda user_id, include_archived: 1,
    )

    result = sessions_service.list_sessions(20, 0, False, _user())
    assert result["total"] == 1
    assert result["sessions"][0]["session_id"] == "s-11"


def test_persist_roundtrip_messages_upserts_user_when_missing(monkeypatch):
    """persist_roundtrip_messages creates/updates user before writing messages."""
    from tradegent_ui.server.services import sessions_service

    captured: dict = {}

    def _upsert_user_by_sub(auth0_sub, email, name=None, picture=None, email_verified=True):
        captured["auth0_sub"] = auth0_sub
        captured["email"] = email
        captured["name"] = name
        return 123

    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "upsert_user_by_sub",
        _upsert_user_by_sub,
    )
    monkeypatch.setattr(
        sessions_service,
        "_resolve_or_create_session_db_id",
        lambda session_id, user_id, title=None: 55,
    )
    monkeypatch.setattr(
        sessions_service.sessions_repository,
        "upsert_messages",
        lambda db_session_id, payloads: None,
    )

    result = sessions_service.persist_roundtrip_messages(
        auth_sub="auth0|ws-user",
        session_id="auth0|ws-user",
        user_content="hello",
        assistant_content="hi",
        assistant_status="complete",
    )

    assert result["success"] is True
    assert captured["auth0_sub"] == "auth0|ws-user"
    assert captured["email"].endswith("@local.invalid")
