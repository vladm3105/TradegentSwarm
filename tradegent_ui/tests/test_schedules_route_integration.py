"""Integration-style tests for schedules routes with service layer wiring."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.auth import UserClaims, get_current_user
from tradegent_ui.server.routes.schedules import router as schedules_router
from tradegent_ui.server.routes import schedules as schedules_route_module


def _fake_user() -> UserClaims:
    return UserClaims(
        sub="test-user",
        email="test@example.com",
        name="Test User",
        roles=["admin"],
        permissions=["manage:schedules"],
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(schedules_router)
    app.dependency_overrides[get_current_user] = _fake_user
    return app


def test_list_schedules_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(
        schedules_route_module.schedules_service,
        "list_schedules",
        lambda: [
            {
                "id": 1,
                "name": "Daily Scan",
                "task_type": "run_scanner",
                "frequency": "daily",
                "is_enabled": True,
                "time_of_day": "09:30",
                "day_of_week": None,
                "interval_minutes": None,
                "next_run_at": None,
                "last_run_at": None,
                "last_run_status": None,
                "fail_count": 0,
                "consecutive_fails": 0,
            }
        ],
    )

    client = TestClient(_build_app())
    response = client.get("/api/schedules/")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Daily Scan"


def test_patch_schedule_route_calls_service(monkeypatch) -> None:
    captured = {}

    def _update(schedule_id: int, updates: dict):
        captured["schedule_id"] = schedule_id
        captured["updates"] = updates
        return {"success": True, "schedule_id": schedule_id}

    monkeypatch.setattr(
        schedules_route_module.schedules_service,
        "update_schedule",
        _update,
    )

    client = TestClient(_build_app())
    response = client.patch(
        "/api/schedules/7",
        json={"is_enabled": False, "interval_minutes": 30},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "schedule_id": 7}
    assert captured["schedule_id"] == 7
    assert captured["updates"] == {"is_enabled": False, "interval_minutes": 30}
