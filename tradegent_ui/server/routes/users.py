"""User routes for Tradegent Agent UI."""
import structlog
import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user, UserClaims, get_db_user_id
from ..audit import log_action
from ..database import get_db_connection

log = structlog.get_logger()
router = APIRouter(prefix="/api/users", tags=["users"])


# ============================================================================
# Profile Management
# ============================================================================

class UpdateProfileRequest(BaseModel):
    """Request to update user profile."""
    name: Optional[str] = None
    timezone: Optional[str] = None
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    default_analysis_type: Optional[str] = None


class ProfileResponse(BaseModel):
    """User profile response."""
    id: int
    email: str
    name: Optional[str]
    picture: Optional[str]
    timezone: str
    theme: str
    notifications_enabled: bool
    default_analysis_type: str


@router.put("/me/profile", response_model=ProfileResponse)
async def update_profile(
    request: UpdateProfileRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> ProfileResponse:
    """Update current user's profile."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Build update query dynamically
            updates = []
            params = []

            if request.name is not None:
                updates.append("name = %s")
                params.append(request.name)

            # Update preferences JSON fields
            pref_updates = {}
            if request.timezone is not None:
                pref_updates["timezone"] = request.timezone
            if request.theme is not None:
                pref_updates["theme"] = request.theme
            if request.notifications_enabled is not None:
                pref_updates["notifications_enabled"] = request.notifications_enabled
            if request.default_analysis_type is not None:
                pref_updates["default_analysis_type"] = request.default_analysis_type

            if pref_updates:
                updates.append("preferences = preferences || %s::jsonb")
                params.append(pref_updates)

            if not updates:
                raise HTTPException(status_code=400, detail="No updates provided")

            updates.append("updated_at = now()")
            params.append(user.sub)

            query = f"""
                UPDATE nexus.users
                SET {', '.join(updates)}
                WHERE auth0_sub = %s
                RETURNING id, email, name, picture, preferences
            """

            cur.execute(query, params)
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            conn.commit()

            # Log action
            await log_action(
                row["id"],
                "user.update_profile",
                details={"updates": list(pref_updates.keys()) + (["name"] if request.name else [])},
                request=req,
            )

            prefs = row["preferences"] or {}
            return ProfileResponse(
                id=row["id"],
                email=row["email"],
                name=row["name"],
                picture=row["picture"],
                timezone=prefs.get("timezone", "America/New_York"),
                theme=prefs.get("theme", "system"),
                notifications_enabled=prefs.get("notifications_enabled", True),
                default_analysis_type=prefs.get("default_analysis_type", "stock"),
            )


# ============================================================================
# IB Account Management
# ============================================================================

class UpdateIBAccountRequest(BaseModel):
    """Request to update IB account settings."""
    ib_account_id: str
    ib_trading_mode: str  # 'paper' or 'live'
    ib_gateway_port: Optional[int] = None


class IBAccountResponse(BaseModel):
    """IB account settings response."""
    ib_account_id: Optional[str]
    ib_trading_mode: str
    ib_gateway_port: Optional[int]


@router.get("/me/ib-account", response_model=IBAccountResponse)
async def get_ib_account(
    user: UserClaims = Depends(get_current_user),
) -> IBAccountResponse:
    """Get current user's IB account settings."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ib_account_id, ib_trading_mode, ib_gateway_port
                FROM nexus.users
                WHERE auth0_sub = %s
            """, (user.sub,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            return IBAccountResponse(
                ib_account_id=row["ib_account_id"],
                ib_trading_mode=row["ib_trading_mode"] or "paper",
                ib_gateway_port=row["ib_gateway_port"],
            )


@router.put("/me/ib-account", response_model=IBAccountResponse)
async def update_ib_account(
    request: UpdateIBAccountRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> IBAccountResponse:
    """Update current user's IB account settings."""
    # Validate trading mode
    if request.ib_trading_mode not in ("paper", "live"):
        raise HTTPException(
            status_code=400,
            detail="Trading mode must be 'paper' or 'live'"
        )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.users
                SET ib_account_id = %s,
                    ib_trading_mode = %s,
                    ib_gateway_port = %s,
                    updated_at = now()
                WHERE auth0_sub = %s
                RETURNING id, ib_account_id, ib_trading_mode, ib_gateway_port
            """, (
                request.ib_account_id,
                request.ib_trading_mode,
                request.ib_gateway_port,
                user.sub,
            ))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            conn.commit()

            # Log action
            await log_action(
                row["id"],
                "user.update_ib_account",
                details={
                    "trading_mode": request.ib_trading_mode,
                    "has_account_id": bool(request.ib_account_id),
                },
                request=req,
            )

            return IBAccountResponse(
                ib_account_id=row["ib_account_id"],
                ib_trading_mode=row["ib_trading_mode"],
                ib_gateway_port=row["ib_gateway_port"],
            )


# ============================================================================
# API Key Management
# ============================================================================

class CreateApiKeyRequest(BaseModel):
    """Request to create an API key."""
    name: str
    permissions: Optional[list[str]] = None
    expires_in_days: Optional[int] = None  # None = never expires


class ApiKeyResponse(BaseModel):
    """API key response (without full key)."""
    id: int
    key_prefix: str
    name: str
    permissions: list[str]
    last_used_at: Optional[str]
    expires_at: Optional[str]
    created_at: str


class CreateApiKeyResponse(BaseModel):
    """Response when creating an API key (includes full key)."""
    key: str  # Full key, only shown once
    api_key: ApiKeyResponse


@router.get("/me/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: UserClaims = Depends(get_current_user),
) -> list[ApiKeyResponse]:
    """List current user's API keys."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        return []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, key_prefix, name, permissions,
                       last_used_at, expires_at, created_at
                FROM nexus.api_keys
                WHERE user_id = %s AND is_active = true
                ORDER BY created_at DESC
            """, (user_id,))

            return [
                ApiKeyResponse(
                    id=row["id"],
                    key_prefix=row["key_prefix"],
                    name=row["name"],
                    permissions=row["permissions"] or [],
                    last_used_at=row["last_used_at"].isoformat() if row["last_used_at"] else None,
                    expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
                    created_at=row["created_at"].isoformat(),
                )
                for row in cur.fetchall()
            ]


@router.post("/me/api-keys", response_model=CreateApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> CreateApiKeyResponse:
    """Create a new API key for current user."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate permissions - must be subset of user's permissions
    if request.permissions:
        invalid_perms = set(request.permissions) - set(user.permissions)
        if invalid_perms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid permissions: {invalid_perms}"
            )
        permissions = request.permissions
    else:
        permissions = user.permissions

    # Generate API key
    # Format: tg_{8 chars prefix}_{24 chars random}
    key_random = secrets.token_urlsafe(24)
    key_prefix = key_random[:8]
    full_key = f"tg_{key_random}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.api_keys
                (user_id, key_hash, key_prefix, name, permissions, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
            """, (
                user_id,
                key_hash,
                key_prefix,
                request.name,
                permissions,
                expires_at,
            ))

            row = cur.fetchone()
            conn.commit()

            # Log action
            await log_action(
                user_id,
                "api_key.create",
                "api_key",
                str(row["id"]),
                {"name": request.name, "expires_in_days": request.expires_in_days},
                req,
            )

            return CreateApiKeyResponse(
                key=full_key,
                api_key=ApiKeyResponse(
                    id=row["id"],
                    key_prefix=key_prefix,
                    name=request.name,
                    permissions=permissions,
                    last_used_at=None,
                    expires_at=expires_at.isoformat() if expires_at else None,
                    created_at=row["created_at"].isoformat(),
                ),
            )


@router.delete("/me/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke an API key."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verify key belongs to user
            cur.execute("""
                UPDATE nexus.api_keys
                SET is_active = false
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (key_id, user_id))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="API key not found")

            conn.commit()

            # Log action
            await log_action(
                user_id,
                "api_key.revoke",
                "api_key",
                str(key_id),
                request=req,
            )

            return {"success": True, "key_id": key_id}


