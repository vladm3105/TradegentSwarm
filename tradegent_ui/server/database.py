"""Database connection management for Tradegent Agent UI."""
import structlog
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

from .config import get_settings

log = structlog.get_logger()


def get_connection_string() -> str:
    """Build PostgreSQL connection string from settings."""
    settings = get_settings()
    return (
        f"postgresql://{settings.pg_user}:{settings.pg_pass}"
        f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_db}"
    )


@contextmanager
def get_db_connection() -> Generator[psycopg.Connection, None, None]:
    """Get a database connection with automatic cleanup.

    Usage:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM nexus.users")
                rows = cur.fetchall()

    Returns rows as dicts (psycopg3 dict_row).
    """
    conn = psycopg.connect(
        get_connection_string(),
        row_factory=dict_row,
    )
    try:
        yield conn
    finally:
        conn.close()


class DatabasePool:
    """Simple connection pool wrapper for async usage."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._pool = None

    async def get_pool(self):
        """Get or create async connection pool."""
        if self._pool is None:
            from psycopg_pool import AsyncConnectionPool

            settings = get_settings()
            conninfo = get_connection_string()

            self._pool = AsyncConnectionPool(
                conninfo=conninfo,
                min_size=2,
                max_size=10,
                kwargs={"row_factory": dict_row},
            )
            await self._pool.open()
            log.info("Database pool opened")

        return self._pool

    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            log.info("Database pool closed")


# Global pool instance
_db_pool = DatabasePool()


async def get_async_connection():
    """Get async database connection from pool."""
    pool = await _db_pool.get_pool()
    return pool.connection()


async def close_pool():
    """Close the global connection pool."""
    await _db_pool.close()


# Helper functions for common operations

async def get_user_by_sub(auth0_sub: str) -> dict | None:
    """Get user by Auth0 subject."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.users WHERE auth0_sub = %s",
                (auth0_sub,)
            )
            return cur.fetchone()


async def get_user_by_id(user_id: int) -> dict | None:
    """Get user by database ID."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.users WHERE id = %s",
                (user_id,)
            )
            return cur.fetchone()


async def get_user_roles(user_id: int) -> list[str]:
    """Get roles for a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.name
                FROM nexus.user_roles ur
                JOIN nexus.roles r ON ur.role_id = r.id
                WHERE ur.user_id = %s
            """, (user_id,))
            return [row["name"] for row in cur.fetchall()]


async def get_user_permissions(user_id: int) -> list[str]:
    """Get permissions for a user."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT nexus.get_user_permissions(%s) as permissions",
                (user_id,)
            )
            row = cur.fetchone()
            return row["permissions"] if row and row["permissions"] else []
