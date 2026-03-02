"""
Analyses API endpoints.
Serves stock analysis data from the kb_stock_analyses table.
"""

import logging
from typing import Optional
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .config import get_settings

router = APIRouter(prefix="/api/analyses", tags=["analyses"])
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
    yaml_content: dict


@router.get("/list", response_model=AnalysisListResponse)
async def list_analyses(
    status: Optional[str] = Query(None, pattern="^(active|expired|all)$"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List analyses with optional filtering."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Build query
                where_clause = ""
                if status == "active":
                    # Active: analysis date within last 30 days
                    where_clause = "WHERE analysis_date >= CURRENT_DATE - INTERVAL '30 days'"
                elif status == "expired":
                    where_clause = "WHERE analysis_date < CURRENT_DATE - INTERVAL '30 days'"

                # Get total count
                cur.execute(f"SELECT COUNT(*) as cnt FROM nexus.kb_stock_analyses {where_clause}")
                total = cur.fetchone()["cnt"]

                # Get analyses
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
                        yaml_content->>'analysis_type' as analysis_type,
                        CASE
                            WHEN analysis_date >= CURRENT_DATE - INTERVAL '30 days' THEN 'active'
                            ELSE 'expired'
                        END as status
                    FROM nexus.kb_stock_analyses
                    {where_clause}
                    ORDER BY analysis_date DESC
                    LIMIT %s OFFSET %s
                """, (limit, offset))

                rows = cur.fetchall()
                analyses = []
                for row in rows:
                    analyses.append(AnalysisSummary(
                        id=row["id"],
                        ticker=row["ticker"],
                        type=row["analysis_type"] or "stock",
                        recommendation=row["recommendation"],
                        confidence=row["confidence"],
                        gate_result=row["gate_result"],
                        expected_value=float(row["expected_value_pct"]) if row["expected_value_pct"] else None,
                        analysis_date=row["analysis_date"].isoformat() if row["analysis_date"] else "",
                        status=row["status"],
                        schema_version=row["schema_version"],
                    ))

                return AnalysisListResponse(analyses=analyses, total=total)

    except Exception as e:
        log.error(f"Failed to list analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detail/{analysis_id}", response_model=AnalysisDetailResponse)
async def get_analysis_detail(analysis_id: int):
    """Get full analysis detail by ID."""
    try:
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
                    WHERE id = %s
                """, (analysis_id,))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Analysis not found")

                return AnalysisDetailResponse(
                    id=row["id"],
                    ticker=row["ticker"],
                    analysis_date=row["analysis_date"].isoformat() if row["analysis_date"] else "",
                    schema_version=row["schema_version"],
                    file_path=row["file_path"],
                    recommendation=row["recommendation"],
                    confidence=row["confidence"],
                    gate_result=row["gate_result"],
                    expected_value=float(row["expected_value_pct"]) if row["expected_value_pct"] else None,
                    current_price=float(row["current_price"]) if row["current_price"] else None,
                    yaml_content=row["yaml_content"] or {},
                )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get analysis detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/by-ticker/{ticker}", response_model=AnalysisDetailResponse)
async def get_latest_analysis_by_ticker(ticker: str):
    """Get most recent analysis for a ticker."""
    try:
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
                    WHERE ticker = %s
                    ORDER BY analysis_date DESC
                    LIMIT 1
                """, (ticker.upper(),))

                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail=f"No analysis found for {ticker}")

                return AnalysisDetailResponse(
                    id=row["id"],
                    ticker=row["ticker"],
                    analysis_date=row["analysis_date"].isoformat() if row["analysis_date"] else "",
                    schema_version=row["schema_version"],
                    file_path=row["file_path"],
                    recommendation=row["recommendation"],
                    confidence=row["confidence"],
                    gate_result=row["gate_result"],
                    expected_value=float(row["expected_value_pct"]) if row["expected_value_pct"] else None,
                    current_price=float(row["current_price"]) if row["current_price"] else None,
                    yaml_content=row["yaml_content"] or {},
                )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get analysis for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
