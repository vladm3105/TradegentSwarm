-- Migration: 022_run_dedup_and_side_effects.sql
-- Description: Add ADK run idempotency and side-effect guard tables
-- Date: 2026-03-05

CREATE TABLE IF NOT EXISTS nexus.run_request_dedup (
    dedup_key VARCHAR(255) PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES nexus.run_state_runs(run_id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'in_progress',
    response_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '24 hours'),
    CONSTRAINT ck_run_request_dedup_status CHECK (
        status IN ('in_progress', 'completed', 'failed', 'blocked')
    )
);

CREATE INDEX IF NOT EXISTS idx_run_request_dedup_expires_at ON nexus.run_request_dedup(expires_at);

CREATE TABLE IF NOT EXISTS nexus.run_side_effect_markers (
    run_id UUID NOT NULL REFERENCES nexus.run_state_runs(run_id) ON DELETE CASCADE,
    phase VARCHAR(64) NOT NULL,
    marker_key VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, phase, marker_key)
);

CREATE INDEX IF NOT EXISTS idx_run_side_effect_markers_phase ON nexus.run_side_effect_markers(phase, created_at DESC);
