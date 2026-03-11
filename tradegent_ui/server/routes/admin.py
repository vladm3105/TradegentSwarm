"""Admin routes for Tradegent Agent UI."""
from fastapi import APIRouter, Depends, Request, Query
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user, UserClaims, require_admin
from ..services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminUser(BaseModel):
    """Admin user view."""
    id: int
    auth0_sub: str
    email: str
    name: Optional[str]
    picture: Optional[str]
    is_active: bool
    is_admin: bool
    roles: list[str]
    last_login_at: Optional[str]
    created_at: str


class UsersListResponse(BaseModel):
    """Paginated users list."""
    users: list[AdminUser]
    total: int
    page: int
    limit: int


class UpdateRolesRequest(BaseModel):
    """Request to update user roles."""
    roles: list[str]


class UpdateStatusRequest(BaseModel):
    """Request to update user status."""
    is_active: bool


@router.get("/users", response_model=UsersListResponse)
@require_admin
async def list_users(
    user: UserClaims = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
) -> UsersListResponse:
    """List all users (admin only)."""
    payload = await admin_service.list_users(page=page, limit=limit, search=search)
    return UsersListResponse(
        users=[AdminUser(**row) for row in payload["users"]],
        total=payload["total"],
        page=payload["page"],
        limit=payload["limit"],
    )


@router.get("/users/{user_id}", response_model=AdminUser)
@require_admin
async def get_user(
    user_id: int,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Get a specific user by ID (admin only)."""
    payload = await admin_service.get_user(user_id)
    return AdminUser(**payload)


@router.put("/users/{user_id}/roles", response_model=AdminUser)
@require_admin
async def update_user_roles(
    user_id: int,
    request: UpdateRolesRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Update a user's roles (admin only)."""
    payload = await admin_service.update_user_roles(user_id, request.roles, req, user)
    return AdminUser(**payload)


@router.put("/users/{user_id}/status", response_model=AdminUser)
@require_admin
async def update_user_status(
    user_id: int,
    request: UpdateStatusRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Activate or deactivate a user (admin only)."""
    payload = await admin_service.update_user_status(user_id, request.is_active, req, user)
    return AdminUser(**payload)


@router.delete("/users/{user_id}/data")
@require_admin
async def delete_user_data(
    user_id: int,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Delete all user data (GDPR compliance, admin only)."""
    return await admin_service.delete_user_data(user_id=user_id, user=user)


@router.get("/roles")
@require_admin
async def list_roles(
    user: UserClaims = Depends(get_current_user),
) -> list[dict]:
    """List all available roles (admin only)."""
    return await admin_service.list_roles()


@router.get("/permissions")
@require_admin
async def list_all_permissions(
    user: UserClaims = Depends(get_current_user),
) -> list[dict]:
    """List all available permissions (admin only)."""
    return await admin_service.list_permissions()


@router.get("/audit-log")
@require_admin
async def get_audit_log(
    user: UserClaims = Depends(get_current_user),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Get audit log entries (admin only)."""
    return await admin_service.get_audit_log(
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset,
    )
