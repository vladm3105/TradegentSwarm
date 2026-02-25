"""Tests for the notification system."""

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from notifications import (
    ConsoleChannel,
    EmailChannel,
    Notification,
    NotificationPriority,
    NotificationRouter,
    RateLimiter,
    TelegramChannel,
    WebhookChannel,
)


# ─── Notification Tests ────────────────────────────────────────────────────────


class TestNotification:
    """Tests for Notification dataclass."""

    def test_notification_creation(self):
        """Test basic notification creation."""
        n = Notification(
            event_type="test_event",
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.HIGH,
            ticker="NVDA"
        )
        assert n.event_type == "test_event"
        assert n.title == "Test Title"
        assert n.priority == NotificationPriority.HIGH
        assert n.ticker == "NVDA"
        assert n.notification_id is not None
        assert isinstance(n.timestamp, datetime)

    def test_notification_with_data(self):
        """Test notification with additional data."""
        n = Notification(
            event_type="position_closed",
            title="NVDA Closed",
            message="Closed at $130",
            priority=NotificationPriority.HIGH,
            data={"exit_price": 130, "pnl_pct": 3.6}
        )
        assert n.data["exit_price"] == 130
        assert n.data["pnl_pct"] == 3.6


# ─── Rate Limiter Tests ────────────────────────────────────────────────────────


class TestRateLimiter:
    """Tests for RateLimiter."""

    def test_rate_limiter_burst(self):
        """Test that burst capacity works."""
        limiter = RateLimiter(rate=1.0, burst=5)
        # Should be able to acquire 5 tokens immediately
        for _ in range(5):
            assert limiter.acquire() is True
        # 6th should fail
        assert limiter.acquire() is False

    def test_rate_limiter_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate=10.0, burst=2)  # Fast refill for testing
        # Exhaust tokens
        assert limiter.acquire() is True
        assert limiter.acquire() is True
        assert limiter.acquire() is False
        # Wait for refill
        time.sleep(0.2)
        assert limiter.acquire() is True

    def test_rate_limiter_wait(self):
        """Test wait functionality."""
        limiter = RateLimiter(rate=10.0, burst=1)
        # Exhaust token
        assert limiter.acquire() is True
        # Wait should succeed
        assert limiter.wait(timeout=1.0) is True

    def test_rate_limiter_wait_timeout(self):
        """Test wait timeout."""
        limiter = RateLimiter(rate=0.1, burst=1)  # Very slow refill
        assert limiter.acquire() is True
        # Wait should timeout
        assert limiter.wait(timeout=0.1) is False


# ─── Channel Tests ─────────────────────────────────────────────────────────────


class TestConsoleChannel:
    """Tests for ConsoleChannel."""

    def test_console_channel_enabled(self):
        """Test console channel is enabled by default."""
        channel = ConsoleChannel()
        assert channel.is_enabled() is True
        assert channel.get_name() == "console"

    def test_console_channel_disabled(self):
        """Test console channel can be disabled."""
        channel = ConsoleChannel(enabled=False)
        assert channel.is_enabled() is False

    def test_console_channel_send(self, capsys):
        """Test console channel prints output."""
        channel = ConsoleChannel()
        n = Notification(
            event_type="test",
            title="Test Title",
            message="Test message",
            priority=NotificationPriority.HIGH,
            ticker="NVDA"
        )
        assert channel.send(n) is True
        captured = capsys.readouterr()
        assert "Test Title" in captured.out
        assert "NVDA" in captured.out


class TestWebhookChannel:
    """Tests for WebhookChannel."""

    def test_webhook_channel_disabled_without_url(self):
        """Test webhook channel is disabled without URL."""
        channel = WebhookChannel(url="")
        assert channel.is_enabled() is False

    def test_webhook_channel_enabled_with_url(self):
        """Test webhook channel is enabled with URL."""
        channel = WebhookChannel(url="https://example.com/webhook")
        # Will be disabled if httpx not installed, but enabled otherwise
        # The is_enabled check requires httpx
        assert channel.get_name() == "webhook"

    @patch("notifications.httpx")
    def test_webhook_channel_send(self, mock_httpx):
        """Test webhook channel sends POST request."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_httpx.post.return_value = mock_response

        channel = WebhookChannel(url="https://example.com/webhook")
        channel._enabled = True  # Force enable for test

        n = Notification(
            event_type="test",
            title="Test",
            message="Test message",
            priority=NotificationPriority.HIGH
        )
        assert channel.send(n) is True
        mock_httpx.post.assert_called_once()


class TestTelegramChannel:
    """Tests for TelegramChannel."""

    def test_telegram_channel_disabled_without_config(self):
        """Test telegram channel is disabled without config."""
        channel = TelegramChannel(bot_token="", chat_id="")
        assert channel.is_enabled() is False

    @patch("notifications.httpx")
    def test_telegram_channel_send(self, mock_httpx):
        """Test telegram channel sends message."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_httpx.post.return_value = mock_response

        channel = TelegramChannel(bot_token="test_token", chat_id="test_chat")
        channel._enabled = True  # Force enable

        n = Notification(
            event_type="test",
            title="Test",
            message="Test message",
            priority=NotificationPriority.CRITICAL,
            ticker="NVDA"
        )
        assert channel.send(n) is True
        mock_httpx.post.assert_called_once()
        call_args = mock_httpx.post.call_args
        assert "api.telegram.org" in call_args[0][0]


class TestEmailChannel:
    """Tests for EmailChannel."""

    def test_email_channel_disabled_without_config(self):
        """Test email channel is disabled without config."""
        channel = EmailChannel()
        assert channel.is_enabled() is False

    def test_email_channel_enabled_with_config(self):
        """Test email channel is enabled with config."""
        channel = EmailChannel(
            smtp_host="smtp.example.com",
            username="test@example.com",
            password="secret",
            to_address="dest@example.com"
        )
        assert channel.is_enabled() is True


