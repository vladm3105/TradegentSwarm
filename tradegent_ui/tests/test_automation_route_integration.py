"""Route integration tests for automation endpoints."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.routes.automation import router as automation_router
from tradegent_ui.server.routes import automation as automation_route_module
from tradegent_ui.server.auth import get_current_user, UserClaims


def _build_app() -> FastAPI:
    app = FastAPI()
    fake_user = UserClaims(sub="u1", email="test@test.com", roles=["admin"])
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.include_router(automation_router)
    return app


def test_get_automation_status_route(monkeypatch) -> None:
    """GET /api/automation/status delegates to automation_service."""
    status_data = {
        "mode": "dry_run",
        "auto_execute": False,
        "is_paused": False,
        "circuit_breaker_triggered": False,
        "circuit_breaker_triggered_at": None,
    }
    monkeypatch.setattr(
        automation_route_module.automation_service,
        "get_automation_status",
        lambda: status_data,
    )
    client = TestClient(_build_app())
    resp = client.get("/api/automation/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "dry_run"
    assert body["auto_execute"] is False


def test_pause_trading_route(monkeypatch) -> None:
    """POST /api/automation/pause delegates to automation_service."""
    monkeypatch.setattr(
        automation_route_module.automation_service,
        "pause_trading",
        lambda: {"success": True, "paused": True},
    )
    client = TestClient(_build_app())
    resp = client.post("/api/automation/pause")

    assert resp.status_code == 200
    assert resp.json()["paused"] is True
