"""Auth service layer for profile and onboarding operations."""

from typing import Any

from fastapi import HTTPException

from ..auth import UserClaims, sync_user_from_auth0
from ..repositories import auth_repository


def _to_user_profile(row: dict[str, Any]) -> dict[str, Any]:
    preferences = row["preferences"] or {}
    return {
        "id": row["id"],
        "auth0_sub": row["auth0_sub"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "roles": row["roles"] or [],
        "permissions": row["permissions"] or [],
        "ib_account_id": row["ib_account_id"],
        "ib_trading_mode": row["ib_trading_mode"],
        "preferences": preferences,
        "requires_onboarding": not preferences.get("onboarding_completed", False),
    }


async def get_current_user_profile(user: UserClaims) -> dict[str, Any]:
    row = auth_repository.get_user_with_roles_permissions_by_sub(user.sub)
    if not row:
        user_id = await sync_user_from_auth0(user)
        row = auth_repository.get_user_with_roles_permissions_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_user_profile(row)


async def complete_onboarding(user: UserClaims) -> dict[str, Any]:
    updated = auth_repository.complete_onboarding(user.sub)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True}
