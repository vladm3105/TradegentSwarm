"""LLM client for A2UI response generation."""
import json
import sys
import time
import structlog
from pathlib import Path
from typing import Any, cast

# Add shared module to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.config import get_settings
from server.errors import LLMError, LLMTimeoutError
from tradegent.llm_gateway import LiteLLMGatewayClient
from shared.observability.metrics_ui import get_metrics
from shared.observability.spans import LLMSpan, GenAISystem, FinishReason

log = structlog.get_logger(__name__)

# System prompt for A2UI generation
A2UI_SYSTEM_PROMPT = """You are a trading assistant that generates structured UI responses.

When responding, output JSON in A2UI format:
{
  "type": "a2ui",
  "text": "Your conversational response here",
  "components": [
    {"type": "ComponentName", "props": {...}}
  ]
}

Available components and their props:

1. AnalysisCard - Stock analysis summary
   Props: ticker (str), recommendation (STRONG_BUY|BUY|WATCH|NO_POSITION|AVOID),
          confidence (0-100), expected_value (float %), gate_result (PASS|MARGINAL|FAIL),
          analysis_date (str), forecast_valid_until (str)

2. PositionCard - Portfolio position
   Props: ticker (str), size (int), avg_price (float), current_price (float),
          pnl (float $), pnl_pct (float %), market_value (float)

3. TradeCard - Trade journal entry
   Props: ticker (str), direction (LONG|SHORT), entry_price (float),
          current_price (float), size (int), pnl_pct (float %),
          status (OPEN|CLOSED|PARTIAL), entry_date (str), exit_date (str|null)

4. WatchlistCard - Watchlist entry
   Props: ticker (str), trigger_type (PRICE_ABOVE|PRICE_BELOW|EVENT|COMBINED),
          trigger_value (float|null), priority (HIGH|MEDIUM|LOW), expires (str), notes (str)

5. GateResult - Do Nothing Gate result
   Props: ev (float %), ev_passed (bool), confidence (int), confidence_passed (bool),
          risk_reward (float), rr_passed (bool), edge_not_priced (bool),
          overall (PASS|MARGINAL|FAIL)

6. ScenarioChart - Scenario probabilities
   Props: scenarios ([{name, probability, return_pct, description}]), weighted_ev (float)

7. MetricsRow - Key metrics display
   Props: metrics ([{label, value, change (optional)}])

8. ChartCard - Price/data visualization
   Props: ticker (str), chart_type (price|pnl|volume), data (array), timeframe (str)

9. ErrorCard - Error display
   Props: code (str), message (str), recoverable (bool), retry_action (str|null)

10. LoadingCard - Loading state
    Props: message (str), progress (0-100|null), task_id (str|null)

11. TextCard - Rich text content
    Props: content (str markdown), title (str|null)

12. TableCard - Data table
    Props: headers ([str]), rows ([[str]]), title (str|null)

13. GrafanaPanel - Embedded Grafana dashboard panel
    Props: dashboard_uid (str), panel_id (int), title (str|null),
           timeframe (1h|6h|24h|7d|30d), height (int 200-600, default 300),
           theme (light|dark, default dark)
    Use for: system health metrics, trading performance charts, pipeline stats

Guidelines:
- Always include a "text" field with conversational response
- Choose appropriate components based on the data available
- Include relevant components only - don't add empty ones
- For positions/trades, always include pnl_pct
- For analyses, always include gate_result
- Format numbers appropriately (2 decimal places for prices, 1 for percentages)
"""

AGENT_CONTEXT_PROMPTS = {
    "analysis": "You are the Analysis Agent. Focus on stock analysis, forecasts, gate results, and recommendations.",
    "trade": "You are the Trade Agent. Focus on trade journaling, order execution, and fill analysis.",
    "portfolio": "You are the Portfolio Agent. Focus on positions, P&L, account summary, and watchlist.",
    "research": "You are the Research Agent. Focus on RAG search results, graph context, and sector analysis.",
    "system": "You are the System Agent. Focus on health status, metrics, and system monitoring. Use GrafanaPanel for visualizing system metrics, MCP latency, pipeline performance, and trading statistics.",
}


