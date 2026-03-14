"""Integration tests for /ws/agent websocket protocol."""

import sys
import types
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tradegent_ui.server.auth import UserClaims
from tradegent_ui.server import main as server_main


class _FakeTaskManager:
    async def stop(self) -> None:
        return None

    async def submit(self, session_id: str, intent: str, query: str) -> str:
        return "task-1"

    async def stream_progress(self, task_id: str):
        yield {
            "type": "progress",
            "task_id": task_id,
            "state": "running",
            "progress": 50,
            "message": "Halfway",
        }
        yield {
            "type": "complete",
            "task_id": task_id,
            "state": "completed",
            "progress": 100,
            "result": {
                "success": True,
                "text": "Async response",
                "a2ui": None,
                "error": None,
            },
        }

    async def cancel_task(self, task_id: str) -> bool:
        return task_id == "task-cancel"


class _FakeCoordinator:
    async def process(self, session_id: str, content: str):
        return types.SimpleNamespace(
            success=True,
            text=f"Echo: {content}",
            a2ui=None,
            debug_metadata={},
            error=None,
        )


def _install_fake_coordinator_module() -> None:
    module = types.ModuleType("agent.coordinator")

    async def _get_coordinator():
        return _FakeCoordinator()

    module.get_coordinator = _get_coordinator
    sys.modules["agent.coordinator"] = module


def _patch_app_dependencies(monkeypatch, *, authorized: bool) -> None:
    fake_task_manager = _FakeTaskManager()

    async def _get_task_manager():
        return fake_task_manager

    monkeypatch.setattr(server_main, "get_task_manager", _get_task_manager)

    if authorized:
        async def _validate(_websocket):
            return UserClaims(sub="auth0|ws-user", email="ws@example.com", roles=["admin"]), None
    else:
        async def _validate(_websocket):
            return None, None

    monkeypatch.setattr(server_main, "validate_websocket_token", _validate)


def test_ws_agent_sync_happy_path(monkeypatch):
    """Synchronous chat messages return a response payload."""
    _patch_app_dependencies(monkeypatch, authorized=True)
    _install_fake_coordinator_module()

    with TestClient(server_main.app) as client:
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "message", "content": "hello", "async": False})
            payload = ws.receive_json()

    assert payload["type"] == "response"
    assert payload["success"] is True
    assert payload["text"] == "Echo: hello"


def test_ws_agent_async_lifecycle(monkeypatch):
    """Async chat emits task_created, progress, and complete events."""
    _patch_app_dependencies(monkeypatch, authorized=True)

    with TestClient(server_main.app) as client:
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "message", "content": "run async", "async": True})
            created = ws.receive_json()
            progress = ws.receive_json()
            complete = ws.receive_json()

    assert created["type"] == "task_created"
    assert created["task_id"] == "task-1"
    assert progress["type"] == "progress"
    assert progress["task_id"] == "task-1"
    assert complete["type"] == "complete"
    assert complete["result"]["text"] == "Async response"


def test_ws_agent_unsubscribe_cancels_task(monkeypatch):
    """Unsubscribe messages cancel active tasks when possible."""
    _patch_app_dependencies(monkeypatch, authorized=True)

    with TestClient(server_main.app) as client:
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json({"type": "unsubscribe", "task_id": "task-cancel"})
            response = ws.receive_json()

    assert response["type"] == "response"
    assert response["success"] is True
    assert response["text"] == "Task cancelled"


def test_ws_agent_rejects_unauthorized(monkeypatch):
    """Unauthorized websocket clients are closed with auth error code."""
    _patch_app_dependencies(monkeypatch, authorized=False)

    with TestClient(server_main.app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws/agent"):
                pass

    assert exc_info.value.code == 4001
