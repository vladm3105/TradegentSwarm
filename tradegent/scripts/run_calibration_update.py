#!/usr/bin/env python3
"""Compute monthly calibration metrics and optionally update priors."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
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


def _bucket_key(row: dict[str, Any]) -> str:
    ticker = str(row.get("ticker") or "UNKNOWN").upper()
    setup_type = str(row.get("setup_type") or "unknown")
    sector = str(row.get("sector") or "unknown")
    month = str(row.get("event_month") or datetime.now(UTC).strftime("%Y-%m"))
    return f"{ticker}|{setup_type}|{sector}|{month}"


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_bucket_key(row)].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for key, group in grouped.items():
        total = len(group)
        if total == 0:
            continue
        predicted = sum(float(item.get("predicted_prob", 0.0)) for item in group)
        realized = sum(1.0 for item in group if bool(item.get("realized")))
        avg_predicted = predicted / total
        realized_rate = realized / total
        drift = realized_rate - avg_predicted
        summary[key] = {
            "sample_size": total,
            "avg_predicted_prob": round(avg_predicted, 6),
            "realized_rate": round(realized_rate, 6),
            "calibration_drift": round(drift, 6),
        }
    return summary


def _build_priors(summary: dict[str, dict[str, Any]], *, sample_floor: int) -> dict[str, Any]:
    priors: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(), "entries": {}}
    for key, item in summary.items():
        sample_size = int(item.get("sample_size", 0))
        if sample_size < sample_floor:
            continue
        priors["entries"][key] = {
            "prior_probability": item.get("realized_rate"),
            "sample_size": sample_size,
        }
    return priors


def main() -> int:
    parser = argparse.ArgumentParser(description="Run calibration update")
    parser.add_argument("outcomes_jsonl", type=Path, help="Forecast/outcome linkage JSONL")
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("tradegent/logs/calibration_report.json"),
        help="Calibration report path",
    )
    parser.add_argument(
        "--priors-output",
        type=Path,
        default=Path("tradegent_knowledge/knowledge/learnings/calibration/earnings_priors.latest.json"),
        help="Priors output path",
    )
    parser.add_argument("--sample-floor", type=int, default=30)
    parser.add_argument(
        "--apply-priors",
        action="store_true",
        help="Write priors file (feature-flagged reversible update path)",
    )
    args = parser.parse_args()

    rows = _load_jsonl(args.outcomes_jsonl)
    summary = _aggregate(rows)

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.outcomes_jsonl),
        "sample_floor": args.sample_floor,
        "segments": summary,
    }

    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote calibration report: {args.report_output}")

    if args.apply_priors:
        priors = _build_priors(summary, sample_floor=args.sample_floor)
        args.priors_output.parent.mkdir(parents=True, exist_ok=True)
        args.priors_output.write_text(json.dumps(priors, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote priors: {args.priors_output}")
    else:
        print("Priors update disabled; run with --apply-priors to publish priors.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
