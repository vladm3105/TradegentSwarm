"""Analysis agent for stock/earnings analysis operations."""
import structlog

from .base_agent import BaseAgent, AgentResponse
from .context_manager import ConversationContext

log = structlog.get_logger()


class AnalysisAgent(BaseAgent):
    """Agent for analysis operations.

    Capabilities:
    - Run stock/earnings analysis
    - Retrieve past analyses
    - Validate analysis reports
    - Compare analyses
    - Check forecast status
    """

    def __init__(self):
        super().__init__("analysis")

    async def process(
        self,
        query: str,
        tickers: list[str],
        context: ConversationContext,
    ) -> AgentResponse:
        """Process an analysis-related query.

        Args:
            query: User query
            tickers: Extracted tickers
            context: Conversation context

        Returns:
            AgentResponse with analysis results
        """
        query_lower = query.lower()
        tool_results = {}

        # Determine which tools to call based on query
        if any(word in query_lower for word in ["analyze", "analysis", "run"]):
            # Run analysis - for each ticker
            for ticker in tickers[:3]:  # Limit to 3 tickers
                result = await self.execute_tool(
                    "get_analysis",
                    {"ticker": ticker, "query": "latest analysis recommendation"},
                )
                tool_results[f"analysis_{ticker}"] = result.result if result.success else result.error

                # Also get graph context for richer response
                graph_result = await self.execute_tool(
                    "get_analysis",
                    {"ticker": ticker, "query": "analysis context peers risks"},
                )
                if graph_result.success:
                    tool_results[f"context_{ticker}"] = graph_result.result

        elif "compare" in query_lower:
            # Compare analyses
            if len(tickers) >= 2:
                for ticker in tickers[:2]:
                    result = await self.execute_tool(
                        "compare_analyses",
                        {"ticker": ticker, "analysis_type": "stock-analysis"},
                    )
                    tool_results[f"compare_{ticker}"] = result.result if result.success else result.error
            else:
                return AgentResponse(
                    success=False,
                    text="Please specify at least 2 tickers to compare.",
                    error="Need 2+ tickers for comparison",
                )

        elif "validate" in query_lower:
            # Validate analysis
            for ticker in tickers[:1]:
                result = await self.execute_tool(
                    "validate_analysis",
                    {"ticker": ticker},
                )
                tool_results[f"validation_{ticker}"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["forecast", "valid", "expire"]):
            # Check forecast status
            for ticker in tickers[:1]:
                result = await self.execute_tool(
                    "get_forecast_status",
                    {"ticker": ticker},
                )
                tool_results[f"forecast_{ticker}"] = result.result if result.success else result.error

        elif "recent" in query_lower or "list" in query_lower:
            # List recent analyses
            result = await self.execute_tool(
                "list_recent_analyses",
                {"query": "recent analysis", "top_k": 10},
            )
            tool_results["recent_analyses"] = result.result if result.success else result.error

        elif "lineage" in query_lower or "chain" in query_lower:
            # Get analysis lineage
            for ticker in tickers[:1]:
                result = await self.execute_tool(
                    "get_analysis_lineage",
                    {"ticker": ticker},
                )
                tool_results[f"lineage_{ticker}"] = result.result if result.success else result.error

        else:
            # Default: get analysis for mentioned tickers
            if tickers:
                for ticker in tickers[:3]:
                    result = await self.execute_tool(
                        "get_analysis",
                        {"ticker": ticker, "query": "analysis recommendation gate"},
                    )
                    tool_results[f"analysis_{ticker}"] = result.result if result.success else result.error
            else:
                # No tickers, list recent
                result = await self.execute_tool(
                    "list_recent_analyses",
                    {"query": "recent analysis recommendation", "top_k": 5},
                )
                tool_results["recent_analyses"] = result.result if result.success else result.error

        # Generate A2UI response
        if not tool_results:
            return AgentResponse(
                success=False,
                text="No analysis results found.",
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
            log.error("Failed to generate analysis response", error=str(e))
            return AgentResponse(
                success=False,
                text=f"Analysis completed but failed to format response: {e}",
                tool_results=tool_results,
                error=str(e),
            )
