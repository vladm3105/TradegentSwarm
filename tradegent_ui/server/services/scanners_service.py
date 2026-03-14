"""Scanners service with route-facing formatting/parsing logic."""

import json
from typing import Any, Optional

from ..repositories import scanners_repository


def list_scanners(scanner_type: Optional[str], enabled_only: bool) -> list[dict[str, Any]]:
    rows = scanners_repository.list_scanners(scanner_type=scanner_type, enabled_only=enabled_only)
    return [
        {
            "id": row["id"],
            "scanner_code": row["scanner_code"],
            "name": row["name"] or row["scanner_code"],
            "description": row["description"],
            "scanner_type": row["scanner_type"],
            "is_enabled": row["is_enabled"],
            "auto_analyze": row["auto_analyze"] or False,
            "analysis_type": row["analysis_type"],
            "last_run": row["last_run"].isoformat() if row["last_run"] else None,
            "last_run_status": row["last_run_status"],
            "candidates_count": row["candidates_count"],
        }
        for row in rows
    ]


def list_results(scanner_code: Optional[str], limit: int) -> list[dict[str, Any]]:
    rows = scanners_repository.list_scanner_results(scanner_code=scanner_code, limit=limit)
    results: list[dict[str, Any]] = []

    for row in rows:
        candidates = []
        candidates_found = 0
        resolved_scanner_code = row.get("scanner_code") or scanner_code or "UNKNOWN"

        if row["raw_output"]:
            try:
                data = json.loads(row["raw_output"]) if isinstance(row["raw_output"], str) else row["raw_output"]
                candidates_found = data.get("candidates_found", 0)
                for c in data.get("candidates", []):
                    candidates.append(
                        {
                            "ticker": c.get("ticker", ""),
                            "score": c.get("score"),
                            "price": c.get("price"),
                            "notes": c.get("notes"),
                        }
                    )
            except (json.JSONDecodeError, TypeError):
                pass

        results.append(
            {
                "id": row["id"],
                "scanner_code": str(resolved_scanner_code),
                "scan_time": row["started_at"].isoformat() if row["started_at"] else "",
                "status": row["status"],
                "duration_seconds": float(row["duration_seconds"]) if row["duration_seconds"] else None,
                "candidates_found": candidates_found,
                "candidates": candidates,
            }
        )

    return results


def latest_candidates(limit: int) -> list[dict[str, Any]]:
    outputs = scanners_repository.list_latest_candidate_outputs()
    all_candidates = []
    seen_tickers = set()

    for raw_output in outputs:
        try:
            data = json.loads(raw_output) if isinstance(raw_output, str) else raw_output
            for c in data.get("candidates", []):
                ticker = c.get("ticker", "")
                if ticker and ticker not in seen_tickers:
                    seen_tickers.add(ticker)
                    all_candidates.append(
                        {
                            "ticker": ticker,
                            "score": c.get("score"),
                            "price": c.get("price"),
                            "notes": c.get("notes"),
                        }
                    )
        except (json.JSONDecodeError, TypeError):
            continue

    return all_candidates[:limit]
