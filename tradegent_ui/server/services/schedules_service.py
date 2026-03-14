"""Business logic service for schedule operations."""

from __future__ import annotations

from typing import Any
from typing import Optional

from fastapi import HTTPException

from ..repositories import schedules_repository


def list_schedules() -> list[dict[str, Any]]:
    return schedules_repository.list_schedules()


def create_schedule(
    name: str,
    task_type: str,
    frequency: str,
    is_enabled: bool = True,
    time_of_day: Optional[Any] = None,
    day_of_week: Optional[str] = None,
    interval_minutes: Optional[int] = None,
) -> dict[str, Any]:
    if not name.strip():
        raise HTTPException(400, "Schedule name is required")
    if not task_type.strip():
        raise HTTPException(400, "Task type is required")
    if not frequency.strip():
        raise HTTPException(400, "Frequency is required")

    schedule_id = schedules_repository.create_schedule(
        {
            "name": name.strip(),
            "task_type": task_type.strip(),
            "frequency": frequency.strip(),
            "is_enabled": is_enabled,
            "time_of_day": time_of_day,
            "day_of_week": day_of_week,
            "interval_minutes": interval_minutes,
        }
    )

    return {"success": True, "schedule_id": schedule_id}


def get_schedule(schedule_id: int) -> dict[str, Any]:
    row = schedules_repository.get_schedule(schedule_id)
    if not row:
        raise HTTPException(404, "Schedule not found")
    return row


def update_schedule(schedule_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    if not updates:
        raise HTTPException(400, "No updates provided")

    updated = schedules_repository.update_schedule(schedule_id, updates)
    if not updated:
        raise HTTPException(404, "Schedule not found")

    return {"success": True, "schedule_id": schedule_id}


def set_schedule_enabled(schedule_id: int, enabled: bool) -> dict[str, Any]:
    updated = schedules_repository.update_schedule(schedule_id, {"is_enabled": enabled})
    if not updated:
        raise HTTPException(404, "Schedule not found")

    return {"success": True, "schedule_id": schedule_id, "is_enabled": enabled}


def run_schedule_now(schedule_id: int) -> dict[str, Any]:
    row = schedules_repository.trigger_schedule_now(schedule_id)
    if not row:
        raise HTTPException(404, "Schedule not found or not enabled")

    return {"success": True, "message": f"Schedule '{row['name']}' triggered"}


def get_schedule_history(schedule_id: int, limit: int = 20) -> dict[str, Any]:
    schedule = schedules_repository.get_schedule_identity(schedule_id)
    if not schedule:
        raise HTTPException(404, "Schedule not found")

    runs = schedules_repository.get_run_history(schedule["task_type"], limit)

    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule["name"],
        "runs": [
            {
                "id": r["id"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "status": r["status"],
                "duration_seconds": r["duration_seconds"],
            }
            for r in runs
        ],
    }
