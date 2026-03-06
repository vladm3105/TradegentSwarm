"""Coordinator agent for intent routing."""
import time
import structlog
from typing import Any

from .base_agent import AgentResponse
from .intent_classifier import (
    Intent,
    ClassificationResult,
    detect_multi_intent,
    get_clarification_prompt,
)
from .context_manager import ConversationContext, context_store
from .llm_client import get_llm_client
from server.errors import IntentClassificationError

log = structlog.get_logger(__name__)


class Coordinator:
    """Coordinator agent for intent classification and routing.

    Responsibilities:
    - Classify user intent
    - Route to appropriate specialist agent
    - Handle multi-intent queries
    - Manage clarification when needed
    """

    def __init__(self):
        self._agents: dict[str, Any] = {}
        self._llm_client = None

    async def initialize(self):
        """Initialize coordinator and specialist agents."""
        from .analysis_agent import AnalysisAgent
        from .trade_agent import TradeAgent
        from .portfolio_agent import PortfolioAgent
        from .research_agent import ResearchAgent

        # Create specialist agents
        self._agents = {
            Intent.ANALYSIS: AnalysisAgent(),
            Intent.TRADE: TradeAgent(),
            Intent.PORTFOLIO: PortfolioAgent(),
            Intent.RESEARCH: ResearchAgent(),
        }

        # Initialize all agents
        for agent in self._agents.values():
            await agent.initialize()

        self._llm_client = get_llm_client()
        log.info("Coordinator initialized", agents=list(self._agents.keys()))

    async def process(
        self,
        session_id: str,
        query: str,
    ) -> AgentResponse:
        """Process a user query.

        Args:
            session_id: Session identifier
            query: User query

        Returns:
            AgentResponse with A2UI components
        """
        start_time = time.perf_counter()

        log.info(
            "agent.process.started",
            session_id=session_id,
            query_length=len(query),
            query_preview=query[:100] if len(query) > 100 else query,
        )

        # Get conversation context
        context = context_store.get(session_id)
        context_size = len(context.messages) if hasattr(context, 'messages') else 0

        # Resolve pronouns using context
        resolved_query = context.resolve_pronouns(query)
        query_resolved = resolved_query != query

        if query_resolved:
            log.debug(
                "agent.pronoun.resolved",
                session_id=session_id,
                original=query[:50],
                resolved=resolved_query[:50],
            )

        # Classify intent
        classify_start = time.perf_counter()
        classifications = detect_multi_intent(resolved_query)
        classify_ms = (time.perf_counter() - classify_start) * 1000

        if not classifications:
            log.warning(
                "agent.intent.unknown",
                session_id=session_id,
                query=query[:100],
                classify_ms=round(classify_ms, 2),
            )
            raise IntentClassificationError(query)

        intents = [c.intent.value for c in classifications]
        tickers = list(set(t for c in classifications for t in c.tickers))

        log.info(
            "agent.intent.classified",
            session_id=session_id,
            intents=intents,
            tickers=tickers,
            confidence=[c.confidence for c in classifications],
            classify_ms=round(classify_ms, 2),
            context_size=context_size,
            multi_intent=len(classifications) > 1,
        )

        # Handle single intent
        if len(classifications) == 1:
            response = await self._route_single(classifications[0], resolved_query, context)
        else:
            # Handle multi-intent
            response = await self._route_multi(classifications, resolved_query, context)

        # Log completion with detailed A2UI breakdown
        total_ms = (time.perf_counter() - start_time) * 1000
        components = response.a2ui.get("components", []) if response.a2ui else []
        component_count = len(components)

        # Build component type breakdown for debugging
        component_types = {}
        for comp in components:
            comp_type = comp.get("type", "unknown")
            component_types[comp_type] = component_types.get(comp_type, 0) + 1

        log.info(
            "agent.process.completed",
            session_id=session_id,
            success=response.success,
            intents=intents,
            tickers=tickers,
            component_count=component_count,
            component_types=component_types,
            text_length=len(response.text) if response.text else 0,
            run_id=(response.debug_metadata or {}).get("run_id") if response.debug_metadata else None,
            run_status=(response.debug_metadata or {}).get("status") if response.debug_metadata else None,
            run_latency_ms=(response.debug_metadata or {}).get("latency_ms") if response.debug_metadata else None,
            duration_ms=round(total_ms, 2),
            has_error=response.error is not None,
        )

        # Debug: log full A2UI structure when debug enabled
        if component_count > 0:
            log.debug(
                "agent.a2ui.components",
                session_id=session_id,
                a2ui_text_preview=(response.a2ui.get("text", "")[:100] if response.a2ui else ""),
                components=[
                    {
                        "type": c.get("type"),
                        "props_keys": list(c.get("props", {}).keys()),
                    }
                    for c in components
                ],
            )

        return response

    async def _route_single(
        self,
        classification: ClassificationResult,
        query: str,
        context: ConversationContext,
    ) -> AgentResponse:
        """Route a single-intent query to specialist agent.

        Args:
            classification: Intent classification
            query: Resolved query
            context: Conversation context

        Returns:
            AgentResponse from specialist agent
        """
        intent = classification.intent
        start_time = time.perf_counter()

        # Handle clarification needed
        if classification.requires_clarification:
            log.info(
                "agent.clarification.needed",
                intent=intent.value,
                reason=classification.clarification_reason if hasattr(classification, 'clarification_reason') else "unknown",
            )

            clarification = get_clarification_prompt(classification)

            # Use LLM for better clarification if available
            if self._llm_client and intent == Intent.UNKNOWN:
                try:
                    clarification = await self._llm_client.generate_clarification(
                        query, context.get_context_summary()
                    )
                    log.debug("agent.clarification.llm_generated")
                except Exception as e:
                    log.warning("agent.clarification.llm_failed", error=str(e))

            return AgentResponse(
                success=True,
                text=clarification,
                a2ui={
                    "type": "a2ui",
                    "text": clarification,
                    "components": [],
                },
            )

        # Handle system intent
        if intent == Intent.SYSTEM:
            log.debug("agent.routing.system", query_preview=query[:50])
            return await self._handle_system(query, context)

        # Handle unknown intent
        if intent == Intent.UNKNOWN:
            log.warning("agent.routing.unknown", query=query[:100])
            raise IntentClassificationError(query)

        # Route to specialist agent
        agent = self._agents.get(intent)
        if not agent:
            log.error("agent.routing.no_agent", intent=intent.value)
            raise IntentClassificationError(query)

        log.info(
            "agent.routing.specialist",
            intent=intent.value,
            agent_type=agent.agent_type,
            tickers=classification.tickers,
        )

        response = await agent.process(
            query=query,
            tickers=classification.tickers,
            context=context,
        )

        route_ms = (time.perf_counter() - start_time) * 1000
        log.info(
            "agent.routing.completed",
            intent=intent.value,
            success=response.success,
            tickers=classification.tickers,
            tool_count=len(response.tool_results) if response.tool_results else 0,
            duration_ms=round(route_ms, 2),
        )

        # Update context
        context.add_message(
            role="user",
            content=query,
            intent=intent,
            tickers=classification.tickers,
        )

        if response.success and response.a2ui:
            context.add_message(
                role="assistant",
                content=response.text,
                a2ui_components=response.a2ui.get("components", []),
            )

        context.update_from_classification(classification, response.tool_results)

        return response

    async def _route_multi(
        self,
        classifications: list[ClassificationResult],
        query: str,
        context: ConversationContext,
    ) -> AgentResponse:
        """Route a multi-intent query to multiple agents.

        Args:
            classifications: List of intent classifications
            query: Resolved query
            context: Conversation context

        Returns:
            Combined AgentResponse
        """
        all_results = []
        all_components = []
        all_text_parts = []

        for classification in classifications:
            if classification.intent in (Intent.UNKNOWN, Intent.SYSTEM):
                continue

            agent = self._agents.get(classification.intent)
            if not agent:
                continue

            try:
                response = await agent.process(
                    query=query,
                    tickers=classification.tickers,
                    context=context,
                )

                if response.success:
                    all_results.append(response)
                    if response.a2ui:
                        all_components.extend(response.a2ui.get("components", []))
                    if response.text:
                        all_text_parts.append(response.text)

            except Exception as e:
                log.error(
                    "Agent processing failed",
                    intent=classification.intent.value,
                    error=str(e),
                )

        if not all_results:
            raise IntentClassificationError(query)

        # Combine results
        combined_text = "\n\n".join(all_text_parts)
        combined_a2ui = {
            "type": "a2ui",
            "text": combined_text,
            "components": all_components,
        }

        # Update context with primary intent
        primary = classifications[0]
        context.add_message(
            role="user",
            content=query,
            intent=primary.intent,
            tickers=[t for c in classifications for t in c.tickers],
        )
        context.add_message(
            role="assistant",
            content=combined_text,
            a2ui_components=all_components,
        )

        return AgentResponse(
            success=True,
            text=combined_text,
            a2ui=combined_a2ui,
            tool_results={
                f"{r.tool_results}" for r in all_results if r.tool_results
            },
        )

    async def _handle_system(
        self,
        query: str,
        context: ConversationContext,
    ) -> AgentResponse:
        """Handle system-level queries (health, help, status).

        Args:
            query: System query
            context: Conversation context

        Returns:
            AgentResponse with system info
        """
        query_lower = query.lower()

        if "health" in query_lower or "status" in query_lower:
            from .mcp_client import get_mcp_pool

            pool = await get_mcp_pool()
            health = await pool.health_check()

            components = [
                {
                    "type": "MetricsRow",
                    "props": {
                        "metrics": [
                            {
                                "label": "IB Gateway",
                                "value": "Connected" if health.ib_mcp else "Disconnected",
                            },
                            {
                                "label": "RAG",
                                "value": "Ready" if health.trading_rag else "Unavailable",
                            },
                            {
                                "label": "Graph",
                                "value": "Ready" if health.trading_graph else "Unavailable",
                            },
                        ]
                    },
                }
            ]

            status = "All systems operational" if health.all_healthy() else "Some systems degraded"

            return AgentResponse(
                success=True,
                text=status,
                a2ui={
                    "type": "a2ui",
                    "text": status,
                    "components": components,
                },
            )

        if "help" in query_lower:
            help_text = """I can help you with:

**Analysis** - Analyze stocks (e.g., "analyze NVDA")
**Portfolio** - View positions and P&L (e.g., "show my positions")
**Trading** - Log trades (e.g., "I bought AAPL at $150")
**Research** - Look up information (e.g., "what do you know about ZIM")
**Status** - Check system health (e.g., "system status")"""

            return AgentResponse(
                success=True,
                text=help_text,
                a2ui={
                    "type": "a2ui",
                    "text": help_text,
                    "components": [
                        {
                            "type": "TextCard",
                            "props": {"content": help_text, "title": "Help"},
                        }
                    ],
                },
            )

        return AgentResponse(
            success=True,
            text="System is running. Type 'help' for available commands.",
            a2ui={
                "type": "a2ui",
                "text": "System is running. Type 'help' for available commands.",
                "components": [],
            },
        )


# Global coordinator instance
_coordinator: Coordinator | None = None


async def get_coordinator() -> Coordinator:
    """Get or create the global coordinator."""
    global _coordinator
    if _coordinator is None:
        _coordinator = Coordinator()
        await _coordinator.initialize()
    return _coordinator
