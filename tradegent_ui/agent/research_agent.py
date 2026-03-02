"""Research agent for RAG search and graph queries."""
import structlog

from .base_agent import BaseAgent, AgentResponse
from .context_manager import ConversationContext

log = structlog.get_logger()


class ResearchAgent(BaseAgent):
    """Agent for research operations.

    Capabilities:
    - Semantic search across knowledge base
    - Find similar analyses
    - Get ticker context from graph
    - Find sector peers
    - Web search for news
    - Get ticker profiles
    """

    def __init__(self):
        super().__init__("research")

    async def process(
        self,
        query: str,
        tickers: list[str],
        context: ConversationContext,
    ) -> AgentResponse:
        """Process a research-related query.

        Args:
            query: User query
            tickers: Extracted tickers
            context: Conversation context

        Returns:
            AgentResponse with research results
        """
        query_lower = query.lower()
        tool_results = {}

        # Determine which tools to call based on query
        if any(word in query_lower for word in ["what do you know", "tell me about", "context"]):
            # Get comprehensive context
            if tickers:
                for ticker in tickers[:2]:
                    # Graph context
                    graph_result = await self.execute_tool(
                        "graph_context",
                        {"ticker": ticker},
                    )
                    tool_results[f"context_{ticker}"] = (
                        graph_result.result if graph_result.success else graph_result.error
                    )

                    # RAG search
                    rag_result = await self.execute_tool(
                        "rag_search",
                        {"ticker": ticker, "query": f"{ticker} analysis context", "top_k": 5},
                    )
                    tool_results[f"rag_{ticker}"] = (
                        rag_result.result if rag_result.success else rag_result.error
                    )
            else:
                # General search
                result = await self.execute_tool(
                    "rag_search",
                    {"query": query, "top_k": 10},
                )
                tool_results["search"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["peer", "competitor", "similar", "sector"]):
            # Get peers
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "graph_peers",
                        {"ticker": ticker},
                    )
                    tool_results[f"peers_{ticker}"] = result.result if result.success else result.error

                    # Also get similar analyses
                    similar = await self.execute_tool(
                        "rag_similar",
                        {"ticker": ticker, "analysis_type": "stock-analysis", "top_k": 5},
                    )
                    if similar.success:
                        tool_results[f"similar_{ticker}"] = similar.result
            else:
                return AgentResponse(
                    success=False,
                    text="Please specify a ticker to find peers for.",
                    error="No ticker specified",
                )

        elif any(word in query_lower for word in ["search", "find", "look"]):
            # General search
            search_query = query

            # If tickers, focus on them
            if tickers:
                for ticker in tickers[:2]:
                    result = await self.execute_tool(
                        "rag_search",
                        {"ticker": ticker, "query": search_query, "top_k": 5},
                    )
                    tool_results[f"search_{ticker}"] = result.result if result.success else result.error
            else:
                result = await self.execute_tool(
                    "rag_search",
                    {"query": search_query, "top_k": 10},
                )
                tool_results["search"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["news", "catalyst", "event"]):
            # Web search for news
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "web_search",
                        {"query": f"{ticker} stock news catalyst"},
                    )
                    tool_results[f"news_{ticker}"] = result.result if result.success else result.error
            else:
                result = await self.execute_tool(
                    "web_search",
                    {"query": query},
                )
                tool_results["news"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["profile", "summary", "overview"]):
            # Get ticker profile
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "get_ticker_profile",
                        {"ticker": ticker},
                    )
                    tool_results[f"profile_{ticker}"] = result.result if result.success else result.error

                    # Also get graph context
                    graph = await self.execute_tool(
                        "graph_context",
                        {"ticker": ticker},
                    )
                    if graph.success:
                        tool_results[f"graph_{ticker}"] = graph.result
            else:
                return AgentResponse(
                    success=False,
                    text="Please specify a ticker to get the profile for.",
                    error="No ticker specified",
                )

        elif "history" in query_lower:
            # Get historical analyses
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "rag_similar",
                        {"ticker": ticker, "analysis_type": "stock-analysis", "top_k": 10},
                    )
                    tool_results[f"history_{ticker}"] = result.result if result.success else result.error
            else:
                result = await self.execute_tool(
                    "rag_search",
                    {"query": "historical analysis", "top_k": 10},
                )
                tool_results["history"] = result.result if result.success else result.error

        else:
            # Default: combined search
            if tickers:
                for ticker in tickers[:2]:
                    # RAG search
                    rag = await self.execute_tool(
                        "rag_search",
                        {"ticker": ticker, "query": query, "top_k": 5},
                    )
                    tool_results[f"rag_{ticker}"] = rag.result if rag.success else rag.error

                    # Graph context
                    graph = await self.execute_tool(
                        "graph_context",
                        {"ticker": ticker},
                    )
                    if graph.success:
                        tool_results[f"graph_{ticker}"] = graph.result
            else:
                # General knowledge search
                result = await self.execute_tool(
                    "rag_search",
                    {"query": query, "top_k": 10},
                )
                tool_results["search"] = result.result if result.success else result.error

        # Generate A2UI response
        if not tool_results:
            return AgentResponse(
                success=False,
                text="No research results found.",
                error="No results",
            )

        try:
            a2ui = await self.generate_response(query, tool_results, context)
            return AgentResponse(
                success=True,
                text=a2ui.get("text", ""),
                a2ui=a2ui,
                tool_results=tool_results,
            )
        except Exception as e:
            log.error("Failed to generate research response", error=str(e))
            return AgentResponse(
                success=False,
                text=f"Research completed but failed to format: {e}",
                tool_results=tool_results,
                error=str(e),
            )