class LLMClient:
    """LLM client for generating A2UI responses."""

    def __init__(self):
        settings = get_settings()
        self.gateway = LiteLLMGatewayClient.from_env(
            timeout=settings.llm_timeout,
        )
        self.model = settings.llm_model

    @staticmethod
    def _system_from_provider(provider: str) -> GenAISystem:
        token = (provider or "").lower()
        if token == "openrouter":
            return GenAISystem.OPENROUTER
        if token == "anthropic":
            return GenAISystem.ANTHROPIC
        return GenAISystem.OPENAI

    async def generate_a2ui(
        self,
        agent_type: str,
        tool_results: list[dict],
        user_query: str,
        context_summary: str = "",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Generate A2UI response from tool results.

        Args:
            agent_type: Type of agent (analysis, trade, portfolio, research)
            tool_results: Results from MCP tool calls
            user_query: Original user query
            context_summary: Summary of conversation context
            conversation_history: Recent messages for context

        Returns:
            A2UI response dict with text and components
        """
        start_time = time.perf_counter()

        log.info(
            "llm.a2ui.generating",
            agent_type=agent_type,
            tool_count=len(tool_results),
            query_length=len(user_query),
            has_context=bool(context_summary),
            history_count=len(conversation_history) if conversation_history else 0,
            model=self.model,
        )

        # Build messages
        messages = [
            {"role": "system", "content": A2UI_SYSTEM_PROMPT},
        ]

        # Add agent-specific context
        agent_context = AGENT_CONTEXT_PROMPTS.get(agent_type, "")
        if agent_context:
            messages.append({"role": "system", "content": agent_context})

        # Add conversation context
        if context_summary:
            messages.append({"role": "system", "content": f"Conversation context:\n{context_summary}"})

        # Add recent conversation history
        if conversation_history:
            for msg in conversation_history[-3:]:  # Last 3 messages
                messages.append(msg)

        # Add current request with tool results
        tool_results_str = json.dumps(tool_results, indent=2, default=str)
        messages.append({
            "role": "user",
            "content": f"User query: {user_query}\n\nTool Results:\n{tool_results_str}\n\nGenerate an A2UI response based on these results.",
        })

        metrics = get_metrics()

        system = GenAISystem.OPENAI

        with LLMSpan(
            system=system,
            model=self.model,
            operation="chat",
            temperature=0.3,
        ) as llm_span:
            try:
                llm_result = await self.gateway.chat_json(
                    role_alias="summarizer_fast",
                    messages=messages,
                    temperature=0.3,
                )

                content = llm_result.content
                result = cast(dict[str, Any], json.loads(content))
                system = self._system_from_provider(llm_result.provider)

                # Record response in span
                llm_span.set_response(
                    response_id=llm_result.response_id,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    finish_reason=FinishReason.STOP,
                    response_model=llm_result.model,
                )

                metrics.record_llm_call(
                    duration_ms=llm_span.duration_ms,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    model=llm_result.model,
                )

                # Ensure proper A2UI structure
                if "type" not in result:
                    result["type"] = "a2ui"
                if "components" not in result:
                    result["components"] = []

                llm_span.add_event("a2ui_generated", {
                    "agent_type": agent_type,
                    "component_count": len(result.get("components", [])),
                })

                duration_ms = (time.perf_counter() - start_time) * 1000
                component_types = [c.get("type") for c in result.get("components", [])]

                log.info(
                    "llm.a2ui.generated",
                    agent_type=agent_type,
                    model=llm_result.model,
                    provider=llm_result.provider,
                    model_alias=llm_result.model_alias,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    component_count=len(result.get("components", [])),
                    component_types=component_types,
                    text_length=len(result.get("text", "")),
                    duration_ms=round(duration_ms, 2),
                )

                return result

            except json.JSONDecodeError as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log.error(
                    "llm.a2ui.json_error",
                    agent_type=agent_type,
                    error=str(e),
                    duration_ms=round(duration_ms, 2),
                )
                llm_span.set_error(f"Invalid JSON response: {e}")
                raise LLMError(f"Invalid JSON response: {e}")

            except TimeoutError:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log.error(
                    "llm.a2ui.timeout",
                    agent_type=agent_type,
                    model=self.model,
                    duration_ms=round(duration_ms, 2),
                )
                llm_span.set_error("Request timed out")
                raise LLMTimeoutError()

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log.error(
                    "llm.a2ui.error",
                    agent_type=agent_type,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                )
                llm_span.set_error(str(e))
                raise LLMError(str(e))

    async def classify_intent_llm(self, query: str, context: str = "") -> dict:
        """Use LLM for intent classification when keyword matching fails.

        Args:
            query: User query
            context: Additional context

        Returns:
            Dict with intent, confidence, and tickers
        """
        start_time = time.perf_counter()

        log.debug(
            "llm.classify.starting",
            query_length=len(query),
            has_context=bool(context),
            model=self.model,
        )

        messages = [
            {
                "role": "system",
                "content": """Classify the user's intent into one of these categories:
- analysis: User wants to analyze a stock, run forecasts, check recommendations
- trade: User wants to log a trade, place an order, review fills
- portfolio: User wants to see positions, P&L, account info, watchlist
- research: User wants to search for information, find context, look up news
- system: User wants health check, help, or system status
- unknown: Cannot determine intent

Also extract any stock tickers mentioned (1-5 uppercase letters).

Respond in JSON format:
{
  "intent": "analysis|trade|portfolio|research|system|unknown",
  "confidence": 0.0-1.0,
  "tickers": ["AAPL", "NVDA"],
  "reasoning": "Brief explanation"
}""",
            },
            {"role": "user", "content": f"Query: {query}\nContext: {context}"},
        ]

        metrics = get_metrics()

        system = GenAISystem.OPENAI

        with LLMSpan(
            system=system,
            model=self.model,
            operation="classify",
            temperature=0.1,
        ) as llm_span:
            try:
                llm_result = await self.gateway.chat_json(
                    role_alias="extraction_fast",
                    messages=messages,
                    temperature=0.1,
                )
                system = self._system_from_provider(llm_result.provider)

                # Record response in span
                llm_span.set_response(
                    response_id=llm_result.response_id,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    finish_reason=FinishReason.STOP,
                    response_model=llm_result.model,
                )

                metrics.record_llm_call(
                    duration_ms=llm_span.duration_ms,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    model=llm_result.model,
                )

                result = cast(dict[str, Any], json.loads(llm_result.content))

                # Record intent classification
                metrics.record_intent_classification(
                    duration_ms=llm_span.duration_ms,
                    intents=[result.get("intent", "unknown")],
                )

                llm_span.add_event("intent_classified", {
                    "intent": result.get("intent", "unknown"),
                    "confidence": result.get("confidence", 0.0),
                    "tickers": result.get("tickers", []),
                })

                duration_ms = (time.perf_counter() - start_time) * 1000
                log.info(
                    "llm.classify.completed",
                    intent=result.get("intent", "unknown"),
                    confidence=result.get("confidence", 0.0),
                    tickers=result.get("tickers", []),
                    model=llm_result.model,
                    provider=llm_result.provider,
                    model_alias=llm_result.model_alias,
                    input_tokens=llm_result.input_tokens,
                    output_tokens=llm_result.output_tokens,
                    duration_ms=round(duration_ms, 2),
                )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log.error(
                    "llm.classify.failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                )
                llm_span.set_error(str(e))
                return {"intent": "unknown", "confidence": 0.0, "tickers": []}

    async def generate_clarification(self, query: str, context: str = "") -> str:
        """Generate a clarification question for ambiguous queries.

        Args:
            query: Ambiguous user query
            context: Conversation context

        Returns:
            Clarification question string
        """
        messages = [
            {
                "role": "system",
                "content": "You are a helpful trading assistant. Generate a brief, friendly clarification question to understand what the user wants to do. Keep it under 2 sentences.",
            },
            {"role": "user", "content": f"The user said: '{query}'\nContext: {context}\n\nWhat clarification question should I ask?"},
        ]

        try:
            llm_result = await self.gateway.chat_text(
                role_alias="summarizer_fast",
                messages=messages,
                temperature=0.5,
                max_tokens=100,
            )

            return cast(str, llm_result.content).strip()

        except Exception:
            return "I'm not sure what you'd like me to do. Could you please clarify?"


# Global LLM client instance
_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
