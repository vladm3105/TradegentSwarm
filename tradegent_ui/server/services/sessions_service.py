"""Sessions service with route-facing business logic."""

from datetime import datetime
from typing import Optional
import re
import uuid

from fastapi import HTTPException

from ..auth import UserClaims
from ..repositories import sessions_repository


def _resolve_or_create_session_db_id(session_id: str, user_id: int, title: Optional[str] = None) -> int:
    """Resolve DB session id by public id, creating the session when needed."""
    db_session_id = sessions_repository.get_session_db_id(session_id, user_id)
    if db_session_id is not None:
        return db_session_id

    created = sessions_repository.create_session(session_id, user_id, title)
    return int(created["id"])


def get_or_create_user_id(user: UserClaims) -> int:
    """Resolve user id from auth subject.

    Sessions are user-scoped data; do not fall back to another account.
    """
    user_id = sessions_repository.get_user_id_by_sub(user.sub)
    if user_id is not None:
        return user_id
    raise HTTPException(status_code=403, detail="User is not provisioned")


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


def _default_user_email(auth_sub: str) -> str:
    """Build a deterministic placeholder email when auth claims omit email."""
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", auth_sub)
    return f"{safe}@local.invalid"


def persist_roundtrip_messages(
    *,
    auth_sub: str,
    user_content: str,
    assistant_content: str,
    assistant_status: str,
    assistant_error: Optional[str] = None,
    assistant_a2ui: Optional[dict] = None,
    task_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
) -> dict:
    """Persist one user/assistant chat roundtrip for server-side chat logging.

    This function is intended for backend-authoritative chat logging in REST/WS
    handlers and async task completion paths.
    """
    user_id = sessions_repository.upsert_user_by_sub(
        auth0_sub=auth_sub,
        email=user_email or _default_user_email(auth_sub),
        name=user_name,
    )

    public_session_id = session_id or auth_sub
    db_session_id = _resolve_or_create_session_db_id(public_session_id, user_id)

    payloads: list[dict] = [
        {
            "message_id": str(uuid.uuid4()),
            "role": "user",
            "content": user_content,
            "status": "complete",
            "error": None,
            "a2ui": None,
            "task_id": task_id,
        },
        {
            "message_id": str(uuid.uuid4()),
            "role": "assistant",
            "content": assistant_content,
            "status": assistant_status,
            "error": assistant_error,
            "a2ui": assistant_a2ui,
            "task_id": task_id,
        },
    ]

    sessions_repository.upsert_messages(db_session_id, payloads)
    return {"success": True, "messages_saved": len(payloads), "session_id": public_session_id}


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
