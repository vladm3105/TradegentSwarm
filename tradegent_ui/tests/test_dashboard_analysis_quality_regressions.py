"""Regression tests for dashboard analysis-quality endpoint behavior."""

from __future__ import annotations

import asyncio

from tradegent_ui.server import dashboard


class _FakeCursor:
    def __init__(self) -> None:
        self.executed_sql: list[str] = []
        self._fetchone_queue = [{"pass_rate": 33.3}]
        self._fetchall_queue = [
            [
                {"recommendation": "BUY", "count": 4},
                {"recommendation": "WATCH", "count": 3},
            ],
            [
                {
                    "confidence_bucket": "60-69",
                    "accuracy": 51.0,
                    "count": 12,
                }
            ],
        ]

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def execute(self, sql: str, params=None) -> None:  # noqa: ANN001
        _ = params
        self.executed_sql.append(sql)

    def fetchone(self):
        return self._fetchone_queue.pop(0)

    def fetchall(self):
        return self._fetchall_queue.pop(0)


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def cursor(self) -> _FakeCursor:
        return self._cursor


def test_get_analysis_quality_uses_degraded_filter_and_returns_payload(monkeypatch) -> None:
    fake_cursor = _FakeCursor()
    fake_conn = _FakeConnection(fake_cursor)

    monkeypatch.setattr(dashboard, "get_db_connection", lambda: fake_conn)

    response = asyncio.run(dashboard.get_analysis_quality())

    assert response.gate_pass_rate == 33.3
    assert response.recommendation_distribution == {"BUY": 4, "WATCH": 3}
    assert len(response.accuracy_by_confidence) == 1
    assert response.accuracy_by_confidence[0].confidence_bucket == "60-69"

    # Regression guard: both quality queries must exclude degraded earnings analyses.
    sql_text = "\n".join(fake_cursor.executed_sql)
    assert "yaml_content->'adk_runtime'->>'degraded'" in sql_text
