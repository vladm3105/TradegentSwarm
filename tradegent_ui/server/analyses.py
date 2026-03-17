"""
Analyses API endpoints.
Serves stock analysis data from the knowledge base.
"""

import logging
import math
from typing import Any, Optional
from datetime import datetime, timezone
from pathlib import Path
import zlib

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
import yaml

from .config import get_settings
from .auth import UserClaims, get_current_user, get_db_user_id

router = APIRouter(prefix="/api/analyses", tags=["analyses"])
log = logging.getLogger(__name__)

_DECLINED_ID_OFFSET = 2_000_000_000
_EARNINGS_ID_OFFSET = 1_000_000_000
_DECLINED_DIR = (
    Path(__file__).resolve().parents[2]
    / "tradegent_knowledge"
    / "knowledge"
    / "analysis"
    / "declined"
)

_settings = get_settings()

DB_CONFIG = {
    "host": _settings.pg_host,
    "port": _settings.pg_port,
    "user": _settings.pg_user,
    "password": _settings.pg_pass,
    "dbname": _settings.pg_db,
}


def get_db_connection():
    """Get database connection."""
    return psycopg.connect(
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        dbname=DB_CONFIG["dbname"],
        row_factory=dict_row,
    )


def _to_float(value: object) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        parsed = float(value)
        return None if math.isnan(parsed) else parsed
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return None if math.isnan(parsed) else parsed
    return None


def _to_int(value: object) -> Optional[int]:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_gate_result(payload: dict[str, Any], row_value: object) -> str:
    gate = _as_dict(payload.get("do_nothing_gate"))
    value = gate.get("gate_result") if gate.get("gate_result") is not None else row_value
    if isinstance(value, str) and value.strip():
        return value.strip().upper()
    return "FAIL"


def _extract_expected_value(payload: dict[str, Any], row_value: object) -> Optional[float]:
    gate = _as_dict(payload.get("do_nothing_gate"))
    for candidate in (gate.get("ev_actual"), gate.get("expected_value_actual"), row_value):
        parsed = _to_float(candidate)
        if parsed is not None:
            return parsed
    return None


def _extract_confidence(payload: dict[str, Any], row_value: object) -> Optional[int]:
    gate = _as_dict(payload.get("do_nothing_gate"))
    recommendation = _as_dict(payload.get("recommendation"))
    decision = _as_dict(payload.get("decision"))
    probability = _as_dict(payload.get("probability"))

    for candidate in (
        gate.get("confidence_actual"),
        row_value,
        recommendation.get("confidence"),
        decision.get("confidence_pct"),
        probability.get("confidence_pct"),
    ):
        parsed = _to_int(candidate)
        if parsed is not None:
            return max(0, min(100, parsed))
    return None


def _declined_analysis_id(file_name: str) -> int:
    return _DECLINED_ID_OFFSET + (zlib.crc32(file_name.encode("utf-8")) & 0x7FFFFFFF)


async def _resolve_user_id(user: UserClaims) -> int:
    # Builtin demo/admin users are system-local and map to admin seed user.
    if user.sub.startswith("builtin|"):
        return 1

    user_id = await get_db_user_id(user.sub)
    if not user_id:
        raise HTTPException(status_code=403, detail="User is not provisioned in database")
    return user_id


