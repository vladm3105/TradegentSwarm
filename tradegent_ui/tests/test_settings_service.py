"""Unit tests for settings_service helpers."""

from pathlib import Path
import pytest
from fastapi import HTTPException

from tradegent_ui.server.services import settings_service


def test_validate_auth0_domain():
    assert settings_service.validate_auth0_domain("tenant.auth0.com") is True
    assert settings_service.validate_auth0_domain("invalid") is False


def test_update_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    settings_service.update_env_file(env_file, {"AUTH0_DOMAIN": "tenant.auth0.com"})
    assert "AUTH0_DOMAIN=tenant.auth0.com" in env_file.read_text()


def test_get_user_id_raises_when_user_missing(monkeypatch):
    monkeypatch.setattr(settings_service.settings_repository, "get_user_id_by_sub", lambda sub: None)

    with pytest.raises(HTTPException) as exc:
        settings_service.get_user_id("auth0|missing")

    assert exc.value.status_code == 404
