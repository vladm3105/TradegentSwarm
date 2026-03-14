"""Unit tests for schedules service layer."""

from fastapi import HTTPException

from tradegent_ui.server.services import schedules_service


def test_update_schedule_requires_updates() -> None:
    try:
        schedules_service.update_schedule(1, {})
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "No updates provided"


def test_get_schedule_history_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        schedules_service.schedules_repository,
        "get_schedule_identity",
        lambda schedule_id: None,
    )

    try:
        schedules_service.get_schedule_history(99, 20)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Schedule not found"


def test_get_schedule_history_success(monkeypatch) -> None:
    class DummyTime:
        def __init__(self, value: str):
            self._value = value

        def isoformat(self) -> str:
            return self._value

    monkeypatch.setattr(
        schedules_service.schedules_repository,
        "get_schedule_identity",
        lambda schedule_id: {"name": "Daily Scan", "task_type": "run_scanner"},
    )
    monkeypatch.setattr(
        schedules_service.schedules_repository,
        "get_run_history",
        lambda task_type, limit: [
            {
                "id": 1,
                "started_at": DummyTime("2026-03-11T10:00:00"),
                "completed_at": DummyTime("2026-03-11T10:00:08"),
                "status": "success",
                "duration_seconds": 8.0,
            }
        ],
    )

    result = schedules_service.get_schedule_history(1, 5)
    assert result["schedule_id"] == 1
    assert result["schedule_name"] == "Daily Scan"
    assert len(result["runs"]) == 1
    assert result["runs"][0]["status"] == "success"


def test_set_schedule_enabled_success(monkeypatch) -> None:
    monkeypatch.setattr(
        schedules_service.schedules_repository,
        "update_schedule",
        lambda schedule_id, updates: schedule_id == 7 and updates == {"is_enabled": False},
    )

    result = schedules_service.set_schedule_enabled(7, False)

    assert result == {"success": True, "schedule_id": 7, "is_enabled": False}


def test_set_schedule_enabled_not_found(monkeypatch) -> None:
    monkeypatch.setattr(
        schedules_service.schedules_repository,
        "update_schedule",
        lambda schedule_id, updates: False,
    )

    try:
        schedules_service.set_schedule_enabled(404, True)
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 404
        assert exc.detail == "Schedule not found"
