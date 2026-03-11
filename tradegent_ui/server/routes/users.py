"""User routes for Tradegent Agent UI."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user, UserClaims
from ..services import users_service

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
    payload = await users_service.update_profile(request, req, user)
    return ProfileResponse(**payload)


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
    payload = await users_service.get_ib_account(user)
    return IBAccountResponse(**payload)


@router.put("/me/ib-account", response_model=IBAccountResponse)
async def update_ib_account(
    request: UpdateIBAccountRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> IBAccountResponse:
    """Update current user's IB account settings."""
    payload = await users_service.update_ib_account(request, req, user)
    return IBAccountResponse(**payload)


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
    rows = await users_service.list_api_keys(user)
    return [ApiKeyResponse(**row) for row in rows]


@router.post("/me/api-keys", response_model=CreateApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> CreateApiKeyResponse:
    """Create a new API key for current user."""
    payload = await users_service.create_api_key(request, req, user)
    return CreateApiKeyResponse(
        key=payload["key"],
        api_key=ApiKeyResponse(**payload["api_key"]),
    )


@router.delete("/me/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke an API key."""
    return await users_service.revoke_api_key(key_id, req, user)


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
    rows = await users_service.list_sessions(user)
    return [SessionResponse(**row) for row in rows]


@router.delete("/me/sessions/{session_id}")
async def revoke_session(
    session_id: int,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke a specific session."""
    return await users_service.revoke_session(session_id, user)


@router.delete("/me/sessions")
async def revoke_all_sessions(
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Revoke all sessions except current."""
    return await users_service.revoke_all_sessions(user)
