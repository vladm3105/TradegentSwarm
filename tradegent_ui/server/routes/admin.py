"""Admin routes for Tradegent Agent UI."""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from typing import Optional

from ..auth import get_current_user, UserClaims, require_admin
from ..audit import log_action
from ..database import get_db_connection

log = structlog.get_logger()
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
    """List all users (admin only).

    Supports pagination and search by email/name.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Build query
            base_query = """
                SELECT u.id, u.auth0_sub, u.email, u.name, u.picture,
                       u.is_active, u.is_admin,
                       nexus.get_user_roles(u.id) as roles,
                       u.last_login_at, u.created_at
                FROM nexus.users u
            """
            count_query = "SELECT COUNT(*) FROM nexus.users u"
            params = []

            if search:
                search_clause = " WHERE u.email ILIKE %s OR u.name ILIKE %s"
                base_query += search_clause
                count_query += search_clause
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern])

            # Get total count
            cur.execute(count_query, params)
            total = cur.fetchone()["count"]

            # Get paginated results
            offset = (page - 1) * limit
            base_query += " ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(base_query, params)
            rows = cur.fetchall()

            users = [
                AdminUser(
                    id=row["id"],
                    auth0_sub=row["auth0_sub"],
                    email=row["email"],
                    name=row["name"],
                    picture=row["picture"],
                    is_active=row["is_active"],
                    is_admin=row["is_admin"],
                    roles=row["roles"] or [],
                    last_login_at=row["last_login_at"].isoformat() if row["last_login_at"] else None,
                    created_at=row["created_at"].isoformat(),
                )
                for row in rows
            ]

            return UsersListResponse(
                users=users,
                total=total,
                page=page,
                limit=limit,
            )


@router.get("/users/{user_id}", response_model=AdminUser)
@require_admin
async def get_user(
    user_id: int,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Get a specific user by ID (admin only)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT u.id, u.auth0_sub, u.email, u.name, u.picture,
                       u.is_active, u.is_admin,
                       nexus.get_user_roles(u.id) as roles,
                       u.last_login_at, u.created_at
                FROM nexus.users u
                WHERE u.id = %s
            """, (user_id,))

            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")

            return AdminUser(
                id=row["id"],
                auth0_sub=row["auth0_sub"],
                email=row["email"],
                name=row["name"],
                picture=row["picture"],
                is_active=row["is_active"],
                is_admin=row["is_admin"],
                roles=row["roles"] or [],
                last_login_at=row["last_login_at"].isoformat() if row["last_login_at"] else None,
                created_at=row["created_at"].isoformat(),
            )


