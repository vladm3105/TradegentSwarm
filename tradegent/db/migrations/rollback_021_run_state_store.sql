-- Rollback: 021_run_state_store.sql
-- Description: Remove ADK run-state lifecycle tables
-- Date: 2026-03-05

DROP INDEX IF EXISTS nexus.idx_run_state_events_run_created;
DROP TABLE IF EXISTS nexus.run_state_events;

DROP INDEX IF EXISTS nexus.idx_run_state_runs_created_at;
DROP TABLE IF EXISTS nexus.run_state_runs;
