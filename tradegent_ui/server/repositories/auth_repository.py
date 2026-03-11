"""Auth repository for direct user profile and onboarding persistence."""

from typing import Any, Optional, cast

from ..database import get_db_connection


def get_user_with_roles_permissions_by_sub(auth0_sub: str) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*, nexus.get_user_roles(u.id) as roles,
                       nexus.get_user_permissions(u.id) as permissions
                FROM nexus.users u
                WHERE u.auth0_sub = %s
                """,
                (auth0_sub,),
            )
            row = cur.fetchone()
    return cast(Optional[dict[str, Any]], row)


def get_user_with_roles_permissions_by_id(user_id: int) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.*, nexus.get_user_roles(u.id) as roles,
                       nexus.get_user_permissions(u.id) as permissions
                FROM nexus.users u
                WHERE u.id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return cast(Optional[dict[str, Any]], row)


def complete_onboarding(auth0_sub: str) -> bool:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.users
                SET preferences = preferences || '{"onboarding_completed": true}'::jsonb,
                    updated_at = now()
                WHERE auth0_sub = %s
                RETURNING id
                """,
                (auth0_sub,),
            )
            row = cur.fetchone()
            conn.commit()
    return row is not None
