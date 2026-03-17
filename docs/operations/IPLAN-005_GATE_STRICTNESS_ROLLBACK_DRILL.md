# IPLAN-005 Gate Strictness Rollback Drill

Date: 2026-03-17 (America/New_York)
Scope: rollback procedure for analysis quality gate strictness in the ADK pipeline

## Objective

Validate that operators can reduce gate strictness without disabling persistence or losing audit metadata.

## Preconditions

- Runtime can execute quality-gated analyses.
- Environment supports setting runtime flags.
- CI benchmark gate remains active in the repository workflow.

## Rollback Trigger Conditions

- Active-analysis throughput drops below operating floor for 3 consecutive days.
- False-positive hard-fail rate exceeds agreed canary threshold.
- Runtime latency/token guardrail violations exceed tolerated rate after strictness rollout.

## Rollback Controls

- Keep persistence enabled for all runs.
- Keep failure metadata fields intact.
- Reduce strictness by moving from hard blocking to non-active persistence where applicable.

## Drill Procedure

1. Record current strictness configuration snapshot:
- ADK_CRITIQUE_SCORE_GATE_ENABLED
- ADK_NON_ACTIVE_PERSISTENCE_ENABLED
- ADK_SEMANTIC_VALIDATION_ENABLED
- ADK_EARNINGS_QUALITY_GATES_ENABLED

2. Apply rollback profile:
- Set ADK_NON_ACTIVE_PERSISTENCE_ENABLED=true.
- Keep ADK_CRITIQUE_SCORE_GATE_ENABLED=true.
- Keep ADK_SEMANTIC_VALIDATION_ENABLED=true.
- Keep ADK_EARNINGS_QUALITY_GATES_ENABLED=true.

3. Execute verification tests:
- Critique gate legacy blocking path test.
- Critique gate non-active path test.
- Critique gate disabled default-path test.

4. Verify output behavior:
- No run is dropped.
- Failing runs persist with inactive status.
- Failure metadata includes failure_code and failed_checks.

5. Verify observability artifacts:
- tradegent/logs/adk_quality_kpis.json
- tradegent/logs/adk_benchmark_report.json
- tradegent/logs/calibration_report.json

6. Record drill evidence in release notes and mark drill pass/fail.

## Pass Criteria

- Rollback profile applies without runtime errors.
- Blocking failures convert to inactive persistence where intended.
- All verification tests pass.
- KPI and benchmark artifacts are produced.

## Failure Handling

- If rollback profile fails, revert to last known-good environment snapshot.
- Re-run verification tests.
- Escalate to on-call and attach logs/artifacts.
