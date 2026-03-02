"""Error hierarchy for Tradegent Agent UI."""
from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorResponse:
    """Structured error response for A2UI."""

    code: str
    message: str
    recoverable: bool = True
    retry_action: str | None = None
    details: dict[str, Any] | None = None

    def to_a2ui(self) -> dict:
        """Convert to A2UI ErrorCard component."""
        return {
            "type": "a2ui",
            "components": [
                {
                    "type": "ErrorCard",
                    "props": {
                        "code": self.code,
                        "message": self.message,
                        "recoverable": self.recoverable,
                        "retry_action": self.retry_action,
                    },
                }
            ],
        }


class AgentUIError(Exception):
    """Base error for Agent UI."""

    def __init__(
        self,
        message: str,
        code: str,
        recoverable: bool = True,
        retry_action: str | None = None,
    ):
        self.message = message
        self.code = code
        self.recoverable = recoverable
        self.retry_action = retry_action
        super().__init__(message)

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            code=self.code,
            message=self.message,
            recoverable=self.recoverable,
            retry_action=self.retry_action,
        )


class MCPConnectionError(AgentUIError):
    """MCP server connection failed."""

    def __init__(self, server: str, detail: str):
        super().__init__(
            message=f"Cannot connect to {server}: {detail}",
            code="MCP_CONN_ERR",
            recoverable=True,
            retry_action="reconnect",
        )
        self.server = server
        self.detail = detail


class MCPTimeoutError(AgentUIError):
    """MCP server timeout."""

    def __init__(self, server: str, timeout: float):
        super().__init__(
            message=f"Request to {server} timed out after {timeout}s",
            code="MCP_TIMEOUT",
            recoverable=True,
            retry_action="retry",
        )


class ToolExecutionError(AgentUIError):
    """Tool execution failed."""

    def __init__(self, tool: str, detail: str):
        super().__init__(
            message=f"Tool '{tool}' failed: {detail}",
            code="TOOL_ERR",
            recoverable=True,
            retry_action=tool,
        )
        self.tool = tool
        self.detail = detail


class IntentClassificationError(AgentUIError):
    """Could not classify user intent."""

    def __init__(self, query: str | None = None):
        super().__init__(
            message="I couldn't understand your request. Could you rephrase?",
            code="INTENT_ERR",
            recoverable=True,
        )
        self.query = query


class LLMError(AgentUIError):
    """LLM API error."""

    def __init__(self, detail: str):
        super().__init__(
            message=f"AI service error: {detail}",
            code="LLM_ERR",
            recoverable=True,
            retry_action="retry",
        )


class LLMTimeoutError(AgentUIError):
    """LLM response timeout."""

    def __init__(self):
        super().__init__(
            message="The AI is taking longer than expected. Please try again.",
            code="LLM_TIMEOUT",
            recoverable=True,
            retry_action="retry",
        )


class TaskNotFoundError(AgentUIError):
    """Task not found."""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task '{task_id}' not found",
            code="TASK_NOT_FOUND",
            recoverable=False,
        )


class ValidationError(AgentUIError):
    """Input validation failed."""

    def __init__(self, field: str, detail: str):
        super().__init__(
            message=f"Invalid {field}: {detail}",
            code="VALIDATION_ERR",
            recoverable=True,
        )
