-- Migration 005: Position Increase Detection
-- Created: 2026-02-25
-- Run: cd tradegent && python scripts/apply_migration.py 005
--
-- Adds support for tracking externally-added positions (via TWS, mobile app, etc.)
-- that weren't created through the orchestrator.

-- Check if migration tracking table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables
                   WHERE table_schema = 'nexus' AND table_name = 'migrations') THEN
        CREATE TABLE nexus.migrations (
            id              VARCHAR(50) PRIMARY KEY,
            applied_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            description     TEXT
        );
    END IF;
END $$;

-- Check if this migration already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM nexus.migrations WHERE id = '005') THEN
        RAISE EXCEPTION 'Migration 005 already applied';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- ADD SOURCE_TYPE TO TRADES TABLE
-- ═══════════════════════════════════════════════════════════════════════════
-- Tracks how the trade was created:
-- - 'orchestrator': Normal flow via orchestrator (default)
-- - 'detected': Auto-created by position monitor
-- - 'confirmed': User verified a detected trade
-- - 'manual': Created via CLI

ALTER TABLE nexus.trades ADD COLUMN IF NOT EXISTS
    source_type VARCHAR(20) DEFAULT 'orchestrator';

COMMENT ON COLUMN nexus.trades.source_type IS
    'How trade was created: orchestrator (normal), detected (position monitor), confirmed (user verified detected), manual (CLI)';

-- Index for filtering by source
CREATE INDEX IF NOT EXISTS idx_trades_source_type ON nexus.trades(source_type);

-- ═══════════════════════════════════════════════════════════════════════════
-- POSITION DETECTION TRACKING TABLE (IDEMPOTENCY)
-- ═══════════════════════════════════════════════════════════════════════════
-- Prevents duplicate trade entries when position monitor runs multiple times
-- for the same detected increase.

CREATE TABLE IF NOT EXISTS nexus.position_detections (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    size            NUMERIC(15,4) NOT NULL,
    trade_id        INTEGER REFERENCES nexus.trades(id),
    detected_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate detections same day
    UNIQUE(ticker, detected_date, size)
);

COMMENT ON TABLE nexus.position_detections IS
    'Tracks detected position increases for idempotency - prevents duplicate trade entries';

CREATE INDEX IF NOT EXISTS idx_position_detections_ticker_date
    ON nexus.position_detections(ticker, detected_date);

-- ═══════════════════════════════════════════════════════════════════════════
-- TRADES ARCHIVE TABLE
-- ═══════════════════════════════════════════════════════════════════════════
-- Stores rejected detected trades for audit trail instead of hard deleting

CREATE TABLE IF NOT EXISTS nexus.trades_archive (
    id              INTEGER PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,
    entry_date      TIMESTAMPTZ,
    entry_price     NUMERIC(12,4),
    entry_size      NUMERIC(15,4),
    direction       VARCHAR(10),
    thesis          TEXT,
    source_type     VARCHAR(20),
    source_analysis VARCHAR(200),
    archived_at     TIMESTAMPTZ DEFAULT now(),
    archive_reason  TEXT
);

COMMENT ON TABLE nexus.trades_archive IS
    'Archive of rejected/deleted trades for audit trail';

-- ═══════════════════════════════════════════════════════════════════════════
-- POSITION DETECTION SETTINGS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('auto_track_position_increases', 'true', 'feature_flags',
     'Auto-create trade entries for externally-added positions'),
    ('position_detect_min_value', '100', 'thresholds',
     'Minimum position value ($) to track (skip tiny positions)'),
    ('position_detect_cooldown_hours', '1', 'rate_limits',
     'Minimum hours between detections for same ticker')
ON CONFLICT (key) DO NOTHING;

-- Record migration
INSERT INTO nexus.migrations (id, description) VALUES
    ('005', 'Position increase detection: source_type, detections, archive tables');
