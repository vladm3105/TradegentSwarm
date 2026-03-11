"""Users repository for profile, IB account, API keys, and user sessions."""

from datetime import datetime
from typing import Any, Optional, cast

from ..database import get_db_connection


def update_profile(auth0_sub: str, name: Optional[str], pref_updates: dict[str, Any]) -> Optional[dict]:
    """Update profile fields and return user row, or None if user not found."""
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        updates.append("name = %s")
        params.append(name)

    if pref_updates:
        updates.append("preferences = preferences || %s::jsonb")
        params.append(pref_updates)

    if not updates:
        return None

    updates.append("updated_at = now()")
    params.append(auth0_sub)

    query = f"""
        UPDATE nexus.users
        SET {', '.join(updates)}
        WHERE auth0_sub = %s
        RETURNING id, email, name, picture, preferences
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            conn.commit()
    return cast(Optional[dict], row)


def get_ib_account(auth0_sub: str) -> Optional[dict]:
    """Fetch IB account settings for a user by auth subject."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ib_account_id, ib_trading_mode, ib_gateway_port
                FROM nexus.users
                WHERE auth0_sub = %s
                """,
                (auth0_sub,),
            )
            return cast(Optional[dict], cur.fetchone())


def update_ib_account(
    auth0_sub: str,
    ib_account_id: str,
    ib_trading_mode: str,
    ib_gateway_port: Optional[int],
) -> Optional[dict]:
    """Update IB account settings and return updated row."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.users
                SET ib_account_id = %s,
                    ib_trading_mode = %s,
                    ib_gateway_port = %s,
                    updated_at = now()
                WHERE auth0_sub = %s
                RETURNING id, ib_account_id, ib_trading_mode, ib_gateway_port
                """,
                (ib_account_id, ib_trading_mode, ib_gateway_port, auth0_sub),
            )
            row = cur.fetchone()
            conn.commit()
    return cast(Optional[dict], row)


def list_api_keys(user_id: int) -> list[dict]:
    """List active API keys for a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, key_prefix, name, permissions,
                       last_used_at, expires_at, created_at
                FROM nexus.api_keys
                WHERE user_id = %s AND is_active = true
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return list(cur.fetchall())


def create_api_key(
    user_id: int,
    key_hash: str,
    key_prefix: str,
    name: str,
    permissions: list[str],
    expires_at: Optional[datetime],
) -> dict:
    """Create an API key and return created row fields."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.api_keys
                (user_id, key_hash, key_prefix, name, permissions, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (user_id, key_hash, key_prefix, name, permissions, expires_at),
            )
            row = cur.fetchone()
            conn.commit()
    return cast(dict, row)


def revoke_api_key(key_id: int, user_id: int) -> bool:
    """Revoke one API key owned by a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE nexus.api_keys
                SET is_active = false
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (key_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return bool(row)


def list_user_sessions(user_id: int) -> list[dict]:
    """List active web sessions for user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, device_info, ip_address, last_active_at, created_at
                FROM nexus.user_sessions
                WHERE user_id = %s AND expires_at > now()
                ORDER BY last_active_at DESC
                """,
                (user_id,),
            )
            return list(cur.fetchall())


def revoke_session(session_id: int, user_id: int) -> bool:
    """Delete one web session owned by a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM nexus.user_sessions
                WHERE id = %s AND user_id = %s
                RETURNING id
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return bool(row)


def revoke_all_sessions(user_id: int) -> int:
    """Delete all web sessions for a user; return deleted count."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM nexus.user_sessions
                WHERE user_id = %s
                RETURNING id
                """,
                (user_id,),
            )
            count = cur.rowcount
            conn.commit()
    return int(count)
