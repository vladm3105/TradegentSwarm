"""Schedule management routes.

⚠️ UNIFIED MESSAGES MIGRATION:
These routes currently return raw responses. They should be updated to wrap
responses in the TradegentMessage envelope for consistency across the API.

See docs/COMMUNICATION_GUIDE.md for migration examples.

Example migration:

    FROM:
        @router.patch("/{schedule_id}")
        async def update_schedule(schedule_id: int, data: dict):
            return {"schedule_id": schedule_id}  # Raw dict

    TO:
        from ..messages import TradegentRequest, TradegentActions
        from ..response import wrap_response, error_to_response

        @router.post("/api")  # Use unified endpoint or wrap existing
        async def unified_api(request: TradegentRequest):
            if request.action == TradegentActions.PATCH_SCHEDULE:
                if request.payload.schedule_id <= 0:
                    return error_to_response(
                        action=request.action,
                        code="VALIDATION_ERROR",
                        message="Schedule ID must be positive",
                        request_id=request.request_id
                    )
                result = {"schedule_id": request.payload.schedule_id}
                return wrap_response(result, action=request.action, request_id=request.request_id)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, time
import structlog

from ..auth import get_current_user, UserClaims
from ..services import schedules_service

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class ScheduleResponse(BaseModel):
    id: int
    name: str
    task_type: str
    frequency: str
    is_enabled: bool
    time_of_day: Optional[time]
    day_of_week: Optional[str]
    interval_minutes: Optional[int]
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    last_run_status: Optional[str]
    fail_count: Optional[int]
    consecutive_fails: Optional[int]
    active_started_at: Optional[datetime] = None
    active_task_label: Optional[str] = None
    active_heartbeat_at: Optional[datetime] = None


class ScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    task_type: Optional[str] = None
    is_enabled: Optional[bool] = None
    frequency: Optional[str] = None
    time_of_day: Optional[time] = None
    day_of_week: Optional[str] = None
    interval_minutes: Optional[int] = None


class ScheduleCreateRequest(BaseModel):
    name: str
    task_type: str
    frequency: str
    is_enabled: bool = True
    time_of_day: Optional[time] = None
    day_of_week: Optional[str] = None
    interval_minutes: Optional[int] = None


@router.get("/", response_model=list[ScheduleResponse])
async def list_schedules(
    user: UserClaims = Depends(get_current_user),
) -> list[ScheduleResponse]:
    """List all scheduled tasks."""
    rows = schedules_service.list_schedules()
    return [ScheduleResponse(**row) for row in rows]


@router.post("/")
async def create_schedule(
    body: ScheduleCreateRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Create a new schedule."""
    result = schedules_service.create_schedule(
        name=body.name,
        task_type=body.task_type,
        frequency=body.frequency,
        is_enabled=body.is_enabled,
        time_of_day=body.time_of_day,
        day_of_week=body.day_of_week,
        interval_minutes=body.interval_minutes,
    )
    log.info("schedule.created", schedule_id=result["schedule_id"], user=user.email)
    return result


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
) -> ScheduleResponse:
    """Get a specific schedule."""
    row = schedules_service.get_schedule(schedule_id)
    return ScheduleResponse(**row)


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: int,
    body: ScheduleUpdateRequest,
    user: UserClaims = Depends(get_current_user),
):
    """Update a schedule."""
    updates: dict[str, object] = {}
    if "name" in body.model_fields_set:
        updates["name"] = body.name
    if "task_type" in body.model_fields_set:
        updates["task_type"] = body.task_type
    if "is_enabled" in body.model_fields_set:
        updates["is_enabled"] = body.is_enabled
    if "frequency" in body.model_fields_set:
        updates["frequency"] = body.frequency
    if "time_of_day" in body.model_fields_set:
        updates["time_of_day"] = body.time_of_day
    if "day_of_week" in body.model_fields_set:
        updates["day_of_week"] = body.day_of_week
    if "interval_minutes" in body.model_fields_set:
        updates["interval_minutes"] = body.interval_minutes

    result = schedules_service.update_schedule(schedule_id, updates)

    log.info("schedule.updated", schedule_id=schedule_id, user=user.email)
    return result


@router.post("/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Trigger a schedule to run immediately."""
    result = schedules_service.run_schedule_now(schedule_id)

    log.info("schedule.triggered", schedule_id=schedule_id, user=user.email)
    return result


@router.post("/{schedule_id}/enable")
async def enable_schedule(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Enable a schedule."""
    result = schedules_service.set_schedule_enabled(schedule_id, True)
    log.info("schedule.enabled", schedule_id=schedule_id, user=user.email)
    return result


@router.post("/{schedule_id}/disable")
async def disable_schedule(
    schedule_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Disable a schedule."""
    result = schedules_service.set_schedule_enabled(schedule_id, False)
    log.info("schedule.disabled", schedule_id=schedule_id, user=user.email)
    return result


@router.get("/history/{schedule_id}")
async def get_schedule_history(
    schedule_id: int,
    limit: int = 20,
    user: UserClaims = Depends(get_current_user),
):
    """Get run history for a schedule."""
    return schedules_service.get_schedule_history(schedule_id, limit)
