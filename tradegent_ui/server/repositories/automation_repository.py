"""Automation repository — all SQL access for automation/circuit-breaker settings."""
from ..database import get_db_connection


def get_automation_settings() -> dict[str, str]:
    """Fetch all settings for the trading and safety sections."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key, value FROM nexus.settings
                WHERE section IN ('trading', 'safety')
            """)
            rows = cur.fetchall()
    return {r['key']: r['value'] for r in rows}


def set_trading_mode(mode: str, auto_execute: str, dry_run: str) -> None:
    """Update trading_mode, auto_execute_enabled, and dry_run_mode in settings."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_mode'
            """, (mode,))
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'auto_execute_enabled'
            """, (auto_execute,))
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'dry_run_mode'
            """, (dry_run,))
            conn.commit()


def set_trading_paused(paused: bool) -> None:
    """Set trading_paused flag (and record paused_at timestamp when pausing)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings
                SET value = %s, updated_at = NOW()
                WHERE section = 'trading' AND key = 'trading_paused'
            """, (str(paused).lower(),))
            if paused:
                cur.execute("""
                    UPDATE nexus.settings
                    SET value = NOW()::text, updated_at = NOW()
                    WHERE section = 'trading' AND key = 'trading_paused_at'
                """)
            conn.commit()


def get_circuit_breaker_settings() -> dict[str, str]:
    """Fetch circuit-breaker settings from the safety section."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT key, value FROM nexus.settings
                WHERE section = 'safety'
            """)
            rows = cur.fetchall()
    return {r['key']: r['value'] for r in rows}


def update_circuit_breaker_settings(
    enabled: bool,
    max_daily_loss: float,
    max_daily_loss_pct: float,
) -> None:
    """Persist circuit-breaker settings updates."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'circuit_breaker_enabled'
            """, (str(enabled).lower(),))
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'max_daily_loss'
            """, (str(max_daily_loss),))
            cur.execute("""
                UPDATE nexus.settings SET value = %s, updated_at = NOW()
                WHERE section = 'safety' AND key = 'max_daily_loss_pct'
            """, (str(max_daily_loss_pct),))
            conn.commit()
