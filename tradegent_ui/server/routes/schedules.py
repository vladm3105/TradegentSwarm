"""Schedule management routes."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import structlog

from ..auth import get_current_user, UserClaims
from ..database import get_db_connection

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleResponse(BaseModel):
    id: int
    name: str
    task_type: str
    frequency: str
    parameters: Optional[dict]
    is_enabled: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]


class ScheduleUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    frequency: Optional[str] = None
    parameters: Optional[dict] = None


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(
    user: UserClaims = Depends(get_current_user),
) -> list[ScheduleResponse]:
    """List all scheduled tasks."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, name, task_type, frequency, parameters,
                    is_enabled, next_run_at, last_run_at, last_run_status
                FROM nexus.schedules
                ORDER BY next_run_at ASC NULLS LAST
            """)
            rows = cur.fetchall()

    return [ScheduleResponse(**row) for row in rows]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
) -> ScheduleResponse:
    """Get a specific schedule."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    id, name, task_type, frequency, parameters,
                    is_enabled, next_run_at, last_run_at, last_run_status
                FROM nexus.schedules
                WHERE id = %s
            """, (schedule_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(404, "Schedule not found")

    return ScheduleResponse(**row)


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdateRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Update a schedule."""
    updates = []
    params = []

    if body.is_enabled is not None:
        updates.append("is_enabled = %s")
        params.append(body.is_enabled)

    if body.frequency is not None:
        updates.append("frequency = %s")
        params.append(body.frequency)

    if body.parameters is not None:
        updates.append("parameters = %s::jsonb")
        import json
        params.append(json.dumps(body.parameters))

    if not updates:
        raise HTTPException(400, "No updates provided")

    params.append(schedule_id)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                UPDATE nexus.schedules
                SET {", ".join(updates)}, updated_at = NOW()
                WHERE id = %s
                RETURNING id
            """, tuple(params))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(404, "Schedule not found")

    log.info("schedule.updated", schedule_id=schedule_id, user=user.email)
    return {"success": True, "schedule_id": schedule_id}


@router.post("/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Trigger a schedule to run immediately."""
    # Update next_run_at to now to trigger immediate execution
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.schedules
                SET next_run_at = NOW(), updated_at = NOW()
                WHERE id = %s AND is_enabled = true
                RETURNING id, name
            """, (schedule_id,))
            row = cur.fetchone()
            conn.commit()

    if not row:
        raise HTTPException(404, "Schedule not found or not enabled")

    log.info("schedule.triggered", schedule_id=schedule_id, name=row['name'], user=user.email)
    return {"success": True, "message": f"Schedule '{row['name']}' triggered"}


@router.get("/history/{schedule_id}")
async def get_schedule_history(
    schedule_id: int,
    limit: int = 20,
    user: UserClaims = Depends(get_current_user),
):
    """Get run history for a schedule."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Get schedule name
            cur.execute("SELECT name, task_type FROM nexus.schedules WHERE id = %s", (schedule_id,))
            schedule = cur.fetchone()
            if not schedule:
                raise HTTPException(404, "Schedule not found")

            # Get run history
            cur.execute("""
                SELECT
                    id, started_at, completed_at, status,
                    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds,
                    raw_output
                FROM nexus.run_history
                WHERE task_type = %s
                ORDER BY started_at DESC
                LIMIT %s
            """, (schedule['task_type'], limit))
            runs = cur.fetchall()

    return {
        "schedule_id": schedule_id,
        "schedule_name": schedule['name'],
        "runs": [
            {
                "id": r['id'],
                "started_at": r['started_at'].isoformat() if r['started_at'] else None,
                "completed_at": r['completed_at'].isoformat() if r['completed_at'] else None,
                "status": r['status'],
                "duration_seconds": r['duration_seconds'],
            }
            for r in runs
        ],
    }
