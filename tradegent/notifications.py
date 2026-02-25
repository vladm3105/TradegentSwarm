"""
Notification System for Tradegent - Alert notifications for trading events.

Supports multiple notification channels (Telegram, Webhook, Email) with:
- Priority filtering
- Rate limiting (token bucket)
- Deduplication
- Retry with exponential backoff
- Async sending via background worker thread
- Database logging for audit trail

Usage:
    router = NotificationRouter(db=db)
    router.add_channel(TelegramChannel())
    router.add_channel(WebhookChannel(url="..."))
    router.start()

    # Send notification (non-blocking)
    router.notify(Notification(
        event_type="position_closed",
        title="NVDA Position Closed",
        message="Closed at $130 (+3.6%)",
        priority=NotificationPriority.HIGH,
        ticker="NVDA"
    ))

    # Cleanup
    router.stop()
"""

import logging
import os
import smtplib
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from enum import Enum
from queue import Queue, Empty
from typing import Protocol, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from db_layer import NexusDB

try:
    import httpx
except ImportError:
    httpx = None  # Optional dependency

log = logging.getLogger("tradegent.notifications")


# ─── Enums and Data Classes ────────────────────────────────────────────────────


class NotificationPriority(Enum):
    """Priority levels for notifications."""
    LOW = 1       # Analysis complete, daily summaries
    MEDIUM = 2    # Options expiring warnings
    HIGH = 3      # Position closed, order filled, trigger fired
    CRITICAL = 4  # Stop hit, urgent actions


@dataclass
class Notification:
    """A notification to be sent."""
    event_type: str
    title: str
    message: str
    priority: NotificationPriority
    ticker: str | None = None
    data: dict | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    notification_id: str = field(default_factory=lambda: str(uuid4()))


# ─── Channel Protocol ──────────────────────────────────────────────────────────


class NotificationChannel(Protocol):
    """Protocol for notification channels."""

    def send(self, notification: Notification) -> bool:
        """Send notification. Returns True on success."""
        ...

    def is_enabled(self) -> bool:
        """Check if channel is enabled and configured."""
        ...

    def get_name(self) -> str:
        """Get channel name for logging."""
        ...


# ─── Rate Limiter ──────────────────────────────────────────────────────────────


class RateLimiter:
    """Token bucket rate limiter for notification throttling."""

    def __init__(self, rate: float = 1.0, burst: int = 5):
        """
        Initialize rate limiter.

        Args:
            rate: Tokens per second (e.g., 1.0 = 1 notification/sec)
            burst: Maximum burst capacity (e.g., 5 = can send 5 at once)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> bool:
        """
        Attempt to acquire a token.

        Returns:
            True if token acquired, False if rate limited
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def wait(self, timeout: float = 10.0) -> bool:
        """
        Wait until a token is available or timeout.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if token acquired, False if timeout
        """
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if self.acquire():
                return True
            time.sleep(0.1)
        return False


# ─── Notification Router ───────────────────────────────────────────────────────


