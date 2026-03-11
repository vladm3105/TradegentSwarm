"""System settings routes for Tradegent Agent UI."""
import os
import structlog
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user, UserClaims, require_admin
from ..audit import log_action
from ..config import get_settings
from ..services import settings_service

log = structlog.get_logger()
router = APIRouter(prefix="/api/settings", tags=["settings"])


class Auth0ConfigRequest(BaseModel):
    """Request to configure Auth0 settings."""
    auth0_domain: str
    auth0_client_id: str
    auth0_client_secret: str
    auth0_audience: Optional[str] = "https://tradegent-api.local"


class Auth0ConfigResponse(BaseModel):
    """Auth0 configuration response (secrets masked)."""
    auth0_domain: str
    auth0_client_id: str
    auth0_client_secret_masked: str
    auth0_audience: str
    is_configured: bool


class SystemSettingsResponse(BaseModel):
    """System settings response."""
    auth0_configured: bool
    auth0_domain: str
    auth0_audience: str
    rate_limit_enabled: bool
    rate_limit_requests_per_minute: int
    max_sessions_per_user: int
    admin_email: str
    debug: bool


@router.get("/system", response_model=SystemSettingsResponse)
@require_admin
async def get_system_settings(
    user: UserClaims = Depends(get_current_user),
) -> SystemSettingsResponse:
    """Get system settings (admin only)."""
    settings = get_settings()

    return SystemSettingsResponse(
        auth0_configured=settings.auth0_configured,
        auth0_domain=settings.auth0_domain,
        auth0_audience=settings.auth0_audience,
        rate_limit_enabled=settings.rate_limit_enabled,
        rate_limit_requests_per_minute=settings.rate_limit_requests_per_minute,
        max_sessions_per_user=settings.max_sessions_per_user,
        admin_email=settings.admin_email,
        debug=settings.debug,
    )


@router.get("/auth0", response_model=Auth0ConfigResponse)
@require_admin
async def get_auth0_config(
    user: UserClaims = Depends(get_current_user),
) -> Auth0ConfigResponse:
    """Get Auth0 configuration (admin only, secrets masked)."""
    settings = get_settings()

    # Mask the client secret
    secret = settings.auth0_client_secret
    if secret:
        masked = secret[:4] + "*" * (len(secret) - 8) + secret[-4:] if len(secret) > 8 else "****"
    else:
        masked = ""

    return Auth0ConfigResponse(
        auth0_domain=settings.auth0_domain,
        auth0_client_id=settings.auth0_client_id,
        auth0_client_secret_masked=masked,
        auth0_audience=settings.auth0_audience,
        is_configured=settings.auth0_configured,
    )


@router.put("/auth0", response_model=Auth0ConfigResponse)
@require_admin
async def update_auth0_config(
    request: Auth0ConfigRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> Auth0ConfigResponse:
    """Update Auth0 configuration (admin only).

    This updates the .env file and stores settings in the database.
    A server restart may be required for changes to take full effect.
    """
    # Validate the Auth0 domain format
    if not request.auth0_domain or "." not in request.auth0_domain:
        raise HTTPException(
            status_code=400,
            detail="Invalid Auth0 domain format (e.g., your-tenant.auth0.com)"
        )

    settings_service.persist_auth0_config(
        domain=request.auth0_domain,
        client_id=request.auth0_client_id,
        client_secret=request.auth0_client_secret,
        audience=request.auth0_audience or "https://tradegent-api.local",
    )

    # Update the .env file for the server
    env_path = Path(__file__).parent.parent / ".env"
    try:
        _update_env_file(env_path, {
            "AUTH0_DOMAIN": request.auth0_domain,
            "AUTH0_CLIENT_ID": request.auth0_client_id,
            "AUTH0_CLIENT_SECRET": request.auth0_client_secret,
            "AUTH0_AUDIENCE": request.auth0_audience or "https://tradegent-api.local",
        })
    except Exception as e:
        log.error("Failed to update .env file", error=str(e))
        # Don't fail - settings are in DB

    # Update the frontend .env.local file
    frontend_env_path = Path(__file__).parent.parent.parent / "frontend" / ".env.local"
    try:
        _update_env_file(frontend_env_path, {
            "NEXT_PUBLIC_AUTH0_CONFIGURED": "true",
            "AUTH0_CLIENT_ID": request.auth0_client_id,
            "AUTH0_ISSUER_BASE_URL": f"https://{request.auth0_domain}",
            "AUTH0_AUDIENCE": request.auth0_audience or "https://tradegent-api.local",
            "NEXT_PUBLIC_AUTH0_ISSUER": f"https://{request.auth0_domain}",
            "NEXT_PUBLIC_AUTH0_CLIENT_ID": request.auth0_client_id,
        })
    except Exception as e:
        log.error("Failed to update frontend .env.local file", error=str(e))

    # Log the action
    await log_action(
        settings_service.get_user_id(user.sub),
        "settings.update_auth0",
        details={"domain": request.auth0_domain},
        request=req,
    )

    # Mask secret for response
    secret = request.auth0_client_secret
    masked = secret[:4] + "*" * (len(secret) - 8) + secret[-4:] if len(secret) > 8 else "****"

    log.info(
        "Auth0 configuration updated",
        domain=request.auth0_domain,
        restart_required=True,
    )

    return Auth0ConfigResponse(
        auth0_domain=request.auth0_domain,
        auth0_client_id=request.auth0_client_id,
        auth0_client_secret_masked=masked,
        auth0_audience=request.auth0_audience or "https://tradegent-api.local",
        is_configured=True,
    )


def _update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """Update key=value pairs in an .env file."""
    settings_service.update_env_file(env_path, updates)


@router.post("/restart-server")
@require_admin
async def restart_server(
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Request server restart to apply configuration changes.

    Note: This signals the need for a restart but doesn't actually restart.
    The actual restart should be handled by the process manager (systemd, docker, etc).
    """
    await log_action(
        settings_service.get_user_id(user.sub),
        "settings.restart_requested",
        request=req,
    )

    log.info("Server restart requested by admin", user=user.email)

    return {
        "success": True,
        "message": "Server restart requested. Changes will take effect after restart.",
        "restart_required": True,
    }
