"""End-to-end tests for calibration update replay script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_run_calibration_update_replay_writes_report_and_priors(tmp_path: Path) -> None:
    """Replay forecast/outcome rows and verify report + priors outputs."""
    outcomes = tmp_path / "outcomes.jsonl"
    report = tmp_path / "calibration_report.json"
    priors = tmp_path / "earnings_priors.latest.json"

    rows = [
        {
            "ticker": "NVDA",
            "setup_type": "earnings_runup",
            "sector": "Technology",
            "event_month": "2026-03",
            "predicted_prob": 0.60,
            "realized": True,
        },
        {
            "ticker": "NVDA",
            "setup_type": "earnings_runup",
            "sector": "Technology",
            "event_month": "2026-03",
            "predicted_prob": 0.20,
            "realized": False,
        },
    ]
    outcomes.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "tradegent" / "scripts" / "run_calibration_update.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            str(outcomes),
            "--report-output",
            str(report),
            "--priors-output",
            str(priors),
            "--sample-floor",
            "2",
            "--apply-priors",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert report.exists()
    assert priors.exists()

    report_payload = json.loads(report.read_text(encoding="utf-8"))
    segments = report_payload.get("segments")
    assert isinstance(segments, dict)
    assert len(segments) == 1

    only_key = next(iter(segments))
    segment = segments[only_key]
    assert segment["sample_size"] == 2
    assert segment["avg_predicted_prob"] == 0.4
    assert segment["realized_rate"] == 0.5
    assert segment["calibration_drift"] == 0.1

    priors_payload = json.loads(priors.read_text(encoding="utf-8"))
    entries = priors_payload.get("entries")
    assert isinstance(entries, dict)
    assert only_key in entries
    assert entries[only_key]["prior_probability"] == 0.5
    assert entries[only_key]["sample_size"] == 2