# ============================================================================
# Session Management
# ============================================================================

class SessionResponse(BaseModel):
    """User session response."""
    id: int
    device_info: Optional[dict]
    ip_address: Optional[str]
    last_active_at: str
    created_at: str


@router.get("/me/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: UserClaims = Depends(get_current_user),
) -> list[SessionResponse]:
    """List current user's active sessions."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        return []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, device_info, ip_address, last_active_at, created_at
                FROM nexus.user_sessions
                WHERE user_id = %s AND expires_at > now()
                ORDER BY last_active_at DESC
            """, (user_id,))

            return [
                SessionResponse(
                    id=row["id"],
                    device_info=row["device_info"],
                    ip_address=str(row["ip_address"]) if row["ip_address"] else None,
                    last_active_at=row["last_active_at"].isoformat(),
                    created_at=row["created_at"].isoformat(),
                )
                for row in cur.fetchall()
            ]


@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke a specific session."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM nexus.user_sessions
                WHERE id = %s AND user_id = %s
                RETURNING id
            """, (session_id, user_id))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")

            conn.commit()
            return {"success": True, "session_id": session_id}


@router.delete("/me/sessions")
async def revoke_all_sessions(
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke all sessions except current."""
    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM nexus.user_sessions
                WHERE user_id = %s
                RETURNING id
            """, (user_id,))

            count = cur.rowcount
            conn.commit()
            return {"success": True, "sessions_revoked": count}