def _collect_declined_rows(
    *,
    ticker: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> list[dict]:
    if status_filter in {"completed", "expired", "error"}:
        return []

    if not _DECLINED_DIR.exists():
        return []

    token = (ticker or "").strip().upper()
    pattern = f"{token}_*.yaml" if token else "*.yaml"
    rows: list[dict] = []

    for path in sorted(_DECLINED_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        meta = _as_dict(payload.get("_meta"))
        recommendation = _as_dict(payload.get("recommendation"))
        gate = _as_dict(payload.get("do_nothing_gate"))
        decline = _as_dict(payload.get("decline"))
        confidence_value = _extract_confidence(payload, recommendation.get("confidence"))
        expected_value = _extract_expected_value(payload, gate.get("ev_actual") or gate.get("expected_value_actual"))
        gate_result = _extract_gate_result(payload, gate.get("gate_result"))

        created_raw = meta.get("created")
        created_iso = ""
        created_dt: Optional[datetime] = None
        if isinstance(created_raw, str) and created_raw.strip():
            try:
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                created_iso = created_dt.isoformat()
            except ValueError:
                created_iso = created_raw

        file_name = path.name
        raw_status = str(meta.get("status") or "declined").strip().lower()
        status_value = raw_status if raw_status.startswith("inactive_") else "declined"

        rows.append(
            {
                "id": _declined_analysis_id(file_name),
                "ticker": str(payload.get("ticker") or path.stem.split("_")[0]).upper(),
                "analysis_date": created_iso,
                "analysis_dt": created_dt,
                "schema_version": str(meta.get("version", "2.7")),
                "file_path": str(path),
                "recommendation": recommendation.get("action"),
                "confidence": confidence_value,
                "expected_value_pct": expected_value,
                "gate_result": gate_result,
                "current_price": payload.get("current_price"),
                "yaml_content": payload,
                "analysis_type": str(meta.get("type") or "stock-analysis"),
                "status": status_value,
                "decline_reason": decline.get("reason"),
            }
        )

    return rows


def _row_to_summary(row: dict) -> "AnalysisSummary":
    payload = _as_dict(row.get("yaml_content"))
    confidence = _extract_confidence(payload, row.get("confidence"))
    expected_value = _extract_expected_value(payload, row.get("expected_value_pct"))
    gate_result = _extract_gate_result(payload, row.get("gate_result"))

    analysis_date = row.get("analysis_date")
    if isinstance(analysis_date, datetime):
        analysis_date_str = analysis_date.isoformat()
    elif isinstance(analysis_date, str):
        analysis_date_str = analysis_date
    else:
        analysis_date_str = ""

    return AnalysisSummary(
        id=row["id"],
        ticker=row["ticker"],
        type=row.get("analysis_type") or "stock",
        recommendation=row.get("recommendation"),
        confidence=confidence,
        gate_result=gate_result,
        expected_value=expected_value,
        analysis_date=analysis_date_str,
        status=row.get("status") or "completed",
        schema_version=str(row.get("schema_version") or ""),
    )


def _row_sort_epoch(row: dict) -> float:
    """Return sortable epoch seconds from row analysis datetime fields."""
    candidate = row.get("analysis_date")
    if isinstance(candidate, str) and candidate.strip():
        try:
            candidate = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        except ValueError:
            candidate = None
    if not isinstance(candidate, datetime):
        candidate = row.get("analysis_dt")
    if not isinstance(candidate, datetime):
        return 0.0
    if candidate.tzinfo is None:
        candidate = candidate.replace(tzinfo=timezone.utc)
    return candidate.timestamp()


def _row_to_detail(row: dict) -> "AnalysisDetailResponse":
    payload = _as_dict(row.get("yaml_content"))
    confidence = _extract_confidence(payload, row.get("confidence"))
    expected_value = _extract_expected_value(payload, row.get("expected_value_pct"))
    gate_result = _extract_gate_result(payload, row.get("gate_result"))

    analysis_date = row.get("analysis_date")
    if isinstance(analysis_date, datetime):
        analysis_date_str = analysis_date.isoformat()
    elif isinstance(analysis_date, str):
        analysis_date_str = analysis_date
    else:
        analysis_date_str = ""

    # Prefer explicit row status (e.g. declined, error), then _meta.status in YAML,
    # then fall back to date-derived completed/expired. Normalize legacy 'active' → 'completed'.
    row_status = row.get("status")
    yaml_content = payload
    if row_status and row_status not in {"active", "completed", "expired"}:
        status = row_status
    else:
        meta = _as_dict(yaml_content.get("_meta"))
        raw = str(meta.get("status") or row_status or "completed")
        status = "completed" if raw == "active" else raw

    return AnalysisDetailResponse(
        id=row["id"],
        ticker=row["ticker"],
        analysis_date=analysis_date_str,
        schema_version=str(row.get("schema_version") or ""),
        file_path=row.get("file_path") or "",
        recommendation=row.get("recommendation"),
        confidence=confidence,
        gate_result=gate_result,
        expected_value=expected_value,
        current_price=_to_float(row.get("current_price")),
        status=status,
        yaml_content=yaml_content,
    )


# Response models
class AnalysisSummary(BaseModel):
    """Summary for analysis list."""
    id: int
    ticker: str
    type: str
    recommendation: Optional[str] = None
    confidence: Optional[int] = None
    gate_result: Optional[str] = None
    expected_value: Optional[float] = None
    analysis_date: str
    status: str
    schema_version: str


class AnalysisListResponse(BaseModel):
    """Response for analysis list."""
    analyses: list[AnalysisSummary]
    total: int


class AnalysisDetailResponse(BaseModel):
    """Full analysis detail response."""
    id: int
    ticker: str
    analysis_date: str
    schema_version: str
    file_path: str
    recommendation: Optional[str] = None
    confidence: Optional[int] = None
    gate_result: Optional[str] = None
    expected_value: Optional[float] = None
    current_price: Optional[float] = None
    status: str = "completed"
    yaml_content: dict


@router.get("/list", response_model=AnalysisListResponse)
async def list_analyses(
    status: Optional[str] = Query(
        None,
        pattern=(
            "^(completed|expired|declined|error|all|"
            "inactive_quality_failed|inactive_data_unavailable|inactive_schema_failed)$"
        ),
    ),
    analysis_type: str = Query("all", pattern="^(stock|earnings|all)$"),
    include_declined: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: UserClaims = Depends(get_current_user),
):
    """List analyses with optional filtering."""
    try:
        user_id = await _resolve_user_id(user)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build query
                conditions = ["user_id = %s"]
                params: list[object] = [user_id]
                if status == "completed":
                    # Completed: recent analysis, not explicitly declined or error
                    conditions.append("analysis_date >= CURRENT_DATE - INTERVAL '30 days'")
                    conditions.append(
                        "COALESCE(yaml_content->'_meta'->>'status', '') NOT IN "
                        "('declined', 'error', 'inactive_quality_failed', 'inactive_data_unavailable', 'inactive_schema_failed')"
                    )
                elif status == "expired":
                    conditions.append("analysis_date < CURRENT_DATE - INTERVAL '30 days'")
                    conditions.append(
                        "COALESCE(yaml_content->'_meta'->>'status', '') NOT IN "
                        "('declined', 'error', 'inactive_quality_failed', 'inactive_data_unavailable', 'inactive_schema_failed')"
                    )
                elif status == "declined":
                    conditions.append(
                        "yaml_content->'_meta'->>'status' IN "
                        "('declined', 'inactive_quality_failed', 'inactive_data_unavailable', 'inactive_schema_failed')"
                    )
                elif status == "error":
                    conditions.append("yaml_content->'_meta'->>'status' = 'error'")
                elif status in {
                    "inactive_quality_failed",
                    "inactive_data_unavailable",
                    "inactive_schema_failed",
                }:
                    conditions.append("yaml_content->'_meta'->>'status' = %s")
                    params.append(status)
                where_clause = "WHERE " + " AND ".join(conditions)

                # Declined folder files: show to all authenticated users
                show_declined_files = include_declined and status in {None, "all", "declined"}
                db_limit = limit + offset
                db_offset = 0

                total = 0
                combined_rows: list[dict] = []

                if analysis_type in {"all", "stock"} and status != "declined":
                    cur.execute(
                        f"SELECT COUNT(*) as cnt FROM nexus.kb_stock_analyses {where_clause}",
                        params,
                    )
                    total += cur.fetchone()["cnt"]

                    cur.execute(f"""
                        SELECT
                            id,
                            ticker,
                            analysis_date,
                            schema_version,
                            recommendation,
                            confidence,
                            expected_value_pct,
                            gate_result,
                            current_price,
                            file_path,
                            yaml_content,
                            COALESCE(yaml_content->>'analysis_type', 'stock') as analysis_type,
                            CASE
                                WHEN yaml_content->'_meta'->>'status' IN (
                                    'declined',
                                    'error',
                                    'completed',
                                    'expired',
                                    'inactive_quality_failed',
                                    'inactive_data_unavailable',
                                    'inactive_schema_failed'
                                )
                                    THEN yaml_content->'_meta'->>'status'
                                WHEN analysis_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'completed'
                                ELSE 'expired'
                            END as status
                        FROM nexus.kb_stock_analyses
                        {where_clause}
                        ORDER BY analysis_date DESC
                        LIMIT %s OFFSET %s
                    """, params + [db_limit, db_offset])
                    combined_rows.extend(dict(row) for row in cur.fetchall())

                if analysis_type in {"all", "earnings"} and status != "declined":
                    cur.execute(
                        f"SELECT COUNT(*) as cnt FROM nexus.kb_earnings_analyses {where_clause}",
                        params,
                    )
                    total += cur.fetchone()["cnt"]

                    cur.execute(f"""
                        SELECT
                            id,
                            ticker,
                            analysis_date,
                            schema_version,
                            recommendation,
                            confidence,
                            expected_value_pct,
                            gate_result,
                            NULL::numeric as current_price,
                            file_path,
                            yaml_content,
                            COALESCE(yaml_content->>'analysis_type', 'earnings') as analysis_type,
                            CASE
                                WHEN yaml_content->'_meta'->>'status' IN (
                                    'declined',
                                    'error',
                                    'completed',
                                    'expired',
                                    'inactive_quality_failed',
                                    'inactive_data_unavailable',
                                    'inactive_schema_failed'
                                )
                                    THEN yaml_content->'_meta'->>'status'
                                WHEN analysis_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'completed'
                                ELSE 'expired'
                            END as status
                        FROM nexus.kb_earnings_analyses
                        {where_clause}
                        ORDER BY analysis_date DESC
                        LIMIT %s OFFSET %s
                    """, params + [db_limit, db_offset])
                    for row in cur.fetchall():
                        entry = dict(row)
                        entry["id"] = _EARNINGS_ID_OFFSET + int(entry["id"])
                        combined_rows.append(entry)

                # Declined artifacts are file-backed; visible to all authenticated users.
                declined_rows: list[dict] = []
                if show_declined_files and analysis_type in {"all", "stock"}:
                    declined_rows = _collect_declined_rows(status_filter=status)
                    combined_rows.extend(declined_rows)

                combined_rows.sort(key=_row_sort_epoch, reverse=True)

                paged_rows = combined_rows[offset: offset + limit]
                analyses = [_row_to_summary(row) for row in paged_rows]

                return AnalysisListResponse(
                    analyses=analyses,
                    total=total + len(declined_rows),
                )

    except Exception as e:
        log.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis_detail(
    analysis_id: int,
    user: UserClaims = Depends(get_current_user),
):
    """Get full analysis detail by ID."""
    try:
        if _EARNINGS_ID_OFFSET <= analysis_id < _DECLINED_ID_OFFSET:
            earnings_id = analysis_id - _EARNINGS_ID_OFFSET
            user_id = await _resolve_user_id(user)
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            %s as id,
                            ticker,
                            analysis_date,
                            schema_version,
                            file_path,
                            recommendation,
                            confidence,
                            expected_value_pct,
                            gate_result,
                            NULL::numeric as current_price,
                            yaml_content
                        FROM nexus.kb_earnings_analyses
                        WHERE id = %s AND user_id = %s
                        """,
                        (analysis_id, earnings_id, user_id),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail="Analysis not found")
                    return _row_to_detail(dict(row))

        if analysis_id >= _DECLINED_ID_OFFSET:
            if "admin" not in user.roles:
                raise HTTPException(status_code=403, detail="Declined analyses require admin role")
            for row in _collect_declined_rows():
                if row["id"] == analysis_id:
                    return _row_to_detail(row)
            raise HTTPException(status_code=404, detail="Declined analysis not found")

        user_id = await _resolve_user_id(user)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        ticker,
                        analysis_date,
                        schema_version,
                        file_path,
                        recommendation,
                        confidence,
                        expected_value_pct,
                        gate_result,
                        current_price,
                        yaml_content
                    FROM nexus.kb_stock_analyses
                        WHERE id = %s AND user_id = %s
                    """, (analysis_id, user_id))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Analysis not found")

                return _row_to_detail(dict(row))

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get analysis detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-ticker/{ticker}", response_model=AnalysisDetailResponse)
async def get_latest_analysis_by_ticker(
    ticker: str,
    user: UserClaims = Depends(get_current_user),
):
    """Get most recent analysis for a ticker."""
    try:
        user_id = await _resolve_user_id(user)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    WITH latest_stock AS (
                        SELECT
                            id,
                            ticker,
                            analysis_date,
                            schema_version,
                            file_path,
                            recommendation,
                            confidence,
                            expected_value_pct,
                            gate_result,
                            current_price,
                            yaml_content
                        FROM nexus.kb_stock_analyses
                        WHERE ticker = %s AND user_id = %s
                        ORDER BY analysis_date DESC
                        LIMIT 1
                    ),
                    latest_earnings AS (
                        SELECT
                            (%s + id) as id,
                            ticker,
                            analysis_date,
                            schema_version,
                            file_path,
                            recommendation,
                            confidence,
                            expected_value_pct,
                            gate_result,
                            NULL::numeric as current_price,
                            yaml_content
                        FROM nexus.kb_earnings_analyses
                        WHERE ticker = %s AND user_id = %s
                        ORDER BY analysis_date DESC
                        LIMIT 1
                    )
                    SELECT *
                    FROM (
                        SELECT * FROM latest_stock
                        UNION ALL
                        SELECT * FROM latest_earnings
                    ) combined
                    ORDER BY analysis_date DESC
                    LIMIT 1
                """, (ticker.upper(), user_id, _EARNINGS_ID_OFFSET, ticker.upper(), user_id))

                row = cur.fetchone()
                if not row:
                    if "admin" not in user.roles:
                        raise HTTPException(status_code=404, detail=f"No analysis found for {ticker}")
                    declined_rows = _collect_declined_rows(ticker=ticker)
                    if not declined_rows:
                        raise HTTPException(status_code=404, detail=f"No analysis found for {ticker}")
                    return _row_to_detail(declined_rows[0])

                return _row_to_detail(dict(row))

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
