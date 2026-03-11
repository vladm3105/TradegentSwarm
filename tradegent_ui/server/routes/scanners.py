"""
Scanners API endpoints.
Serves scanner configurations and results from the database.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services import scanners_service

router = APIRouter(prefix="/api/scanners", tags=["scanners"])
log = logging.getLogger(__name__)


class ScannerConfig(BaseModel):
    """Scanner configuration."""
    id: int
    scanner_code: str
    name: str
    description: Optional[str] = None
    scanner_type: Optional[str] = None
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
        scanners = scanners_service.list_scanners(scanner_type=scanner_type, enabled_only=enabled_only)
        return ScannerListResponse(
            scanners=[ScannerConfig(**s) for s in scanners],
            total=len(scanners),
        )
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
        results = scanners_service.list_results(scanner_code=scanner_code, limit=limit)
        return ScannerResultsResponse(
            results=[ScannerResult(**r) for r in results],
            total=len(results),
        )
    except Exception as e:
        log.error(f"Failed to get scanner results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest", response_model=list[ScannerCandidate])
async def get_latest_candidates(limit: int = Query(10, ge=1, le=50)):
    """Get latest scanner candidates across all scanners."""
    try:
        rows = scanners_service.latest_candidates(limit)
        return [ScannerCandidate(**row) for row in rows]
    except Exception as e:
        log.error(f"Failed to get latest candidates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
