"""Integration and unit tests for backend-authoritative chat logging."""

from __future__ import annotations

import sys
import types

import pytest
from fastapi.testclient import TestClient

from tradegent_ui.server import main as server_main
from tradegent_ui.server.auth import UserClaims
from tradegent_ui.server.task_manager import AgentTask, TaskManager, TaskState


class _SyncCoordinator:
    async def process(self, session_id: str, content: str):
        return types.SimpleNamespace(
            success=True,
            text=f"Echo: {content}",
            a2ui={"type": "a2ui", "text": f"Echo: {content}", "components": []},
            debug_metadata={},
            error=None,
        )


def _install_sync_coordinator() -> None:
    module = types.ModuleType("agent.coordinator")

    async def _get_coordinator():
        return _SyncCoordinator()

    setattr(module, "get_coordinator", _get_coordinator)
    sys.modules["agent.coordinator"] = module


@pytest.mark.asyncio
async def test_rest_chat_roundtrip_persists_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """REST sync /api/chat persists one user+assistant roundtrip."""
    calls: list[dict] = []

    async def _fake_get_required_user(_req):
        return UserClaims(sub="auth0|u1", email="u1@example.com", roles=["admin"])

    def _fake_persist_roundtrip_messages(**kwargs):
        calls.append(kwargs)
        return {"success": True, "messages_saved": 2}

    monkeypatch.setattr(server_main, "get_required_user", _fake_get_required_user)
    monkeypatch.setattr(
        server_main.sessions_service,
        "persist_roundtrip_messages",
        _fake_persist_roundtrip_messages,
    )
    _install_sync_coordinator()

    with TestClient(server_main.app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "hello from rest", "async_mode": False, "session_id": "rest-session-1"},
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True

    assert len(calls) == 1
    persisted = calls[0]
    assert persisted["auth_sub"] == "auth0|u1"
    assert persisted["session_id"] == "rest-session-1"
    assert persisted["user_content"] == "hello from rest"
    assert persisted["assistant_content"] == "Echo: hello from rest"
    assert persisted["assistant_status"] == "complete"


def test_ws_chat_roundtrip_persists_records(monkeypatch: pytest.MonkeyPatch) -> None:
    """WS sync chat roundtrip persists one user+assistant record pair."""
    calls: list[dict] = []

    async def _fake_validate(_websocket):
        return UserClaims(sub="auth0|ws-user", email="ws@example.com", roles=["admin"]), None

    def _fake_persist_roundtrip_messages(**kwargs):
        calls.append(kwargs)
        return {"success": True, "messages_saved": 2}

    monkeypatch.setattr(server_main, "validate_websocket_token", _fake_validate)
    monkeypatch.setattr(
        server_main.sessions_service,
        "persist_roundtrip_messages",
        _fake_persist_roundtrip_messages,
    )
    _install_sync_coordinator()

    with TestClient(server_main.app) as client:
        with client.websocket_connect("/ws/agent") as ws:
            ws.send_json(
                {
                    "type": "message",
                    "content": "hello from ws",
                    "async": False,
                    "session_id": "ws-session-1",
                }
            )
            payload = ws.receive_json()

    assert payload["type"] == "response"
    assert payload["success"] is True

    assert len(calls) == 1
    persisted = calls[0]
    assert persisted["auth_sub"] == "auth0|ws-user"
    assert persisted["session_id"] == "ws-session-1"
    assert persisted["user_content"] == "hello from ws"
    assert persisted["assistant_content"] == "Echo: hello from ws"
    assert persisted["assistant_status"] == "complete"


@pytest.mark.asyncio
async def test_async_task_completion_persists_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """Async task completion persists one user+assistant roundtrip."""
    calls: list[dict] = []

    def _fake_persist_roundtrip_messages(**kwargs):
        calls.append(kwargs)
        return {"success": True, "messages_saved": 2}

    # Install fake coordinator used by TaskManager._process_task import path.
    _install_sync_coordinator()

    import tradegent_ui.server.task_manager as task_manager_module

    monkeypatch.setattr(
        task_manager_module.sessions_service,
        "persist_roundtrip_messages",
        _fake_persist_roundtrip_messages,
    )

    manager = TaskManager(max_concurrent=1)
    task = AgentTask(
        session_id="auth0|task-user",
        intent="chat",
        query="async hello",
        state=TaskState.QUEUED,
    )

    await manager._process_task(task, worker_id=1)

    assert task.state == TaskState.COMPLETED
    assert len(calls) == 1
    persisted = calls[0]
    assert persisted["auth_sub"] == "auth0|task-user"
    assert persisted["session_id"] == "auth0|task-user"
    assert persisted["user_content"] == "async hello"
    assert persisted["assistant_content"] == "Echo: async hello"
    assert persisted["assistant_status"] == "complete"
    assert persisted["task_id"] == task.task_id
