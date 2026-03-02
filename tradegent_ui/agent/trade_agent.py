"""Trade agent for trade journaling and order execution."""
import re
import structlog

from .base_agent import BaseAgent, AgentResponse
from .context_manager import ConversationContext

log = structlog.get_logger()


class TradeAgent(BaseAgent):
    """Agent for trade operations.

    Capabilities:
    - Journal trade entries/exits
    - Execute orders via IB
    - Review trades
    - Analyze fill quality
    """

    def __init__(self):
        super().__init__("trade")

    async def process(
        self,
        query: str,
        tickers: list[str],
        context: ConversationContext,
    ) -> AgentResponse:
        """Process a trade-related query.

        Args:
            query: User query
            tickers: Extracted tickers
            context: Conversation context

        Returns:
            AgentResponse with trade results
        """
        query_lower = query.lower()
        tool_results = {}

        # Extract trade details from query
        trade_info = self._extract_trade_info(query)

        if any(word in query_lower for word in ["bought", "entered", "long", "buy"]):
            # Journal entry
            if not tickers:
                return AgentResponse(
                    success=False,
                    text="Please specify which stock you bought.",
                    error="No ticker specified",
                )

            ticker = tickers[0]
            entry_price = trade_info.get("price")
            size = trade_info.get("size", 100)

            if not entry_price:
                return AgentResponse(
                    success=False,
                    text=f"What price did you enter {ticker} at?",
                    error="No entry price",
                )

            result = await self.execute_tool(
                "journal_entry",
                {
                    "ticker": ticker,
                    "direction": "LONG",
                    "entry_price": entry_price,
                    "size": size,
                    "stop_loss": trade_info.get("stop"),
                    "target": trade_info.get("target"),
                },
            )
            tool_results[f"entry_{ticker}"] = result.result if result.success else result.error

        elif any(word in query_lower for word in ["sold", "exited", "closed", "sell"]):
            # Journal exit or place sell order
            if not tickers:
                return AgentResponse(
                    success=False,
                    text="Please specify which stock you sold.",
                    error="No ticker specified",
                )

            ticker = tickers[0]
            exit_price = trade_info.get("price")

            if exit_price:
                # Journal exit
                result = await self.execute_tool(
                    "journal_exit",
                    {
                        "ticker": ticker,
                        "exit_price": exit_price,
                        "exit_reason": trade_info.get("reason", "manual"),
                    },
                )
                tool_results[f"exit_{ticker}"] = result.result if result.success else result.error
            else:
                return AgentResponse(
                    success=False,
                    text=f"What price did you exit {ticker} at?",
                    error="No exit price",
                )

        elif any(word in query_lower for word in ["short", "shorted"]):
            # Short entry
            if not tickers:
                return AgentResponse(
                    success=False,
                    text="Please specify which stock you shorted.",
                    error="No ticker specified",
                )

            ticker = tickers[0]
            entry_price = trade_info.get("price")
            size = trade_info.get("size", 100)

            if not entry_price:
                return AgentResponse(
                    success=False,
                    text=f"What price did you short {ticker} at?",
                    error="No entry price",
                )

            result = await self.execute_tool(
                "journal_entry",
                {
                    "ticker": ticker,
                    "direction": "SHORT",
                    "entry_price": entry_price,
                    "size": size,
                    "stop_loss": trade_info.get("stop"),
                    "target": trade_info.get("target"),
                },
            )
            tool_results[f"entry_{ticker}"] = result.result if result.success else result.error

        elif "execute" in query_lower or "place order" in query_lower:
            # Execute order via IB
            if not tickers:
                return AgentResponse(
                    success=False,
                    text="Please specify the ticker for the order.",
                    error="No ticker specified",
                )

            ticker = tickers[0]
            action = "BUY" if "buy" in query_lower else "SELL"
            quantity = trade_info.get("size", 100)
            order_type = "LMT" if trade_info.get("price") else "MKT"
            limit_price = trade_info.get("price")

            result = await self.execute_tool(
                "execute_order",
                {
                    "ticker": ticker,
                    "action": action,
                    "quantity": quantity,
                    "order_type": order_type,
                    "limit_price": limit_price,
                },
            )
            tool_results[f"order_{ticker}"] = result.result if result.success else result.error

        elif "review" in query_lower:
            # Review trade
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "review_trade",
                        {"ticker": ticker, "query": "trade review lessons"},
                    )
                    tool_results[f"review_{ticker}"] = result.result if result.success else result.error
            else:
                result = await self.execute_tool(
                    "review_trade",
                    {"query": "recent trade reviews lessons"},
                )
                tool_results["recent_reviews"] = result.result if result.success else result.error

        elif "fill" in query_lower:
            # Analyze fills
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "analyze_fill",
                        {"ticker": ticker},
                    )
                    tool_results[f"fill_{ticker}"] = result.result if result.success else result.error
            else:
                return AgentResponse(
                    success=False,
                    text="Please specify which ticker to analyze fills for.",
                    error="No ticker specified",
                )

        else:
            # Get trade details
            if tickers:
                for ticker in tickers[:1]:
                    result = await self.execute_tool(
                        "get_trade",
                        {"ticker": ticker},
                    )
                    tool_results[f"trade_{ticker}"] = result.result if result.success else result.error
            else:
                return AgentResponse(
                    success=True,
                    text="What would you like to do? I can help you journal trades, execute orders, or review past trades.",
                    a2ui={
                        "type": "a2ui",
                        "text": "What would you like to do? I can help you journal trades, execute orders, or review past trades.",
                        "components": [],
                    },
                )

        # Generate A2UI response
        if not tool_results:
            return AgentResponse(
                success=False,
                text="No trade action taken.",
                error="No action",
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
            log.error("Failed to generate trade response", error=str(e))
            return AgentResponse(
                success=False,
                text=f"Trade action completed but failed to format: {e}",
                tool_results=tool_results,
                error=str(e),
            )

    def _extract_trade_info(self, query: str) -> dict:
        """Extract trade details from query.

        Args:
            query: User query

        Returns:
            Dict with price, size, stop, target if found
        """
        info = {}

        # Extract price (at $X, @ X, price X)
        price_patterns = [
            r"at\s*\$?(\d+\.?\d*)",
            r"@\s*\$?(\d+\.?\d*)",
            r"price\s*\$?(\d+\.?\d*)",
            r"\$(\d+\.?\d*)",
        ]
        for pattern in price_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info["price"] = float(match.group(1))
                break

        # Extract size (X shares, qty X)
        size_patterns = [
            r"(\d+)\s*shares",
            r"qty\s*(\d+)",
            r"quantity\s*(\d+)",
            r"(\d+)\s*units",
        ]
        for pattern in size_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info["size"] = int(match.group(1))
                break

        # Extract stop loss
        stop_patterns = [
            r"stop\s*(?:loss)?\s*(?:at)?\s*\$?(\d+\.?\d*)",
            r"sl\s*\$?(\d+\.?\d*)",
        ]
        for pattern in stop_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info["stop"] = float(match.group(1))
                break

        # Extract target
        target_patterns = [
            r"target\s*(?:at)?\s*\$?(\d+\.?\d*)",
            r"tp\s*\$?(\d+\.?\d*)",
            r"take\s*profit\s*(?:at)?\s*\$?(\d+\.?\d*)",
        ]
        for pattern in target_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                info["target"] = float(match.group(1))
                break

        return info
