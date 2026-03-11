"""Settings repository for settings upsert and user id lookup."""

from typing import Optional

from ..database import get_db_connection


def upsert_auth0_settings(domain: str, client_id: str, client_secret: str, audience: str) -> None:
    settings_to_save = [
        ("auth0", "domain", domain),
        ("auth0", "client_id", client_id),
        ("auth0", "client_secret", client_secret),
        ("auth0", "audience", audience),
    ]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for section, key, value in settings_to_save:
                cur.execute(
                    """
                    INSERT INTO nexus.settings (section, key, value)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (section, key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = now()
                    """,
                    (section, key, value),
                )
            conn.commit()


def get_user_id_by_sub(sub: str) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM nexus.users WHERE auth0_sub = %s", (sub,))
            row = cur.fetchone()
    return int(row["id"]) if row else 1
