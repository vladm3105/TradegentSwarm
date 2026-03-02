"""JWT Authentication for Tradegent Agent UI.

Provides:
- Auth0 JWT validation (when configured)
- Built-in JWT validation (when Auth0 not configured)
- API key validation
- User claims extraction
- Permission decorators
"""
import hashlib
import hmac
import structlog
from datetime import datetime, timedelta
from typing import Optional, Callable
from functools import wraps

import bcrypt
import httpx
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import HTTPException, Depends, Request, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .config import get_settings

log = structlog.get_logger()

# Security scheme
security = HTTPBearer(auto_error=False)


class UserClaims(BaseModel):
    """User claims extracted from JWT or API key."""
    sub: str  # Auth0 subject (e.g., "auth0|123" or "google-oauth2|456")
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    roles: list[str] = []
    permissions: list[str] = []
    email_verified: bool = True
    is_api_key: bool = False
    api_key_id: Optional[int] = None


# Cache for JWKS (JSON Web Key Set)
_jwks_cache: dict = {}
_jwks_cache_expiry: Optional[datetime] = None
JWKS_CACHE_TTL = timedelta(hours=24)


async def get_jwks(domain: str) -> dict:
    """Fetch and cache JWKS from Auth0."""
    global _jwks_cache, _jwks_cache_expiry

    # Return cached JWKS if not expired
    if _jwks_cache and _jwks_cache_expiry and datetime.utcnow() < _jwks_cache_expiry:
        return _jwks_cache

    # Fetch JWKS from Auth0
    jwks_url = f"https://{domain}/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            _jwks_cache = response.json()
            _jwks_cache_expiry = datetime.utcnow() + JWKS_CACHE_TTL
            log.info("JWKS cache refreshed", domain=domain)
            return _jwks_cache
    except Exception as e:
        log.error("Failed to fetch JWKS", domain=domain, error=str(e))
        # Return cached version if available (fallback)
        if _jwks_cache:
            log.warn("Using stale JWKS cache")
            return _jwks_cache
        raise HTTPException(status_code=503, detail="Auth service unavailable")


def get_signing_key(jwks: dict, token: str) -> str:
    """Get the signing key from JWKS that matches the token's kid."""
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header.get("kid"):
            return key

    raise HTTPException(status_code=401, detail="Unable to find appropriate key")


async def validate_token(token: str) -> UserClaims:
    """Validate a JWT and return user claims.

    Supports both Auth0 RS256 tokens and built-in HS256 tokens.
    """
    import os
    settings = get_settings()

    # Check for demo token - ONLY allowed in development/debug mode
    # SECURITY: Demo tokens bypass authentication, never allow in production
    if token.startswith("demo-token-"):
        is_debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        if not is_debug:
            log.warning("Demo token rejected in production mode", token_prefix=token[:15])
            raise HTTPException(status_code=401, detail="Demo tokens not allowed in production")
        return _create_demo_claims(token)

    # If Auth0 is not configured, validate as built-in JWT
    if not settings.auth0_configured:
        return await _validate_builtin_token(token)

    try:
        # Get JWKS
        jwks = await get_jwks(settings.auth0_domain)
        signing_key = get_signing_key(jwks, token)

        # Verify and decode token
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=settings.auth0_algorithms,
            audience=settings.auth0_audience,
            issuer=f"https://{settings.auth0_domain}/",
        )

        # Extract claims
        namespace = "https://tradegent.local"
        return UserClaims(
            sub=payload.get("sub", ""),
            email=payload.get("email", ""),
            name=payload.get("name"),
            picture=payload.get("picture"),
            roles=payload.get(f"{namespace}/roles", []),
            permissions=payload.get("permissions", []),
            email_verified=payload.get("email_verified", True),
        )

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        log.error("JWT validation failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


async def _validate_builtin_token(token: str) -> UserClaims:
    """Validate a built-in HS256 JWT token."""
    settings = get_settings()

    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )

        return UserClaims(
            sub=payload.get("sub", ""),
            email=payload.get("email", ""),
            name=payload.get("name"),
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            email_verified=True,
        )

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        log.error("Built-in JWT validation failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token")


def create_builtin_token(user_id: str, email: str, name: str,
                         roles: list[str], permissions: list[str]) -> str:
    """Create a built-in HS256 JWT token."""
    settings = get_settings()

    if not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "roles": roles,
        "permissions": permissions,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours),
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


