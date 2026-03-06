-- Rollback: 022_run_dedup_and_side_effects.sql
-- Description: Remove ADK run idempotency and side-effect marker tables
-- Date: 2026-03-05

DROP INDEX IF EXISTS nexus.idx_run_side_effect_markers_phase;
DROP TABLE IF EXISTS nexus.run_side_effect_markers;

DROP INDEX IF EXISTS nexus.idx_run_request_dedup_expires_at;
DROP TABLE IF EXISTS nexus.run_request_dedup;
