"""
Order Reconciler - Polls IB for order status updates.

Tracks pending orders and updates trade status when filled/cancelled.
Uses direct IB client (not Claude Code) to avoid API costs.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db_layer import NexusDB
    from ib_client import IBClient
    from notifications import NotificationRouter

log = logging.getLogger("tradegent.order-reconciler")


class OrderReconciler:
    """
    Reconciles pending orders with IB order status.

    Workflow:
    1. Get trades with pending orders from DB
    2. Query IB for each order's status
    3. Update trade with fill info when order completes
    """

    def __init__(self, db: "NexusDB", ib_client: "IBClient", notifier: "NotificationRouter | None" = None):
        self.db = db
        self.ib = ib_client
        self.notifier = notifier

    def reconcile_pending_orders(self) -> dict:
        """
        Check and update all pending orders.

        Returns:
            Dict with counts: {filled: N, partial: N, cancelled: N, pending: N, errors: N}
        """
        results = {"filled": 0, "partial": 0, "cancelled": 0, "pending": 0, "errors": 0}

        pending_trades = self.db.get_trades_with_pending_orders()
        if not pending_trades:
            return results

        log.info(f"Reconciling {len(pending_trades)} pending orders")

        for trade in pending_trades:
            order_id = trade["order_id"]
            if not order_id:
                continue

            try:
                status = self.ib.get_order_status(order_id)
                if status is None:
                    results["errors"] += 1
                    continue

                ib_status = (status.get("status") or "").upper()

                if ib_status in ("FILLED", "FILL"):
                    self._handle_filled(trade, status)
                    results["filled"] += 1
                elif ib_status in ("PARTIALLYFILLED", "PARTIALFILL", "PARTIAL"):
                    self._handle_partial_fill(trade, status)
                    results["partial"] += 1
                elif ib_status in ("CANCELLED", "CANCELED", "CANCEL"):
                    self._handle_cancelled(trade, status)
                    results["cancelled"] += 1
                elif ib_status in ("SUBMITTED", "PRESUBMITTED", "PENDINGSUBMIT"):
                    results["pending"] += 1
                elif ib_status in ("INACTIVE", "ERROR"):
                    self._handle_error(trade, status)
                    results["errors"] += 1
                else:
                    log.debug(f"Order {order_id}: {ib_status}")
                    results["pending"] += 1

            except Exception as e:
                log.error(f"Error reconciling order {order_id}: {e}")
                results["errors"] += 1

        return results

    def _handle_filled(self, trade: dict, status: dict):
        """Handle filled order."""
        order_id = trade["order_id"]
        avg_fill = status.get("avgFillPrice") or status.get("avg_fill_price") or status.get("avgPrice")
        filled_qty = status.get("filled") or status.get("filledQuantity") or status.get("cumQty")
        ticker = trade["ticker"]

        log.info(f"Order {order_id} FILLED: {filled_qty} @ ${avg_fill}")

        # Update trade with fill info
        self.db.update_trade_order(
            trade["id"],
            order_id,
            "Filled",
            avg_fill_price=float(avg_fill) if avg_fill else None
        )

        # Update entry price to actual fill price
        if avg_fill:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    UPDATE nexus.trades
                    SET entry_price = %s,
                        current_size = COALESCE(current_size, entry_size),
                        updated_at = now()
                    WHERE id = %s
                """, [float(avg_fill), trade["id"]])
            self.db.conn.commit()

        # Send notification
        if self.notifier:
            from notifications import Notification, NotificationPriority
            self.notifier.notify(Notification(
                event_type="order_filled",
                title=f"Order {order_id} Filled",
                message=f"Filled: {filled_qty} {ticker} @ ${avg_fill}",
                priority=NotificationPriority.HIGH,
                ticker=ticker,
                data={"order_id": order_id, "filled_qty": filled_qty, "avg_fill": float(avg_fill) if avg_fill else None}
            ))

        # Queue fill analysis if enabled
        if self.db.cfg._get("fill_analysis_enabled", "skills", "true").lower() == "true":
            self.db.queue_task(
                task_type="fill_analysis",
                ticker=ticker,
                prompt=f"Analyze fill for order {order_id}",
                priority=5,
                cooldown_key=f"fill_analysis:{order_id}",
                cooldown_hours=24
            )

    def _handle_partial_fill(self, trade: dict, status: dict):
        """Handle partially filled order."""
        import json

        order_id = trade["order_id"]
        filled_qty = float(status.get("filled") or status.get("filledQuantity") or 0)
        avg_fill = status.get("avgFillPrice") or status.get("avg_fill_price")

        log.info(f"Order {order_id} PARTIAL FILL: {filled_qty} filled")

        # Update with partial fill info
        partial_fill = {
            "time": datetime.now().isoformat(),
            "filled": filled_qty,
            "price": float(avg_fill) if avg_fill else None,
        }

        # Get existing partial fills
        existing = trade.get("partial_fills") or []
        if isinstance(existing, str):
            existing = json.loads(existing)
        existing.append(partial_fill)

        self.db.update_trade_order(
            trade["id"],
            order_id,
            "PartialFilled",
            partial_fills=existing,
            avg_fill_price=float(avg_fill) if avg_fill else None
        )

        # Update current_size to reflect filled portion
        if filled_qty > 0:
            with self.db.conn.cursor() as cur:
                cur.execute("""
                    UPDATE nexus.trades
                    SET current_size = %s, updated_at = now()
                    WHERE id = %s
                """, [filled_qty, trade["id"]])
            self.db.conn.commit()

    def _handle_cancelled(self, trade: dict, status: dict):
        """Handle cancelled order."""
        order_id = trade["order_id"]
        ticker = trade["ticker"]
        log.info(f"Order {order_id} CANCELLED")

        self.db.update_trade_order(trade["id"], order_id, "Cancelled")

        # Close the trade as cancelled (P&L = 0)
        with self.db.conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.trades
                SET status = 'closed',
                    exit_reason = 'order_cancelled',
                    exit_date = now(),
                    pnl_dollars = 0,
                    pnl_pct = 0,
                    updated_at = now()
                WHERE id = %s
            """, [trade["id"]])
        self.db.conn.commit()

        # Update stock position
        self.db.update_stock_position(ticker, False, "none")

        # Send notification
        if self.notifier:
            from notifications import Notification, NotificationPriority
            self.notifier.notify(Notification(
                event_type="order_cancelled",
                title=f"Order {order_id} Cancelled",
                message=f"Order for {ticker} was cancelled",
                priority=NotificationPriority.MEDIUM,
                ticker=ticker,
                data={"order_id": order_id}
            ))

    def _handle_error(self, trade: dict, status: dict):
        """Handle order error."""
        order_id = trade["order_id"]
        error_msg = status.get("message") or status.get("error") or "Unknown error"
        log.warning(f"Order {order_id} ERROR: {error_msg}")

        self.db.update_trade_order(trade["id"], order_id, "Error")
