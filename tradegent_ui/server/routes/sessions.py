"""Agent chat sessions API routes."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends

from ..auth import get_current_user, UserClaims
from ..services import sessions_service

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


@router.get("/list", response_model=SessionListResponse)
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
    user: UserClaims = Depends(get_current_user),
):
    """List user's chat sessions."""
    payload = sessions_service.list_sessions(limit, offset, include_archived, user)
    sessions = [SessionSummary(**row) for row in payload["sessions"]]
    return SessionListResponse(sessions=sessions, total=payload["total"])


@router.get("/detail/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    user: UserClaims = Depends(get_current_user),
):
    """Get a session with all messages."""
    payload = sessions_service.get_session_detail(session_id, user)
    return SessionDetail(**payload)


@router.post("/create")
async def create_session(
    request: SessionCreate,
    user: UserClaims = Depends(get_current_user),
):
    """Create a new session."""
    return sessions_service.create_session(request.title, user)


@router.post("/{session_id}/messages")
async def save_messages(
    session_id: str,
    messages: list[MessageCreate],
    user: UserClaims = Depends(get_current_user),
):
    """Save messages to a session."""
    return sessions_service.save_messages(session_id, messages, user)


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    title: Optional[str] = None,
    is_archived: Optional[bool] = None,
    user: UserClaims = Depends(get_current_user),
):
    """Update session metadata."""
    return sessions_service.update_session(session_id, title, is_archived, user)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: UserClaims = Depends(get_current_user),
):
    """Delete a session and all its messages."""
    return sessions_service.delete_session(session_id, user)
