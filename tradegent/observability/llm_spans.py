"""
LLM-specific spans following OpenTelemetry GenAI semantic conventions.

Reference: https://opentelemetry.io/docs/specs/semconv/gen-ai/
Blog: https://opentelemetry.io/blog/2024/llm-observability/

Provides structured tracing for:
- LLM API calls (Claude, OpenAI, etc.)
- Tool/function calls within LLM interactions
- Token usage and cost estimation
- Prompt/completion content (optional)
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Generator

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from .tracing import get_tracer, get_config


class GenAISystem(str, Enum):
    """Supported GenAI systems."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CLAUDE_CODE = "claude_code"  # Claude Code CLI
    OLLAMA = "ollama"


class FinishReason(str, Enum):
    """Why the LLM stopped generating."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_CALLS = "tool_calls"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"


# GenAI Semantic Convention attribute names
# https://opentelemetry.io/docs/specs/semconv/attributes-registry/gen-ai/
class GenAIAttributes:
    """OpenTelemetry GenAI semantic convention attribute names."""

    # System
    SYSTEM = "gen_ai.system"
    OPERATION_NAME = "gen_ai.operation.name"

    # Request
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
    REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    REQUEST_TOP_P = "gen_ai.request.top_p"
    REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"

    # Response
    RESPONSE_ID = "gen_ai.response.id"
    RESPONSE_MODEL = "gen_ai.response.model"
    RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"

    # Usage
    USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

    # Content (optional, can be large)
    PROMPT = "gen_ai.prompt"
    COMPLETION = "gen_ai.completion"

    # Tool calls
    TOOL_NAME = "gen_ai.tool.name"
    TOOL_DESCRIPTION = "gen_ai.tool.description"


# Custom Tradegent attributes
class TradegentAttributes:
    """Custom attributes for trading analysis tracing."""

    TICKER = "tradegent.ticker"
    ANALYSIS_TYPE = "tradegent.analysis_type"
    PHASE = "tradegent.phase"
    PHASE_NAME = "tradegent.phase_name"
    TOOL_CALLS_COUNT = "tradegent.tool_calls_count"
    GATE_PASSED = "tradegent.gate_passed"
    RECOMMENDATION = "tradegent.recommendation"
    CONFIDENCE = "tradegent.confidence"
    EXPECTED_VALUE = "tradegent.expected_value_pct"
    ALLOWED_TOOLS = "tradegent.allowed_tools"
    SUBPROCESS_CMD = "tradegent.subprocess_cmd"
    OUTPUT_LENGTH = "tradegent.output_length"


@dataclass
class ToolCall:
    """Represents a tool/function call made by the LLM."""

    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    duration_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class LLMCallMetrics:
    """Metrics collected during an LLM call."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: FinishReason = FinishReason.STOP
    model: str = ""
    cost_usd: float = 0.0