async def authenticate_builtin_user(email: str, password: str) -> Optional[UserClaims]:
    """Authenticate a user with email/password against built-in accounts.

    Built-in accounts:
    - Admin: Superuser with full access (like PostgreSQL's postgres user)
    - Demo: Test account with trader role (optional)
    """
    settings = get_settings()

    # Check admin account (superuser)
    # SECURITY: Use constant-time comparison to prevent timing attacks
    if settings.admin_email and email.lower() == settings.admin_email.lower():
        if settings.admin_password and hmac.compare_digest(password, settings.admin_password):
            return UserClaims(
                sub="builtin|admin",
                email=settings.admin_email,
                name=settings.admin_name,
                roles=["admin"],
                permissions=[
                    "read:portfolio", "write:portfolio",
                    "read:trades", "write:trades",
                    "read:analyses", "write:analyses",
                    "read:watchlist", "write:watchlist",
                    "read:knowledge", "write:knowledge",
                    "admin:users", "admin:system", "admin:settings",
                ],
            )

    # Check demo account (optional, for testing)
    # SECURITY: Use constant-time comparison to prevent timing attacks
    if settings.demo_email and email.lower() == settings.demo_email.lower():
        if settings.demo_password and hmac.compare_digest(password, settings.demo_password):
            return UserClaims(
                sub="builtin|demo",
                email=settings.demo_email,
                name="Demo Trader",
                roles=["trader"],
                permissions=[
                    "read:portfolio", "write:portfolio",
                    "read:trades", "write:trades",
                    "read:analyses", "write:analyses",
                    "read:watchlist", "write:watchlist",
                    "read:knowledge", "write:knowledge",
                ],
            )

    return None


def _create_demo_claims(token: str) -> UserClaims:
    """Create claims for demo tokens (development only).

    SECURITY: This function should only be called after validate_token()
    has verified that DEBUG mode is enabled. Demo tokens are a security
    risk and must never be accepted in production.
    """
    settings = get_settings()

    # Extract user ID from demo token
    user_id = token.replace("demo-token-", "")

    # Demo users
    if user_id == "1" or user_id == "demo":
        return UserClaims(
            sub="builtin|demo",
            email=settings.demo_email or "demo@tradegent.local",
            name="Demo Trader",
            roles=["trader"],
            permissions=[
                "read:portfolio", "write:portfolio",
                "read:trades", "write:trades",
                "read:analyses", "write:analyses",
                "read:watchlist", "write:watchlist",
                "read:knowledge", "write:knowledge",
            ],
        )
    elif user_id == "2" or user_id == "admin":
        return UserClaims(
            sub="builtin|admin",
            email=settings.admin_email or "admin@tradegent.local",
            name=settings.admin_name,
            roles=["admin"],
            permissions=[
                "read:portfolio", "write:portfolio",
                "read:trades", "write:trades",
                "read:analyses", "write:analyses",
                "read:watchlist", "write:watchlist",
                "read:knowledge", "write:knowledge",
                "admin:users", "admin:system", "admin:settings",
            ],
        )

    raise HTTPException(status_code=401, detail="Invalid demo token")


