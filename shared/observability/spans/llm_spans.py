"""LLM call spans with GenAI semantic conventions.

Follows OpenTelemetry GenAI semantic conventions:
https://opentelemetry.io/docs/specs/semconv/gen-ai/
"""
import json
import time
from enum import Enum
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.trace import Span, Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

import structlog

log = structlog.get_logger()


class GenAISystem(str, Enum):
    """GenAI system identifiers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    COHERE = "cohere"


class FinishReason(str, Enum):
    """LLM finish reasons."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


# GenAI semantic convention attribute names
class GenAIAttributes:
    """OpenTelemetry GenAI semantic convention attributes."""

    # System attributes
    SYSTEM = "gen_ai.system"
    OPERATION_NAME = "gen_ai.operation.name"

    # Request attributes
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    REQUEST_TEMPERATURE = "gen_ai.request.temperature"

    # Response attributes
    RESPONSE_ID = "gen_ai.response.id"
    RESPONSE_MODEL = "gen_ai.response.model"
    RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

    # Usage attributes
    USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

    # Content (optional, may contain sensitive data)
    PROMPT = "gen_ai.prompt"
    COMPLETION = "gen_ai.completion"


class LLMSpan:
    """Span for LLM API calls with GenAI semantic conventions.

    Tracks LLM invocations with:
    - Model and system identification
    - Token usage (input/output)
    - Duration and latency
    - Finish reason

    Example:
        with LLMSpan(
            system=GenAISystem.OPENAI,
            model="gpt-4o-mini",
            operation="chat",
        ) as span:
            response = await client.chat.completions.create(...)
            span.set_response(
                response_id=response.id,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                finish_reason=FinishReason.STOP,
            )
    """

    def __init__(
        self,
        system: GenAISystem | str,
        model: str,
        operation: str = "chat",
        temperature: float | None = None,
        max_tokens: int | None = None,
        capture_prompt: bool = False,
        capture_completion: bool = False,
    ):
        """Initialize LLM span.

        Args:
            system: LLM provider (openai, anthropic, etc.)
            model: Model name
            operation: Operation type (chat, completion, embedding)
            temperature: Request temperature
            max_tokens: Max tokens requested
            capture_prompt: Whether to capture prompt (sensitive)
            capture_completion: Whether to capture completion (sensitive)
        """
        self.system = system if isinstance(system, str) else system.value
        self.model = model
        self.operation = operation
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.capture_prompt = capture_prompt
        self.capture_completion = capture_completion

        self._span: "Span | None" = None
        self._start_time: float = 0
        self.duration_ms: float = 0

        # Response data
        self._response_id: str | None = None
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._finish_reason: str | None = None
        self._success: bool = True

    def __enter__(self) -> "LLMSpan":
        """Start the span."""
        self._start_time = time.perf_counter()

        if OTEL_AVAILABLE:
            tracer = trace.get_tracer(__name__)
            self._span = tracer.start_span(
                f"gen_ai.{self.operation}",
                attributes={
                    GenAIAttributes.SYSTEM: self.system,
                    GenAIAttributes.OPERATION_NAME: self.operation,
                    GenAIAttributes.REQUEST_MODEL: self.model,
                    **(
                        {GenAIAttributes.REQUEST_TEMPERATURE: self.temperature}
                        if self.temperature is not None
                        else {}
                    ),
                    **(
                        {GenAIAttributes.REQUEST_MAX_TOKENS: self.max_tokens}
                        if self.max_tokens is not None
                        else {}
                    ),
                },
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """End the span."""
        self.duration_ms = (time.perf_counter() - self._start_time) * 1000

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("duration_ms", self.duration_ms)

            if self._response_id:
                self._span.set_attribute(GenAIAttributes.RESPONSE_ID, self._response_id)
            if self._input_tokens:
                self._span.set_attribute(
                    GenAIAttributes.USAGE_INPUT_TOKENS, self._input_tokens
                )
            if self._output_tokens:
                self._span.set_attribute(
                    GenAIAttributes.USAGE_OUTPUT_TOKENS, self._output_tokens
                )
            if self._finish_reason:
                self._span.set_attribute(
                    GenAIAttributes.RESPONSE_FINISH_REASONS, [self._finish_reason]
                )

            if exc_type is not None:
                self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
                self._span.record_exception(exc_val)
            elif not self._success:
                self._span.set_status(Status(StatusCode.ERROR, "LLM call failed"))
            else:
                self._span.set_status(Status(StatusCode.OK))

            self._span.end()

        # Log the call
        log_method = log.info if self._success else log.warning
        log_method(
            "LLM call completed",
            system=self.system,
            model=self.model,
            operation=self.operation,
            duration_ms=round(self.duration_ms, 2),
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            finish_reason=self._finish_reason,
        )

    def set_response(
        self,
        response_id: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        finish_reason: FinishReason | str | None = None,
        response_model: str | None = None,
    ) -> None:
        """Set response data.

        Args:
            response_id: API response ID
            input_tokens: Number of input/prompt tokens
            output_tokens: Number of output/completion tokens
            finish_reason: Why the generation stopped
            response_model: Actual model used (may differ from request)
        """
        self._response_id = response_id
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._finish_reason = (
            finish_reason.value
            if isinstance(finish_reason, FinishReason)
            else finish_reason
        )

        if OTEL_AVAILABLE and self._span:
            if response_model:
                self._span.set_attribute(GenAIAttributes.RESPONSE_MODEL, response_model)

    def set_error(self, error: str) -> None:
        """Mark the call as failed.

        Args:
            error: Error message
        """
        self._success = False

        if OTEL_AVAILABLE and self._span:
            self._span.set_attribute("error.message", error)

    def set_prompt(self, prompt: str) -> None:
        """Capture the prompt (if enabled).

        Args:
            prompt: The prompt text
        """
        if self.capture_prompt and OTEL_AVAILABLE and self._span:
            # Truncate to avoid huge spans
            truncated = prompt[:4000] if len(prompt) > 4000 else prompt
            self._span.set_attribute(GenAIAttributes.PROMPT, truncated)

    def set_completion(self, completion: str) -> None:
        """Capture the completion (if enabled).

        Args:
            completion: The completion text
        """
        if self.capture_completion and OTEL_AVAILABLE and self._span:
            # Truncate to avoid huge spans
            truncated = completion[:4000] if len(completion) > 4000 else completion
            self._span.set_attribute(GenAIAttributes.COMPLETION, truncated)

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        if OTEL_AVAILABLE and self._span:
            self._span.add_event(name, attributes=attributes or {})
