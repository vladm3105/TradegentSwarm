"""
Watchlist Trigger Monitoring (IPLAN-004)

Monitors watchlist entries for trigger/invalidation conditions.
When a trigger fires, marks the entry as triggered and queues follow-up action.

Components:
- parse_trigger(): Parse natural language triggers into structured conditions
- ConditionEvaluator: Evaluate conditions against current market data
- WatchlistMonitor: Monitor active watchlist entries
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Callable, TYPE_CHECKING
import logging
import re

if TYPE_CHECKING:
    from db_layer import NexusDB
    from ib_client import IBClientProtocol, Quote
    from notifications import NotificationRouter

log = logging.getLogger("tradegent.watchlist-monitor")


# ─── Condition Types ───────────────────────────────────────────────────────────


class ConditionType(Enum):
    """Types of trigger conditions that can be automatically evaluated."""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PRICE_RANGE = "price_range"
    SUPPORT_HOLD = "support_hold"
    RESISTANCE_BREAK = "resistance_break"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    VOLUME_ABOVE = "volume_above"
    CUSTOM = "custom"  # Cannot be auto-evaluated


@dataclass
class ParsedCondition:
    """Parsed trigger condition."""
    type: ConditionType
    value: float | str | None = None
    secondary_value: float | str | None = None
    raw_text: str = ""
    confidence: float = 1.0  # How confident we are in the parse (0-1)


# ─── Trigger Parsing ────────────────────────────────────────────────────────────


def parse_trigger(trigger_text: str) -> ParsedCondition:
    """
    Parse natural language trigger into structured condition.

    Examples:
    - "Price breaks above $150" → PRICE_ABOVE, 150
    - "Drops below $140" → PRICE_BELOW, 140
    - "Holds $145 support" → SUPPORT_HOLD, 145
    - "Breaks $160 resistance" → RESISTANCE_BREAK, 160
    - "Before earnings on 2026-03-15" → DATE_BEFORE, 2026-03-15
    - "Volume > 2x ADV" → VOLUME_ABOVE, 2.0
    """
    text = trigger_text.lower().strip()

    # Price above patterns
    above_patterns = [
        r'(?:breaks?|crosses?)\s*(?:above|over)\s*\$?([\d.]+)',
        r'(?:above|over)\s*\$?([\d.]+)',
        r'\$?([\d.]+)\s*(?:breakout|resistance\s*break)',
        r'price\s*(?:>|>=)\s*\$?([\d.]+)',
    ]
    for pattern in above_patterns:
        if match := re.search(pattern, text):
            return ParsedCondition(
                type=ConditionType.PRICE_ABOVE,
                value=float(match.group(1)),
                raw_text=trigger_text
            )

    # Price below patterns
    below_patterns = [
        r'(?:drops?|falls?|breaks?)\s*(?:below|under)\s*\$?([\d.]+)',
        r'(?:below|under)\s*\$?([\d.]+)',
        r'price\s*(?:<|<=)\s*\$?([\d.]+)',
    ]
    for pattern in below_patterns:
        if match := re.search(pattern, text):
            return ParsedCondition(
                type=ConditionType.PRICE_BELOW,
                value=float(match.group(1)),
                raw_text=trigger_text
            )

    # Support hold pattern
    if match := re.search(r'holds?\s*\$?([\d.]+)\s*support', text):
        return ParsedCondition(
            type=ConditionType.SUPPORT_HOLD,
            value=float(match.group(1)),
            raw_text=trigger_text
        )

    # Resistance break pattern
    if match := re.search(r'breaks?\s*\$?([\d.]+)\s*resistance', text):
        return ParsedCondition(
            type=ConditionType.RESISTANCE_BREAK,
            value=float(match.group(1)),
            raw_text=trigger_text
        )

    # Date patterns
    date_patterns = [
        (r'before\s+(?:earnings\s+(?:on\s+)?)?(\d{4}-\d{2}-\d{2})', ConditionType.DATE_BEFORE),
        (r'before\s+(\d{4}-\d{2}-\d{2})', ConditionType.DATE_BEFORE),
        (r'after\s+(\d{4}-\d{2}-\d{2})', ConditionType.DATE_AFTER),
    ]
    for pattern, cond_type in date_patterns:
        if match := re.search(pattern, text):
            return ParsedCondition(
                type=cond_type,
                value=match.group(1),
                raw_text=trigger_text
            )

    # Volume patterns
    if match := re.search(r'volume\s*[>]\s*([\d.]+)\s*x?\s*(?:adv|average)?', text):
        return ParsedCondition(
            type=ConditionType.VOLUME_ABOVE,
            value=float(match.group(1)),
            raw_text=trigger_text
        )

    # Couldn't parse - return as custom with low confidence
    log.warning(f"Could not parse trigger: {trigger_text}")
    return ParsedCondition(
        type=ConditionType.CUSTOM,
        raw_text=trigger_text,
        confidence=0.0
    )


# ─── Condition Evaluator ────────────────────────────────────────────────────────


class ConditionEvaluator:
    """Evaluates parsed conditions against current market data."""

    def __init__(
        self,
        ib_client: "IBClientProtocol",
        price_tolerance_pct: float = 0.5,
        support_hold_periods: int = 3  # Number of checks price must hold above support
    ):
        self.ib = ib_client
        self.price_tolerance_pct = price_tolerance_pct
        self.support_hold_periods = support_hold_periods
        self._support_hold_counts: dict[str, int] = {}  # ticker:level -> consecutive holds

    def evaluate(
        self,
        ticker: str,
        condition: ParsedCondition,
        quote: "Quote | None" = None
    ) -> tuple[bool, str]:
        """
        Check if condition is met.

        Args:
            ticker: Stock symbol
            condition: Parsed condition to evaluate
            quote: Optional quote (fetched if not provided)

        Returns:
            (is_met, reason) - Whether condition is met and explanation
        """
        # Fetch quote if not provided
        if quote is None:
            quote = self.ib.get_quote(ticker)

        if quote is None:
            return False, "No quote available"

        last_price = quote.last or quote.close
        if last_price is None:
            return False, "No price data"

        # Calculate tolerance threshold
        tolerance = last_price * (self.price_tolerance_pct / 100)

        if condition.type == ConditionType.PRICE_ABOVE:
            target = float(condition.value)
            if last_price >= (target - tolerance):
                return True, f"Price ${last_price:.2f} >= target ${target:.2f}"
            return False, f"Price ${last_price:.2f} < target ${target:.2f}"

        elif condition.type == ConditionType.PRICE_BELOW:
            target = float(condition.value)
            if last_price <= (target + tolerance):
                return True, f"Price ${last_price:.2f} <= target ${target:.2f}"
            return False, f"Price ${last_price:.2f} > target ${target:.2f}"

        elif condition.type == ConditionType.SUPPORT_HOLD:
            support = float(condition.value)
            if last_price >= (support - tolerance):
                # Increment hold count
                key = f"{ticker}:{support}"
                self._support_hold_counts[key] = self._support_hold_counts.get(key, 0) + 1
                if self._support_hold_counts[key] >= self.support_hold_periods:
                    return True, f"Price held ${support:.2f} support for {self.support_hold_periods} periods"
                return False, f"Holding support ({self._support_hold_counts[key]}/{self.support_hold_periods})"
            else:
                # Reset hold count - support broken
                self._support_hold_counts[f"{ticker}:{support}"] = 0
                return False, f"Support ${support:.2f} broken (price ${last_price:.2f})"

        elif condition.type == ConditionType.RESISTANCE_BREAK:
            resistance = float(condition.value)
            if last_price >= (resistance + tolerance):
                return True, f"Price ${last_price:.2f} broke resistance ${resistance:.2f}"
            return False, f"Price ${last_price:.2f} below resistance ${resistance:.2f}"

        elif condition.type == ConditionType.DATE_BEFORE:
            target = date.fromisoformat(str(condition.value))
            today = date.today()
            if today <= target:
                return True, f"Today {today} is before {target}"
            return False, f"Date {target} has passed"

        elif condition.type == ConditionType.DATE_AFTER:
            target = date.fromisoformat(str(condition.value))
            today = date.today()
            if today >= target:
                return True, f"Today {today} is after {target}"
            return False, f"Today {today} is before {target}"

        elif condition.type == ConditionType.VOLUME_ABOVE:
            if quote.volume is None:
                return False, "No volume data"
            # For volume comparison, we'd need ADV from historical data
            # This is a simplified check - full implementation would fetch 20-day ADV
            multiplier = float(condition.value)
            return False, f"Volume check requires ADV data (not implemented)"

        elif condition.type == ConditionType.CUSTOM:
            return False, "Custom condition requires manual evaluation"

        return False, f"Unknown condition type: {condition.type}"


# ─── Monitor Events ─────────────────────────────────────────────────────────────


@dataclass
class MonitorEvent:
    """Event emitted when watchlist state changes."""
    event_type: str  # 'triggered', 'invalidated', 'expired', 'error'
    ticker: str
    entry_id: int
    reason: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MonitorResults:
    """Results from a monitoring run."""
    checked: int = 0
    triggered: int = 0
    invalidated: int = 0
    expired: int = 0
    errors: int = 0
    events: list[MonitorEvent] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Checked: {self.checked}, Triggered: {self.triggered}, "
            f"Invalidated: {self.invalidated}, Expired: {self.expired}, "
            f"Errors: {self.errors}"
        )


# ─── Watchlist Monitor ───────────────────────────────────────────────────────────


class WatchlistMonitor:
    """Monitors watchlist entries for trigger/invalidation conditions."""

    def __init__(
        self,
        db: "NexusDB",
        ib_client: "IBClientProtocol",
        price_tolerance_pct: float = 0.5,
        on_event: Callable[[MonitorEvent], None] | None = None,
        notifier: "NotificationRouter | None" = None
    ):
        self.db = db
        self.ib = ib_client
        self.evaluator = ConditionEvaluator(ib_client, price_tolerance_pct)
        self.on_event = on_event or self._default_event_handler
        self.notifier = notifier

    def _default_event_handler(self, event: MonitorEvent):
        """Default handler - just log the event."""
        log.info(f"Watchlist event: {event.event_type} - {event.ticker}: {event.reason}")

    def check_entries(self) -> MonitorResults:
        """Check all active watchlist entries."""
        results = MonitorResults()

        entries = self.db.get_active_watchlist()
        if not entries:
            return results

        # Batch fetch quotes for all tickers
        tickers = list(set(e["ticker"] for e in entries))
        quotes = self.ib.get_quotes_batch(tickers)

        for entry in entries:
            results.checked += 1
            ticker = entry["ticker"]
            quote = quotes.get(ticker)

            try:
                # Check expiration first (cheapest check)
                if self._is_expired(entry):
                    self._handle_expired(entry, results)
                    continue

                # Check invalidation
                invalidated, reason = self._is_invalidated(entry, quote)
                if invalidated:
                    self._handle_invalidated(entry, reason, results)
                    continue

                # Check trigger
                triggered, reason = self._is_triggered(entry, quote)
                if triggered:
                    self._handle_triggered(entry, reason, results)

            except Exception as e:
                log.error(f"Error checking {ticker}: {e}")
                results.errors += 1
                results.events.append(MonitorEvent(
                    event_type="error",
                    ticker=ticker,
                    entry_id=entry["id"],
                    reason=str(e)
                ))

        return results

    def _is_expired(self, entry: dict) -> bool:
        """Check if entry has expired."""
        expires_at = entry.get("expires_at")
        if expires_at is None:
            return False

        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        elif isinstance(expires_at, date) and not isinstance(expires_at, datetime):
            expires_at = datetime.combine(expires_at, datetime.max.time())

        return datetime.now() > expires_at

    def _is_invalidated(self, entry: dict, quote) -> tuple[bool, str]:
        """Check if entry's invalidation condition is met."""
        # Check text-based invalidation
        invalidation_text = entry.get("invalidation")
        if invalidation_text:
            condition = parse_trigger(invalidation_text)
            if condition.type != ConditionType.CUSTOM:
                is_met, reason = self.evaluator.evaluate(entry["ticker"], condition, quote)
                if is_met:
                    return True, reason

        # Check price-based invalidation
        invalidation_price = entry.get("invalidation_price")
        if invalidation_price and quote:
            last_price = quote.last or quote.close
            if last_price is not None:
                # Assume invalidation_price is a stop level (below entry)
                if last_price <= float(invalidation_price):
                    return True, f"Price ${last_price:.2f} <= invalidation ${invalidation_price}"

        return False, ""

    def _is_triggered(self, entry: dict, quote) -> tuple[bool, str]:
        """Check if entry's trigger condition is met."""
        # Check text-based trigger
        trigger_text = entry.get("entry_trigger")
        if trigger_text:
            condition = parse_trigger(trigger_text)
            if condition.type != ConditionType.CUSTOM:
                is_met, reason = self.evaluator.evaluate(entry["ticker"], condition, quote)
                if is_met:
                    return True, reason

        # Check price-based trigger
        entry_price = entry.get("entry_price")
        if entry_price and quote:
            last_price = quote.last or quote.close
            if last_price is not None:
                # For entry_price, trigger when price reaches or exceeds
                if last_price >= float(entry_price):
                    return True, f"Price ${last_price:.2f} >= entry ${entry_price}"

        return False, ""

    def _handle_expired(self, entry: dict, results: MonitorResults):
        """Handle expired watchlist entry."""
        ticker = entry["ticker"]
        reason = f"Entry expired (expires_at: {entry.get('expires_at')})"

        log.info(f"Watchlist entry expired: {ticker}")
        self.db.update_watchlist_status(entry["id"], "expired", notes=reason)

        event = MonitorEvent(
            event_type="expired",
            ticker=ticker,
            entry_id=entry["id"],
            reason=reason
        )
        results.expired += 1
        results.events.append(event)
        self.on_event(event)

    def _handle_invalidated(self, entry: dict, reason: str, results: MonitorResults):
        """Handle invalidated watchlist entry."""
        ticker = entry["ticker"]

        log.info(f"Watchlist entry invalidated: {ticker} - {reason}")
        self.db.update_watchlist_status(entry["id"], "invalidated", notes=reason)

        # Send notification
        if self.notifier:
            from notifications import Notification, NotificationPriority
            self.notifier.notify(Notification(
                event_type="watchlist_invalidated",
                title=f"{ticker} Thesis Invalidated",
                message=f"Reason: {reason}",
                priority=NotificationPriority.MEDIUM,
                ticker=ticker,
                data={"entry_id": entry["id"]}
            ))

        event = MonitorEvent(
            event_type="invalidated",
            ticker=ticker,
            entry_id=entry["id"],
            reason=reason
        )
        results.invalidated += 1
        results.events.append(event)
        self.on_event(event)

    def _handle_triggered(self, entry: dict, reason: str, results: MonitorResults):
        """Handle triggered watchlist entry."""
        ticker = entry["ticker"]

        log.info(f"Watchlist trigger fired: {ticker} - {reason}")
        self.db.update_watchlist_status(entry["id"], "triggered", notes=reason)

        # Queue task for follow-up action (if task queue available)
        try:
            self.db.queue_task(
                task_type="watchlist_triggered",
                ticker=ticker,
                prompt=f"Watchlist trigger fired: {reason}. Entry: {entry.get('entry_trigger')}",
                priority=8  # High priority
            )
        except Exception as e:
            log.warning(f"Failed to queue task for {ticker}: {e}")

        # Send notification
        if self.notifier:
            from notifications import Notification, NotificationPriority
            self.notifier.notify(Notification(
                event_type="watchlist_triggered",
                title=f"{ticker} Trigger Fired",
                message=f"Trigger: {reason}",
                priority=NotificationPriority.HIGH,
                ticker=ticker,
                data={"entry_trigger": entry.get("entry_trigger"), "entry_id": entry["id"]}
            ))

        event = MonitorEvent(
            event_type="triggered",
            ticker=ticker,
            entry_id=entry["id"],
            reason=reason
        )
        results.triggered += 1
        results.events.append(event)
        self.on_event(event)
