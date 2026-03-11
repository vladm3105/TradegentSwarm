"""Unit tests for sessions_repository JSONB adaptation behavior."""

from psycopg.types.json import Jsonb

from tradegent_ui.server.repositories import sessions_repository


class _FakeCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query, params):
        self.executed.append((query, params))


class _FakeConn:
    def __init__(self):
        self.cur = _FakeCursor()
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True


def test_upsert_messages_wraps_a2ui_jsonb(monkeypatch):
    fake_conn = _FakeConn()
    monkeypatch.setattr(sessions_repository, "get_db_connection", lambda: fake_conn)

    sessions_repository.upsert_messages(
        session_db_id=1,
        messages=[
            {
                "message_id": "m1",
                "role": "assistant",
                "content": "hello",
                "status": "complete",
                "error": None,
                "a2ui": {"type": "panel", "value": 1},
                "task_id": None,
            }
        ],
    )

    assert fake_conn.committed is True
    assert len(fake_conn.cur.executed) == 1
    _, params = fake_conn.cur.executed[0]
    assert isinstance(params[6], Jsonb)
