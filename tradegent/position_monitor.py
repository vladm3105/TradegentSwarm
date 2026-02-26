"""
Position Monitor - Detects IB position changes and triggers trade closes.

Integrated into service.py tick loop. Compares IB positions vs nexus.trades
to detect when positions are closed externally (stop hit, manual close, etc.)

Key features:
- Handles multiple trades per ticker
- Supports long and short positions
- Full options support with OCC symbol parsing (v3 - IPLAN-006)
- Gets actual exit prices from IB
- Uses direct IB client (not Claude Code) to avoid API costs
- Detects position increases from external sources (v2 - IPLAN-005)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable

from options_utils import ParsedOptionSymbol, parse_option_symbol

if TYPE_CHECKING:
    from db_layer import NexusDB
    from ib_client import IBClient
    from notifications import NotificationRouter

log = logging.getLogger("tradegent.position-monitor")


@dataclass
class PositionDelta:
    """Represents a change in position state."""
    ticker: str
    trade_id: int  # 0 if no existing trade
    action: str  # 'closed', 'partial', 'increase', 'opened'
    db_size: Decimal
    ib_size: Decimal
    direction: str = "long"  # 'long' or 'short'
    ib_avg_cost: Decimal | None = None
    last_price: Decimal | None = None  # For accurate exit/entry price
    detected_at: datetime = field(default_factory=datetime.now)
    # NEW: Store IBPosition reference for options support
    ib_position: "IBPosition | None" = None

    @property
    def size_difference(self) -> Decimal:
        """Get the absolute size difference, rounded to IB precision."""
        diff = abs(self.ib_size - self.db_size)
        return diff.quantize(Decimal("0.0001"))

    @property
    def is_new_position(self) -> bool:
        """Check if this is a completely new position (no prior DB record)."""
        return self.db_size == Decimal("0") and self.ib_size > Decimal("0")

    @property
    def is_option(self) -> bool:
        """Check if this delta is for an option position."""
        return self.ib_position is not None and self.ib_position.is_option

    @property
    def full_symbol(self) -> str:
        """Get full symbol (OCC for options, ticker for stocks)."""
        if self.ib_position and self.ib_position.option_data:
            return self.ib_position.option_data.raw_symbol
        return self.ticker


@dataclass
class IBPosition:
    """Normalized IB position with options support."""
    symbol: str           # Base symbol (e.g., "NVDA")
    raw_symbol: str       # Original symbol from IB
    position: float       # Signed quantity (negative = short)
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    is_option: bool = False
    option_data: ParsedOptionSymbol | None = None

    @property
    def display_symbol(self) -> str:
        """Return display name (option short name or stock ticker)."""
        if self.option_data:
            return self.option_data.short_name
        return self.symbol

    @property
    def multiplier(self) -> int:
        """Return contract multiplier (100 for options, 1 for stocks)."""
        if self.option_data:
            return self.option_data.multiplier
        return 1


def normalize_ib_symbol(raw_symbol: str) -> str:
    """
    Normalize IB symbol to base ticker.

    IB formats:
    - Stock: "NVDA"
    - Option: "NVDA  240315C00500000" or "NVDA 240315C00500000"

    Returns base ticker (e.g., "NVDA")
    """
    if not raw_symbol:
        return ""
    parts = raw_symbol.split()
    if parts:
        return parts[0].upper()
    return ""  # Whitespace-only input


def parse_ib_positions(raw_positions: list[dict]) -> list[IBPosition]:
    """
    Parse raw IB MCP response into normalized positions with full options support.

    Handles different field naming conventions from IB MCP.
    Options are parsed to extract underlying, expiration, strike, and type.
    """
    positions = []

    for p in raw_positions:
        # Handle different field names from IB MCP
        raw_symbol = p.get("symbol") or p.get("contract", {}).get("symbol", "")
        position_qty = float(p.get("position") or p.get("pos") or p.get("quantity") or 0)

        if abs(position_qty) < 0.001:
            continue  # Skip zero positions

        # Try to parse as option first
        option_data = parse_option_symbol(raw_symbol)
        is_option = option_data is not None

        # Use underlying for options, normalized symbol for stocks
        if option_data:
            base_symbol = option_data.underlying
        else:
            base_symbol = normalize_ib_symbol(raw_symbol)

        positions.append(IBPosition(
            symbol=base_symbol,
            raw_symbol=raw_symbol,
            position=position_qty,
            avg_cost=float(p.get("avgCost") or p.get("avg_cost") or p.get("averageCost") or 0),
            market_value=float(p.get("marketValue") or p.get("market_value") or 0),
            unrealized_pnl=float(p.get("unrealizedPnl") or p.get("unrealized_pnl") or p.get("unrealizedPNL") or 0),
            is_option=is_option,
            option_data=option_data,
        ))

    return positions


class PositionMonitor:
    """
    Monitors IB positions vs DB trades and detects closures and increases.

    Workflow:
    1. Get open trades from nexus.trades (status='open')
    2. Get current positions from IB MCP (get_positions)
    3. Compare: detect closes, partial closes, and size changes
    4. Auto-close trades in DB and trigger post-trade review
    5. Auto-create trades for detected position increases (v2)
    """

    def __init__(self, db: "NexusDB", ib_client: "IBClient", notifier: "NotificationRouter | None" = None):
        self.db = db
        self.ib = ib_client
        self.notifier = notifier
        self._last_check: datetime | None = None
        self._settings: dict = {}
        self._refresh_settings()

    def _refresh_settings(self):
        """Refresh settings from database."""
        self._settings = {
            "auto_track_position_increases": self.db.get_setting("auto_track_position_increases", True),
            "position_detect_min_value": float(self.db.get_setting("position_detect_min_value", 100)),
        }

    def _get_pending_order_tickers(self) -> set[str]:
        """Get tickers that have pending orchestrator orders."""
        trades = self.db.get_trades_with_pending_orders()
        return {t["ticker"] for t in trades}

    def check_positions(self) -> list[PositionDelta]:
        """
        Compare DB trades vs IB positions.

        Returns:
            List of position deltas requiring action
        """
        deltas = []

        # Get all open trades from DB (may have multiple per ticker)
        open_trades = self.db.get_all_open_trades()

        # Get tickers with pending orchestrator orders (skip these for increases)
        pending_tickers = self._get_pending_order_tickers()

        # Get IB positions directly (no Claude Code cost!)
        raw_positions = self.ib.get_positions()
        if raw_positions is None:
            log.warning("Failed to get IB positions")
            return deltas

        # Parse and normalize IB positions
        ib_parsed = parse_ib_positions(raw_positions)

        # Build lookup: ticker -> total IB position (sum if multiple)
        ib_by_ticker: dict[str, IBPosition] = {}
        for pos in ib_parsed:
            if pos.symbol in ib_by_ticker:
                existing = ib_by_ticker[pos.symbol]
                existing.position += pos.position
                existing.market_value += pos.market_value
            else:
                ib_by_ticker[pos.symbol] = pos

        # Group trades by ticker
        trades_by_ticker: dict[str, list[dict]] = {}
        for trade in open_trades:
            ticker = trade["ticker"]
            trades_by_ticker.setdefault(ticker, []).append(trade)

        # Track tickers we've seen in DB
        db_tickers = set(trades_by_ticker.keys())

        # Compare each ticker's trades vs IB position
        for ticker, trades in trades_by_ticker.items():
            ib_pos = ib_by_ticker.get(ticker)

            # Calculate total DB position for this ticker
            db_total = sum(
                float(t.get("current_size") or t.get("entry_size") or 0)
                for t in trades
            )

            # Get current price for accurate exit
            last_price = self._get_last_price(ticker)

            if ib_pos is None or abs(ib_pos.position) < 0.01:
                # No IB position -> all trades for this ticker are closed
                for trade in trades:
                    trade_size = float(trade.get("current_size") or trade.get("entry_size") or 0)
                    deltas.append(PositionDelta(
                        ticker=ticker,
                        trade_id=trade["id"],
                        action="closed",
                        db_size=Decimal(str(trade_size)),
                        ib_size=Decimal("0"),
                        direction=trade.get("direction", "long"),
                        ib_avg_cost=Decimal(str(ib_pos.avg_cost)) if ib_pos else None,
                        last_price=Decimal(str(last_price)) if last_price else None,
                    ))
            else:
                # IB position exists - check for size changes
                ib_size = abs(ib_pos.position)
                ib_direction = "long" if ib_pos.position > 0 else "short"

                if abs(ib_size - db_total) > 0.01:
                    # Size mismatch - use FIFO to determine affected trades
                    remaining_ib = ib_size

                    for trade in sorted(trades, key=lambda t: t["entry_date"]):
                        trade_size = float(trade.get("current_size") or trade.get("entry_size") or 0)

                        if remaining_ib <= 0:
                            deltas.append(PositionDelta(
                                ticker=ticker,
                                trade_id=trade["id"],
                                action="closed",
                                db_size=Decimal(str(trade_size)),
                                ib_size=Decimal("0"),
                                direction=trade.get("direction", "long"),
                                ib_avg_cost=Decimal(str(ib_pos.avg_cost)),
                                last_price=Decimal(str(last_price)) if last_price else None,
                            ))
                        elif remaining_ib < trade_size:
                            deltas.append(PositionDelta(
                                ticker=ticker,
                                trade_id=trade["id"],
                                action="partial",
                                db_size=Decimal(str(trade_size)),
                                ib_size=Decimal(str(remaining_ib)),
                                direction=trade.get("direction", "long"),
                                ib_avg_cost=Decimal(str(ib_pos.avg_cost)),
                                last_price=Decimal(str(last_price)) if last_price else None,
                            ))
                            remaining_ib = 0
                        else:
                            remaining_ib -= trade_size

                    # Position increased externally
                    if remaining_ib > 0.01:
                        # Skip if ticker has pending orchestrator orders
                        if ticker in pending_tickers:
                            log.debug(f"Skipping {ticker} increase - has pending orchestrator orders")
                        # Skip if likely corporate action
                        elif self._is_likely_corporate_action(ticker, db_total, ib_size, Decimal(str(ib_pos.avg_cost))):
                            log.info(f"{ticker}: Share count change likely corporate action, skipping")
                        else:
                            log.warning(f"{ticker}: IB has {remaining_ib} more shares than DB tracks")
                            deltas.append(PositionDelta(
                                ticker=ticker,
                                trade_id=0,  # No existing trade
                                action="increase",
                                db_size=Decimal(str(db_total)),
                                ib_size=Decimal(str(ib_size)),
                                direction=ib_direction,
                                ib_avg_cost=Decimal(str(ib_pos.avg_cost)),
                                last_price=Decimal(str(last_price)) if last_price else None,
                                ib_position=ib_pos,  # Store for options support
                            ))

        # Check for completely new positions (in IB but not in DB)
        for ticker, ib_pos in ib_by_ticker.items():
            if ticker not in db_tickers and abs(ib_pos.position) > 0.01:
                # Skip if has pending orders
                if ticker in pending_tickers:
                    log.debug(f"Skipping new position {ticker} - has pending orchestrator orders")
                    continue

                last_price = self._get_last_price(ticker)
                ib_direction = "long" if ib_pos.position > 0 else "short"

                unit = "contracts" if ib_pos.is_option else "shares"
                log.warning(f"{ticker}: New position detected ({abs(ib_pos.position)} {unit}) not in DB")
                deltas.append(PositionDelta(
                    ticker=ticker,
                    trade_id=0,
                    action="increase",
                    db_size=Decimal("0"),
                    ib_size=Decimal(str(abs(ib_pos.position))),
                    direction=ib_direction,
                    ib_avg_cost=Decimal(str(ib_pos.avg_cost)),
                    last_price=Decimal(str(last_price)) if last_price else None,
                    ib_position=ib_pos,  # Store for options support
                ))

        self._last_check = datetime.now()
        return deltas

    def _get_last_price(self, ticker: str) -> float | None:
        """Get last price from IB."""
        try:
            result = self.ib.get_stock_price(ticker)
            if result:
                return float(result.get("last") or result.get("lastPrice") or
                           result.get("close") or 0) or None
        except Exception as e:
            log.warning(f"Failed to get price for {ticker}: {e}")
        return None

    def _is_likely_corporate_action(self, ticker: str, db_size: float,
                                    ib_size: float, ib_avg_cost: Decimal) -> bool:
        """Detect likely stock split or dividend.

        Heuristic: If share count changed by round ratio (2x, 3x, 0.5x)
        and position value is approximately same, likely corporate action.
        """
        if db_size == 0:
            return False

        ratio = ib_size / db_size
        # Common split ratios
        split_ratios = [2.0, 3.0, 4.0, 5.0, 10.0, 20.0, 0.5, 0.25, 0.1, 0.05]

        for split_ratio in split_ratios:
            if abs(ratio - split_ratio) < 0.01:
                log.info(f"{ticker}: Ratio {ratio:.2f} matches split pattern {split_ratio}")
                return True
        return False

    def _already_detected_today(self, symbol_key: str, size: Decimal) -> bool:
        """Check if we already created an entry for this increase today.

        Args:
            symbol_key: Full OCC symbol for options, ticker for stocks

        Note: Allows multiple detections if sizes differ significantly (>5%).
        This handles legitimate scale-ins vs duplicate detection.
        """
        detections = self.db.get_position_detections_today(symbol_key)

        for detection in detections:
            existing_size = Decimal(str(detection['size']))
            if existing_size > 0:
                # If sizes match within 5%, consider it duplicate
                diff_ratio = abs(existing_size - size) / max(existing_size, size)
                if diff_ratio < Decimal("0.05"):
                    return True
        return False

    def _estimate_entry_price(self, delta: PositionDelta) -> Decimal:
        """Estimate entry price for detected position.

        Strategy:
        - New position (db_size=0): IB avg cost is accurate
        - Existing position: IB avg is blended, use last price as estimate
        - ACATS detection: avg cost near $0 suggests transfer
        - Fallback: Use whatever we have
        """
        # ACATS detection: avg cost is $0 or suspiciously low
        if delta.ib_avg_cost and delta.ib_avg_cost < Decimal("0.01"):
            log.warning(f"{delta.ticker}: Zero avg cost suggests ACATS transfer")
            return delta.last_price or Decimal("0")

        if delta.is_new_position and delta.ib_avg_cost:
            # New position - IB avg cost reflects this purchase
            return delta.ib_avg_cost
        elif delta.last_price:
            # Existing position - avg cost is blended, last price is better estimate
            return delta.last_price
        elif delta.ib_avg_cost:
            # Fallback to avg cost (imperfect but better than nothing)
            return delta.ib_avg_cost
        else:
            # Should not happen - log error and use 0
            log.error(f"No price available for {delta.ticker}, using 0")
            return Decimal("0")

    def process_deltas(self, deltas: list[PositionDelta]) -> dict:
        """
        Process position deltas: close trades, update sizes, trigger reviews.

        Returns:
            Dict with counts: {closed: N, partial: N, increase: N, errors: N}
        """
        results = {"closed": 0, "partial": 0, "increase": 0, "errors": 0}

        for delta in deltas:
            try:
                if delta.action == "closed":
                    self._handle_close(delta)
                    results["closed"] += 1
                elif delta.action == "partial":
                    self._handle_partial(delta)
                    results["partial"] += 1
                elif delta.action == "increase":
                    if self._settings.get("auto_track_position_increases", True):
                        self._handle_increase(delta)
                        results["increase"] += 1
                    else:
                        log.info(f"Position increase tracking disabled, skipping {delta.ticker}")
            except Exception as e:
                log.error(f"Error processing delta for {delta.ticker}: {e}")
                results["errors"] += 1

        return results

    def _handle_close(self, delta: PositionDelta):
        """Handle full position closure with direction-aware P&L and options support."""
        log.info(f"Position closed: {delta.ticker} (trade {delta.trade_id}, "
                 f"size={delta.db_size}, direction={delta.direction})")

        # Get trade to check if it's an option
        trade = self.db.get_trade(delta.trade_id)
        is_option = trade and trade.get("option_underlying") is not None
        entry_price = float(trade.get("entry_price", 0)) if trade else 0

        # Determine exit price (prefer last_price over avg_cost)
        exit_price = float(delta.last_price or delta.ib_avg_cost or 0)

        if exit_price == 0:
            log.warning(f"No exit price for {delta.ticker}, using 0")

        if is_option:
            # Use options-aware P&L calculation
            self.db.close_option_trade(
                delta.trade_id,
                exit_price,
                "position_monitor",
                expiration_action=None  # Not an expiration close
            )
        else:
            # Standard stock P&L
            self.db.close_trade_with_direction(
                delta.trade_id, exit_price, "position_monitor", delta.direction
            )

        # Update stock position state if no more open trades
        remaining = self.db.get_open_trades_by_ticker(delta.ticker)
        if not remaining:
            self.db.update_stock_position(delta.ticker, False, "none")

        # Send notification
        if self.notifier:
            from notifications import Notification, NotificationPriority

            # Calculate P&L
            pnl_pct = 0.0
            if entry_price > 0:
                if delta.direction == "long":
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                else:  # short
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100

            self.notifier.notify(Notification(
                event_type="position_closed",
                title=f"{delta.ticker} Position Closed",
                message=f"Closed at ${exit_price:.2f} ({pnl_pct:+.1f}%)",
                priority=NotificationPriority.HIGH,
                ticker=delta.ticker,
                data={"exit_price": exit_price, "pnl_pct": pnl_pct, "trade_id": delta.trade_id}
            ))

        # Queue position close review (will queue full review if significant)
        self.db.queue_task(
            task_type="position_close_review",
            ticker=delta.ticker,
            prompt=f"Position closed: {delta.ticker} (trade {delta.trade_id})",
            priority=7,
            cooldown_key=f"position_close_review:{delta.ticker}",
            cooldown_hours=1
        )

    def _handle_partial(self, delta: PositionDelta):
        """Handle partial position close."""
        log.info(f"Partial close: {delta.ticker} (trade {delta.trade_id}, "
                 f"{delta.db_size} -> {delta.ib_size})")

        self.db.update_trade_size(delta.trade_id, float(delta.ib_size))

    def _handle_increase(self, delta: PositionDelta):
        """Create trade entry for externally-added shares/contracts with options support."""

        # Get option data from stored ib_position
        ib_pos = delta.ib_position
        option_data = ib_pos.option_data if ib_pos else None
        is_option = option_data is not None

        # Use full_symbol for idempotency (different options on same underlying)
        symbol_key = delta.full_symbol

        # GUARD 1: Check for duplicate detection (idempotency) using full_symbol
        if self._already_detected_today(symbol_key, delta.size_difference):
            log.info(f"Already tracked increase for {symbol_key} today, skipping")
            return

        # GUARD 2: Minimum threshold (adjusted for options multiplier)
        min_value = Decimal(str(self._settings.get("position_detect_min_value", 100)))
        multiplier = ib_pos.multiplier if ib_pos else 1
        position_value = delta.size_difference * (delta.last_price or Decimal("0")) * multiplier

        if position_value < min_value:
            log.debug(f"Position value ${position_value} below ${min_value} threshold, skipping")
            return

        # GUARD 3: Skip fractional shares below threshold
        if delta.size_difference < Decimal("0.001"):
            log.debug(f"Size difference {delta.size_difference} below threshold, skipping")
            return

        # Calculate entry price
        entry_price = self._estimate_entry_price(delta)

        if is_option:
            log.info(f"Options position detected: {option_data.display_name} +{delta.size_difference} contracts @ ${entry_price}")
        else:
            log.info(f"Position increase detected: {delta.ticker} +{delta.size_difference} shares @ ${entry_price}")

        # Build trade entry
        trade = {
            "ticker": delta.ticker,
            "entry_date": delta.detected_at,
            "entry_price": float(entry_price),
            "entry_size": float(delta.size_difference),
            "entry_type": "option" if is_option else "stock",
            "direction": delta.direction,
            "thesis": "External position - added outside orchestrator",
            "source_analysis": "position_monitor:detected",
            "source_type": "detected",
            "full_symbol": symbol_key,
        }

        # Add options-specific fields
        if option_data:
            trade.update({
                "option_underlying": option_data.underlying,
                "option_expiration": option_data.expiration,
                "option_strike": float(option_data.strike),
                "option_type": option_data.option_type,
                "option_multiplier": option_data.multiplier,
                "is_credit": delta.direction == "short",
            })

        try:
            trade_id = self.db.add_trade_detected(trade)

            # Queue task for user review
            display = option_data.display_name if option_data else delta.ticker
            self.db.queue_task(
                task_type="detected_position",
                ticker=delta.ticker,
                prompt=f"Position detected: {display} +{delta.size_difference} @ ${entry_price}",
                priority=6,
                cooldown_key=f"detected_position:{delta.ticker}",
                cooldown_hours=1
            )

            # Record detection for idempotency (use full_symbol)
            self.db.record_position_detection(
                ticker=delta.ticker,
                size=float(delta.size_difference),
                trade_id=trade_id,
                full_symbol=symbol_key,
            )

            log.info(f"Created trade {trade_id} for detected position")

            # Send notification for detected position
            if self.notifier:
                from notifications import Notification, NotificationPriority
                self.notifier.notify(Notification(
                    event_type="position_detected",
                    title=f"{delta.ticker} Position Detected",
                    message=f"New position: +{delta.size_difference} shares @ ${entry_price}",
                    priority=NotificationPriority.MEDIUM,
                    ticker=delta.ticker,
                    data={"size": float(delta.size_difference), "entry_price": float(entry_price), "trade_id": trade_id}
                ))

        except Exception as e:
            log.error(f"Failed to create trade entry for detected position: {e}")

    def _trigger_review(self, trade_id: int):
        """Trigger post-trade review via task queue."""
        try:
            from orchestrator import _chain_to_post_trade_review, cfg
            if cfg.task_queue_enabled:
                _chain_to_post_trade_review(self.db, trade_id)
        except Exception as e:
            log.warning(f"Failed to trigger post-trade review for trade {trade_id}: {e}")
