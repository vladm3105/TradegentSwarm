"""CI Benchmark Gate — evaluates quality-KPI scores from ADK telemetry.

Score is the fraction of benchmark records classified as active-quality (not
inactive / not blocked by a quality gate).

Thresholds
----------
HARD_FLOOR  = 0.85  — score below this blocks CI merge
PASS_TARGET = 0.88  — score at or above this is a clean pass
Between HARD_FLOOR and PASS_TARGET is the warning zone.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

HARD_FLOOR: float = 0.85
PASS_TARGET: float = 0.88
MIN_RECORDS: int = 10


def _record_passes_quality(record: dict[str, Any]) -> bool:
    """Return True if the benchmark record is not an inactive/rejected artifact."""
    if record.get("artifact_inactive") is True:
        return False
    status = record.get("analysis_artifact_status", "")
    if isinstance(status, str) and status.startswith("inactive_"):
        return False
    return True


def compute_benchmark_score(records: list[dict[str, Any]]) -> float:
    """Compute quality fraction: (passing records) / (total records).

    Returns ``float("nan")`` when records is empty.
    """
    if not records:
        return float("nan")
    passing = sum(1 for r in records if _record_passes_quality(r))
    return passing / len(records)


def evaluate_gate(
    score: float,
    *,
    hard_floor: float = HARD_FLOOR,
    pass_target: float = PASS_TARGET,
) -> str:
    """Classify a benchmark score into PASS / WARNING / FAIL.

    Returns ``"FAIL"`` when score < hard_floor or score is NaN,
    ``"WARNING"`` when hard_floor ≤ score < pass_target,
    ``"PASS"`` when score ≥ pass_target.
    """
    if math.isnan(score) or score < hard_floor:
        return "FAIL"
    if score < pass_target:
        return "WARNING"
    return "PASS"


def load_records(jsonl_path: Path, *, last_n: int | None = None) -> list[dict[str, Any]]:
    """Read a JSONL benchmark file and return parsed records.

    Silently skips blank lines and malformed JSON.  When *last_n* is given,
    only the trailing *last_n* records are returned.
    """
    records: list[dict[str, Any]] = []
    if not jsonl_path.exists():
        return records
    with jsonl_path.open(encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if last_n is not None and last_n > 0:
        records = records[-last_n:]
    return records


def check_benchmark_gate(
    jsonl_path: Path,
    *,
    min_records: int = MIN_RECORDS,
    last_n: int | None = None,
    hard_floor: float = HARD_FLOOR,
    pass_target: float = PASS_TARGET,
) -> dict[str, Any]:
    """Evaluate the CI benchmark gate for a JSONL telemetry file.

    Returns a result dict with keys:

    ``status``
        ``"PASS"`` / ``"WARNING"`` / ``"FAIL"`` / ``"SKIP"`` (insufficient
        records).
    ``score``
        Quality fraction (float) or ``NaN`` when not enough data.
    ``record_count``
        Total records evaluated.
    ``passing_count``
        Records classified as active-quality.
    ``message``
        Human-readable summary string.
    """
    records = load_records(jsonl_path, last_n=last_n)
    record_count = len(records)

    if record_count < min_records:
        return {
            "status": "SKIP",
            "score": float("nan"),
            "record_count": record_count,
            "passing_count": 0,
            "message": (
                f"Insufficient data: {record_count} records (min {min_records}). "
                "Gate skipped."
            ),
        }

    score = compute_benchmark_score(records)
    passing_count = sum(1 for r in records if _record_passes_quality(r))
    gate_result = evaluate_gate(score, hard_floor=hard_floor, pass_target=pass_target)

    if gate_result == "FAIL":
        msg = (
            f"FAIL — score {score:.3f} below hard floor {hard_floor:.2f}. "
            f"({passing_count}/{record_count} records active). CI merge blocked."
        )
    elif gate_result == "WARNING":
        msg = (
            f"WARNING — score {score:.3f} in warning zone "
            f"[{hard_floor:.2f}, {pass_target:.2f}). "
            f"({passing_count}/{record_count} records active). "
            "Merge allowed, improvement needed."
        )
    else:
        msg = (
            f"PASS — score {score:.3f} >= target {pass_target:.2f}. "
            f"({passing_count}/{record_count} records active)."
        )

    return {
        "status": gate_result,
        "score": score,
        "record_count": record_count,
        "passing_count": passing_count,
        "message": msg,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: check_benchmark_gate <jsonl_path> [--last-n N].

    Exit codes: 0 = PASS or SKIP, 1 = FAIL, 2 = WARNING.
    """
    import argparse

    parser = argparse.ArgumentParser(description="ADK CI benchmark gate checker")
    parser.add_argument("jsonl_path", type=Path, help="Path to adk_benchmark_metrics.jsonl")
    parser.add_argument(
        "--last-n", type=int, default=None, metavar="N",
        help="Evaluate only the last N records",
    )
    parser.add_argument(
        "--min-records", type=int, default=MIN_RECORDS,
        help=f"Minimum records required for evaluation (default: {MIN_RECORDS})",
    )
    parser.add_argument(
        "--hard-floor", type=float, default=HARD_FLOOR,
        help=f"Hard floor threshold (default: {HARD_FLOOR})",
    )
    parser.add_argument(
        "--pass-target", type=float, default=PASS_TARGET,
        help=f"Pass target threshold (default: {PASS_TARGET})",
    )
    args = parser.parse_args(argv)

    result = check_benchmark_gate(
        args.jsonl_path,
        min_records=args.min_records,
        last_n=args.last_n,
        hard_floor=args.hard_floor,
        pass_target=args.pass_target,
    )

    print(result["message"])

    status = result["status"]
    if status == "FAIL":
        return 1
    if status == "WARNING":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
