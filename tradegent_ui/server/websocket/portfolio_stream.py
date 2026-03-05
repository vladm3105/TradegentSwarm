"""Real-time portfolio P&L streaming."""
import asyncio
import structlog
from typing import Set
from decimal import Decimal
from fastapi import WebSocket

from ..services.circuit_breaker import get_circuit_breaker

log = structlog.get_logger(__name__)


class PortfolioStreamManager:
    """Manages real-time portfolio streaming to clients."""

    def __init__(self):
        self._subscribers: Set[WebSocket] = set()
        self._last_portfolio: dict = {}
        self._running = False
        self._task: asyncio.Task | None = None

    async def subscribe(self, websocket: WebSocket):
        """Subscribe to portfolio updates."""
        self._subscribers.add(websocket)
        log.debug("portfolio_stream.subscribed")

        # Send last known state immediately
        if self._last_portfolio:
            try:
                await websocket.send_json({
                    "type": "portfolio_update",
                    "data": self._last_portfolio,
                })
            except Exception:
                pass

    async def unsubscribe(self, websocket: WebSocket):
        """Unsubscribe from portfolio updates."""
        self._subscribers.discard(websocket)

    async def start(self):
        """Start the portfolio fetching loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("portfolio_stream.started")

    async def stop(self):
        """Stop the portfolio streaming."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("portfolio_stream.stopped")

    async def _run_loop(self):
        """Main portfolio fetching loop."""
        while self._running:
            try:
                await self._fetch_and_broadcast()
            except Exception as e:
                log.error("portfolio_stream.loop_error", error=str(e))
            await asyncio.sleep(5)  # 5-second interval

    async def _fetch_and_broadcast(self):
        """Fetch portfolio and broadcast to subscribers."""
        if not self._subscribers:
            return

        try:
            from ...agent.mcp_client import get_mcp_pool
            pool = await get_mcp_pool()

            # Fetch positions and P&L
            positions_result = await pool.call_ib_mcp("get_positions", {})
            pnl_result = await pool.call_ib_mcp("get_pnl", {})

            positions = positions_result.result if positions_result.success else []
            pnl = pnl_result.result if pnl_result.success else {}

            import time
            portfolio_data = {
                "positions": positions,
                "pnl": pnl,
                "timestamp": time.time(),
            }

            self._last_portfolio = portfolio_data

            # Check circuit breaker
            if pnl and isinstance(pnl, dict) and 'daily_pnl' in pnl:
                cb = get_circuit_breaker()
                await cb.check(Decimal(str(pnl['daily_pnl'])))

            await self._broadcast(portfolio_data)

        except Exception as e:
            log.error("portfolio_stream.fetch_failed", error=str(e))

    async def _broadcast(self, portfolio_data: dict):
        """Broadcast portfolio update to all subscribers."""
        dead_sockets = set()

        message = {
            "type": "portfolio_update",
            "data": portfolio_data,
        }

        for websocket in self._subscribers:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)

        # Clean up dead connections
        for ws in dead_sockets:
            self._subscribers.discard(ws)

    def get_last_portfolio(self) -> dict:
        """Get the last known portfolio state."""
        return self._last_portfolio

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)


# Singleton
_portfolio_stream_manager: PortfolioStreamManager | None = None


def get_portfolio_stream_manager() -> PortfolioStreamManager:
    global _portfolio_stream_manager
    if _portfolio_stream_manager is None:
        _portfolio_stream_manager = PortfolioStreamManager()
    return _portfolio_stream_manager