class LLMSpan:
    """
    Context manager for tracing LLM calls with GenAI semantic conventions.

    Usage:
        with LLMSpan(
            operation="chat",
            system=GenAISystem.CLAUDE_CODE,
            model="claude-sonnet-4-20250514",
            ticker="NVDA",
            analysis_type="earnings",
        ) as span:
            # Make LLM call
            result = call_claude(prompt)

            # Record metrics
            span.set_tokens(input=1500, output=800)
            span.set_finish_reason(FinishReason.STOP)
            span.add_tool_call("mcp__ib-mcp__get_stock_price", {"symbol": "NVDA"})

            # Optionally capture content
            span.set_prompt(prompt)
            span.set_completion(result)
    """

    def __init__(
        self,
        operation: str = "chat",
        system: GenAISystem = GenAISystem.CLAUDE_CODE,
        model: str = "unknown",
        ticker: Optional[str] = None,
        analysis_type: Optional[str] = None,
        phase: Optional[int] = None,
        phase_name: Optional[str] = None,
        allowed_tools: Optional[str] = None,
        parent_span: Optional[Span] = None,
    ):
        self.operation = operation
        self.system = system
        self.model = model
        self.ticker = ticker
        self.analysis_type = analysis_type
        self.phase = phase
        self.phase_name = phase_name
        self.allowed_tools = allowed_tools
        self.parent_span = parent_span

        self._span: Optional[Span] = None
        self._start_time: float = 0
        self._metrics = LLMCallMetrics(model=model)
        self._tool_spans: List[Span] = []

    def __enter__(self) -> "LLMSpan":
        tracer = get_tracer()
        config = get_config()

        # Create span name
        span_name = f"gen_ai.{self.operation}"
        if self.ticker:
            span_name = f"{span_name} {self.ticker}"

        # Start span
        context = trace.set_span_in_context(self.parent_span) if self.parent_span else None
        self._span = tracer.start_span(span_name, context=context)
        self._start_time = time.perf_counter()

        # Set GenAI attributes
        self._span.set_attribute(GenAIAttributes.SYSTEM, self.system.value)
        self._span.set_attribute(GenAIAttributes.OPERATION_NAME, self.operation)
        self._span.set_attribute(GenAIAttributes.REQUEST_MODEL, self.model)

        # Set Tradegent attributes
        if self.ticker:
            self._span.set_attribute(TradegentAttributes.TICKER, self.ticker)
        if self.analysis_type:
            self._span.set_attribute(TradegentAttributes.ANALYSIS_TYPE, self.analysis_type)
        if self.phase is not None:
            self._span.set_attribute(TradegentAttributes.PHASE, self.phase)
        if self.phase_name:
            self._span.set_attribute(TradegentAttributes.PHASE_NAME, self.phase_name)
        if self.allowed_tools:
            self._span.set_attribute(TradegentAttributes.ALLOWED_TOOLS, self.allowed_tools)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span is None:
            return

        # Calculate duration
        self._metrics.duration_ms = (time.perf_counter() - self._start_time) * 1000

        # Set final metrics
        self._span.set_attribute(
            GenAIAttributes.USAGE_INPUT_TOKENS, self._metrics.input_tokens
        )
        self._span.set_attribute(
            GenAIAttributes.USAGE_OUTPUT_TOKENS, self._metrics.output_tokens
        )
        self._span.set_attribute(
            GenAIAttributes.RESPONSE_FINISH_REASONS, [self._metrics.finish_reason.value]
        )
        self._span.set_attribute(
            TradegentAttributes.TOOL_CALLS_COUNT, len(self._metrics.tool_calls)
        )

        # Handle errors
        if exc_type is not None:
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            self._span.record_exception(exc_val)
            self._metrics.finish_reason = FinishReason.ERROR
        else:
            self._span.set_status(Status(StatusCode.OK))

        self._span.end()

    @property
    def span(self) -> Optional[Span]:
        """Get the underlying OpenTelemetry span."""
        return self._span

    @property
    def metrics(self) -> LLMCallMetrics:
        """Get collected metrics."""
        return self._metrics

    def set_tokens(self, input: int = 0, output: int = 0):
        """Set token usage."""
        self._metrics.input_tokens = input
        self._metrics.output_tokens = output
        self._metrics.total_tokens = input + output

        # Estimate cost (Claude Sonnet pricing as of 2024)
        # $3/M input, $15/M output
        input_cost = (input / 1_000_000) * 3.0
        output_cost = (output / 1_000_000) * 15.0
        self._metrics.cost_usd = input_cost + output_cost

    def set_finish_reason(self, reason: FinishReason):
        """Set why the LLM stopped generating."""
        self._metrics.finish_reason = reason

    def set_prompt(self, prompt: str):
        """Capture the prompt (if enabled in config)."""
        config = get_config()
        if config.capture_prompts and self._span:
            truncated = prompt[: config.max_content_length]
            if len(prompt) > config.max_content_length:
                truncated += f"... [truncated, total {len(prompt)} chars]"
            self._span.set_attribute(GenAIAttributes.PROMPT, truncated)

    def set_completion(self, completion: str):
        """Capture the completion (if enabled in config)."""
        config = get_config()
        if config.capture_completions and self._span:
            truncated = completion[: config.max_content_length]
            if len(completion) > config.max_content_length:
                truncated += f"... [truncated, total {len(completion)} chars]"
            self._span.set_attribute(GenAIAttributes.COMPLETION, truncated)
            self._span.set_attribute(TradegentAttributes.OUTPUT_LENGTH, len(completion))

    def set_output_length(self, length: int):
        """Set output length without capturing content."""
        if self._span:
            self._span.set_attribute(TradegentAttributes.OUTPUT_LENGTH, length)

    def set_result(
        self,
        gate_passed: bool,
        recommendation: str,
        confidence: float,
        expected_value: Optional[float] = None,
    ):
        """Set analysis result attributes."""
        if self._span:
            self._span.set_attribute(TradegentAttributes.GATE_PASSED, gate_passed)
            self._span.set_attribute(TradegentAttributes.RECOMMENDATION, recommendation)
            self._span.set_attribute(TradegentAttributes.CONFIDENCE, confidence)
            if expected_value is not None:
                self._span.set_attribute(TradegentAttributes.EXPECTED_VALUE, expected_value)

    def set_subprocess_cmd(self, cmd: List[str]):
        """Record the subprocess command being executed."""
        if self._span:
            self._span.set_attribute(TradegentAttributes.SUBPROCESS_CMD, " ".join(cmd[:5]))

    @contextmanager
    def tool_call(
        self, name: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Generator[Span, None, None]:
        """
        Create a child span for a tool call.

        Usage:
            with span.tool_call("mcp__ib-mcp__get_stock_price", {"symbol": "NVDA"}) as tool_span:
                result = call_tool(...)
        """
        tracer = get_tracer()

        tool_span = tracer.start_span(
            f"gen_ai.tool.{name}",
            context=trace.set_span_in_context(self._span) if self._span else None,
        )

        tool_span.set_attribute(GenAIAttributes.TOOL_NAME, name)
        if arguments:
            # Store arguments as JSON string to avoid attribute type issues
            import json

            tool_span.set_attribute("gen_ai.tool.arguments", json.dumps(arguments))

        start_time = time.perf_counter()
        tool_call = ToolCall(name=name, arguments=arguments or {})

        try:
            yield tool_span
            tool_span.set_status(Status(StatusCode.OK))
        except Exception as e:
            tool_span.set_status(Status(StatusCode.ERROR, str(e)))
            tool_span.record_exception(e)
            tool_call.error = str(e)
            raise
        finally:
            tool_call.duration_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.tool_calls.append(tool_call)
            self._tool_spans.append(tool_span)
            tool_span.end()

    def add_tool_call(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        duration_ms: Optional[float] = None,
    ):
        """
        Add a tool call record (for when you can't use the context manager).
        """
        tool_call = ToolCall(
            name=name,
            arguments=arguments or {},
            result=result,
            duration_ms=duration_ms,
        )
        self._metrics.tool_calls.append(tool_call)

        # Create a completed span for it
        if self._span:
            tracer = get_tracer()
            tool_span = tracer.start_span(
                f"gen_ai.tool.{name}",
                context=trace.set_span_in_context(self._span),
            )
            tool_span.set_attribute(GenAIAttributes.TOOL_NAME, name)
            tool_span.set_status(Status(StatusCode.OK))
            tool_span.end()


class ToolCallSpan:
    """
    Standalone context manager for MCP tool calls.

    Use when tool calls happen outside of LLM spans.

    Usage:
        with ToolCallSpan("mcp__ib-mcp__get_stock_price", ticker="NVDA") as span:
            result = call_ib_mcp(...)
            span.set_result(result)
    """

    def __init__(
        self,
        tool_name: str,
        ticker: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
    ):
        self.tool_name = tool_name
        self.ticker = ticker
        self.arguments = arguments or {}

        self._span: Optional[Span] = None
        self._start_time: float = 0

    def __enter__(self) -> "ToolCallSpan":
        tracer = get_tracer()

        span_name = f"tool.{self.tool_name}"
        if self.ticker:
            span_name = f"{span_name} {self.ticker}"

        self._span = tracer.start_span(span_name)
        self._start_time = time.perf_counter()

        self._span.set_attribute(GenAIAttributes.TOOL_NAME, self.tool_name)
        if self.ticker:
            self._span.set_attribute(TradegentAttributes.TICKER, self.ticker)
        if self.arguments:
            import json

            self._span.set_attribute("tool.arguments", json.dumps(self.arguments))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span is None:
            return

        duration_ms = (time.perf_counter() - self._start_time) * 1000
        self._span.set_attribute("tool.duration_ms", duration_ms)

        if exc_type is not None:
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            self._span.record_exception(exc_val)
        else:
            self._span.set_status(Status(StatusCode.OK))

        self._span.end()

    def set_result(self, result: Any, result_size: Optional[int] = None):
        """Record tool call result."""
        if self._span:
            if result_size:
                self._span.set_attribute("tool.result_size", result_size)
            elif isinstance(result, (str, bytes)):
                self._span.set_attribute("tool.result_size", len(result))


class PipelineSpan:
    """
    Span for the entire analysis pipeline.

    Usage:
        with PipelineSpan(ticker="NVDA", analysis_type="earnings") as pipeline:
            with pipeline.phase(1, "Fresh analysis"):
                # Phase 1 work
                pass

            with pipeline.phase(2, "Dual ingest"):
                # Phase 2 work
                pass
    """

    def __init__(
        self,
        ticker: str,
        analysis_type: str,
        run_id: Optional[str] = None,
    ):
        self.ticker = ticker
        self.analysis_type = analysis_type
        self.run_id = run_id

        self._span: Optional[Span] = None
        self._start_time: float = 0
        self._current_phase: Optional[Span] = None

    def __enter__(self) -> "PipelineSpan":
        tracer = get_tracer()

        self._span = tracer.start_span(f"pipeline.{self.ticker}")
        self._start_time = time.perf_counter()

        self._span.set_attribute(TradegentAttributes.TICKER, self.ticker)
        self._span.set_attribute(TradegentAttributes.ANALYSIS_TYPE, self.analysis_type)
        if self.run_id:
            self._span.set_attribute("tradegent.run_id", self.run_id)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span is None:
            return

        duration_ms = (time.perf_counter() - self._start_time) * 1000
        self._span.set_attribute("pipeline.duration_ms", duration_ms)

        if exc_type is not None:
            self._span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            self._span.record_exception(exc_val)
        else:
            self._span.set_status(Status(StatusCode.OK))

        self._span.end()

    @contextmanager
    def phase(self, phase_num: int, phase_name: str) -> Generator[Span, None, None]:
        """Create a child span for a pipeline phase."""
        tracer = get_tracer()

        phase_span = tracer.start_span(
            f"phase.{phase_num}.{phase_name}",
            context=trace.set_span_in_context(self._span) if self._span else None,
        )

        phase_span.set_attribute(TradegentAttributes.PHASE, phase_num)
        phase_span.set_attribute(TradegentAttributes.PHASE_NAME, phase_name)
        phase_span.set_attribute(TradegentAttributes.TICKER, self.ticker)

        start_time = time.perf_counter()

        try:
            yield phase_span
            phase_span.set_status(Status(StatusCode.OK))
        except Exception as e:
            phase_span.set_status(Status(StatusCode.ERROR, str(e)))
            phase_span.record_exception(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            phase_span.set_attribute("phase.duration_ms", duration_ms)
            phase_span.end()

    def set_result(
        self,
        gate_passed: bool,
        recommendation: str,
        confidence: float,
    ):
        """Set pipeline result attributes."""
        if self._span:
            self._span.set_attribute(TradegentAttributes.GATE_PASSED, gate_passed)
            self._span.set_attribute(TradegentAttributes.RECOMMENDATION, recommendation)
            self._span.set_attribute(TradegentAttributes.CONFIDENCE, confidence)
