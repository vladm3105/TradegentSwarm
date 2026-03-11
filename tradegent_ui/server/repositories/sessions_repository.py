"""Sessions repository with all SQL access for chat sessions and messages."""

from typing import Any, Optional, cast

from ..database import get_db_connection


def get_user_id_by_sub(auth0_sub: str) -> Optional[int]:
    """Return user id by auth0 subject, or None when not found."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nexus.users WHERE auth0_sub = %s", (auth0_sub,))
            row = cur.fetchone()
    return row["id"] if row else None


def get_fallback_user_id() -> int:
    """Return fallback user id (first available user) or 1 when empty."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nexus.users LIMIT 1")
            row = cur.fetchone()
    return row["id"] if row else 1


def list_sessions(user_id: int, limit: int, offset: int, include_archived: bool) -> list[dict]:
    """List sessions for a user including shared sessions with user_id NULL."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if include_archived:
                cur.execute(
                    """
                    SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                    FROM nexus.agent_sessions
                    WHERE user_id = %s OR user_id IS NULL
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                    FROM nexus.agent_sessions
                    WHERE (user_id = %s OR user_id IS NULL) AND is_archived = false
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (user_id, limit, offset),
                )
            return list(cur.fetchall())


def count_sessions(user_id: int, include_archived: bool) -> int:
    """Count sessions for a user including shared sessions with user_id NULL."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if include_archived:
                cur.execute(
                    "SELECT COUNT(*) as count FROM nexus.agent_sessions WHERE user_id = %s OR user_id IS NULL",
                    (user_id,),
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) as count FROM nexus.agent_sessions WHERE (user_id = %s OR user_id IS NULL) AND is_archived = false",
                    (user_id,),
                )
            row = cast(dict[str, Any], cur.fetchone())
            return int(row["count"])


def get_session_by_public_id(session_id: str, user_id: int) -> Optional[dict]:
    """Get a session by public session_id constrained to user ownership/shared."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            return cast(Optional[dict[str, Any]], row)


def get_messages_for_session(session_db_id: int) -> list[dict]:
    """Get all messages for a DB session id ordered by timestamp."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT message_id, role, content, status, error, a2ui, task_id, created_at
                FROM nexus.agent_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
                """,
                (session_db_id,),
            )
            return list(cur.fetchall())


def create_session(session_id: str, user_id: int, title: Optional[str]) -> dict:
    """Insert a session and return created row fields."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.agent_sessions (session_id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING id, session_id, title, created_at, updated_at
                """,
                (session_id, user_id, title),
            )
            row = cast(dict[str, Any], cur.fetchone())
            conn.commit()
    return row


def get_session_db_id(session_id: str, user_id: int) -> Optional[int]:
    """Resolve DB session id from public session id constrained to user/shared."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
    return row["id"] if row else None


def upsert_messages(session_db_id: int, messages: list[dict]) -> None:
    """Upsert message payloads by message_id in one transaction."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for msg in messages:
                cur.execute(
                    """
                    INSERT INTO nexus.agent_messages (session_id, message_id, role, content, status, error, a2ui, task_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        status = EXCLUDED.status,
                        error = EXCLUDED.error,
                        a2ui = EXCLUDED.a2ui
                    """,
                    (
                        session_db_id,
                        msg["message_id"],
                        msg["role"],
                        msg["content"],
                        msg["status"],
                        msg["error"],
                        msg["a2ui"],
                        msg["task_id"],
                    ),
                )
            conn.commit()


def update_session_metadata(
    session_id: str,
    user_id: int,
    title: Optional[str],
    is_archived: Optional[bool],
) -> bool:
    """Update title/is_archived fields when provided; return True when session exists."""
    updates: list[str] = []
    params: list = []

    if title is not None:
        updates.append("title = %s")
        params.append(title)

    if is_archived is not None:
        updates.append("is_archived = %s")
        params.append(is_archived)

    if not updates:
        return False

    params.extend([session_id, user_id])
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE nexus.agent_sessions
                SET {", ".join(updates)}, updated_at = now()
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                RETURNING id
                """,
                tuple(params),
            )
            row = cur.fetchone()
            conn.commit()
    return bool(row)


def delete_session(session_id: str, user_id: int) -> bool:
    """Delete a session by public id constrained to user/shared; return True when deleted."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                RETURNING id
                """,
                (session_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
    return bool(row)
