"""Response wrapper utilities for FastAPI routes using unified TradegentMessage envelope.

This module provides fixtures and helpers for wrapping FastAPI response data
into the unified TradegentMessage envelope format.

All REST responses should be wrapped using these utilities to maintain
consistent format across the entire API surface.

Usage in Routes:

    from fastapi import APIRouter, HTTPException
    from tradegent_ui.server.messages import (
        TradegentResponse,
        TradegentRequest,
        TradegentMessage,
        create_response,
        create_error,
        TradegentActions
    )
    from tradegent_ui.server.response import wrap_response, error_to_response

    router = APIRouter()

    @router.post("/api")
    async def unified_api(request: TradegentRequest):
        '''Unified REST API endpoint that handles all request-response operations.'''
        action = request.action
        request_id = request.request_id

        if action == TradegentActions.PATCH_SCHEDULE:
            try:
                # ... business logic ...
                result = {"schedule_id": 1, "enabled": False}
                return wrap_response(result, action, request_id)
            except ValueError as e:
                return error_to_response(
                    action=action,
                    code="VALIDATION_ERROR",
                    message=str(e),
                    request_id=request_id
                )

        return error_to_response(
            action=action,
            code="NOT_FOUND",
            message=f"Unknown action: {action}",
            request_id=request_id,
            status_code=404
        )

    # Or use in traditional routes (one endpoint per action):

    @router.patch("/schedules/{schedule_id}")
    async def update_schedule(schedule_id: int, data: dict):
        '''Traditional route returning envelope-wrapped response.'''
        try:
            # ... business logic ...
            return wrap_response(
                {"schedule_id": schedule_id, "enabled": data.get("enabled")},
                action="patch_schedule"
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=error_to_response(
                    action="patch_schedule",
                    code="VALIDATION_ERROR",
                    message=str(e)
                ).model_dump()
            )
"""

from typing import Any, Optional
from fastapi import HTTPException
from .messages import (
    TradegentResponse,
    TradegentMessage,
    create_response,
    create_error,
    TradegentError,
)


def wrap_response(
    data: Any,
    action: str,
    request_id: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> TradegentResponse:
    """Wrap response data in TradegentMessage envelope.

    Use this in FastAPI routes to return data wrapped in the unified message format.

    Args:
        data: Response payload to wrap
        action: Action identifier (e.g., 'patch_schedule', 'get_schedules')
        request_id: Optional correlation ID from request
        timestamp: Optional explicit timestamp (uses current time if not provided)

    Returns:
        TradegentResponse envelope ready to send to client

    Example:
        @router.patch("/schedules/{schedule_id}")
        async def update_schedule(schedule_id: int, data: dict):
            result = {"schedule_id": schedule_id, "enabled": data.get("enabled")}
            return wrap_response(result, action="patch_schedule")
    """
    return create_response(
        action=action,
        payload=data,
        request_id=request_id,
        timestamp=timestamp,
    )


def error_to_response(
    action: str,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    status_code: int = 400,
) -> TradegentMessage:
    """Convert error to unified TradegentMessage error envelope.

    Use this in FastAPI error handlers or exception handlers to return
    errors in the unified message format.

    Args:
        action: Related action identifier
        code: Machine-readable error code (VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, etc.)
        message: Human-readable error message
        request_id: Optional correlation ID from request
        details: Optional action-specific error details (field validation errors, etc.)
        status_code: HTTP status code to use in HTTPException

    Returns:
        TradegentMessage error envelope ready to send to client

    Example:
        try:
            # ... business logic ...
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=error_to_response(
                    action="patch_schedule",
                    code="VALIDATION_ERROR",
                    message=str(e),
                    details={"field": "schedule_id"}
                ).model_dump()
            )
    """
    return create_error(
        action=action,
        code=code,
        message=message,
        request_id=request_id,
        details=details,
    )


def http_exception_to_response(
    action: str,
    http_exception: HTTPException,
    request_id: Optional[str] = None,
) -> TradegentMessage:
    """Convert FastAPI HTTPException to unified error envelope.

    Use this in exception handlers to wrap HTTPException into TradegentMessage format.

    Args:
        action: Related action identifier
        http_exception: HTTPException to convert
        request_id: Optional correlation ID from request

    Returns:
        TradegentMessage error envelope
    """
    code = f"HTTP_{http_exception.status_code}"
    message = http_exception.detail if isinstance(http_exception.detail, str) else str(http_exception.detail)

    return create_error(
        action=action,
        code=code,
        message=message,
        request_id=request_id,
    )
