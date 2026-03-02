"""Agent chat sessions API routes."""
import json
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Depends

from ..database import get_db_connection
from ..auth import get_current_user, UserClaims

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# Pydantic models
class SessionCreate(BaseModel):
    """Request to create a new session."""
    title: Optional[str] = None


class MessageCreate(BaseModel):
    """Request to save a message."""
    message_id: str
    role: str
    content: str
    status: str = "complete"
    error: Optional[str] = None
    a2ui: Optional[dict] = None
    task_id: Optional[str] = None


class SessionSummary(BaseModel):
    """Session summary for listing."""
    id: int
    session_id: str
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime
    is_archived: bool


class SessionDetail(BaseModel):
    """Full session with messages."""
    id: int
    session_id: str
    title: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime
    is_archived: bool
    messages: list[dict]


class SessionListResponse(BaseModel):
    """Session list response."""
    sessions: list[SessionSummary]
    total: int


async def get_or_create_user_id(user: UserClaims) -> int:
    """Get the database user ID for the current user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM nexus.users WHERE auth0_sub = %s",
                (user.sub,)
            )
            row = cur.fetchone()
            if row:
                return row["id"]
            # Return a fallback user ID for development (admin)
            cur.execute("SELECT id FROM nexus.users LIMIT 1")
            row = cur.fetchone()
            return row["id"] if row else 1


@router.get("/list", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
    user: UserClaims = Depends(get_current_user),
):
    """List user's chat sessions."""
    user_id = await get_or_create_user_id(user)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get sessions
            if include_archived:
                cur.execute("""
                    SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                    FROM nexus.agent_sessions
                    WHERE user_id = %s OR user_id IS NULL
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))
            else:
                cur.execute("""
                    SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                    FROM nexus.agent_sessions
                    WHERE (user_id = %s OR user_id IS NULL) AND is_archived = false
                    ORDER BY updated_at DESC
                    LIMIT %s OFFSET %s
                """, (user_id, limit, offset))

            sessions = [
                SessionSummary(
                    id=row["id"],
                    session_id=row["session_id"],
                    title=row["title"],
                    message_count=row["message_count"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    is_archived=row["is_archived"],
                )
                for row in cur.fetchall()
            ]

            # Get total count
            if include_archived:
                cur.execute(
                    "SELECT COUNT(*) as count FROM nexus.agent_sessions WHERE user_id = %s OR user_id IS NULL",
                    (user_id,)
                )
            else:
                cur.execute(
                    "SELECT COUNT(*) as count FROM nexus.agent_sessions WHERE (user_id = %s OR user_id IS NULL) AND is_archived = false",
                    (user_id,)
                )
            total = cur.fetchone()["count"]

            return SessionListResponse(sessions=sessions, total=total)


@router.get("/detail/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    user: UserClaims = Depends(get_current_user),
):
    """Get a session with all messages."""
    user_id = await get_or_create_user_id(user)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get session
            cur.execute("""
                SELECT id, session_id, title, message_count, created_at, updated_at, is_archived
                FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
            """, (session_id, user_id))

            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            # Get messages
            cur.execute("""
                SELECT message_id, role, content, status, error, a2ui, task_id, created_at
                FROM nexus.agent_messages
                WHERE session_id = %s
                ORDER BY created_at ASC
            """, (session["id"],))

            messages = [
                {
                    "id": row["message_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "status": row["status"],
                    "error": row["error"],
                    "a2ui": row["a2ui"],
                    "taskId": row["task_id"],
                    "timestamp": row["created_at"].isoformat(),
                }
                for row in cur.fetchall()
            ]

            return SessionDetail(
                id=session["id"],
                session_id=session["session_id"],
                title=session["title"],
                message_count=session["message_count"],
                created_at=session["created_at"],
                updated_at=session["updated_at"],
                is_archived=session["is_archived"],
                messages=messages,
            )


@router.post("/create")
async def create_session(
    request: SessionCreate,
    user: UserClaims = Depends(get_current_user),
):
    """Create a new session."""
    import uuid

    user_id = await get_or_create_user_id(user)
    session_id = str(uuid.uuid4())

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.agent_sessions (session_id, user_id, title)
                VALUES (%s, %s, %s)
                RETURNING id, session_id, title, created_at, updated_at
            """, (session_id, user_id, request.title))

            row = cur.fetchone()
            conn.commit()

            return {
                "id": row["id"],
                "session_id": row["session_id"],
                "title": row["title"],
                "created_at": row["created_at"].isoformat(),
                "updated_at": row["updated_at"].isoformat(),
            }


@router.post("/{session_id}/messages")
async def save_messages(
    session_id: str,
    messages: list[MessageCreate],
    user: UserClaims = Depends(get_current_user),
):
    """Save messages to a session."""
    user_id = await get_or_create_user_id(user)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get session
            cur.execute("""
                SELECT id FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
            """, (session_id, user_id))

            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            db_session_id = session["id"]

            # Insert messages (upsert based on message_id)
            for msg in messages:
                cur.execute("""
                    INSERT INTO nexus.agent_messages (session_id, message_id, role, content, status, error, a2ui, task_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        status = EXCLUDED.status,
                        error = EXCLUDED.error,
                        a2ui = EXCLUDED.a2ui
                """, (
                    db_session_id,
                    msg.message_id,
                    msg.role,
                    msg.content,
                    msg.status,
                    msg.error,
                    json.dumps(msg.a2ui) if msg.a2ui else None,
                    msg.task_id,
                ))

            conn.commit()

            return {"success": True, "messages_saved": len(messages)}


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    title: Optional[str] = None,
    is_archived: Optional[bool] = None,
    user: UserClaims = Depends(get_current_user),
):
    """Update session metadata."""
    user_id = await get_or_create_user_id(user)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            updates = []
            params = []

            if title is not None:
                updates.append("title = %s")
                params.append(title)

            if is_archived is not None:
                updates.append("is_archived = %s")
                params.append(is_archived)

            if not updates:
                raise HTTPException(status_code=400, detail="No updates provided")

            params.extend([session_id, user_id])
            cur.execute(f"""
                UPDATE nexus.agent_sessions
                SET {", ".join(updates)}, updated_at = now()
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                RETURNING id
            """, params)

            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Session not found")

            conn.commit()
            return {"success": True}


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: UserClaims = Depends(get_current_user),
):
    """Delete a session and all its messages."""
    user_id = await get_or_create_user_id(user)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM nexus.agent_sessions
                WHERE session_id = %s AND (user_id = %s OR user_id IS NULL)
                RETURNING id
            """, (session_id, user_id))

            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Session not found")

            conn.commit()
            return {"success": True}
