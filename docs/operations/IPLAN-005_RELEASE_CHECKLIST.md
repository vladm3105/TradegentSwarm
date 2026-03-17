# IPLAN-005 Release Checklist

Date: 2026-03-17 (America/New_York)
Scope: release evidence requirements for analysis quality upgrade

## Required Attachments

1. Benchmark report artifact attached:
- Path: tradegent/logs/adk_benchmark_report.json

2. Semantic pass-rate snapshot attached:
- Source: quality telemetry and validator outcomes
- Evidence file: tradegent/logs/adk_quality_kpis.json

3. Placeholder-rate snapshot attached:
- Source: quality telemetry inactive/active classification
- Evidence file: tradegent/logs/adk_quality_kpis.json

## Verification Steps

1. Confirm CI uploaded quality artifacts under artifact name adk-quality-artifacts.
2. Confirm benchmark gate status from report is PASS or WARNING for intended release policy.
3. Confirm semantic pass-rate and placeholder-rate snapshot values are included in release notes.
4. Confirm rollback drill reference is included:
- docs/operations/IPLAN-005_GATE_STRICTNESS_ROLLBACK_DRILL.md

## Gate Result

- PASS: all required attachments present and benchmark policy satisfied.
- FAIL: any required attachment missing or benchmark policy violated.
