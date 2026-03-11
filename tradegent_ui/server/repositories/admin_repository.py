"""Admin repository for user/role/audit/GDPR data operations."""

from typing import Any, Optional, cast

from psycopg import sql

from ..database import get_db_connection


def list_users(page: int, limit: int, search: Optional[str]) -> tuple[int, list[dict[str, Any]]]:
    """List users with pagination and optional search."""
    base_query = """
        SELECT u.id, u.auth0_sub, u.email, u.name, u.picture,
               u.is_active, u.is_admin,
               nexus.get_user_roles(u.id) as roles,
               u.last_login_at, u.created_at
        FROM nexus.users u
    """
    count_query = "SELECT COUNT(*) FROM nexus.users u"
    params: list[Any] = []

    if search:
        search_clause = " WHERE u.email ILIKE %s OR u.name ILIKE %s"
        base_query += search_clause
        count_query += search_clause
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_query, tuple(params))
            total_row = cast(dict[str, Any], cur.fetchone())
            total = int(total_row["count"])

            offset = (page - 1) * limit
            query = base_query + " ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
            cur.execute(query, tuple(params + [limit, offset]))
            rows = cast(list[dict[str, Any]], cur.fetchall())

    return total, rows


def get_user(user_id: int) -> Optional[dict[str, Any]]:
    """Get one user by id with computed role names."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.id, u.auth0_sub, u.email, u.name, u.picture,
                       u.is_active, u.is_admin,
                       nexus.get_user_roles(u.id) as roles,
                       u.last_login_at, u.created_at
                FROM nexus.users u
                WHERE u.id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return cast(Optional[dict[str, Any]], row)


def get_user_id_by_sub(auth0_sub: str) -> Optional[int]:
    """Resolve DB user id from auth0 subject."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nexus.users WHERE auth0_sub = %s", (auth0_sub,))
            row = cur.fetchone()
    return int(row["id"]) if row else None


def user_exists(user_id: int) -> bool:
    """Check whether a user exists by id."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM nexus.users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return row is not None


def get_role_map(role_names: list[str]) -> dict[str, int]:
    """Return mapping of role_name -> role_id for requested names."""
    if not role_names:
        return {}
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM nexus.roles WHERE name = ANY(%s)",
                (role_names,),
            )
            rows = cur.fetchall()
    return {r["name"]: int(r["id"]) for r in rows}


def replace_user_roles(user_id: int, role_ids: list[int], assigned_by: Optional[int]) -> None:
    """Replace all user roles with given role ids."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM nexus.user_roles WHERE user_id = %s", (user_id,))
            for role_id in role_ids:
                cur.execute(
                    """
                    INSERT INTO nexus.user_roles (user_id, role_id, assigned_by)
                    VALUES (%s, %s, %s)
                    """,
                    (user_id, role_id, assigned_by),
                )
            conn.commit()


def update_user_status(user_id: int, is_active: bool) -> bool:
    """Set user active status. Returns True if user exists."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.users
                SET is_active = %s, updated_at = now()
                WHERE id = %s
                RETURNING id
                """,
                (is_active, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return row is not None


def get_user_email(user_id: int) -> Optional[str]:
    """Get user email by id."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email FROM nexus.users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return str(row["email"]) if row else None


def create_gdpr_deletion_request(user_id: int, user_email: str, processed_by: Optional[int]) -> int:
    """Create GDPR deletion request and return request id."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.gdpr_deletion_requests
                (user_id, user_email, processed_by, status)
                VALUES (%s, %s, %s, 'processing')
                RETURNING id
                """,
                (user_id, user_email, processed_by),
            )
            row = cast(dict[str, Any], cur.fetchone())
            conn.commit()
    return int(row["id"])


def execute_gdpr_deletion(
    request_id: int,
    user_id: int,
    user_data_tables: list[str],
) -> list[str]:
    """Execute GDPR deletion in one DB transaction and return cleared table summary."""
    tables_cleared: list[str] = []
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for table in user_data_tables:
                schema_name, table_name = table.split(".", 1)
                query = sql.SQL("DELETE FROM {}.{} WHERE user_id = %s").format(
                    sql.Identifier(schema_name),
                    sql.Identifier(table_name),
                )
                cur.execute(query, (user_id,))
                if cur.rowcount > 0:
                    tables_cleared.append(f"{table}: {cur.rowcount}")

            cur.execute("DELETE FROM nexus.users WHERE id = %s RETURNING id", (user_id,))
            if not cur.fetchone():
                raise ValueError("User not found during GDPR deletion")

            cur.execute(
                """
                UPDATE nexus.gdpr_deletion_requests
                SET status = 'completed', processed_at = now(), tables_cleared = %s
                WHERE id = %s
                """,
                (tables_cleared, request_id),
            )
            conn.commit()
    return tables_cleared


def mark_gdpr_request_completed(request_id: int, tables_cleared: list[str]) -> None:
    """Mark GDPR request as completed and persist cleared-table summary."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.gdpr_deletion_requests
                SET status = 'completed', processed_at = now(), tables_cleared = %s
                WHERE id = %s
                """,
                (tables_cleared, request_id),
            )
            conn.commit()


def mark_gdpr_request_failed(request_id: int, error_message: str) -> None:
    """Mark GDPR request as failed with error message."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.gdpr_deletion_requests
                SET status = 'failed', error_message = %s
                WHERE id = %s
                """,
                (error_message, request_id),
            )
            conn.commit()


def list_roles() -> list[dict[str, Any]]:
    """List all roles with aggregated permissions."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT r.id, r.name, r.display_name, r.description, r.is_system,
                       ARRAY_AGG(p.code) as permissions
                FROM nexus.roles r
                LEFT JOIN nexus.role_permissions rp ON r.id = rp.role_id
                LEFT JOIN nexus.permissions p ON rp.permission_id = p.id
                GROUP BY r.id
                ORDER BY r.id
                """
            )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def list_permissions() -> list[dict[str, Any]]:
    """List all permissions."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT code, display_name, description, resource_type, action
                FROM nexus.permissions
                ORDER BY resource_type, action
                """
            )
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)


def list_audit_log(
    user_id: Optional[int],
    action: Optional[str],
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    """List audit log entries with optional filtering."""
    query = """
        SELECT al.id, al.user_id, u.email as user_email,
               al.action, al.resource_type, al.resource_id,
               al.details, al.ip_address, al.created_at
        FROM nexus.audit_log al
        LEFT JOIN nexus.users u ON al.user_id = u.id
        WHERE 1=1
    """
    params: list[Any] = []

    if user_id is not None:
        query += " AND al.user_id = %s"
        params.append(user_id)

    if action:
        query += " AND al.action LIKE %s"
        params.append(f"{action}%")

    query += " ORDER BY al.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
    return cast(list[dict[str, Any]], rows)
