-- Migration 008: Skill settings and invocation tracking
-- Created: 2026-02-25
-- Run: cd tradegent && python scripts/apply_migration.py 008
-- Depends on: 007 (notification log)
--
-- Adds:
-- - Skill-related settings for cost control and feature flags
-- - Skill invocations tracking table for monitoring and cost tracking
-- - stop_loss and target_price columns to trades (if missing)

-- Check if this migration already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM nexus.migrations WHERE id = '008') THEN
        RAISE EXCEPTION 'Migration 008 already applied';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 1: SKILL SETTINGS
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('skill_auto_invoke_enabled', 'true', 'skills', 'Enable auto-triggered skill processing'),
    ('skill_use_claude_code', 'false', 'skills', 'Use Claude Code for complex skills (costs $0.20-0.45/call)'),
    ('skill_daily_cost_limit', '5.00', 'skills', 'Max daily spend on Claude Code skill calls'),
    ('skill_cooldown_hours', '1', 'skills', 'Hours between same skill invocation for same ticker'),
    ('detected_position_auto_create_trade', 'true', 'skills', 'Auto-create trade entry for detected positions'),
    ('fill_analysis_enabled', 'true', 'skills', 'Enable fill quality analysis'),
    ('position_close_review_enabled', 'true', 'skills', 'Enable position close review'),
    ('expiration_review_enabled', 'true', 'skills', 'Enable expiration review')
ON CONFLICT (key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 2: SKILL INVOCATIONS TRACKING TABLE
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS nexus.skill_invocations (
    id              SERIAL PRIMARY KEY,
    skill_name      VARCHAR(50) NOT NULL,
    ticker          VARCHAR(20),
    invocation_type VARCHAR(20) NOT NULL,  -- 'python' or 'claude_code'
    cost_estimate   DECIMAL(10,4) DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'started',  -- started, completed, failed
    error_message   TEXT,
    output_path     VARCHAR(255),
    -- Context tracking
    trigger_source  VARCHAR(50),  -- position_monitor, expiration_monitor, order_reconciler, user
    task_id         INTEGER
);

CREATE INDEX IF NOT EXISTS idx_skill_invocations_date
ON nexus.skill_invocations(started_at);

CREATE INDEX IF NOT EXISTS idx_skill_invocations_skill
ON nexus.skill_invocations(skill_name);

CREATE INDEX IF NOT EXISTS idx_skill_invocations_daily_cost
ON nexus.skill_invocations(started_at, invocation_type)
WHERE status = 'completed';

COMMENT ON TABLE nexus.skill_invocations IS
    'Tracks skill invocations for cost monitoring and debugging';

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 3: TRADES TABLE ENHANCEMENTS
-- ═══════════════════════════════════════════════════════════════════════════

-- Add stop_loss and target_price if not present
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'nexus' AND table_name = 'trades'
                   AND column_name = 'stop_loss') THEN
        ALTER TABLE nexus.trades ADD COLUMN stop_loss DECIMAL(12,4);
        COMMENT ON COLUMN nexus.trades.stop_loss IS 'Stop loss price';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_schema = 'nexus' AND table_name = 'trades'
                   AND column_name = 'target_price') THEN
        ALTER TABLE nexus.trades ADD COLUMN target_price DECIMAL(12,4);
        COMMENT ON COLUMN nexus.trades.target_price IS 'Target/take-profit price';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- PART 4: VIEW FOR DAILY SKILL COSTS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW nexus.v_skill_daily_costs AS
SELECT
    DATE(started_at) as date,
    COUNT(*) FILTER (WHERE invocation_type = 'claude_code') as claude_calls,
    COUNT(*) FILTER (WHERE invocation_type = 'python') as python_calls,
    COALESCE(SUM(cost_estimate) FILTER (WHERE invocation_type = 'claude_code' AND status = 'completed'), 0) as total_cost,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_calls
FROM nexus.skill_invocations
WHERE started_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(started_at)
ORDER BY date DESC;

-- Record migration
INSERT INTO nexus.migrations (id, description) VALUES
    ('008', 'Skill settings and invocation tracking for monitoring integration');
