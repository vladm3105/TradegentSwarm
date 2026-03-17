"""Tests for CI benchmark gate logic (IPLAN-005 Phase E)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from adk_runtime.benchmark_gate import (
    HARD_FLOOR,
    MIN_RECORDS,
    PASS_TARGET,
    check_benchmark_gate,
    compute_benchmark_score,
    evaluate_gate,
    load_records,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _active(run_id: str = "r") -> dict:
    return {
        "run_id": run_id,
        "artifact_inactive": False,
        "analysis_artifact_status": "active",
    }


def _inactive(code: str = "PLACEHOLDER_CONTENT", run_id: str = "r") -> dict:
    return {
        "run_id": run_id,
        "artifact_inactive": True,
        "analysis_artifact_status": "inactive_quality_failed",
        "quality_failure_code": code,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


# ---------------------------------------------------------------------------
# compute_benchmark_score
# ---------------------------------------------------------------------------


class TestComputeBenchmarkScore:
    def test_empty_returns_nan(self) -> None:
        assert math.isnan(compute_benchmark_score([]))

    def test_all_active_returns_one(self) -> None:
        assert compute_benchmark_score([_active() for _ in range(10)]) == 1.0

    def test_all_inactive_returns_zero(self) -> None:
        assert compute_benchmark_score([_inactive() for _ in range(10)]) == 0.0

    def test_mixed_returns_fraction(self) -> None:
        records = [_active() for _ in range(9)] + [_inactive()]
        assert abs(compute_benchmark_score(records) - 0.9) < 1e-9

    def test_inactive_by_status_prefix_only(self) -> None:
        # artifact_inactive=False but status starts with "inactive_" → inactive
        rec = {"artifact_inactive": False, "analysis_artifact_status": "inactive_data_unavailable"}
        assert compute_benchmark_score([rec]) == 0.0

    def test_record_without_quality_fields_counts_as_passing(self) -> None:
        rec = {"run_id": "old", "status": "success"}
        assert compute_benchmark_score([rec]) == 1.0


# ---------------------------------------------------------------------------
# evaluate_gate
# ---------------------------------------------------------------------------


class TestEvaluateGate:
    def test_nan_is_fail(self) -> None:
        assert evaluate_gate(float("nan")) == "FAIL"

    def test_zero_is_fail(self) -> None:
        assert evaluate_gate(0.0) == "FAIL"

    def test_below_hard_floor_is_fail(self) -> None:
        assert evaluate_gate(HARD_FLOOR - 0.001) == "FAIL"

    def test_exactly_hard_floor_is_warning(self) -> None:
        assert evaluate_gate(HARD_FLOOR) == "WARNING"

    def test_in_warning_zone(self) -> None:
        mid = (HARD_FLOOR + PASS_TARGET) / 2
        assert evaluate_gate(mid) == "WARNING"

    def test_exactly_pass_target_is_pass(self) -> None:
        assert evaluate_gate(PASS_TARGET) == "PASS"

    def test_above_pass_target_is_pass(self) -> None:
        assert evaluate_gate(1.0) == "PASS"
        assert evaluate_gate(PASS_TARGET + 0.001) == "PASS"

    def test_custom_thresholds(self) -> None:
        assert evaluate_gate(0.70, hard_floor=0.60, pass_target=0.80) == "WARNING"
        assert evaluate_gate(0.55, hard_floor=0.60, pass_target=0.80) == "FAIL"
        assert evaluate_gate(0.85, hard_floor=0.60, pass_target=0.80) == "PASS"


# ---------------------------------------------------------------------------
# load_records
# ---------------------------------------------------------------------------


class TestLoadRecords:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_records(tmp_path / "missing.jsonl") == []

    def test_reads_valid_jsonl(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        f.write_text(json.dumps({"run_id": "a"}) + "\n" + json.dumps({"run_id": "b"}) + "\n")
        records = load_records(f)
        assert len(records) == 2
        assert records[0]["run_id"] == "a"

    def test_skips_blank_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        f.write_text("\n" + json.dumps({"run_id": "x"}) + "\n\n")
        assert len(load_records(f)) == 1

    def test_last_n_slices_tail(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        lines = [json.dumps({"run_id": str(i)}) for i in range(20)]
        f.write_text("\n".join(lines) + "\n")
        records = load_records(f, last_n=5)
        assert len(records) == 5
        assert records[0]["run_id"] == "15"

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        f.write_text('{"run_id": "ok"}\nnot-json\n{"run_id": "ok2"}\n')
        assert len(load_records(f)) == 2


# ---------------------------------------------------------------------------
# check_benchmark_gate
# ---------------------------------------------------------------------------


class TestCheckBenchmarkGate:
    def test_skip_for_missing_file(self, tmp_path: Path) -> None:
        result = check_benchmark_gate(tmp_path / "nonexistent.jsonl")
        assert result["status"] == "SKIP"
        assert math.isnan(result["score"])

    def test_skip_when_insufficient_records(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        _write_jsonl(f, [_active() for _ in range(MIN_RECORDS - 1)])
        result = check_benchmark_gate(f)
        assert result["status"] == "SKIP"
        assert result["record_count"] == MIN_RECORDS - 1

    def test_pass_when_all_active(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        _write_jsonl(f, [_active() for _ in range(20)])
        result = check_benchmark_gate(f)
        assert result["status"] == "PASS"
        assert abs(result["score"] - 1.0) < 1e-9

    def test_fail_below_hard_floor(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # 14/20 = 0.70 < HARD_FLOOR (0.85)
        records = [_active() for _ in range(14)] + [_inactive() for _ in range(6)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f)
        assert result["status"] == "FAIL"
        assert result["score"] < HARD_FLOOR

    def test_warning_at_hard_floor(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # 17/20 = 0.85 = HARD_FLOOR exactly → WARNING
        records = [_active() for _ in range(17)] + [_inactive() for _ in range(3)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f)
        assert result["status"] == "WARNING"
        assert HARD_FLOOR <= result["score"] < PASS_TARGET

    def test_boundary_score_0849_is_fail(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # 849/1000 = 0.849 -> FAIL
        records = [_active() for _ in range(849)] + [_inactive() for _ in range(151)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f, min_records=10)
        assert result["status"] == "FAIL"
        assert result["score"] == pytest.approx(0.849, abs=1e-9)

    def test_boundary_score_0850_is_warning(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # 850/1000 = 0.850 -> WARNING
        records = [_active() for _ in range(850)] + [_inactive() for _ in range(150)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f, min_records=10)
        assert result["status"] == "WARNING"
        assert result["score"] == pytest.approx(0.850, abs=1e-9)

    def test_boundary_score_0880_is_pass(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # 880/1000 = 0.880 -> PASS
        records = [_active() for _ in range(880)] + [_inactive() for _ in range(120)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f, min_records=10)
        assert result["status"] == "PASS"
        assert result["score"] == pytest.approx(0.880, abs=1e-9)

    def test_pass_at_pass_target(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # Need exactly PASS_TARGET fraction — use 25 records: 22 active = 22/25 = 0.88
        records = [_active() for _ in range(22)] + [_inactive() for _ in range(3)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f)
        assert result["status"] == "PASS"
        assert result["score"] >= PASS_TARGET

    def test_result_counts_are_accurate(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        records = [_active() for _ in range(18)] + [_inactive() for _ in range(2)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f)
        assert result["record_count"] == 20
        assert result["passing_count"] == 18

    def test_last_n_parameter_respected(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        # First 10 inactive, last 20 active → evaluating last 20 → PASS
        records = [_inactive() for _ in range(10)] + [_active() for _ in range(20)]
        _write_jsonl(f, records)
        result = check_benchmark_gate(f, last_n=20)
        assert result["status"] == "PASS"
        assert result["record_count"] == 20
        assert result["passing_count"] == 20

    def test_message_contains_score_and_counts(self, tmp_path: Path) -> None:
        f = tmp_path / "bench.jsonl"
        _write_jsonl(f, [_active() for _ in range(20)])
        result = check_benchmark_gate(f)
        assert "20" in result["message"]
        assert result["status"] in result["message"]
