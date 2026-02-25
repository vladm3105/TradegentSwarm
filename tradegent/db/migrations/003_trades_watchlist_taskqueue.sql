-- Migration 003: Add trades, watchlist, and task_queue tables
-- Created: 2026-02-25
-- Run: cd tradegent && python scripts/apply_migration.py 003

-- Verify prerequisite function exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc
        WHERE proname = 'update_timestamp'
        AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'nexus')
    ) THEN
        RAISE EXCEPTION 'Required function nexus.update_timestamp() does not exist. Run init.sql first.';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- MIGRATION TRACKING TABLE
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.migrations (
    id              VARCHAR(50) PRIMARY KEY,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    description     TEXT
);

-- Check if this migration already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM nexus.migrations WHERE id = '003') THEN
        RAISE EXCEPTION 'Migration 003 already applied';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- TRADES TABLE
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.trades (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    entry_date      TIMESTAMPTZ NOT NULL,
    entry_price     DECIMAL(12,4) NOT NULL,
    entry_size      DECIMAL(12,4),
    entry_type      VARCHAR(20) DEFAULT 'stock',
    status          VARCHAR(20) DEFAULT 'open',
    current_size    DECIMAL(12,4),
    exit_date       TIMESTAMPTZ,
    exit_price      DECIMAL(12,4),
    exit_reason     VARCHAR(50),
    pnl_dollars     DECIMAL(12,2),
    pnl_pct         DECIMAL(8,4),
    thesis          TEXT,
    source_analysis VARCHAR(200),
    review_status   VARCHAR(20) DEFAULT 'pending',
    review_path     VARCHAR(200),
    -- Order tracking
    order_id        VARCHAR(50),
    ib_order_status VARCHAR(20),
    partial_fills   JSONB DEFAULT '[]',
    avg_fill_price  DECIMAL(12,4),
    -- Direction tracking (for short positions)
    direction       VARCHAR(10) DEFAULT 'long',  -- 'long' or 'short'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON nexus.trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_status ON nexus.trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_review ON nexus.trades(review_status) WHERE status = 'closed';
CREATE INDEX IF NOT EXISTS idx_trades_order_id ON nexus.trades(order_id) WHERE order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trades_open ON nexus.trades(ticker, status) WHERE status = 'open';

DROP TRIGGER IF EXISTS trades_updated_at ON nexus.trades;
CREATE TRIGGER trades_updated_at BEFORE UPDATE ON nexus.trades
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

-- ═══════════════════════════════════════════════════════════════════════════
-- WATCHLIST TABLE
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.watchlist (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    entry_trigger   TEXT NOT NULL,
    entry_price     DECIMAL(12,4),
    invalidation    TEXT,
    invalidation_price DECIMAL(12,4),
    expires_at      TIMESTAMPTZ,
    priority        VARCHAR(10) DEFAULT 'medium',
    status          VARCHAR(20) DEFAULT 'active',
    source          VARCHAR(50),
    source_analysis VARCHAR(200),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON nexus.watchlist(ticker);
CREATE INDEX IF NOT EXISTS idx_watchlist_active ON nexus.watchlist(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_watchlist_expires ON nexus.watchlist(expires_at) WHERE status = 'active';

DROP TRIGGER IF EXISTS watchlist_updated_at ON nexus.watchlist;
CREATE TRIGGER watchlist_updated_at BEFORE UPDATE ON nexus.watchlist
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

-- ═══════════════════════════════════════════════════════════════════════════
-- TASK QUEUE TABLE
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.task_queue (
    id              SERIAL PRIMARY KEY,
    task_type       VARCHAR(50) NOT NULL,
    ticker          VARCHAR(10),
    analysis_type   VARCHAR(20),
    prompt          TEXT,
    priority        INTEGER DEFAULT 5,
    status          VARCHAR(20) DEFAULT 'pending',
    cooldown_key    VARCHAR(100),
    cooldown_until  TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_queue_pending ON nexus.task_queue(status, priority DESC) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_task_queue_cooldown ON nexus.task_queue(cooldown_key, cooldown_until);

-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFLOW AUTOMATION SETTINGS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('auto_viz_enabled', 'true', 'feature_flags', 'Auto-generate SVG after analysis'),
    ('auto_watchlist_chain', 'true', 'feature_flags', 'Auto-add WATCH recommendations to watchlist'),
    ('scanner_auto_route', 'true', 'feature_flags', 'Auto-route scanner results to analysis/watchlist'),
    ('task_queue_enabled', 'true', 'feature_flags', 'Enable async task queue processing'),
    ('analysis_cooldown_hours', '4', 'rate_limits', 'Hours between re-analyzing same ticker'),
    ('position_monitor_enabled', 'true', 'feature_flags', 'Enable position monitoring in service tick'),
    ('position_monitor_interval_seconds', '300', 'scheduler', 'Seconds between position checks')
ON CONFLICT (key) DO NOTHING;

-- Record migration
INSERT INTO nexus.migrations (id, description) VALUES ('003', 'Add trades, watchlist, task_queue tables');
