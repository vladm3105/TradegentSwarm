-- Migration 006: Options-specific trade tracking
-- Created: 2026-02-25
-- Run: cd tradegent && python scripts/apply_migration.py 006
-- Depends on: 005 (position detection)
--
-- Adds options-specific columns to trades table:
-- - full_symbol: Full OCC symbol for options (e.g., "NVDA  240315C00500000")
-- - option_underlying: Base ticker (e.g., "NVDA")
-- - option_expiration: Expiration date
-- - option_strike: Strike price
-- - option_type: 'call' or 'put'
-- - option_multiplier: Contract multiplier (100 standard, 10 mini)
-- - is_credit: True if sold to open
-- - expiration_action: How position ended (expired_worthless, exercised, assigned)

-- Check if this migration already applied
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM nexus.migrations WHERE id = '006') THEN
        RAISE EXCEPTION 'Migration 006 already applied';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- ADD OPTIONS-SPECIFIC COLUMNS TO TRADES TABLE
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE nexus.trades
ADD COLUMN IF NOT EXISTS full_symbol VARCHAR(50),
ADD COLUMN IF NOT EXISTS option_underlying VARCHAR(10),
ADD COLUMN IF NOT EXISTS option_expiration DATE,
ADD COLUMN IF NOT EXISTS option_strike DECIMAL(10,2),
ADD COLUMN IF NOT EXISTS option_type VARCHAR(4),  -- 'call' or 'put'
ADD COLUMN IF NOT EXISTS option_multiplier INTEGER DEFAULT 100,
ADD COLUMN IF NOT EXISTS is_credit BOOLEAN DEFAULT FALSE,  -- True if sold to open
ADD COLUMN IF NOT EXISTS expiration_action VARCHAR(20);  -- 'expired_worthless', 'exercised', 'assigned'

COMMENT ON COLUMN nexus.trades.full_symbol IS 'Full OCC symbol for options, ticker for stocks';
COMMENT ON COLUMN nexus.trades.option_underlying IS 'Underlying ticker for options';
COMMENT ON COLUMN nexus.trades.option_expiration IS 'Option expiration date';
COMMENT ON COLUMN nexus.trades.option_strike IS 'Option strike price';
COMMENT ON COLUMN nexus.trades.option_type IS 'call or put';
COMMENT ON COLUMN nexus.trades.option_multiplier IS 'Contract multiplier (100 standard, 10 mini)';
COMMENT ON COLUMN nexus.trades.is_credit IS 'True if position opened with credit (sold option)';
COMMENT ON COLUMN nexus.trades.expiration_action IS 'How option position ended: expired_worthless, exercised, assigned';

-- Index for options queries
CREATE INDEX IF NOT EXISTS idx_trades_options
ON nexus.trades(option_underlying, option_expiration)
WHERE option_underlying IS NOT NULL;

-- Index for expiration monitoring
CREATE INDEX IF NOT EXISTS idx_trades_option_expiry
ON nexus.trades(option_expiration)
WHERE option_expiration IS NOT NULL AND status = 'open';

-- Index for full_symbol lookups (used in idempotency)
CREATE INDEX IF NOT EXISTS idx_trades_full_symbol
ON nexus.trades(full_symbol)
WHERE full_symbol IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- UPDATE POSITION_DETECTIONS FOR OPTIONS SUPPORT
-- ═══════════════════════════════════════════════════════════════════════════
-- Add full_symbol column for options idempotency (different options same underlying)

ALTER TABLE nexus.position_detections
ADD COLUMN IF NOT EXISTS full_symbol VARCHAR(50);

-- Drop old unique constraint and add new one with full_symbol
ALTER TABLE nexus.position_detections
DROP CONSTRAINT IF EXISTS position_detections_ticker_detected_date_size_key;

-- New unique constraint: use full_symbol if present, else ticker
CREATE UNIQUE INDEX IF NOT EXISTS idx_position_detections_unique
ON nexus.position_detections(COALESCE(full_symbol, ticker), detected_date, size);

-- ═══════════════════════════════════════════════════════════════════════════
-- VIEW: OPEN OPTIONS POSITIONS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW nexus.v_options_positions AS
SELECT
    id,
    ticker,
    full_symbol,
    option_underlying,
    option_expiration,
    option_strike,
    option_type,
    option_multiplier,
    is_credit,
    entry_price,
    entry_size,
    current_size,
    status,
    direction,
    source_type,
    (option_expiration - CURRENT_DATE) as days_to_expiry,
    CASE
        WHEN (option_expiration - CURRENT_DATE) < 0 THEN 'EXPIRED'
        WHEN (option_expiration - CURRENT_DATE) <= 3 THEN 'CRITICAL'
        WHEN (option_expiration - CURRENT_DATE) <= 7 THEN 'WARNING'
        ELSE 'OK'
    END as expiry_status
FROM nexus.trades
WHERE option_underlying IS NOT NULL
  AND status = 'open'
ORDER BY option_expiration ASC;

-- ═══════════════════════════════════════════════════════════════════════════
-- VIEW: EXPIRING OPTIONS (next 7 days)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW nexus.v_expiring_options AS
SELECT * FROM nexus.v_options_positions
WHERE days_to_expiry <= 7
ORDER BY option_expiration ASC;

-- ═══════════════════════════════════════════════════════════════════════════
-- SETTINGS
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('options_expiry_warning_days', '7', 'thresholds',
     'Days before expiry to warn about options'),
    ('options_expiry_critical_days', '3', 'thresholds',
     'Days before expiry for critical warning'),
    ('track_options_separately', 'true', 'feature_flags',
     'Use full symbol for options positions'),
    ('auto_close_expired_options', 'true', 'feature_flags',
     'Auto-close options on expiration date')
ON CONFLICT (key) DO NOTHING;

-- Record migration
INSERT INTO nexus.migrations (id, description) VALUES
    ('006', 'Options-specific trade tracking: full_symbol, expiration, strike, multiplier');