# ─── Router Tests ──────────────────────────────────────────────────────────────


class TestNotificationRouter:
    """Tests for NotificationRouter."""

    def test_router_add_channel(self):
        """Test adding channels to router."""
        router = NotificationRouter()
        channel = ConsoleChannel()
        router.add_channel(channel)
        assert channel in router._channels

    def test_router_priority_filtering(self):
        """Test that notifications below min priority are skipped."""
        router = NotificationRouter()
        router.set_min_priority(NotificationPriority.HIGH)

        n = Notification(
            event_type="test",
            title="Test",
            message="Test",
            priority=NotificationPriority.LOW
        )
        router.notify(n)
        # Should be empty because LOW < HIGH
        assert router._queue.empty()

    def test_router_priority_accepted(self):
        """Test that notifications at/above min priority are queued."""
        router = NotificationRouter()
        router.set_min_priority(NotificationPriority.MEDIUM)

        n = Notification(
            event_type="test",
            title="Test",
            message="Test",
            priority=NotificationPriority.HIGH
        )
        router.notify(n)
        # Should be queued because HIGH >= MEDIUM
        assert not router._queue.empty()

    def test_router_deduplication(self):
        """Test that duplicate notifications are skipped."""
        router = NotificationRouter()

        n = Notification(
            event_type="test",
            title="Test",
            message="Test",
            priority=NotificationPriority.HIGH,
            notification_id="unique-id-123"
        )

        router.notify(n)
        router.notify(n)  # Same ID

        # Should only have 1 in queue
        assert router._queue.qsize() == 1

    def test_router_start_stop(self):
        """Test router start/stop lifecycle."""
        router = NotificationRouter()
        router.start()
        assert router._running is True
        assert router._worker_thread is not None
        assert router._worker_thread.is_alive()

        router.stop()
        assert router._running is False

    def test_router_sends_to_channels(self):
        """Test that router sends to enabled channels."""
        router = NotificationRouter()

        # Create mock channel
        mock_channel = MagicMock()
        mock_channel.is_enabled.return_value = True
        mock_channel.get_name.return_value = "mock"
        mock_channel.send.return_value = True

        router.add_channel(mock_channel)
        router.start()

        n = Notification(
            event_type="test",
            title="Test",
            message="Test",
            priority=NotificationPriority.HIGH
        )
        router.notify(n)

        # Wait for worker to process
        time.sleep(0.5)
        router.stop()

        mock_channel.send.assert_called()

    def test_router_skips_disabled_channels(self):
        """Test that router skips disabled channels."""
        router = NotificationRouter()

        # Create disabled mock channel
        mock_channel = MagicMock()
        mock_channel.is_enabled.return_value = False
        mock_channel.get_name.return_value = "mock"

        router.add_channel(mock_channel)
        router.start()

        n = Notification(
            event_type="test",
            title="Test",
            message="Test",
            priority=NotificationPriority.HIGH
        )
        router.notify(n)

        # Wait for worker to process
        time.sleep(0.5)
        router.stop()

        # Send should not be called on disabled channel
        mock_channel.send.assert_not_called()


# ─── Integration Tests ─────────────────────────────────────────────────────────


class TestNotificationIntegration:
    """Integration tests for notification system."""

    def test_full_workflow_with_console(self, capsys):
        """Test full notification workflow with console channel."""
        router = NotificationRouter()
        router.add_channel(ConsoleChannel())
        router.start()

        notifications = [
            Notification(
                event_type="position_closed",
                title="NVDA Closed",
                message="Closed at $130 (+3.6%)",
                priority=NotificationPriority.HIGH,
                ticker="NVDA"
            ),
            Notification(
                event_type="order_filled",
                title="Order 123 Filled",
                message="100 shares @ $125.50",
                priority=NotificationPriority.HIGH,
                ticker="NVDA"
            ),
        ]

        for n in notifications:
            router.notify(n)

        # Wait for processing
        time.sleep(1)
        router.stop()

        captured = capsys.readouterr()
        assert "NVDA Closed" in captured.out
        assert "Order 123 Filled" in captured.out

    def test_rate_limiting_integration(self):
        """Test that rate limiting affects notification timing."""
        router = NotificationRouter(rate=2.0, burst=2)  # 2/sec, burst 2

        mock_channel = MagicMock()
        mock_channel.is_enabled.return_value = True
        mock_channel.get_name.return_value = "mock"
        mock_channel.send.return_value = True

        router.add_channel(mock_channel)
        router.start()

        # Send 5 notifications rapidly
        for i in range(5):
            n = Notification(
                event_type="test",
                title=f"Test {i}",
                message="Test",
                priority=NotificationPriority.HIGH,
                notification_id=f"id-{i}"
            )
            router.notify(n)

        # Wait for all to be processed (with rate limiting)
        time.sleep(3)
        router.stop()

        # All should eventually be sent
        assert mock_channel.send.call_count == 5


# ─── Priority Tests ────────────────────────────────────────────────────────────


class TestNotificationPriority:
    """Tests for priority enum."""

    def test_priority_ordering(self):
        """Test priority value ordering."""
        assert NotificationPriority.LOW.value < NotificationPriority.MEDIUM.value
        assert NotificationPriority.MEDIUM.value < NotificationPriority.HIGH.value
        assert NotificationPriority.HIGH.value < NotificationPriority.CRITICAL.value

    def test_priority_comparison(self):
        """Test priority comparison."""
        low = NotificationPriority.LOW
        high = NotificationPriority.HIGH
        assert low.value < high.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
