"""
Scanners API endpoints.
Serves scanner configurations and results from the database.
"""

import json
import logging
from typing import Optional
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings

router = APIRouter(prefix="/api/scanners", tags=["scanners"])
log = logging.getLogger(__name__)

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


# Response models
class ScannerConfig(BaseModel):
    """Scanner configuration."""
    id: int
    scanner_code: str
    name: str
    description: Optional[str] = None
    scanner_type: Optional[str] = None  # instrument type (STK, etc.)
    is_enabled: bool
    auto_analyze: bool = False
    analysis_type: Optional[str] = None
    last_run: Optional[str] = None
    last_run_status: Optional[str] = None
    candidates_count: Optional[int] = None


class ScannerCandidate(BaseModel):
    """Scanner result candidate."""
    ticker: str
    score: Optional[float] = None
    price: Optional[float] = None
    notes: Optional[str] = None


class ScannerResult(BaseModel):
    """Scanner run result."""
    id: int
    scanner_code: str
    scan_time: str
    status: str
    duration_seconds: Optional[float] = None
    candidates_found: int
    candidates: list[ScannerCandidate]


class ScannerListResponse(BaseModel):
    """Response for scanner list."""
    scanners: list[ScannerConfig]
    total: int


class ScannerResultsResponse(BaseModel):
    """Response for scanner results."""
    results: list[ScannerResult]
    total: int


@router.get("/list", response_model=ScannerListResponse)
async def list_scanners(
    scanner_type: Optional[str] = Query(None),
    enabled_only: bool = Query(False),
):
    """List available scanners."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build where clause
                conditions = []
                params = []

                if scanner_type:
                    conditions.append("s.instrument = %s")
                    params.append(scanner_type)

                if enabled_only:
                    conditions.append("s.is_enabled = true")

                where_clause = ""
                if conditions:
                    where_clause = "WHERE " + " AND ".join(conditions)

                # Get scanners from ib_scanners table
                cur.execute(f"""
                    SELECT
                        s.id,
                        s.scanner_code,
                        s.display_name as name,
                        s.description,
                        s.instrument as scanner_type,
                        s.is_enabled,
                        s.auto_analyze,
                        s.analysis_type,
                        r.started_at as last_run,
                        r.status as last_run_status,
                        CASE
                            WHEN r.raw_output IS NOT NULL THEN
                                (r.raw_output::jsonb->>'candidates_found')::int
                            ELSE 0
                        END as candidates_count
                    FROM nexus.ib_scanners s
                    LEFT JOIN LATERAL (
                        SELECT started_at, status, raw_output
                        FROM nexus.run_history
                        WHERE task_type = 'run_scanner'
                        AND ticker = s.scanner_code
                        ORDER BY started_at DESC
                        LIMIT 1
                    ) r ON true
                    {where_clause}
                    ORDER BY s.instrument, s.display_name
                """, params)

                rows = cur.fetchall()
                scanners = []
                for row in rows:
                    scanners.append(ScannerConfig(
                        id=row["id"],
                        scanner_code=row["scanner_code"],
                        name=row["name"] or row["scanner_code"],
                        description=row["description"],
                        scanner_type=row["scanner_type"],
                        is_enabled=row["is_enabled"],
                        auto_analyze=row["auto_analyze"] or False,
                        analysis_type=row["analysis_type"],
                        last_run=row["last_run"].isoformat() if row["last_run"] else None,
                        last_run_status=row["last_run_status"],
                        candidates_count=row["candidates_count"],
                    ))

                return ScannerListResponse(scanners=scanners, total=len(scanners))

    except Exception as e:
        log.error(f"Failed to list scanners: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results", response_model=ScannerResultsResponse)
async def get_scanner_results(
    scanner_code: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent scanner results."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build where clause
                conditions = ["task_type = 'run_scanner'"]
                params = []

                if scanner_code:
                    conditions.append("ticker = %s")
                    params.append(scanner_code)

                where_clause = "WHERE " + " AND ".join(conditions)

                cur.execute(f"""
                    SELECT
                        id,
                        ticker as scanner_code,
                        started_at,
                        status,
                        duration_seconds,
                        raw_output
                    FROM nexus.run_history
                    {where_clause}
                    ORDER BY started_at DESC
                    LIMIT %s
                """, params + [limit])

                rows = cur.fetchall()
                results = []
                for row in rows:
                    # Parse raw_output JSON
                    candidates = []
                    candidates_found = 0

                    if row["raw_output"]:
                        try:
                            data = json.loads(row["raw_output"]) if isinstance(row["raw_output"], str) else row["raw_output"]
                            candidates_found = data.get("candidates_found", 0)
                            for c in data.get("candidates", []):
                                candidates.append(ScannerCandidate(
                                    ticker=c.get("ticker", ""),
                                    score=c.get("score"),
                                    price=c.get("price"),
                                    notes=c.get("notes"),
                                ))
                        except (json.JSONDecodeError, TypeError):
                            pass

                    results.append(ScannerResult(
                        id=row["id"],
                        scanner_code=row["scanner_code"],
                        scan_time=row["started_at"].isoformat() if row["started_at"] else "",
                        status=row["status"],
                        duration_seconds=float(row["duration_seconds"]) if row["duration_seconds"] else None,
                        candidates_found=candidates_found,
                        candidates=candidates,
                    ))

                return ScannerResultsResponse(results=results, total=len(results))

    except Exception as e:
        log.error(f"Failed to get scanner results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", response_model=list[ScannerCandidate])
async def get_latest_candidates(limit: int = Query(10, ge=1, le=50)):
    """Get latest scanner candidates across all scanners."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Get most recent successful scanner run with candidates
                cur.execute("""
                    SELECT raw_output
                    FROM nexus.run_history
                    WHERE task_type = 'run_scanner'
                    AND status = 'completed'
                    AND raw_output IS NOT NULL
                    AND (raw_output::jsonb->>'candidates_found')::int > 0
                    ORDER BY started_at DESC
                    LIMIT 5
                """)

                all_candidates = []
                seen_tickers = set()

                for row in cur.fetchall():
                    try:
                        data = json.loads(row["raw_output"]) if isinstance(row["raw_output"], str) else row["raw_output"]
                        for c in data.get("candidates", []):
                            ticker = c.get("ticker", "")
                            if ticker and ticker not in seen_tickers:
                                seen_tickers.add(ticker)
                                all_candidates.append(ScannerCandidate(
                                    ticker=ticker,
                                    score=c.get("score"),
                                    price=c.get("price"),
                                    notes=c.get("notes"),
                                ))
                    except (json.JSONDecodeError, TypeError):
                        continue

                return all_candidates[:limit]

    except Exception as e:
        log.error(f"Failed to get latest candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
