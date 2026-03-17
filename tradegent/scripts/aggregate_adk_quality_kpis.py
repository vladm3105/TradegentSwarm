#!/usr/bin/env python3
"""Aggregate daily ADK quality KPIs from benchmark telemetry JSONL."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _day_bucket(row: dict[str, Any]) -> str:
    ts_raw = row.get("ts")
    if isinstance(ts_raw, str):
        try:
            return datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    return datetime.now(UTC).date().isoformat()


def _safe_div(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 6)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_day_bucket(row)].append(row)

    daily: dict[str, dict[str, Any]] = {}
    for day, records in sorted(grouped.items()):
        total = len(records)
        inactive = 0
        failed_validation = 0
        run_counts: Counter[str] = Counter()
        section_reason_counts: Counter[str] = Counter()

        for row in records:
            run_id = row.get("run_id")
            if isinstance(run_id, str) and run_id.strip():
                run_counts[run_id] += 1

            artifact_status = row.get("analysis_artifact_status")
            if isinstance(artifact_status, str) and artifact_status.startswith("inactive_"):
                inactive += 1

            failure_code = row.get("quality_failure_code")
            if isinstance(failure_code, str) and failure_code.strip():
                failed_validation += 1

            failed_checks = row.get("quality_failed_checks")
            if isinstance(failed_checks, list):
                for check in failed_checks:
                    if isinstance(check, str) and check.strip().startswith("critique score below threshold"):
                        parts = check.split("'")
                        if len(parts) >= 2:
                            section_reason_counts[parts[1]] += 1

        retries_total = sum(max(0, count - 1) for count in run_counts.values())
        retry_count_per_run = _safe_div(retries_total, max(1, len(run_counts)))

        daily[day] = {
            "total_runs": total,
            "placeholder_rate": _safe_div(inactive, total),
            "validation_fail_rate": _safe_div(failed_validation, total),
            "retry_count_per_run": retry_count_per_run,
            "section_score_distribution": dict(section_reason_counts),
            "prediction_calibration_drift": None,
        }

    return daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate ADK quality KPI metrics")
    parser.add_argument("input_jsonl", type=Path, help="Path to adk_benchmark_metrics.jsonl")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tradegent/logs/adk_quality_kpis.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    rows = _load_jsonl(args.input_jsonl)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.input_jsonl),
        "daily": aggregate(rows),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote KPI report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
