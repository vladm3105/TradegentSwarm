# IPLAN-005 Acceptance Evidence

Date: 2026-03-17 (America/New_York)
Scope: recorded evidence for Section 6 acceptance criteria

## Acceptance Criteria Status

1. Zero placeholder analyses saved as active over 30 consecutive days:
- Status: pending observation window
- Evidence source: tradegent/logs/adk_quality_kpis.json

2. 100% active analyses pass schema validation before active classification:
- Status: implemented path enforced
- Evidence source: runtime contract validation + inactive_schema_failed handling

3. >=95% analyses pass semantic validation without manual intervention:
- Status: measurable with telemetry snapshots
- Evidence source: tradegent/logs/adk_quality_kpis.json

4. Benchmark quality score meets or exceeds curated baseline:
- Status: enforced by benchmark gate policy
- Evidence source: tradegent/logs/adk_benchmark_report.json

5. Gate outcomes are logically consistent with EV/confidence/R:R values:
- Status: validator enforced
- Evidence source: semantic validator checks and test coverage

6. 100% failed runs are persisted with non-active status and machine-readable failure metadata:
- Status: implemented
- Evidence source: failure metadata in persisted artifacts

7. CI blocks merges when benchmark score regresses beyond tolerance:
- Status: implemented
- Evidence source: .github/workflows/ci.yml benchmark step and exit-code policy

8. Runtime p95 and token budget remain within defined guardrails:
- Status: pending ongoing SLO observation
- Evidence source: telemetry dashboards and runbook monitoring

## Notes

- Criteria requiring time-window observation are marked pending until enough production data is accumulated.
- This document records evidence locations and current evaluation state for release governance.
