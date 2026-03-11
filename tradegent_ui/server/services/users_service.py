"""Users service layer for profile, IB account, API keys, and sessions."""

import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, Request

from ..audit import log_action
from ..auth import UserClaims, get_db_user_id
from ..repositories import users_repository


async def update_profile(request, req: Request, user: UserClaims) -> dict:
    """Update user profile fields and preference JSON values."""
    pref_updates = {}
    if request.timezone is not None:
        pref_updates["timezone"] = request.timezone
    if request.theme is not None:
        pref_updates["theme"] = request.theme
    if request.notifications_enabled is not None:
        pref_updates["notifications_enabled"] = request.notifications_enabled
    if request.default_analysis_type is not None:
        pref_updates["default_analysis_type"] = request.default_analysis_type

    if request.name is None and not pref_updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    row = users_repository.update_profile(user.sub, request.name, pref_updates)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    await log_action(
        row["id"],
        "user.update_profile",
        details={"updates": list(pref_updates.keys()) + (["name"] if request.name else [])},
        request=req,
    )

    prefs = row["preferences"] or {}
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "timezone": prefs.get("timezone", "America/New_York"),
        "theme": prefs.get("theme", "system"),
        "notifications_enabled": prefs.get("notifications_enabled", True),
        "default_analysis_type": prefs.get("default_analysis_type", "stock"),
    }


async def get_ib_account(user: UserClaims) -> dict:
    """Return IB account settings for current user."""
    row = users_repository.get_ib_account(user.sub)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "ib_account_id": row["ib_account_id"],
        "ib_trading_mode": row["ib_trading_mode"] or "paper",
        "ib_gateway_port": row["ib_gateway_port"],
    }


async def update_ib_account(request, req: Request, user: UserClaims) -> dict:
    """Update current user's IB account settings."""
    if request.ib_trading_mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="Trading mode must be 'paper' or 'live'")

    row = users_repository.update_ib_account(
        user.sub,
        request.ib_account_id,
        request.ib_trading_mode,
        request.ib_gateway_port,
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    await log_action(
        row["id"],
        "user.update_ib_account",
        details={
            "trading_mode": request.ib_trading_mode,
            "has_account_id": bool(request.ib_account_id),
        },
        request=req,
    )

    return {
        "ib_account_id": row["ib_account_id"],
        "ib_trading_mode": row["ib_trading_mode"],
        "ib_gateway_port": row["ib_gateway_port"],
    }


async def list_api_keys(user: UserClaims) -> list[dict]:
    """List API keys for current user."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        return []

    rows = users_repository.list_api_keys(user_id)
    return [
        {
            "id": row["id"],
            "key_prefix": row["key_prefix"],
            "name": row["name"],
            "permissions": row["permissions"] or [],
            "last_used_at": row["last_used_at"].isoformat() if row["last_used_at"] else None,
            "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


async def create_api_key(request, req: Request, user: UserClaims) -> dict:
    """Create API key for current user and return one-time full key response."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    if request.permissions:
        invalid_perms = set(request.permissions) - set(user.permissions)
        if invalid_perms:
            raise HTTPException(status_code=400, detail=f"Invalid permissions: {invalid_perms}")
        permissions = request.permissions
    else:
        permissions = user.permissions

    key_random = secrets.token_urlsafe(24)
    key_prefix = key_random[:8]
    full_key = f"tg_{key_random}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    row = users_repository.create_api_key(
        user_id=user_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
        name=request.name,
        permissions=permissions,
        expires_at=expires_at,
    )

    await log_action(
        user_id,
        "api_key.create",
        "api_key",
        str(row["id"]),
        {"name": request.name, "expires_in_days": request.expires_in_days},
        req,
    )

    return {
        "key": full_key,
        "api_key": {
            "id": row["id"],
            "key_prefix": key_prefix,
            "name": request.name,
            "permissions": permissions,
            "last_used_at": None,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "created_at": row["created_at"].isoformat(),
        },
    }


async def revoke_api_key(key_id: int, req: Request, user: UserClaims) -> dict:
    """Revoke an API key owned by current user."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    ok = users_repository.revoke_api_key(key_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")

    await log_action(user_id, "api_key.revoke", "api_key", str(key_id), request=req)
    return {"success": True, "key_id": key_id}


async def list_sessions(user: UserClaims) -> list[dict]:
    """List current user's active sessions."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        return []

    rows = users_repository.list_user_sessions(user_id)
    return [
        {
            "id": row["id"],
            "device_info": row["device_info"],
            "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
            "last_active_at": row["last_active_at"].isoformat(),
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]


async def revoke_session(session_id: int, user: UserClaims) -> dict:
    """Revoke one active user session."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    ok = users_repository.revoke_session(session_id, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session_id": session_id}


async def revoke_all_sessions(user: UserClaims) -> dict:
    """Revoke all active sessions for current user."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    count = users_repository.revoke_all_sessions(user_id)
    return {"success": True, "sessions_revoked": count}
