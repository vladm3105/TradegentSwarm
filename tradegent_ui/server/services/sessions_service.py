"""Sessions service with route-facing business logic."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi import HTTPException

from ..auth import UserClaims
from ..repositories import sessions_repository


def get_or_create_user_id(user: UserClaims) -> int:
    """Resolve user id from auth subject with fallback for development sessions."""
    user_id = sessions_repository.get_user_id_by_sub(user.sub)
    if user_id is not None:
        return user_id
    return sessions_repository.get_fallback_user_id()


def list_sessions(limit: int, offset: int, include_archived: bool, user: UserClaims) -> dict:
    """List sessions and total count for a user."""
    user_id = get_or_create_user_id(user)
    rows = sessions_repository.list_sessions(user_id, limit, offset, include_archived)
    total = sessions_repository.count_sessions(user_id, include_archived)

    sessions = [
        {
            "id": row["id"],
            "session_id": row["session_id"],
            "title": row["title"],
            "message_count": row["message_count"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "is_archived": row["is_archived"],
        }
        for row in rows
    ]
    return {"sessions": sessions, "total": total}


def get_session_detail(session_id: str, user: UserClaims) -> dict:
    """Get one session plus ordered message list."""
    user_id = get_or_create_user_id(user)
    session = sessions_repository.get_session_by_public_id(session_id, user_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message_rows = sessions_repository.get_messages_for_session(session["id"])
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
        for row in message_rows
    ]

    return {
        "id": session["id"],
        "session_id": session["session_id"],
        "title": session["title"],
        "message_count": session["message_count"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "is_archived": session["is_archived"],
        "messages": messages,
    }


def create_session(title: Optional[str], user: UserClaims) -> dict:
    """Create a new chat session."""
    user_id = get_or_create_user_id(user)
    session_id = str(uuid.uuid4())
    row = sessions_repository.create_session(session_id, user_id, title)
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "updated_at": row["updated_at"].isoformat(),
    }


def save_messages(session_id: str, messages: list, user: UserClaims) -> dict:
    """Save or update message rows for a session."""
    user_id = get_or_create_user_id(user)
    db_session_id = sessions_repository.get_session_db_id(session_id, user_id)
    if db_session_id is None:
        raise HTTPException(status_code=404, detail="Session not found")

    payloads = [
        {
            "message_id": msg.message_id,
            "role": msg.role,
            "content": msg.content,
            "status": msg.status,
            "error": msg.error,
            "a2ui": msg.a2ui,
            "task_id": msg.task_id,
        }
        for msg in messages
    ]
    sessions_repository.upsert_messages(db_session_id, payloads)

    return {"success": True, "messages_saved": len(messages)}


def update_session(
    session_id: str,
    title: Optional[str],
    is_archived: Optional[bool],
    user: UserClaims,
) -> dict:
    """Update title/archive metadata for a session."""
    if title is None and is_archived is None:
        raise HTTPException(status_code=400, detail="No updates provided")

    user_id = get_or_create_user_id(user)
    found = sessions_repository.update_session_metadata(
        session_id=session_id,
        user_id=user_id,
        title=title,
        is_archived=is_archived,
    )
    if not found:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}


def delete_session(session_id: str, user: UserClaims) -> dict:
    """Delete a session and all its messages."""
    user_id = get_or_create_user_id(user)
    deleted = sessions_repository.delete_session(session_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
