"""Real-time order status streaming."""
import asyncio
import structlog
from typing import Set
from fastapi import WebSocket

log = structlog.get_logger(__name__)


class OrderStreamManager:
    """Manages real-time order status streaming to clients."""

    def __init__(self):
        self._subscribers: Set[WebSocket] = set()
        self._orders: dict[str, dict] = {}  # order_id -> order data
        self._running = False
        self._task: asyncio.Task | None = None

    async def subscribe(self, websocket: WebSocket):
        """Subscribe to order updates."""
        self._subscribers.add(websocket)
        log.debug("order_stream.subscribed")

        # Send current open orders immediately
        if self._orders:
            try:
                await websocket.send_json({
                    "type": "orders_snapshot",
                    "data": list(self._orders.values()),
                })
            except Exception:
                pass

    async def unsubscribe(self, websocket: WebSocket):
        """Unsubscribe from order updates."""
        self._subscribers.discard(websocket)

    async def start(self):
        """Start the order fetching loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info("order_stream.started")

    async def stop(self):
        """Stop the order streaming."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("order_stream.stopped")

    async def _run_loop(self):
        """Main order fetching loop."""
        while self._running:
            try:
                await self._fetch_and_broadcast()
            except Exception as e:
                log.error("order_stream.loop_error", error=str(e))
            await asyncio.sleep(2)  # 2-second interval

    async def _fetch_and_broadcast(self):
        """Fetch orders and broadcast changes to subscribers."""
        if not self._subscribers:
            return

        try:
            from ...agent.mcp_client import get_mcp_pool
            pool = await get_mcp_pool()

            # Fetch open orders
            result = await pool.call_ib_mcp("get_open_orders", {})

            if not result.success:
                return

            new_orders = {}
            for order in (result.result or []):
                order_id = str(order.get('order_id', order.get('id', '')))
                if order_id:
                    new_orders[order_id] = order

            # Detect changes
            added = []
            updated = []
            removed = []

            for order_id, order in new_orders.items():
                if order_id not in self._orders:
                    added.append(order)
                elif order != self._orders[order_id]:
                    updated.append(order)

            for order_id in self._orders:
                if order_id not in new_orders:
                    removed.append(self._orders[order_id])

            self._orders = new_orders

            # Broadcast changes
            if added or updated or removed:
                await self._broadcast_changes(added, updated, removed)

        except Exception as e:
            log.error("order_stream.fetch_failed", error=str(e))

    async def _broadcast_changes(self, added: list, updated: list, removed: list):
        """Broadcast order changes to all subscribers."""
        dead_sockets = set()

        message = {
            "type": "orders_update",
            "added": added,
            "updated": updated,
            "removed": removed,
        }

        for websocket in self._subscribers:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)

        # Clean up dead connections
        for ws in dead_sockets:
            self._subscribers.discard(ws)

    async def notify_order_event(self, event_type: str, order: dict):
        """Manually notify subscribers of an order event."""
        message = {
            "type": "order_event",
            "event": event_type,
            "order": order,
        }

        dead_sockets = set()
        for websocket in self._subscribers:
            try:
                await websocket.send_json(message)
            except Exception:
                dead_sockets.add(websocket)

        for ws in dead_sockets:
            self._subscribers.discard(ws)

    def get_open_orders(self) -> list[dict]:
        """Get current open orders."""
        return list(self._orders.values())

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)


# Singleton
_order_stream_manager: OrderStreamManager | None = None


def get_order_stream_manager() -> OrderStreamManager:
    global _order_stream_manager
    if _order_stream_manager is None:
        _order_stream_manager = OrderStreamManager()
    return _order_stream_manager
