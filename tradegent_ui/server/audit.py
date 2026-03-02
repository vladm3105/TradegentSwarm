"""Audit logging for Tradegent Agent UI."""
import structlog
from datetime import datetime
from typing import Optional, Any
from fastapi import Request

log = structlog.get_logger()


async def log_action(
    user_id: int,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> Optional[int]:
    """Log a user action to the audit log.

    Args:
        user_id: Database user ID
        action: Action performed (e.g., "create_analysis", "execute_trade")
        resource_type: Type of resource affected (e.g., "stock", "trade")
        resource_id: Identifier of the resource (e.g., ticker, trade_id)
        details: Additional action-specific data
        request: FastAPI request for IP/user agent extraction

    Returns:
        Audit log entry ID, or None if logging failed

    Common actions:
        - auth.login, auth.logout, auth.failed_login
        - user.create, user.update, user.deactivate, user.delete_data
        - analysis.create, analysis.update, analysis.delete
        - trade.execute, trade.journal_create, trade.journal_update
        - watchlist.add, watchlist.remove, watchlist.trigger
        - portfolio.view, portfolio.export
        - api_key.create, api_key.revoke, api_key.use
        - admin.user_role_change, admin.user_deactivate
    """
    from .database import get_db_connection

    # Extract request info
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.audit_log
                    (user_id, action, resource_type, resource_id, details, ip_address, user_agent)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    user_id,
                    action,
                    resource_type,
                    resource_id,
                    details,
                    ip_address,
                    user_agent,
                ))

                audit_id = cur.fetchone()["id"]
                conn.commit()

                log.debug(
                    "Audit log entry created",
                    audit_id=audit_id,
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                )

                return audit_id

    except Exception as e:
        # Don't fail the request if audit logging fails
        log.error(
            "Failed to create audit log entry",
            user_id=user_id,
            action=action,
            error=str(e),
        )
        return None


async def log_login(
    user_id: int,
    success: bool,
    request: Request,
    failure_reason: Optional[str] = None,
) -> None:
    """Log a login attempt.

    Args:
        user_id: Database user ID (or 0 if unknown)
        success: Whether login was successful
        request: FastAPI request
        failure_reason: Reason for failure (e.g., "invalid_password", "account_locked")
    """
    from .database import get_db_connection

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.login_history
                    (user_id, success, ip_address, user_agent, failure_reason)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    user_id if user_id else None,
                    success,
                    ip_address,
                    user_agent,
                    failure_reason,
                ))
                conn.commit()

    except Exception as e:
        log.error("Failed to log login attempt", error=str(e))


async def check_brute_force(
    ip_address: str,
    window_minutes: int = 15,
    max_attempts: int = 5,
) -> bool:
    """Check if an IP address is exhibiting brute force behavior.

    Args:
        ip_address: IP address to check
        window_minutes: Time window to check
        max_attempts: Max failed attempts allowed

    Returns:
        True if brute force detected, False otherwise
    """
    from .database import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as failed_attempts
                    FROM nexus.login_history
                    WHERE ip_address = %s
                      AND success = false
                      AND created_at > (now() - interval '%s minutes')
                """, (ip_address, window_minutes))

                row = cur.fetchone()
                failed_attempts = row["failed_attempts"] if row else 0

                if failed_attempts >= max_attempts:
                    log.warn(
                        "Brute force detected",
                        ip_address=ip_address,
                        failed_attempts=failed_attempts,
                        window_minutes=window_minutes,
                    )
                    return True

                return False

    except Exception as e:
        log.error("Failed to check brute force", error=str(e))
        return False


async def get_user_audit_history(
    user_id: int,
    limit: int = 100,
    offset: int = 0,
    action_filter: Optional[str] = None,
) -> list[dict]:
    """Get audit history for a user.

    Args:
        user_id: Database user ID
        limit: Max entries to return
        offset: Offset for pagination
        action_filter: Optional action prefix filter (e.g., "trade.")

    Returns:
        List of audit log entries
    """
    from .database import get_db_connection

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, action, resource_type, resource_id, details,
                           ip_address, created_at
                    FROM nexus.audit_log
                    WHERE user_id = %s
                """
                params = [user_id]

                if action_filter:
                    query += " AND action LIKE %s"
                    params.append(f"{action_filter}%")

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)
                return [dict(row) for row in cur.fetchall()]

    except Exception as e:
        log.error("Failed to get audit history", user_id=user_id, error=str(e))
        return []


class AuditContext:
    """Context manager for batch audit logging."""

    def __init__(self, user_id: int, request: Optional[Request] = None):
        self.user_id = user_id
        self.request = request
        self.entries: list[tuple] = []

    async def log(
        self,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Add an entry to the batch."""
        self.entries.append((action, resource_type, resource_id, details))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Flush all entries on exit."""
        for action, resource_type, resource_id, details in self.entries:
            await log_action(
                self.user_id,
                action,
                resource_type,
                resource_id,
                details,
                self.request,
            )
