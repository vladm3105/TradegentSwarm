"""Unit tests for auth_service DB-backed profile/onboarding paths."""

import pytest
from fastapi import HTTPException

from tradegent_ui.server.auth import UserClaims
from tradegent_ui.server.services import auth_service


def _user() -> UserClaims:
    return UserClaims(sub="auth0|u1", email="u@example.com", roles=["viewer"])


@pytest.mark.asyncio
async def test_complete_onboarding_not_found(monkeypatch):
    monkeypatch.setattr(auth_service.auth_repository, "complete_onboarding", lambda sub: False)

    with pytest.raises(HTTPException) as exc:
        await auth_service.complete_onboarding(_user())
    assert exc.value.status_code == 404