@router.put("/users/{user_id}/roles", response_model=AdminUser)
@require_admin
async def update_user_roles(
    user_id: int,
    request: UpdateRolesRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Update a user's roles (admin only)."""
    admin_user_id = None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get admin's user ID
            cur.execute(
                "SELECT id FROM nexus.users WHERE auth0_sub = %s",
                (user.sub,)
            )
            admin_row = cur.fetchone()
            admin_user_id = admin_row["id"] if admin_row else None

            # Verify target user exists
            cur.execute("SELECT id FROM nexus.users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            # Get role IDs
            cur.execute(
                "SELECT id, name FROM nexus.roles WHERE name = ANY(%s)",
                (request.roles,)
            )
            role_map = {r["name"]: r["id"] for r in cur.fetchall()}

            # Validate all roles exist
            for role_name in request.roles:
                if role_name not in role_map:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid role: {role_name}"
                    )

            # Clear existing roles and add new ones
            cur.execute("DELETE FROM nexus.user_roles WHERE user_id = %s", (user_id,))
            for role_name in request.roles:
                cur.execute("""
                    INSERT INTO nexus.user_roles (user_id, role_id, assigned_by)
                    VALUES (%s, %s, %s)
                """, (user_id, role_map[role_name], admin_user_id))

            conn.commit()

    # Log the action
    if admin_user_id:
        await log_action(
            admin_user_id,
            "admin.user_role_change",
            "user",
            str(user_id),
            {"new_roles": request.roles},
            req,
        )

    # Return updated user
    return await get_user(user_id, user)


@router.put("/users/{user_id}/status", response_model=AdminUser)
@require_admin
async def update_user_status(
    user_id: int,
    request: UpdateStatusRequest,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> AdminUser:
    """Activate or deactivate a user (admin only)."""
    admin_user_id = None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get admin's user ID
            cur.execute(
                "SELECT id FROM nexus.users WHERE auth0_sub = %s",
                (user.sub,)
            )
            admin_row = cur.fetchone()
            admin_user_id = admin_row["id"] if admin_row else None

            # Update user status
            cur.execute("""
                UPDATE nexus.users
                SET is_active = %s, updated_at = now()
                WHERE id = %s
                RETURNING id
            """, (request.is_active, user_id))

            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            conn.commit()

    # Log the action
    if admin_user_id:
        action = "admin.user_activate" if request.is_active else "admin.user_deactivate"
        await log_action(
            admin_user_id,
            action,
            "user",
            str(user_id),
            request=req,
        )

    return await get_user(user_id, user)


@router.delete("/users/{user_id}/data")
@require_admin
async def delete_user_data(
    user_id: int,
    req: Request,
    user: UserClaims = Depends(get_current_user),
) -> dict:
    """Delete all user data (GDPR compliance, admin only).

    This permanently deletes all user data from:
    - All tables with user_id column
    - Neo4j graph (TODO)
    - RAG embeddings (TODO)
    """
    admin_user_id = None

    # Tables to clear (ordered by dependencies)
    USER_DATA_TABLES = [
        "nexus.audit_log",
        "nexus.login_history",
        "nexus.user_sessions",
        "nexus.api_keys",
        "nexus.user_roles",
        "nexus.skill_invocations",
        "nexus.task_queue",
        "nexus.run_history",
        "nexus.trades",
        "nexus.stocks",
        "nexus.schedules",
        "nexus.kb_stock_analyses",
        "nexus.kb_earnings_analyses",
        "nexus.kb_research_analyses",
        "nexus.kb_ticker_profiles",
        "nexus.kb_trade_journals",
        "nexus.kb_watchlist_entries",
        "nexus.kb_reviews",
        "nexus.kb_learnings",
        "nexus.kb_strategies",
        "nexus.kb_scanner_configs",
        "nexus.rag_documents",
        "nexus.rag_chunks",
    ]

    tables_cleared = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get admin's user ID
            cur.execute(
                "SELECT id FROM nexus.users WHERE auth0_sub = %s",
                (user.sub,)
            )
            admin_row = cur.fetchone()
            admin_user_id = admin_row["id"] if admin_row else None

            # Get user info before deletion
            cur.execute(
                "SELECT email FROM nexus.users WHERE id = %s",
                (user_id,)
            )
            user_row = cur.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="User not found")

            user_email = user_row["email"]

            # Log GDPR request
            cur.execute("""
                INSERT INTO nexus.gdpr_deletion_requests
                (user_id, user_email, processed_by, status)
                VALUES (%s, %s, %s, 'processing')
                RETURNING id
            """, (user_id, user_email, admin_user_id))
            request_id = cur.fetchone()["id"]

            try:
                # Delete from all tables
                for table in USER_DATA_TABLES:
                    try:
                        cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
                        if cur.rowcount > 0:
                            tables_cleared.append(f"{table}: {cur.rowcount}")
                    except Exception as e:
                        log.warn(f"Could not clear {table}", error=str(e))

                # Finally delete the user
                cur.execute("DELETE FROM nexus.users WHERE id = %s", (user_id,))

                # Update GDPR request
                cur.execute("""
                    UPDATE nexus.gdpr_deletion_requests
                    SET status = 'completed', processed_at = now(), tables_cleared = %s
                    WHERE id = %s
                """, (tables_cleared, request_id))

                conn.commit()

                log.info("User data deleted", user_id=user_id, tables=len(tables_cleared))

            except Exception as e:
                # Update GDPR request with error
                cur.execute("""
                    UPDATE nexus.gdpr_deletion_requests
                    SET status = 'failed', error_message = %s
                    WHERE id = %s
                """, (str(e), request_id))
                conn.commit()
                raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")

    return {
        "success": True,
        "user_id": user_id,
        "tables_cleared": tables_cleared,
    }


@router.get("/roles")
@require_admin
async def list_roles(
    user: UserClaims = Depends(get_current_user),
) -> list[dict]:
    """List all available roles (admin only)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id, r.name, r.display_name, r.description, r.is_system,
                       ARRAY_AGG(p.code) as permissions
                FROM nexus.roles r
                LEFT JOIN nexus.role_permissions rp ON r.id = rp.role_id
                LEFT JOIN nexus.permissions p ON rp.permission_id = p.id
                GROUP BY r.id
                ORDER BY r.id
            """)

            return [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "display_name": row["display_name"],
                    "description": row["description"],
                    "is_system": row["is_system"],
                    "permissions": [p for p in row["permissions"] if p],
                }
                for row in cur.fetchall()
            ]


@router.get("/permissions")
@require_admin
async def list_all_permissions(
    user: UserClaims = Depends(get_current_user),
) -> list[dict]:
    """List all available permissions (admin only)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT code, display_name, description, resource_type, action
                FROM nexus.permissions
                ORDER BY resource_type, action
            """)

            return [dict(row) for row in cur.fetchall()]


@router.get("/audit-log")
@require_admin
async def get_audit_log(
    user: UserClaims = Depends(get_current_user),
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """Get audit log entries (admin only).

    Supports filtering by user_id and action prefix.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT al.id, al.user_id, u.email as user_email,
                       al.action, al.resource_type, al.resource_id,
                       al.details, al.ip_address, al.created_at
                FROM nexus.audit_log al
                LEFT JOIN nexus.users u ON al.user_id = u.id
                WHERE 1=1
            """
            params = []

            if user_id:
                query += " AND al.user_id = %s"
                params.append(user_id)

            if action:
                query += " AND al.action LIKE %s"
                params.append(f"{action}%")

            query += " ORDER BY al.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])

            cur.execute(query, params)

            return [
                {
                    **dict(row),
                    "created_at": row["created_at"].isoformat(),
                    "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
                }
                for row in cur.fetchall()
            ]
