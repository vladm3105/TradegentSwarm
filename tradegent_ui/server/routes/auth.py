"""Authentication routes for Tradegent Agent UI."""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..auth import (
    get_current_user,
    UserClaims,
    sync_user_from_auth0,
    get_db_user_id,
)
from ..audit import log_action, log_login
from ..database import get_db_connection

log = structlog.get_logger()
router = APIRouter(prefix="/api/auth", tags=["auth"])


class UserProfile(BaseModel):
    """User profile response."""
    id: int
    auth0_sub: str
    email: str
    name: Optional[str]
    picture: Optional[str]
    roles: list[str]
    permissions: list[str]
    ib_account_id: Optional[str] = None
    ib_trading_mode: Optional[str] = None
    preferences: dict = {}
    requires_onboarding: bool = False


class SyncUserRequest(BaseModel):
    """Request to sync user from Auth0."""
    sub: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    email_verified: bool = True
    roles: list[str] = []


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    user: UserClaims = Depends(get_current_user),
) -> UserProfile:
    """Get current user's profile.

    Returns user profile with roles, permissions, and preferences.
    """
    # Get database user
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.*, nexus.get_user_roles(u.id) as roles,
                       nexus.get_user_permissions(u.id) as permissions
                FROM nexus.users u
                WHERE u.auth0_sub = %s
            """, (user.sub,))

            row = cur.fetchone()

            if not row:
                # User not synced yet, sync from claims
                user_id = await sync_user_from_auth0(user)
                cur.execute("""
                    SELECT u.*, nexus.get_user_roles(u.id) as roles,
                           nexus.get_user_permissions(u.id) as permissions
                    FROM nexus.users u
                    WHERE u.id = %s
                """, (user_id,))
                row = cur.fetchone()

            # Check onboarding status
            preferences = row["preferences"] or {}
            requires_onboarding = not preferences.get("onboarding_completed", False)

            return UserProfile(
                id=row["id"],
                auth0_sub=row["auth0_sub"],
                email=row["email"],
                name=row["name"],
                picture=row["picture"],
                roles=row["roles"] or [],
                permissions=row["permissions"] or [],
                ib_account_id=row["ib_account_id"],
                ib_trading_mode=row["ib_trading_mode"],
                preferences=preferences,
                requires_onboarding=requires_onboarding,
            )


@router.post("/sync-user")
async def sync_user(
    request: SyncUserRequest,
    req: Request,
) -> dict:
    """Sync user from Auth0 callback.

    Called during login flow to ensure user exists in database.
    Semi-public endpoint - should be called from frontend during auth callback.
    """
    try:
        claims = UserClaims(
            sub=request.sub,
            email=request.email,
            name=request.name,
            picture=request.picture,
            email_verified=request.email_verified,
            roles=request.roles,
        )

        user_id = await sync_user_from_auth0(claims)

        # Log successful login
        await log_login(user_id, success=True, request=req)
        await log_action(user_id, "auth.login", request=req)

        return {"success": True, "user_id": user_id}

    except Exception as e:
        log.error("Failed to sync user", sub=request.sub, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to sync user")


@router.post("/logout")
async def logout(
    request: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Log out current user.

    Records logout in audit log. Frontend handles actual session cleanup.
    """
    user_id = await get_db_user_id(user.sub)
    if user_id:
        await log_action(user_id, "auth.logout", request=request)

    return {"success": True}


@router.post("/complete-onboarding")
async def complete_onboarding(
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Mark onboarding as complete for current user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.users
                SET preferences = preferences || '{"onboarding_completed": true}'::jsonb,
                    updated_at = now()
                WHERE auth0_sub = %s
                RETURNING id
            """, (user.sub,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            conn.commit()
            return {"success": True}


class CheckPermissionRequest(BaseModel):
    """Request to check permission."""
    permission: str


@router.post("/check-permission")
async def check_permission(
    request: CheckPermissionRequest,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Check if current user has a specific permission."""
    has_permission = request.permission in user.permissions
    return {
        "permission": request.permission,
        "granted": has_permission,
    }


@router.get("/permissions")
async def list_permissions(
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """List all permissions for current user."""
    return {
        "permissions": user.permissions,
        "roles": user.roles,
    }
