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

    @staticmethod
    def _safe_number(value) -> float | None:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_string(value) -> str:
        if value is None:
            return ""
        return str(value)

    @staticmethod
    def _as_list(value) -> list:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            for key in ("positions", "items", "data", "result"):
                nested = value.get(key)
                if isinstance(nested, list):
                    return nested
        return []

    def _build_portfolio_fallback(self, tool_results: dict, formatting_error: str) -> dict:
        """Build deterministic portfolio response when LLM formatting is unavailable."""
        lines: list[str] = [
            "AI formatting is temporarily unavailable. Showing a direct portfolio summary.",
        ]

        pnl_data = tool_results.get("pnl")
        if isinstance(pnl_data, dict):
            total = self._safe_number(
                pnl_data.get("total_pnl")
                or pnl_data.get("totalPnL")
                or pnl_data.get("unrealized_pnl")
                or pnl_data.get("unrealizedPnL")
            )
            daily = self._safe_number(pnl_data.get("daily_pnl") or pnl_data.get("dailyPnL"))

            pnl_bits: list[str] = []
            if total is not None:
                pnl_bits.append(f"Total P&L: {total:,.2f}")
            if daily is not None:
                pnl_bits.append(f"Daily P&L: {daily:,.2f}")
            if pnl_bits:
                lines.append(" | ".join(pnl_bits))

        positions_data = tool_results.get("positions")
        positions = self._as_list(positions_data)
        if positions:
            lines.append(f"Open positions: {len(positions)}")
            for pos in positions[:8]:
                if not isinstance(pos, dict):
                    continue
                ticker = self._safe_string(pos.get("ticker") or pos.get("symbol") or pos.get("contract")) or "UNKNOWN"
                qty = pos.get("position") or pos.get("quantity") or pos.get("qty") or pos.get("size")
                current_price = self._safe_number(pos.get("current_price") or pos.get("marketPrice") or pos.get("last_price"))
                unrealized = self._safe_number(pos.get("unrealized_pnl") or pos.get("unrealizedPnL") or pos.get("pnl"))

                row_bits = [ticker]
                if qty is not None:
                    row_bits.append(f"qty {qty}")
                if current_price is not None:
                    row_bits.append(f"px {current_price:,.2f}")
                if unrealized is not None:
                    row_bits.append(f"uPnL {unrealized:,.2f}")
                lines.append("- " + ", ".join(row_bits))
        elif "positions" in tool_results:
            lines.append("Open positions: none")

        account_data = tool_results.get("account")
        if isinstance(account_data, dict):
            net_liq = self._safe_number(account_data.get("net_liquidation") or account_data.get("netLiquidation"))
            buying_power = self._safe_number(account_data.get("buying_power") or account_data.get("buyingPower"))
            account_bits: list[str] = []
            if net_liq is not None:
                account_bits.append(f"Net liq: {net_liq:,.2f}")
            if buying_power is not None:
                account_bits.append(f"Buying power: {buying_power:,.2f}")
            if account_bits:
                lines.append(" | ".join(account_bits))

        if len(lines) == 1:
            lines.append("Portfolio data was retrieved, but no structured fields were available to render.")

        lines.append(f"Formatting error: {formatting_error}")

        text = "\n".join(lines)
        return {
            "type": "a2ui",
            "text": text,
            "components": [
                {
                    "type": "TextCard",
                    "props": {
                        "title": "Portfolio Summary (Fallback)",
                        "content": text,
                    },
                }
            ],
        }

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
            fallback_a2ui = self._build_portfolio_fallback(tool_results, str(e))
            return AgentResponse(
                success=True,
                text=fallback_a2ui.get("text", ""),
                a2ui=fallback_a2ui,
                tool_results=tool_results,
            )
