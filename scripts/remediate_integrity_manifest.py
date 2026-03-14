#!/usr/bin/env python3
"""Manifest-driven remediation runner for stock-analysis artifacts.

This tool consumes an integrity manifest JSON file and applies safe, idempotent
repairs for selected reason categories. It is designed for IPLAN-014 follow-up
remediation where many historical artifacts need normalization before revalidation.

Default behavior is dry-run. Use --apply to write changes.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


DEFAULT_MANIFEST = Path("tmp/IPLAN/IPLAN014_integrity_manifest.json")
DEFAULT_REPORT = Path("tmp/IPLAN/IPLAN014_remediation_report.json")
DEFAULT_REASON_SET = {
    "missing_ev_actual",
    "missing_rr_actual",
    "missing_confidence_actual",
    "gate_result_mismatch",
}


@dataclass
class FileChange:
    file: str
    reasons: list[str]
    changed_fields: list[str]
    skipped: bool
    skip_reason: str | None = None


@dataclass
class ValidationSummary:
    valid: int
    total: int
    raw_exit_code: int


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        try:
            f = float(text)
        except ValueError:
            return None
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    if f is None:
        return None
    return int(round(f))


def _safe_div(numerator: float, denominator: float) -> float | None:
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def _compute_rr_from_key_levels(doc: dict[str, Any]) -> float | None:
    summary = doc.get("summary")
    if not isinstance(summary, dict):
        return None
    key_levels = summary.get("key_levels")
    if not isinstance(key_levels, dict):
        return None

    entry = _to_float(key_levels.get("entry"))
    stop = _to_float(key_levels.get("stop"))
    target_1 = _to_float(key_levels.get("target_1"))

    if entry is None or stop is None or target_1 is None:
        return None
    if entry <= 0 or stop <= 0 or target_1 <= 0:
        return None

    reward = target_1 - entry
    risk = entry - stop
    rr = _safe_div(reward, risk)
    if rr is None:
        return None
    return round(abs(rr), 4)


def _recompute_gate_fields(gate: dict[str, Any], changed_fields: list[str]) -> None:
    ev_threshold = _to_float(gate.get("ev_threshold"))
    ev_actual = _to_float(gate.get("ev_actual"))
    confidence_threshold = _to_float(gate.get("confidence_threshold"))
    confidence_actual = _to_float(gate.get("confidence_actual"))
    rr_threshold = _to_float(gate.get("rr_threshold"))
    rr_actual = _to_float(gate.get("rr_actual"))

    if ev_threshold is not None and ev_actual is not None:
        ev_passes = ev_actual >= ev_threshold
        if gate.get("ev_passes") is not ev_passes:
            gate["ev_passes"] = ev_passes
            changed_fields.append("do_nothing_gate.ev_passes")

    if confidence_threshold is not None and confidence_actual is not None:
        confidence_passes = confidence_actual >= confidence_threshold
        if gate.get("confidence_passes") is not confidence_passes:
            gate["confidence_passes"] = confidence_passes
            changed_fields.append("do_nothing_gate.confidence_passes")

    if rr_threshold is not None and rr_actual is not None:
        rr_passes = rr_actual >= rr_threshold
        if gate.get("rr_passes") is not rr_passes:
            gate["rr_passes"] = rr_passes
            changed_fields.append("do_nothing_gate.rr_passes")

    ev_passes_b = bool(gate.get("ev_passes"))
    confidence_passes_b = bool(gate.get("confidence_passes"))
    rr_passes_b = bool(gate.get("rr_passes"))
    edge_exists = ev_passes_b and confidence_passes_b and rr_passes_b

    if gate.get("edge_exists") is not edge_exists:
        gate["edge_exists"] = edge_exists
        changed_fields.append("do_nothing_gate.edge_exists")

    gates_passed = int(ev_passes_b) + int(confidence_passes_b) + int(rr_passes_b) + int(edge_exists)
    if _to_int(gate.get("gates_passed")) != gates_passed:
        gate["gates_passed"] = gates_passed
        changed_fields.append("do_nothing_gate.gates_passed")

    if gates_passed >= 4:
        expected_gate_result = "PASS"
    elif gates_passed == 3:
        expected_gate_result = "MARGINAL"
    else:
        expected_gate_result = "FAIL"

    if gate.get("gate_result") != expected_gate_result:
        gate["gate_result"] = expected_gate_result
        changed_fields.append("do_nothing_gate.gate_result")


def _apply_safe_repairs(doc: dict[str, Any], requested_reasons: set[str]) -> list[str]:
    changed_fields: list[str] = []

    gate = doc.get("do_nothing_gate")
    if not isinstance(gate, dict):
        return changed_fields

    if "missing_ev_actual" in requested_reasons and _to_float(gate.get("ev_actual")) is None:
        scenarios = doc.get("scenarios")
        if isinstance(scenarios, dict):
            expected_value = _to_float(scenarios.get("expected_value"))
            if expected_value is not None:
                gate["ev_actual"] = round(expected_value, 4)
                changed_fields.append("do_nothing_gate.ev_actual")

    if "missing_confidence_actual" in requested_reasons and _to_float(gate.get("confidence_actual")) is None:
        recommendation = doc.get("recommendation")
        rec_conf = _to_float(recommendation.get("confidence")) if isinstance(recommendation, dict) else None
        if rec_conf is not None:
            gate["confidence_actual"] = int(round(rec_conf))
            changed_fields.append("do_nothing_gate.confidence_actual")

    if "missing_rr_actual" in requested_reasons and _to_float(gate.get("rr_actual")) is None:
        rr = _compute_rr_from_key_levels(doc)
        if rr is not None:
            gate["rr_actual"] = rr
            changed_fields.append("do_nothing_gate.rr_actual")

    if "gate_result_mismatch" in requested_reasons or changed_fields:
        _recompute_gate_fields(gate, changed_fields)

    return changed_fields


def _run_validator(workspace_root: Path) -> ValidationSummary:
    cmd = [sys.executable, "scripts/validate_analysis.py", "--all", "--quiet"]
    proc = subprocess.run(
        cmd,
        cwd=workspace_root,
        check=False,
        capture_output=True,
        text=True,
    )

    valid = 0
    total = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("VALIDATION SUMMARY:") and "files valid" in line:
            payload = line.split(":", 1)[1].strip().split(" ", 1)[0]
            if "/" in payload:
                left, right = payload.split("/", 1)
                valid = int(left)
                total = int(right)
            break

    return ValidationSummary(valid=valid, total=total, raw_exit_code=proc.returncode)


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    with manifest_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("Manifest root must be a JSON object")
    return cast(dict[str, Any], payload)


def _load_yaml(file_path: Path) -> dict[str, Any]:
    with file_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _dump_yaml(file_path: Path, doc: dict[str, Any]) -> None:
    with file_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            doc,
            fh,
            allow_unicode=False,
            sort_keys=False,
            default_flow_style=False,
            width=120,
        )


def run(
    workspace_root: Path,
    manifest_path: Path,
    apply: bool,
    limit: int | None,
    requested_reasons: set[str],
    run_validation: bool,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    suspicious = manifest.get("suspicious", [])
    if not isinstance(suspicious, list):
        raise ValueError("Manifest field 'suspicious' must be a list")

    before_validation = _run_validator(workspace_root) if run_validation else None

    changes: list[FileChange] = []
    evaluated = 0

    for item in suspicious:
        if limit is not None and evaluated >= limit:
            break

        file_rel = item.get("file")
        reasons = item.get("reasons", [])
        if not isinstance(file_rel, str) or not isinstance(reasons, list):
            continue

        reason_set = {str(r) for r in reasons}
        if not (reason_set & requested_reasons):
            continue

        evaluated += 1
        file_path = workspace_root / file_rel
        if not file_path.exists():
            changes.append(
                FileChange(
                    file=file_rel,
                    reasons=sorted(reason_set),
                    changed_fields=[],
                    skipped=True,
                    skip_reason="file_not_found",
                )
            )
            continue

        try:
            doc = _load_yaml(file_path)
        except Exception as exc:  # noqa: BLE001
            changes.append(
                FileChange(
                    file=file_rel,
                    reasons=sorted(reason_set),
                    changed_fields=[],
                    skipped=True,
                    skip_reason=f"yaml_load_error:{exc}",
                )
            )
            continue

        changed_fields = _apply_safe_repairs(doc, requested_reasons)

        if changed_fields and apply:
            _dump_yaml(file_path, doc)

        changes.append(
            FileChange(
                file=file_rel,
                reasons=sorted(reason_set),
                changed_fields=sorted(set(changed_fields)),
                skipped=False,
            )
        )

    after_validation = _run_validator(workspace_root) if run_validation else None

    updated_files = [c for c in changes if c.changed_fields]
    skipped_files = [c for c in changes if c.skipped]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_root": str(workspace_root),
        "manifest_path": str(manifest_path),
        "apply": apply,
        "requested_reasons": sorted(requested_reasons),
        "evaluated_entries": evaluated,
        "total_manifest_suspicious": len(suspicious),
        "updated_files": len(updated_files),
        "skipped_files": len(skipped_files),
        "validation_before": None
        if before_validation is None
        else {
            "valid": before_validation.valid,
            "total": before_validation.total,
            "exit_code": before_validation.raw_exit_code,
        },
        "validation_after": None
        if after_validation is None
        else {
            "valid": after_validation.valid,
            "total": after_validation.total,
            "exit_code": after_validation.raw_exit_code,
        },
        "changes": [
            {
                "file": c.file,
                "reasons": c.reasons,
                "changed_fields": c.changed_fields,
                "skipped": c.skipped,
                "skip_reason": c.skip_reason,
            }
            for c in changes
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply safe manifest-driven remediation for stock analysis artifacts."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Path to integrity manifest JSON (default: {DEFAULT_MANIFEST})",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help=f"Path to write remediation report JSON (default: {DEFAULT_REPORT})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write file changes. Default is dry-run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum eligible manifest entries to process.",
    )
    parser.add_argument(
        "--reasons",
        type=str,
        default=",".join(sorted(DEFAULT_REASON_SET)),
        help="Comma-separated reason filters to remediate.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip running scripts/validate_analysis.py --all before/after remediation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]

    requested_reasons = {
        token.strip() for token in args.reasons.split(",") if token.strip()
    }
    if not requested_reasons:
        requested_reasons = set(DEFAULT_REASON_SET)

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = workspace_root / manifest_path

    report_path = args.report
    if not report_path.is_absolute():
        report_path = workspace_root / report_path

    if not manifest_path.exists():
        print(f"ERROR: manifest file not found: {manifest_path}")
        return 2

    report = run(
        workspace_root=workspace_root,
        manifest_path=manifest_path,
        apply=args.apply,
        limit=args.limit,
        requested_reasons=requested_reasons,
        run_validation=not args.skip_validation,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=True)
        fh.write("\n")

    before = report.get("validation_before")
    after = report.get("validation_after")
    print("Remediation run complete")
    print(f"- apply mode: {report.get('apply')}")
    print(f"- evaluated entries: {report.get('evaluated_entries')}")
    print(f"- updated files: {report.get('updated_files')}")
    print(f"- skipped files: {report.get('skipped_files')}")
    if before and after:
        print(
            "- validation delta: "
            f"{before.get('valid')}/{before.get('total')} -> "
            f"{after.get('valid')}/{after.get('total')}"
        )
    print(f"- report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
