-- Migration: 021_run_state_store.sql
-- Description: Add ADK run state tables for durable orchestration lifecycle tracking
-- Date: 2026-03-05

CREATE TABLE IF NOT EXISTS nexus.run_state_runs (
    run_id UUID PRIMARY KEY,
    parent_run_id UUID,
    intent VARCHAR(32),
    ticker VARCHAR(20),
    analysis_type VARCHAR(32),
    status VARCHAR(32) NOT NULL,
    contract_version VARCHAR(32),
    routing_policy_version VARCHAR(64),
    effective_config_hash VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_run_state_runs_status CHECK (
        status IN ('requested', 'planned', 'retrieval_done', 'draft_done', 'critique_done', 'validated', 'completed', 'failed', 'blocked')
    )
);

CREATE INDEX IF NOT EXISTS idx_run_state_runs_created_at ON nexus.run_state_runs(created_at DESC);

CREATE TABLE IF NOT EXISTS nexus.run_state_events (
    id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES nexus.run_state_runs(run_id) ON DELETE CASCADE,
    from_state VARCHAR(32) NOT NULL,
    to_state VARCHAR(32) NOT NULL,
    phase VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL DEFAULT 'state_transition',
    event_payload_json JSONB,
    policy_decisions_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_run_state_events_transition CHECK (
        (from_state = 'requested' AND to_state = 'planned') OR
        (from_state = 'planned' AND to_state = 'retrieval_done') OR
        (from_state = 'retrieval_done' AND to_state = 'draft_done') OR
        (from_state = 'draft_done' AND to_state = 'critique_done') OR
        (from_state = 'draft_done' AND to_state = 'validated') OR
        (from_state = 'critique_done' AND to_state = 'validated') OR
        (from_state = 'validated' AND to_state = 'completed') OR
        (from_state = 'validated' AND to_state = 'failed') OR
        (from_state = 'validated' AND to_state = 'blocked')
    )
);

CREATE INDEX IF NOT EXISTS idx_run_state_events_run_created ON nexus.run_state_events(run_id, created_at DESC);
