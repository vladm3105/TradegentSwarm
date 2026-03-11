"""Integration tests for scanners routes with service delegation."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tradegent_ui.server.routes.scanners import router as scanners_router
from tradegent_ui.server.routes import scanners as scanners_route_module


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(scanners_router)
    return app


def test_scanner_list_route_delegates(monkeypatch):
    monkeypatch.setattr(
        scanners_route_module.scanners_service,
        "list_scanners",
        lambda scanner_type, enabled_only: [
            {
                "id": 1,
                "scanner_code": "TOP_GAINERS",
                "name": "Top Gainers",
                "description": None,
                "scanner_type": "STK",
                "is_enabled": True,
                "auto_analyze": False,
                "analysis_type": None,
                "last_run": None,
                "last_run_status": None,
                "candidates_count": 0,
            }
        ],
    )

    client = TestClient(_build_app())
    resp = client.get("/api/scanners/list")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
