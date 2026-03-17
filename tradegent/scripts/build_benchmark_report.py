#!/usr/bin/env python3
"""Generate a machine-readable benchmark report from ADK telemetry."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adk_runtime.benchmark_gate import check_benchmark_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Build benchmark report artifact")
    parser.add_argument("input_jsonl", type=Path, help="Path to adk_benchmark_metrics.jsonl")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tradegent/logs/adk_benchmark_report.json"),
        help="Output report path",
    )
    parser.add_argument("--last-n", type=int, default=None, help="Evaluate only last N records")
    parser.add_argument("--min-records", type=int, default=10)
    args = parser.parse_args()

    result = check_benchmark_gate(
        args.input_jsonl,
        min_records=args.min_records,
        last_n=args.last_n,
    )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": str(args.input_jsonl),
        "result": result,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote benchmark report: {args.output}")
    print(result.get("message", ""))

    if result.get("status") == "FAIL":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
