"""Admin service for user administration and GDPR deletion workflows."""

from typing import Optional, Any

import structlog
from fastapi import HTTPException, Request

from ..audit import log_action
from ..auth import UserClaims
from ..repositories import admin_repository

log = structlog.get_logger()

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


def _to_admin_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "auth0_sub": row["auth0_sub"],
        "email": row["email"],
        "name": row["name"],
        "picture": row["picture"],
        "is_active": row["is_active"],
        "is_admin": row["is_admin"],
        "roles": row["roles"] or [],
        "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None,
        "created_at": row["created_at"].isoformat(),
    }


async def list_users(page: int, limit: int, search: Optional[str]) -> dict[str, Any]:
    total, rows = admin_repository.list_users(page=page, limit=limit, search=search)
    return {
        "users": [_to_admin_user(row) for row in rows],
        "total": total,
        "page": page,
        "limit": limit,
    }


async def get_user(user_id: int) -> dict[str, Any]:
    row = admin_repository.get_user(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_admin_user(row)


async def update_user_roles(user_id: int, roles: list[str], req: Request, user: UserClaims) -> dict[str, Any]:
    admin_user_id = admin_repository.get_user_id_by_sub(user.sub)

    if not admin_repository.user_exists(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    role_map = admin_repository.get_role_map(roles)
    for role_name in roles:
        if role_name not in role_map:
            raise HTTPException(status_code=400, detail=f"Invalid role: {role_name}")

    admin_repository.replace_user_roles(user_id, [role_map[r] for r in roles], admin_user_id)

    if admin_user_id:
        await log_action(
            admin_user_id,
            "admin.user_role_change",
            "user",
            str(user_id),
            {"new_roles": roles},
            req,
        )

    return await get_user(user_id)


async def update_user_status(
    user_id: int,
    is_active: bool,
    req: Request,
    user: UserClaims,
) -> dict[str, Any]:
    admin_user_id = admin_repository.get_user_id_by_sub(user.sub)

    updated = admin_repository.update_user_status(user_id, is_active)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    if admin_user_id:
        action = "admin.user_activate" if is_active else "admin.user_deactivate"
        await log_action(admin_user_id, action, "user", str(user_id), request=req)

    return await get_user(user_id)


async def delete_user_data(user_id: int, user: UserClaims) -> dict[str, Any]:
    admin_user_id = admin_repository.get_user_id_by_sub(user.sub)

    user_email = admin_repository.get_user_email(user_id)
    if not user_email:
        raise HTTPException(status_code=404, detail="User not found")

    request_id = admin_repository.create_gdpr_deletion_request(
        user_id=user_id,
        user_email=user_email,
        processed_by=admin_user_id,
    )

    try:
        tables_cleared = admin_repository.execute_gdpr_deletion(
            request_id=request_id,
            user_id=user_id,
            user_data_tables=USER_DATA_TABLES,
        )
        log.info("User data deleted", user_id=user_id, tables=len(tables_cleared))
    except Exception as e:
        admin_repository.mark_gdpr_request_failed(request_id, str(e))
        raise HTTPException(status_code=500, detail=f"Deletion failed: {e}")

    return {
        "success": True,
        "user_id": user_id,
        "tables_cleared": tables_cleared,
    }


async def list_roles() -> list[dict[str, Any]]:
    rows = admin_repository.list_roles()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "display_name": row["display_name"],
            "description": row["description"],
            "is_system": row["is_system"],
            "permissions": [p for p in row["permissions"] if p],
        }
        for row in rows
    ]


async def list_permissions() -> list[dict[str, Any]]:
    return [dict(row) for row in admin_repository.list_permissions()]


async def get_audit_log(
    user_id: Optional[int],
    action: Optional[str],
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    rows = admin_repository.list_audit_log(
        user_id=user_id,
        action=action,
        limit=limit,
        offset=offset,
    )

    return [
        {
            **dict(row),
            "created_at": row["created_at"].isoformat(),
            "ip_address": str(row["ip_address"]) if row["ip_address"] else None,
        }
        for row in rows
    ]