async def validate_api_key(key: str) -> UserClaims:
    """Validate an API key and return user claims."""
    from .database import get_db_connection

    # API keys start with "tg_"
    if not key.startswith("tg_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # Hash the key for comparison
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[3:11]  # First 8 chars after "tg_"

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Find API key
                cur.execute("""
                    SELECT ak.id, ak.user_id, ak.permissions, ak.expires_at,
                           u.email, u.name, u.is_active
                    FROM nexus.api_keys ak
                    JOIN nexus.users u ON ak.user_id = u.id
                    WHERE ak.key_hash = %s AND ak.key_prefix = %s AND ak.is_active = true
                """, (key_hash, key_prefix))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=401, detail="Invalid API key")

                # Check expiration
                if row["expires_at"] and row["expires_at"] < datetime.utcnow():
                    raise HTTPException(status_code=401, detail="API key expired")

                # Check user is active
                if not row["is_active"]:
                    raise HTTPException(status_code=403, detail="User account deactivated")

                # Update last used timestamp
                cur.execute(
                    "UPDATE nexus.api_keys SET last_used_at = now() WHERE id = %s",
                    (row["id"],)
                )
                conn.commit()

                # Get user roles
                cur.execute("""
                    SELECT r.name FROM nexus.user_roles ur
                    JOIN nexus.roles r ON ur.role_id = r.id
                    WHERE ur.user_id = %s
                """, (row["user_id"],))
                roles = [r["name"] for r in cur.fetchall()]

                return UserClaims(
                    sub=f"api_key|{row['user_id']}",
                    email=row["email"],
                    name=row["name"],
                    roles=roles,
                    permissions=row["permissions"] or [],
                    is_api_key=True,
                    api_key_id=row["id"],
                )

    except HTTPException:
        raise
    except Exception as e:
        log.error("API key validation failed", error=str(e))
        raise HTTPException(status_code=500, detail="Auth error")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Dependency to get the current authenticated user.

    Authentication is ALWAYS required. There is no bypass.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = credentials.credentials

    # Check if it's an API key (starts with "tg_")
    if token.startswith("tg_"):
        return await validate_api_key(token)

    # Otherwise validate as JWT
    claims = await validate_token(token)

    # Check if user is still active in database (skip for builtin users)
    if not claims.sub.startswith("builtin|"):
        await _check_user_active(claims.sub)

    return claims


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Optional[UserClaims]:
    """Optional authentication - returns None if not authenticated."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def _check_user_active(auth0_sub: str) -> None:
    """Check if user is still active in the database."""
    from .database import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT is_active FROM nexus.users WHERE auth0_sub = %s",
                    (auth0_sub,)
                )
                row = cur.fetchone()

                if row and not row["is_active"]:
                    raise HTTPException(status_code=403, detail="Account deactivated")

    except HTTPException:
        raise
    except Exception as e:
        # Log but don't fail - user might not be synced yet
        log.warn("Could not check user active status", sub=auth0_sub, error=str(e))


async def validate_websocket_token(websocket: WebSocket) -> Optional[UserClaims]:
    """Validate token from WebSocket query parameter.

    Authentication is ALWAYS required for WebSocket connections.
    """
    # Get token from query param
    token = websocket.query_params.get("token")
    if not token:
        return None

    try:
        if token.startswith("tg_"):
            return await validate_api_key(token)
        return await validate_token(token)
    except HTTPException:
        return None


def require_permission(permission: str) -> Callable:
    """Decorator to require a specific permission."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: UserClaims = Depends(get_current_user), **kwargs):
            if permission not in user.permissions:
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission} required"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def require_role(role: str) -> Callable:
    """Decorator to require a specific role."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: UserClaims = Depends(get_current_user), **kwargs):
            if role not in user.roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Role denied: {role} required"
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator


def require_admin(func: Callable) -> Callable:
    """Decorator to require admin role."""
    return require_role("admin")(func)


async def get_db_user_id(auth0_sub: str) -> Optional[int]:
    """Get the database user ID for an Auth0 subject."""
    from .database import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM nexus.users WHERE auth0_sub = %s",
                    (auth0_sub,)
                )
                row = cur.fetchone()
                return row["id"] if row else None
    except Exception as e:
        log.error("Failed to get user ID", sub=auth0_sub, error=str(e))
        return None


async def sync_user_from_auth0(claims: UserClaims) -> int:
    """Sync user from Auth0 claims to database, return user ID."""
    from .database import get_db_connection

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Upsert user
            cur.execute("""
                INSERT INTO nexus.users (auth0_sub, email, name, picture, email_verified, last_login_at)
                VALUES (%s, %s, %s, %s, %s, now())
                ON CONFLICT (auth0_sub) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    picture = EXCLUDED.picture,
                    email_verified = EXCLUDED.email_verified,
                    last_login_at = now(),
                    updated_at = now()
                RETURNING id
            """, (claims.sub, claims.email, claims.name, claims.picture, claims.email_verified))

            user_id = cur.fetchone()["id"]

            # Sync roles if provided by Auth0
            if claims.roles:
                # Get role IDs
                cur.execute(
                    "SELECT id, name FROM nexus.roles WHERE name = ANY(%s)",
                    (claims.roles,)
                )
                role_map = {r["name"]: r["id"] for r in cur.fetchall()}

                # Clear existing roles and add new ones
                cur.execute("DELETE FROM nexus.user_roles WHERE user_id = %s", (user_id,))
                for role_name in claims.roles:
                    if role_name in role_map:
                        cur.execute(
                            "INSERT INTO nexus.user_roles (user_id, role_id) VALUES (%s, %s)",
                            (user_id, role_map[role_name])
                        )

            conn.commit()
            log.info("User synced from Auth0", user_id=user_id, sub=claims.sub)
            return user_id
