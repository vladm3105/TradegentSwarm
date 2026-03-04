-- Migration 018: Complete Schema Gaps
-- Addresses remaining schema gaps for full data integrity and tracking

-- ============================================================================
-- 1. Fix kb_trade_journals.source_analysis_id FK constraint
-- ============================================================================

-- Add FK to kb_stock_analyses (nullable, can reference either stock or earnings)
ALTER TABLE nexus.kb_trade_journals
    ADD COLUMN IF NOT EXISTS source_stock_analysis_id INTEGER REFERENCES nexus.kb_stock_analyses(id),
    ADD COLUMN IF NOT EXISTS source_earnings_analysis_id INTEGER REFERENCES nexus.kb_earnings_analyses(id);

COMMENT ON COLUMN nexus.kb_trade_journals.source_stock_analysis_id IS 'FK to stock analysis that triggered this trade';
COMMENT ON COLUMN nexus.kb_trade_journals.source_earnings_analysis_id IS 'FK to earnings analysis that triggered this trade';

-- Backfill from source_analysis_id based on source_analysis_type
UPDATE nexus.kb_trade_journals
SET source_stock_analysis_id = source_analysis_id
WHERE source_analysis_type = 'stock' AND source_analysis_id IS NOT NULL;

UPDATE nexus.kb_trade_journals
SET source_earnings_analysis_id = source_analysis_id
WHERE source_analysis_type = 'earnings' AND source_analysis_id IS NOT NULL;

-- ============================================================================
-- 2. Add source analysis link to kb_watchlist_entries
-- ============================================================================

ALTER TABLE nexus.kb_watchlist_entries
    ADD COLUMN IF NOT EXISTS source_stock_analysis_id INTEGER REFERENCES nexus.kb_stock_analyses(id),
    ADD COLUMN IF NOT EXISTS source_earnings_analysis_id INTEGER REFERENCES nexus.kb_earnings_analyses(id),
    ADD COLUMN IF NOT EXISTS source_scanner_id INTEGER REFERENCES nexus.kb_scanner_configs(id),
    ADD COLUMN IF NOT EXISTS triggered_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS triggered_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS resulting_trade_id INTEGER REFERENCES nexus.kb_trade_journals(id);

COMMENT ON COLUMN nexus.kb_watchlist_entries.source_stock_analysis_id IS 'Stock analysis that created this watchlist entry';
COMMENT ON COLUMN nexus.kb_watchlist_entries.source_earnings_analysis_id IS 'Earnings analysis that created this watchlist entry';
COMMENT ON COLUMN nexus.kb_watchlist_entries.source_scanner_id IS 'Scanner that found this opportunity';
COMMENT ON COLUMN nexus.kb_watchlist_entries.triggered_at IS 'When the entry trigger condition was met';
COMMENT ON COLUMN nexus.kb_watchlist_entries.triggered_price IS 'Price when trigger fired';
COMMENT ON COLUMN nexus.kb_watchlist_entries.resulting_trade_id IS 'Trade created from this watchlist entry';

-- ============================================================================
-- 3. Create kb_price_history for backtesting
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.kb_price_history (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    price_date DATE NOT NULL,

    -- OHLCV
    open_price NUMERIC(12,4),
    high_price NUMERIC(12,4),
    low_price NUMERIC(12,4),
    close_price NUMERIC(12,4),
    adj_close NUMERIC(12,4),
    volume BIGINT,

    -- Technical indicators (can be computed or stored)
    sma_20 NUMERIC(12,4),
    sma_50 NUMERIC(12,4),
    sma_200 NUMERIC(12,4),
    ema_9 NUMERIC(12,4),
    ema_21 NUMERIC(12,4),
    rsi_14 NUMERIC(5,2),
    atr_14 NUMERIC(12,4),

    -- Relative strength
    relative_volume NUMERIC(8,4),  -- Volume / Avg volume
    distance_from_52w_high NUMERIC(8,4),
    distance_from_52w_low NUMERIC(8,4),

    -- Source
    data_source VARCHAR(50),  -- ib_mcp, yahoo, polygon

    created_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_price_history UNIQUE (ticker, price_date)
);