class NotificationRouter:
    """Routes notifications to configured channels with async sending."""

    def __init__(self, db: "NexusDB | None" = None, rate: float = 1.0, burst: int = 5):
        """
        Initialize notification router.

        Args:
            db: Database for logging (optional)
            rate: Notifications per second
            burst: Burst capacity
        """
        self._channels: list[NotificationChannel] = []
        self._min_priority = NotificationPriority.MEDIUM
        self._queue: Queue[Notification] = Queue()
        self._seen_ids: set[str] = set()  # Deduplication
        self._seen_max = 1000
        self._rate_limiter = RateLimiter(rate=rate, burst=burst)
        self._db = db
        self._worker_thread: threading.Thread | None = None
        self._running = False

    def start(self):
        """Start background worker thread."""
        if self._running:
            log.warning("Notification router already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        log.info("Notification router started")

    def stop(self):
        """Stop background worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        log.info("Notification router stopped")

    def add_channel(self, channel: NotificationChannel):
        """Add a notification channel."""
        self._channels.append(channel)
        log.info(f"Added notification channel: {channel.get_name()}")

    def set_min_priority(self, priority: NotificationPriority):
        """Set minimum priority for sending notifications."""
        self._min_priority = priority

    def notify(self, notification: Notification):
        """
        Queue notification for async sending (non-blocking).

        Notifications below minimum priority or duplicates are skipped.
        """
        # Priority filter
        if notification.priority.value < self._min_priority.value:
            log.debug(f"Notification below min priority: {notification.title}")
            return

        # Deduplication
        if notification.notification_id in self._seen_ids:
            log.debug(f"Duplicate notification skipped: {notification.notification_id}")
            return

        self._seen_ids.add(notification.notification_id)
        if len(self._seen_ids) > self._seen_max:
            # Prune oldest entries (approximation using set conversion)
            self._seen_ids = set(list(self._seen_ids)[-500:])

        self._queue.put(notification)
        log.debug(f"Queued notification: {notification.title}")

    def _worker(self):
        """Background worker that sends notifications."""
        while self._running:
            try:
                notification = self._queue.get(timeout=1)
            except Empty:
                continue

            # Rate limiting with wait
            if not self._rate_limiter.wait(timeout=30):
                log.warning(f"Rate limit timeout for: {notification.title}")
                continue

            # Send to all enabled channels
            for channel in self._channels:
                if channel.is_enabled():
                    success = self._send_with_retry(channel, notification)
                    self._log_to_db(notification, channel.get_name(), success)

    def _send_with_retry(
        self,
        channel: NotificationChannel,
        notification: Notification,
        max_retries: int = 3
    ) -> bool:
        """Send with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                if channel.send(notification):
                    log.debug(f"Sent via {channel.get_name()}: {notification.title}")
                    return True
            except Exception as e:
                log.warning(f"Attempt {attempt + 1} failed for {channel.get_name()}: {e}")

            if attempt < max_retries - 1:
                backoff = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(backoff)

        log.error(f"All retries failed for {channel.get_name()}: {notification.title}")
        return False

    def _log_to_db(self, notification: Notification, channel: str, success: bool):
        """Log notification to database for audit."""
        if not self._db:
            return

        try:
            with self._db.conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO nexus.notification_log
                       (notification_id, event_type, title, message, priority, ticker, channel, success)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        notification.notification_id,
                        notification.event_type,
                        notification.title,
                        notification.message,
                        notification.priority.name,
                        notification.ticker,
                        channel,
                        success
                    )
                )
            self._db.conn.commit()
        except Exception as e:
            log.warning(f"Failed to log notification: {e}")


# ─── Webhook Channel ───────────────────────────────────────────────────────────


class WebhookChannel:
    """Send notifications via webhook (generic HTTP POST)."""

    def __init__(self, url: str, headers: dict | None = None):
        """
        Initialize webhook channel.

        Args:
            url: Webhook URL to POST to
            headers: Optional HTTP headers (e.g., auth tokens)
        """
        self.url = url
        self.headers = headers or {}
        self._enabled = True

        if not httpx:
            log.warning("httpx not installed - webhook channel disabled")
            self._enabled = False

    def get_name(self) -> str:
        return "webhook"

    def is_enabled(self) -> bool:
        return self._enabled and bool(self.url) and httpx is not None

    def send(self, notification: Notification) -> bool:
        """Send notification via HTTP POST."""
        if not httpx:
            return False

        payload = {
            "event_type": notification.event_type,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority.name,
            "ticker": notification.ticker,
            "data": notification.data,
            "timestamp": notification.timestamp.isoformat(),
            "notification_id": notification.notification_id,
        }

        try:
            response = httpx.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            return response.is_success
        except Exception as e:
            log.error(f"Webhook send failed: {e}")
            return False


# ─── Telegram Channel ──────────────────────────────────────────────────────────


