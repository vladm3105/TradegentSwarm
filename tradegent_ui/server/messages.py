"""Unified message envelope for all Tradegent client-server communication.

This module defines the common message format (TradegentMessage) used across
both WebSocket (push/subscribe) and REST (request/response) transports.

A single envelope type enables:
  - Consistent error handling across transports
  - Shared request/response correlation via request_id
  - Type-safe payloads with Pydantic validation
  - Easy serialization to JSON and back

Architecture:
  - REST (stateless): HTTP request body → TradegentMessage (request)
                      → TradegentMessage (response with data) → HTTP response body
  - WS (stateful):    Client sends TradegentMessage (subscribe/request)
                      Server sends TradegentMessage (events/errors)

Usage:

    from tradegent_ui.server.messages import (
        TradegentMessage,
        TradegentError,
        TradegentResponse,
        create_response,
        create_error,
    )

    # REST response
    response = create_response(
        action="get_schedules",
        payload={"schedules": [...]},
        request_id="req-123"
    )

    # Error response
    error = create_error(
        action="patch_schedule",
        code="VALIDATION_ERROR",
        message="Schedule ID must be positive",
        request_id="req-123",
        details={"field": "schedule_id"}
    )

    # Send error via FastAPI
    raise HTTPException(
        status_code=400,
        detail=error.model_dump()
    )
"""

import uuid
from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")


class MessageType(str, Enum):
    """Message type enumeration."""
    REQUEST = "request"  # Client request (REST body or WS)
    RESPONSE = "response"  # Server response (REST body or WS)
    SUBSCRIPTION = "subscription"  # Client subscribes to push events
    EVENT = "event"  # Server pushes event to subscribed client
    ERROR = "error"  # Error response (replaces normal response)


class TradegentError(BaseModel):
    """Unified error response for all transports.

    Example:
        {
          "code": "VALIDATION_ERROR",
          "message": "Schedule ID must be positive",
          "details": {"field": "schedule_id", "reason": "positive"}
        }
    """

    code: str = Field(
        ...,
        description="Machine-readable error code (VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, SERVER_ERROR, etc.)",
    )
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(
        None,
        description="Optional action-specific error details",
    )


class TradegentMessage(BaseModel, Generic[T]):
    """Unified message envelope for all client-server communication.

    Works across both REST and WebSocket transports. All messages follow
    this structure to enable consistent handling, logging, and correlation.

    Attributes:
        type: Message type (request, response, subscription, event, error)
        action: Action identifier (e.g., 'get_schedules', 'subscribe_prices')
        request_id: Optional correlation ID for request-response correlation
        payload: Action-specific data
        timestamp: Message creation timestamp in milliseconds
        error: Error details (only if type='error')

    Example:
        # REST request body
        {
          "type": "request",
          "action": "patch_schedule",
          "request_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {"schedule_id": 1, "enabled": false},
          "timestamp": 1694520000000
        }

        # REST response body
        {
          "type": "response",
          "action": "patch_schedule",
          "request_id": "550e8400-e29b-41d4-a716-446655440000",
          "payload": {"schedule_id": 1, "enabled": false, "updated_at": "2024-01-01T00:00:00Z"},
          "timestamp": 1694520001000
        }

        # WS subscription message
        {
          "type": "subscription",
          "action": "subscribe_prices",
          "request_id": "550e8400-e29b-41d4-a716-446655440001",
          "payload": {"tickers": ["NVDA", "AAPL"]},
          "timestamp": 1694520000000
        }

        # WS error event
        {
          "type": "error",
          "action": "patch_schedule",
          "request_id": "550e8400-e29b-41d4-a716-446655440000",
          "error": {
            "code": "VALIDATION_ERROR",
            "message": "Schedule ID must be positive",
            "details": {"field": "schedule_id"}
          },
          "timestamp": 1694520001000
        }
    """

    type: MessageType = Field(
        ...,
        description="Message type: request, response, subscription, event, or error",
    )
    action: str = Field(
        ...,
        description="Action identifier (e.g., 'get_schedules', 'subscribe_prices')",
    )
    request_id: Optional[str] = Field(
        None,
        description="Optional unique request ID for correlation (UUID recommended)",
    )
    payload: Optional[T] = Field(
        None,
        description="Action-specific payload data",
    )
    timestamp: Optional[int] = Field(
        None,
        description="Message creation timestamp in milliseconds since epoch",
    )
    error: Optional[TradegentError] = Field(
        None,
        description="Error details (only present if type='error')",
    )

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class TradegentResponse(TradegentMessage):
    """Type-safe response wrapper for REST endpoints.

    Wraps actual response data in TradegentMessage envelope.

    Example:
        response = TradegentResponse(
            action="get_schedules",
            request_id="123",
            payload={"schedules": [...]},
            timestamp=1694520000000
        )
    """

    type: MessageType = Field(
        MessageType.RESPONSE,
        description="Message type is always 'response' for responses",
    )


