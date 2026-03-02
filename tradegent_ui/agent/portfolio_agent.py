"""Portfolio agent for positions, P&L, and watchlist operations."""
import structlog

from .base_agent import BaseAgent, AgentResponse
from .context_manager import ConversationContext

log = structlog.get_logger()


class PortfolioAgent(BaseAgent):
    """Agent for portfolio operations.

    Capabilities:
    - Get current positions
    - View P&L summary
    - Check account balances
    - Manage watchlist
    - View open orders
    """

    def __init__(self):
        super().__init__("portfolio")

    async def process(
        self,
        query: str,
        tickers: list[str],
        context: ConversationContext,
    ) -> AgentResponse:
        """Process a portfolio-related query.

        Args:
            query: User query
            tickers: Extracted tickers (for filtering)
            context: Conversation context

        Returns:
            AgentResponse with portfolio data
        """
        query_lower = query.lower()
        tool_results = {}

        # Determine which tools to call based on query
        if any(word in query_lower for word in ["position", "holding", "own", "portfolio"]):
            # Get positions
            result = await self.execute_tool("get_positions", {})
            tool_results["positions"] = result.result if result.success else result.error

            # Also get P&L for context
            pnl_result = await self.execute_tool("get_pnl", {})
            if pnl_result.success:
                tool_results["pnl"] = pnl_result.result

        elif any(word in query_lower for word in ["pnl", "p&l", "profit", "loss", "performance"]):
            # Get P&L
            result = await self.execute_tool("get_pnl", {})
            tool_results["pnl"] = result.result if result.success else result.error

            # Also get positions for context
            pos_result = await self.execute_tool("get_positions", {})
            if pos_result.success:
                tool_results["positions"] = pos_result.result

        elif any(word in query_lower for word in ["account", "balance", "margin", "buying power"]):
            # Get account summary
            result = await self.execute_tool("get_account_summary", {})
            tool_results["account"] = result.result if result.success else result.error

        elif "watchlist" in query_lower:
            if "add" in query_lower and tickers:
                # Add to watchlist
                for ticker in tickers[:1]:
                    # Extract trigger info from query if present
                    trigger_type = "EVENT"
                    trigger_value = None
                    priority = "MEDIUM"

                    if "above" in query_lower:
                        trigger_type = "PRICE_ABOVE"
                    elif "below" in query_lower:
                        trigger_type = "PRICE_BELOW"

                    if "high" in query_lower:
                        priority = "HIGH"
                    elif "low" in query_lower:
                        priority = "LOW"

                    result = await self.execute_tool(
                        "add_to_watchlist",
                        {
                            "ticker": ticker,
                            "trigger_type": trigger_type,
                            "trigger_value": trigger_value,
                            "priority": priority,
                            "expires": "30d",
                        },
                    )
                    tool_results[f"add_watchlist_{ticker}"] = result.result if result.success else result.error
            else:
                # Get watchlist
                result = await self.execute_tool(
                    "get_watchlist",
                    {"status": "active"},
                )
                tool_results["watchlist"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["order", "pending", "open order"]):
            # Get open orders
            result = await self.execute_tool("get_open_orders", {})
            tool_results["open_orders"] = result.result if result.success else result.error

        elif "cancel" in query_lower:
            # Cancel order - would need order_id from context or query
            return AgentResponse(
                success=False,
                text="Please specify which order to cancel (order ID).",
                error="Need order ID",
            )

        else:
            # Default: show portfolio overview
            positions = await self.execute_tool("get_positions", {})
            pnl = await self.execute_tool("get_pnl", {})
            account = await self.execute_tool("get_account_summary", {})

            tool_results["positions"] = positions.result if positions.success else positions.error
            tool_results["pnl"] = pnl.result if pnl.success else pnl.error
            tool_results["account"] = account.result if account.success else account.error

        # Generate A2UI response
        if not tool_results:
            return AgentResponse(
                success=False,
                text="No portfolio data available.",
                error="No data",
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
            log.error("Failed to generate portfolio response", error=str(e))
            return AgentResponse(
                success=False,
                text=f"Portfolio data retrieved but failed to format: {e}",
                tool_results=tool_results,
                error=str(e),
            )
