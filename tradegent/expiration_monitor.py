"""
Expiration Monitor - Track and handle options approaching/at expiration.

Integrated into service.py tick loop. Checks for:
- Options expiring soon (warning)
- Options expiring today (action required)
- Options already expired (auto-close)
"""

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from options_utils import is_itm

if TYPE_CHECKING:
    from db_layer import NexusDB
    from position_monitor import IBPosition
    from notifications import NotificationRouter

log = logging.getLogger("tradegent.expiration-monitor")


class ExpirationMonitor:
    """Monitor options approaching expiration."""

    def __init__(self, db: "NexusDB", notifier: "NotificationRouter | None" = None):
        self.db = db
        self.notifier = notifier
        self._settings = {}
        self._refresh_settings()

    def _refresh_settings(self):
        self._settings = {
            "warning_days": int(self.db.get_setting("options_expiry_warning_days", 7)),
            "critical_days": int(self.db.get_setting("options_expiry_critical_days", 3)),
            "auto_close": self.db.get_setting("auto_close_expired_options", True),
        }

    def get_expiring_soon(self, days: int | None = None) -> list[dict]:
        """Get options expiring within N days."""
        if days is None:
            days = self._settings["warning_days"]

        with self.db.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.v_options_positions
                WHERE days_to_expiry <= %s AND days_to_expiry >= 0
                ORDER BY option_expiration ASC
            """, [days])
            return [dict(r) for r in cur.fetchall()]

    def get_critical(self) -> list[dict]:
        """Get options in critical expiration window."""
        return self.get_expiring_soon(self._settings["critical_days"])

    def get_expired(self) -> list[dict]:
        """Get options that have expired but not closed."""
        with self.db.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.v_options_positions
                WHERE days_to_expiry < 0
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_expiring_today(self) -> list[dict]:
        """Get options expiring today."""
        with self.db.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.v_options_positions
                WHERE option_expiration = CURRENT_DATE
            """)
            return [dict(r) for r in cur.fetchall()]

    def process_expirations(self, get_stock_price_fn=None) -> dict:
        """
        Process expired options: auto-close with appropriate action.

        Args:
            get_stock_price_fn: Optional function to get stock price for ITM detection.
                                Signature: (ticker: str) -> float | None

        Returns:
            Dict with counts: {expired_worthless: N, needs_review: N, errors: N}
        """
        results = {"expired_worthless": 0, "needs_review": 0, "errors": 0}

        if not self._settings["auto_close"]:
            log.info("Auto-close expired options disabled")
            return results

        expired = self.get_expired()

        for opt in expired:
            try:
                trade_id = opt["id"]
                ticker = opt["option_underlying"]

                # Check if option was ITM at expiration (needs manual review)
                needs_review = False

                if get_stock_price_fn:
                    stock_price = get_stock_price_fn(ticker)
                    if stock_price:
                        was_itm = is_itm(
                            opt["option_type"],
                            float(opt["option_strike"]),
                            stock_price
                        )
                        if was_itm:
                            needs_review = True
                            log.warning(f"Expired option {trade_id} was ITM - queuing for review")
                else:
                    # Fallback: if entry_price > $0.50, might have been ITM
                    if opt.get("entry_price", 0) > 0.50:
                        needs_review = True

                if needs_review:
                    self.db.queue_task(
                        task_type="review_expired_option",
                        ticker=ticker,
                        prompt=f"Option {opt['full_symbol']} expired - verify if exercised/assigned",
                        priority=7
                    )
                    results["needs_review"] += 1
                    continue

                # Close as expired worthless
                self.db.close_expired_option_worthless(trade_id)
                results["expired_worthless"] += 1
                log.info(f"Closed trade {trade_id} as expired worthless")

                # Send notification
                if self.notifier:
                    from notifications import Notification, NotificationPriority
                    self.notifier.notify(Notification(
                        event_type="option_expired",
                        title=f"{ticker} Option Expired",
                        message=f"{opt.get('full_symbol', ticker)} expired worthless",
                        priority=NotificationPriority.MEDIUM,
                        ticker=ticker,
                        data={"trade_id": trade_id, "full_symbol": opt.get("full_symbol")}
                    ))

            except Exception as e:
                log.error(f"Error processing expired option {opt.get('id')}: {e}")
                results["errors"] += 1

        return results

    def send_expiration_warnings(self) -> int:
        """
        Send notifications for options expiring soon.

        Returns count of warnings sent.
        """
        if not self.notifier:
            return 0

        from notifications import Notification, NotificationPriority

        warnings_sent = 0
        critical = self.get_critical()

        for opt in critical:
            ticker = opt.get("option_underlying", opt.get("ticker"))
            days_left = opt.get("days_to_expiry", 0)
            full_symbol = opt.get("full_symbol", "")

            self.notifier.notify(Notification(
                event_type="options_expiring",
                title=f"{ticker} Option Expiring",
                message=f"{full_symbol} expires in {days_left} days",
                priority=NotificationPriority.MEDIUM if days_left > 1 else NotificationPriority.HIGH,
                ticker=ticker,
                data={
                    "days_left": days_left,
                    "full_symbol": full_symbol,
                    "expiration": str(opt.get("option_expiration")),
                    "strike": opt.get("option_strike"),
                    "option_type": opt.get("option_type")
                }
            ))
            warnings_sent += 1

        return warnings_sent

    def check_for_assignment(self, underlying: str, ib_positions: list["IBPosition"]) -> list[dict]:
        """
        Check if short options were assigned by looking for unexpected stock position.

        When a short put is assigned, the option disappears and stock appears.
        When a short call is assigned, the option disappears and stock decreases.

        Returns list of potential assignment events for review.
        """
        assignments = []

        # Get open short options for this underlying
        short_options = self.db.get_short_options_by_underlying(underlying)

        if not short_options:
            return assignments

        # Get current stock position from IB
        stock_positions = [p for p in ib_positions if p.symbol == underlying and not p.is_option]
        stock_qty = sum(p.position for p in stock_positions)

        for opt in short_options:
            contracts = opt.get("current_size") or opt.get("entry_size") or 0
            shares_per_contract = opt.get("option_multiplier", 100)
            expected_shares = contracts * shares_per_contract

            if opt["option_type"] == "put":
                # Short put assignment = we bought stock at strike
                # Check if we have unexpected long stock position
                if stock_qty >= expected_shares * 0.9:  # 90% threshold for partial
                    log.warning(f"Possible put assignment: {opt['full_symbol']} -> {underlying} +{expected_shares} shares")
                    assignments.append({
                        "type": "put_assignment",
                        "option_trade_id": opt["id"],
                        "full_symbol": opt["full_symbol"],
                        "underlying": underlying,
                        "expected_shares": expected_shares,
                        "actual_shares": stock_qty,
                        "strike": opt["option_strike"],
                    })

            elif opt["option_type"] == "call":
                # Short call assignment = our stock was called away
                # Harder to detect without knowing previous stock position
                # Queue for review if option disappeared but we have the data
                log.info(f"Checking for call assignment on {opt['full_symbol']}")
                # Note: Full implementation would compare against previous tick's stock position

        # Queue tasks for detected assignments
        for assignment in assignments:
            self.db.queue_task(
                task_type="review_assignment",
                ticker=assignment["underlying"],
                prompt=f"{assignment['type']}: {assignment['full_symbol']} may have been assigned - verify positions",
                priority=8
            )

        return assignments

    def get_summary(self) -> dict:
        """Get summary of options status."""
        return {
            "expiring_today": len(self.get_expiring_today()),
            "critical": len(self.get_critical()),
            "warning": len(self.get_expiring_soon()),
            "expired": len(self.get_expired()),
        }