CREATE INDEX IF NOT EXISTS idx_price_history_ticker ON nexus.kb_price_history(ticker);
CREATE INDEX IF NOT EXISTS idx_price_history_date ON nexus.kb_price_history(price_date DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_ticker_date ON nexus.kb_price_history(ticker, price_date DESC);

COMMENT ON TABLE nexus.kb_price_history IS 'Historical price data for backtesting and target verification';

-- ============================================================================
-- 4. Create kb_alert_tracking for monitoring alert triggers
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.kb_alert_tracking (
    id SERIAL PRIMARY KEY,

    -- Source
    ticker VARCHAR(20) NOT NULL,
    source_stock_analysis_id INTEGER REFERENCES nexus.kb_stock_analyses(id),
    source_earnings_analysis_id INTEGER REFERENCES nexus.kb_earnings_analyses(id),
    source_watchlist_id INTEGER REFERENCES nexus.kb_watchlist_entries(id),

    -- Alert definition
    alert_type VARCHAR(50) NOT NULL,  -- price_above, price_below, volume_spike, news, earnings_date
    alert_level NUMERIC(12,4),        -- Price level for price alerts
    alert_tag VARCHAR(50),            -- Tag from analysis (e.g., "20-day MA", "Entry")
    direction VARCHAR(10),            -- above, below
    significance TEXT,                -- Why this level matters

    -- Alert state
    status VARCHAR(20) DEFAULT 'active',  -- active, triggered, expired, cancelled
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,

    -- Trigger details
    triggered_at TIMESTAMPTZ,
    triggered_price NUMERIC(12,4),
    trigger_source VARCHAR(50),       -- ib_mcp, manual, scheduled_check

    -- Action taken
    action_taken VARCHAR(100),
    resulting_trade_id INTEGER REFERENCES nexus.kb_trade_journals(id),
    notes TEXT,

    user_id INTEGER REFERENCES nexus.users(id)
);

CREATE INDEX IF NOT EXISTS idx_alert_tracking_ticker ON nexus.kb_alert_tracking(ticker);
CREATE INDEX IF NOT EXISTS idx_alert_tracking_status ON nexus.kb_alert_tracking(status);
CREATE INDEX IF NOT EXISTS idx_alert_tracking_active ON nexus.kb_alert_tracking(ticker, status) WHERE status = 'active';

COMMENT ON TABLE nexus.kb_alert_tracking IS 'Tracks price alerts from analyses and their trigger status';

-- ============================================================================
-- 5. Create kb_target_tracking for verifying if targets were hit
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.kb_target_tracking (
    id SERIAL PRIMARY KEY,

    -- Source analysis
    ticker VARCHAR(20) NOT NULL,
    source_stock_analysis_id INTEGER REFERENCES nexus.kb_stock_analyses(id),
    source_earnings_analysis_id INTEGER REFERENCES nexus.kb_earnings_analyses(id),
    analysis_date TIMESTAMPTZ NOT NULL,

    -- Prices at analysis time
    price_at_analysis NUMERIC(12,4),
    entry_price NUMERIC(12,4),
    stop_price NUMERIC(12,4),
    target_1_price NUMERIC(12,4),
    target_2_price NUMERIC(12,4),

    -- Recommendation
    recommendation VARCHAR(20),
    gate_result VARCHAR(20),

    -- Outcome tracking
    entry_hit BOOLEAN DEFAULT FALSE,
    entry_hit_date DATE,
    entry_hit_price NUMERIC(12,4),

    stop_hit BOOLEAN DEFAULT FALSE,
    stop_hit_date DATE,
    stop_hit_price NUMERIC(12,4),

    target_1_hit BOOLEAN DEFAULT FALSE,
    target_1_hit_date DATE,
    target_1_hit_price NUMERIC(12,4),

    target_2_hit BOOLEAN DEFAULT FALSE,
    target_2_hit_date DATE,
    target_2_hit_price NUMERIC(12,4),

    -- Time-based outcome
    days_tracked INTEGER DEFAULT 0,
    max_price_seen NUMERIC(12,4),
    max_price_date DATE,
    min_price_seen NUMERIC(12,4),
    min_price_date DATE,

    -- Final outcome
    outcome VARCHAR(30),  -- target_1_hit, target_2_hit, stopped_out, expired, mixed
    return_if_traded_pct NUMERIC(8,4),  -- Hypothetical return if traded

    -- Metadata
    tracking_start_date DATE,
    tracking_end_date DATE,
    status VARCHAR(20) DEFAULT 'tracking',  -- tracking, completed, abandoned

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_target_tracking_ticker ON nexus.kb_target_tracking(ticker);
CREATE INDEX IF NOT EXISTS idx_target_tracking_status ON nexus.kb_target_tracking(status);
CREATE INDEX IF NOT EXISTS idx_target_tracking_outcome ON nexus.kb_target_tracking(outcome);

COMMENT ON TABLE nexus.kb_target_tracking IS 'Tracks whether analysis price targets were actually hit';

-- ============================================================================
-- 6. Link kb_stock_analyses to kb_earnings_results via ticker proximity
-- ============================================================================

-- Add column to link stock analysis to nearest earnings result
ALTER TABLE nexus.kb_stock_analyses
    ADD COLUMN IF NOT EXISTS nearest_earnings_result_id INTEGER REFERENCES nexus.kb_earnings_results(id),
    ADD COLUMN IF NOT EXISTS days_from_earnings INTEGER;

COMMENT ON COLUMN nexus.kb_stock_analyses.nearest_earnings_result_id IS 'Nearest earnings result for context';
COMMENT ON COLUMN nexus.kb_stock_analyses.days_from_earnings IS 'Days from/to nearest earnings (negative=before, positive=after)';

-- ============================================================================
-- 7. Views for tracking and backtesting
-- ============================================================================

-- Active alerts view
CREATE OR REPLACE VIEW nexus.v_active_alerts AS
SELECT
    a.id,
    a.ticker,
    a.alert_type,
    a.alert_level,
    a.alert_tag,
    a.direction,
    a.significance,
    a.expires_at,
    CASE
        WHEN sa.id IS NOT NULL THEN 'stock'
        WHEN ea.id IS NOT NULL THEN 'earnings'
        ELSE 'watchlist'
    END as source_type,
    COALESCE(sa.recommendation, ea.recommendation) as recommendation,
    COALESCE(sa.gate_result, ea.gate_result) as gate_result
FROM nexus.kb_alert_tracking a
LEFT JOIN nexus.kb_stock_analyses sa ON a.source_stock_analysis_id = sa.id
LEFT JOIN nexus.kb_earnings_analyses ea ON a.source_earnings_analysis_id = ea.id
WHERE a.status = 'active'
ORDER BY a.ticker, a.alert_level;

COMMENT ON VIEW nexus.v_active_alerts IS 'All active price alerts from analyses';

-- Target tracking summary view
CREATE OR REPLACE VIEW nexus.v_target_accuracy AS
SELECT
    recommendation,
    gate_result,
    COUNT(*) as total_analyses,
    SUM(CASE WHEN entry_hit THEN 1 ELSE 0 END) as entries_hit,
    SUM(CASE WHEN target_1_hit THEN 1 ELSE 0 END) as target_1_hits,
    SUM(CASE WHEN target_2_hit THEN 1 ELSE 0 END) as target_2_hits,
    SUM(CASE WHEN stop_hit THEN 1 ELSE 0 END) as stops_hit,
    ROUND(100.0 * SUM(CASE WHEN target_1_hit THEN 1 ELSE 0 END) / NULLIF(SUM(CASE WHEN entry_hit THEN 1 ELSE 0 END), 0), 1) as target_1_rate,
    ROUND(AVG(return_if_traded_pct), 2) as avg_return_pct
FROM nexus.kb_target_tracking
WHERE status = 'completed'
GROUP BY recommendation, gate_result
ORDER BY recommendation, gate_result;

COMMENT ON VIEW nexus.v_target_accuracy IS 'Analysis accuracy by recommendation and gate result';

-- Trade flow view (analysis → watchlist → trade → review)
CREATE OR REPLACE VIEW nexus.v_trade_flow AS
SELECT
    t.id as trade_id,
    t.ticker,
    t.direction,
    t.entry_date,
    t.exit_date,
    t.return_pct,
    t.outcome,
    t.overall_grade,
    sa.id as stock_analysis_id,
    sa.recommendation as stock_rec,
    sa.gate_result as stock_gate,
    ea.id as earnings_analysis_id,
    ea.recommendation as earnings_rec,
    w.id as watchlist_id,
    w.status as watchlist_status,
    r.id as review_id,
    r.overall_grade as review_grade,
    r.primary_lesson
FROM nexus.kb_trade_journals t
LEFT JOIN nexus.kb_stock_analyses sa ON t.source_stock_analysis_id = sa.id
LEFT JOIN nexus.kb_earnings_analyses ea ON t.source_earnings_analysis_id = ea.id
LEFT JOIN nexus.kb_watchlist_entries w ON w.resulting_trade_id = t.id
LEFT JOIN nexus.kb_reviews r ON r.source_trade_id = t.id
ORDER BY t.entry_date DESC;

COMMENT ON VIEW nexus.v_trade_flow IS 'Complete trade flow from analysis to review';

-- ============================================================================
-- 8. Add indexes for common query patterns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_stock_analyses_rec_gate ON nexus.kb_stock_analyses(recommendation, gate_result);
CREATE INDEX IF NOT EXISTS idx_earnings_analyses_rec_gate ON nexus.kb_earnings_analyses(recommendation, gate_result);
CREATE INDEX IF NOT EXISTS idx_trade_journals_outcome ON nexus.kb_trade_journals(outcome);
CREATE INDEX IF NOT EXISTS idx_trade_journals_ticker_date ON nexus.kb_trade_journals(ticker, entry_date DESC);