class TelegramChannel:
    """Send notifications to Telegram via Bot API."""

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        """
        Initialize Telegram channel.

        Args:
            bot_token: Bot token from @BotFather (or TELEGRAM_BOT_TOKEN env var)
            chat_id: Chat/group ID (or TELEGRAM_CHAT_ID env var)
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._enabled = True

        if not httpx:
            log.warning("httpx not installed - telegram channel disabled")
            self._enabled = False

    def get_name(self) -> str:
        return "telegram"

    def is_enabled(self) -> bool:
        return (
            self._enabled
            and bool(self.bot_token)
            and bool(self.chat_id)
            and httpx is not None
        )

    def send(self, notification: Notification) -> bool:
        """Send notification to Telegram."""
        if not httpx:
            return False

        # Priority emoji mapping
        emoji = {
            NotificationPriority.LOW: "i",
            NotificationPriority.MEDIUM: "-",
            NotificationPriority.HIGH: "*",
            NotificationPriority.CRITICAL: "!",
        }.get(notification.priority, "-")

        # Format message with Markdown
        timestamp = notification.timestamp.strftime("%H:%M:%S")
        text = f"[{emoji}] *{notification.title}*\n\n{notification.message}\n\n_{timestamp}_"
        if notification.ticker:
            text += f"\nTicker: *{notification.ticker}*"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }

        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json=payload,
                timeout=10
            )
            return response.is_success
        except Exception as e:
            log.error(f"Telegram send failed: {e}")
            return False


# ─── Email Channel ─────────────────────────────────────────────────────────────


class EmailChannel:
    """Send notifications via email (SMTP)."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        to_address: str | None = None
    ):
        """
        Initialize email channel.

        All parameters can be provided via env vars:
        - EMAIL_SMTP_HOST, EMAIL_SMTP_PORT
        - EMAIL_USERNAME, EMAIL_PASSWORD
        - EMAIL_TO_ADDRESS
        """
        self.smtp_host = smtp_host or os.getenv("EMAIL_SMTP_HOST", "")
        self.smtp_port = smtp_port or int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self.username = username or os.getenv("EMAIL_USERNAME", "")
        self.password = password or os.getenv("EMAIL_PASSWORD", "")
        self.to_address = to_address or os.getenv("EMAIL_TO_ADDRESS", "")
        self._enabled = True

    def get_name(self) -> str:
        return "email"

    def is_enabled(self) -> bool:
        return (
            self._enabled
            and bool(self.smtp_host)
            and bool(self.username)
            and bool(self.to_address)
        )

    def send(self, notification: Notification) -> bool:
        """Send notification via email."""
        body = f"{notification.message}\n\n---\nTime: {notification.timestamp}\nID: {notification.notification_id}"
        if notification.ticker:
            body += f"\nTicker: {notification.ticker}"

        msg = MIMEText(body)
        msg["Subject"] = f"[{notification.priority.name}] {notification.title}"
        msg["From"] = self.username
        msg["To"] = self.to_address

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception as e:
            log.error(f"Email send failed: {e}")
            return False


# ─── Console Channel (for testing/development) ─────────────────────────────────


class ConsoleChannel:
    """Print notifications to console (for testing)."""

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    def get_name(self) -> str:
        return "console"

    def is_enabled(self) -> bool:
        return self._enabled

    def send(self, notification: Notification) -> bool:
        """Print notification to console."""
        emoji = {
            NotificationPriority.LOW: "i",
            NotificationPriority.MEDIUM: "-",
            NotificationPriority.HIGH: "*",
            NotificationPriority.CRITICAL: "!",
        }.get(notification.priority, "-")

        print(f"[{emoji}] [{notification.priority.name}] {notification.title}")
        print(f"    {notification.message}")
        if notification.ticker:
            print(f"    Ticker: {notification.ticker}")
        print()
        return True


# ─── Helper Functions ──────────────────────────────────────────────────────────


def create_notification_router(db: "NexusDB | None" = None) -> NotificationRouter | None:
    """
    Create and configure notification router from database settings.

    Returns None if notifications are disabled.
    """
    if db:
        enabled = db.get_setting("notifications_enabled", False)
        if not enabled:
            log.info("Notifications disabled in settings")
            return None

    router = NotificationRouter(db=db)

    # Add Telegram channel (loads from env vars)
    telegram = TelegramChannel()
    if telegram.is_enabled():
        router.add_channel(telegram)

    # Add webhook channel if configured
    if db:
        webhook_url = db.get_setting("webhook_url", "")
        if webhook_url:
            import json
            headers_str = db.get_setting("webhook_headers", "{}")
            try:
                headers = json.loads(headers_str) if headers_str else {}
            except json.JSONDecodeError:
                headers = {}
            router.add_channel(WebhookChannel(webhook_url, headers))

    # Add email channel (loads from env vars)
    email = EmailChannel()
    if email.is_enabled():
        router.add_channel(email)

    # Set minimum priority
    if db:
        min_priority_str = db.get_setting("notification_min_priority", "MEDIUM")
        try:
            min_priority = NotificationPriority[min_priority_str]
            router.set_min_priority(min_priority)
        except KeyError:
            log.warning(f"Invalid notification_min_priority: {min_priority_str}")

    return router
