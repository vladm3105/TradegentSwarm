"""Real-time price streaming via WebSocket.

Unified Messages Pattern:
This module handles the /ws/stream endpoint which uses the TradegentMessage envelope.

Protocol:
1. Client sends TradegentSubscription:
   {
     "type": "subscription",
     "action": "subscribe_prices",
     "request_id": "uuid",
     "payload": {"tickers": ["NVDA", "AAPL"]},
     "timestamp": 1694520000000
   }

2. Server responds with TradegentEvent messages:
   {
     "type": "event",
     "action": "subscribe_prices",
     "request_id": "uuid",  // Same as subscription
     "payload": {"ticker": "NVDA", "bid": 950.25, "ask": 950.30},
     "timestamp": 1694520001000
   }

See docs/architecture/UNIFIED_MESSAGES.md for full protocol specification.
"""
import asyncio
import structlog
from typing import Set
from fastapi import WebSocket

log = structlog.get_logger(__name__)


class PriceStreamManager:
    """Manages real-time price streaming to clients."""

    def __init__(self):
        self._subscriptions: dict[str, Set[WebSocket]] = {}  # ticker -> websockets
        self._prices: dict[str, dict] = {}  # ticker -> latest price data
        self._running = False
        self._task: asyncio.Task | None = None

    async def subscribe(self, websocket: WebSocket, tickers: list[str]):
        """Subscribe a websocket to price updates for tickers."""
        for ticker in tickers:
            if ticker not in self._subscriptions:
                self._subscriptions[ticker] = set()
            self._subscriptions[ticker].add(websocket)
            log.debug("price_stream.subscribed", ticker=ticker)

    async def unsubscribe(self, websocket: WebSocket, tickers: list[str] | None = None):
        """Unsubscribe a websocket from price updates."""
        if tickers is None:
            # Unsubscribe from all
            for ticker_subs in self._subscriptions.values():
                ticker_subs.discard(websocket)
        else:
            for ticker in tickers:
                if ticker in self._subscriptions:
                    self._subscriptions[ticker].discard(websocket)

    async def start(self):
        """Start the price fetching loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("price_stream.started")

    async def stop(self):
        """Stop the price streaming."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("price_stream.stopped")

    async def _run_loop(self):
        """Main price fetching loop."""
        while self._running:
            try:
                await self._fetch_and_broadcast()
            except Exception as e:
                log.error("price_stream.loop_error", error=str(e))
            await asyncio.sleep(1)  # 1-second interval

    async def _fetch_and_broadcast(self):
        """Fetch prices and broadcast to subscribers."""
        if not self._subscriptions:
            return

        tickers = list(self._subscriptions.keys())
        if not tickers:
            return

        try:
            from ...agent.mcp_client import get_mcp_pool
            pool = await get_mcp_pool()

            # Batch fetch prices
            for ticker in tickers:
                if ticker not in self._subscriptions or not self._subscriptions[ticker]:
                    continue

                try:
                    result = await pool.call_ib_mcp(
                        "get_stock_price",
                        {"symbol": ticker}
                    )
                    if result.success and result.result:
                        self._prices[ticker] = result.result
                        await self._broadcast_price(ticker, result.result)
                except Exception as e:
                    log.warning("price_stream.fetch_failed", ticker=ticker, error=str(e))

        except Exception as e:
            log.error("price_stream.batch_failed", error=str(e))

    async def _broadcast_price(self, ticker: str, price_data: dict):
        """Broadcast price update to all subscribers."""
        subscribers = self._subscriptions.get(ticker, set())
        dead_sockets = set()

        message = {
            "type": "price_update",
            "ticker": ticker,
            "data": price_data,
        }

        for websocket in subscribers:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)

        # Clean up dead connections
        for ws in dead_sockets:
            self._subscriptions[ticker].discard(ws)

    def get_latest_price(self, ticker: str) -> dict | None:
        """Get the latest cached price for a ticker."""
        return self._prices.get(ticker)

    @property
    def subscriber_count(self) -> int:
        """Total number of active subscriptions."""
        return sum(len(subs) for subs in self._subscriptions.values())


# Singleton
_price_stream_manager: PriceStreamManager | None = None


def get_price_stream_manager() -> PriceStreamManager:
    global _price_stream_manager
    if _price_stream_manager is None:
        _price_stream_manager = PriceStreamManager()
    return _price_stream_manager
