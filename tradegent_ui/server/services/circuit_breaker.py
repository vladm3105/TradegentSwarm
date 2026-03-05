"""Circuit breaker service for autonomous trading safety."""
import structlog
from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from ..database import get_db_connection

log = structlog.get_logger(__name__)
ET = ZoneInfo("America/New_York")


class CircuitBreaker:
    """Circuit breaker to halt trading on max loss.

    Note: Database operations use synchronous context manager.
    For truly async behavior, refactor to use get_async_connection().
    """

    def __init__(self):
        self._is_triggered = False
        self._triggered_at: Optional[datetime] = None

    async def check(self, daily_pnl: Decimal) -> bool:
        """Check if circuit breaker should trigger.

        Returns True if trading should be halted.
        """
        settings = self._get_settings_sync()

        if not settings['enabled']:
            return False

        if self._is_triggered:
            return True

        max_loss = Decimal(str(settings['max_daily_loss']))

        # Check absolute loss
        if daily_pnl < -max_loss:
            await self._trigger(f"Daily loss ${abs(daily_pnl)} exceeded max ${max_loss}")
            return True

        return False

    async def _trigger(self, reason: str):
        """Trigger circuit breaker."""
        self._is_triggered = True
        self._triggered_at = datetime.now(ET)

        log.critical(
            "circuit_breaker.triggered",
            reason=reason,
            triggered_at=self._triggered_at.isoformat(),
        )

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Update settings
                cur.execute("""
                    UPDATE nexus.settings
                    SET value = 'true', updated_at = NOW()
                    WHERE section = 'safety' AND key = 'circuit_breaker_triggered'
                """)
                cur.execute("""
                    UPDATE nexus.settings
                    SET value = %s, updated_at = NOW()
                    WHERE section = 'safety' AND key = 'circuit_breaker_triggered_at'
                """, (self._triggered_at.isoformat(),))

                # Pause trading
                cur.execute("""
                    UPDATE nexus.settings
                    SET value = 'true', updated_at = NOW()
                    WHERE section = 'trading' AND key = 'trading_paused'
                """)

                # Log event
                cur.execute("""
                    INSERT INTO nexus.circuit_breaker_log (reason, daily_pnl, threshold)
                    VALUES (%s, %s, %s)
                """, (reason, None, None))

                conn.commit()

        # Create critical notification
        self._notify_user_sync(reason)

    async def reset(self, user_id: str) -> bool:
        """Reset circuit breaker (requires confirmation)."""
        if not self._is_triggered:
            return False

        self._is_triggered = False
        self._triggered_at = None

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE nexus.settings
                    SET value = 'false', updated_at = NOW()
                    WHERE section = 'safety' AND key = 'circuit_breaker_triggered'
                """)
                cur.execute("""
                    UPDATE nexus.circuit_breaker_log
                    SET reset_at = NOW(), reset_by = %s
                    WHERE reset_at IS NULL
                    ORDER BY triggered_at DESC LIMIT 1
                """, (user_id,))
                conn.commit()

        log.warning("circuit_breaker.reset", user_id=user_id)
        return True

    def _get_settings_sync(self) -> dict:
        """Get circuit breaker settings (synchronous)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT key, value FROM nexus.settings
                    WHERE section = 'safety'
                """)
                rows = cur.fetchall()
                return {
                    'enabled': next((r['value'] == 'true' for r in rows if r['key'] == 'circuit_breaker_enabled'), True),
                    'max_daily_loss': next((r['value'] for r in rows if r['key'] == 'max_daily_loss'), '1000'),
                    'max_daily_loss_pct': next((r['value'] for r in rows if r['key'] == 'max_daily_loss_pct'), '5'),
                    'is_triggered': next((r['value'] == 'true' for r in rows if r['key'] == 'circuit_breaker_triggered'), False),
                }

    def _notify_user_sync(self, reason: str):
        """Create critical notification (synchronous)."""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO nexus.notifications (user_id, type, severity, title, message)
                    VALUES ('system', 'system', 'critical', 'Circuit Breaker Triggered', %s)
                """, (reason,))
                conn.commit()

    def load_state_from_db(self):
        """Load triggered state from database on startup."""
        settings = self._get_settings_sync()
        self._is_triggered = settings.get('is_triggered', False)

    @property
    def is_triggered(self) -> bool:
        return self._is_triggered

    @property
    def triggered_at(self) -> Optional[datetime]:
        return self._triggered_at


# Singleton instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
        _circuit_breaker.load_state_from_db()
    return _circuit_breaker
