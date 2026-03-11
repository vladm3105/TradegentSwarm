"""Unit tests for settings_service helpers."""

from pathlib import Path

from tradegent_ui.server.services import settings_service


def test_validate_auth0_domain():
    assert settings_service.validate_auth0_domain("tenant.auth0.com") is True
    assert settings_service.validate_auth0_domain("invalid") is False


def test_update_env_file(tmp_path: Path):
    env_file = tmp_path / ".env"
    settings_service.update_env_file(env_file, {"AUTH0_DOMAIN": "tenant.auth0.com"})
    assert "AUTH0_DOMAIN=tenant.auth0.com" in env_file.read_text()