class TradegentEvent(TradegentMessage):
    """Type-safe event message for WebSocket push.

    Server pushes these to subscribed clients.

    Example:
        event = TradegentEvent(
            action="subscribe_prices",
            request_id="123",
            payload={"ticker": "NVDA", "bid": 950.25, "ask": 950.30},
            timestamp=1694520000000
        )
    """

    type: MessageType = Field(
        MessageType.EVENT,
        description="Message type is always 'event' for push messages",
    )


class TradegentSubscription(TradegentMessage):
    """Type-safe subscription request for WebSocket.

    Client sends these to subscribe to event streams.

    Example:
        subscription = TradegentSubscription(
            action="subscribe_prices",
            request_id="123",
            payload={"tickers": ["NVDA", "AAPL"]},
            timestamp=1694520000000
        )
    """

    type: MessageType = Field(
        MessageType.SUBSCRIPTION,
        description="Message type is always 'subscription' for subscription requests",
    )


class TradegentRequest(TradegentMessage):
    """Type-safe request message for REST or WS RPC.

    Client sends these for request-response operations.

    Example:
        request = TradegentRequest(
            action="patch_schedule",
            request_id="123",
            payload={"schedule_id": 1, "enabled": False},
            timestamp=1694520000000
        )
    """

    type: MessageType = Field(
        MessageType.REQUEST,
        description="Message type is always 'request' for requests",
    )


def create_response(
    action: str,
    payload: Any = None,
    request_id: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> TradegentResponse:
    """Create a response message with default timestamp.

    Args:
        action: Action identifier (e.g., 'get_schedules', 'patch_schedule')
        payload: Action-specific response data
        request_id: Optional correlation ID from request (for matching)
        timestamp: Optional explicit timestamp (uses current time if not provided)

    Returns:
        TradegentResponse message ready to send to client
    """
    return TradegentResponse(
        action=action,
        request_id=request_id,
        payload=payload,
        timestamp=timestamp or int(datetime.now().timestamp() * 1000),
    )


def create_event(
    action: str,
    payload: Any = None,
    request_id: Optional[str] = None,
    timestamp: Optional[int] = None,
) -> TradegentEvent:
    """Create an event message for WebSocket push.

    Args:
        action: Action identifier (e.g., 'subscribe_prices')
        payload: Event-specific data
        request_id: Optional correlation ID (links to subscription request)
        timestamp: Optional explicit timestamp (uses current time if not provided)

    Returns:
        TradegentEvent message ready to push to client
    """
    return TradegentEvent(
        action=action,
        request_id=request_id,
        payload=payload,
        timestamp=timestamp or int(datetime.now().timestamp() * 1000),
    )


def create_error(
    action: str,
    code: str,
    message: str,
    request_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    timestamp: Optional[int] = None,
) -> TradegentMessage:
    """Create an error response message.

    Args:
        action: Related action identifier
        code: Machine-readable error code (VALIDATION_ERROR, NOT_FOUND, UNAUTHORIZED, SERVER_ERROR, etc.)
        message: Human-readable error message
        request_id: Optional correlation ID (from request)
        details: Optional action-specific error details (e.g., field validation errors)
        timestamp: Optional explicit timestamp (uses current time if not provided)

    Returns:
        TradegentMessage with error type and details ready to send to client
    """
    return TradegentMessage(
        type=MessageType.ERROR,
        action=action,
        request_id=request_id,
        error=TradegentError(code=code, message=message, details=details),
        timestamp=timestamp or int(datetime.now().timestamp() * 1000),
    )


def generate_request_id() -> str:
    """Generate a unique request ID for correlation.

    Returns:
        UUID string suitable for request_id field
    """
    return str(uuid.uuid4())


# Common action identifiers (matches TypeScript TRADEGENT_ACTIONS)
class TradegentActions:
    """Standard action names used across Tradegent."""

    # Schedule management
    GET_SCHEDULES = "get_schedules"
    PATCH_SCHEDULE = "patch_schedule"
    RUN_SCHEDULE_NOW = "run_schedule_now"
    GET_SCHEDULE_HISTORY = "get_schedule_history"

    # Price/portfolio streaming
    SUBSCRIBE_PRICES = "subscribe_prices"
    SUBSCRIBE_PORTFOLIO = "subscribe_portfolio"
    SUBSCRIBE_ORDERS = "subscribe_orders"

    # Dashboard metrics
    SUBSCRIBE_METRICS = "subscribe_metrics"
    SUBSCRIBE_ALERTS = "subscribe_alerts"

    # Generic operations
    UNSUBSCRIBE = "unsubscribe"
