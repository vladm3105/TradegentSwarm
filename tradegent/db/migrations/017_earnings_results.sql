-- Migration 017: Create kb_earnings_results table
-- Stores actual earnings results for easy querying and historical analysis

-- ============================================================================
-- kb_earnings_results: Actual earnings data
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.kb_earnings_results (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    earnings_time VARCHAR(10),  -- BMO (before market open), AMC (after market close)
    fiscal_quarter VARCHAR(10), -- Q1, Q2, Q3, Q4
    fiscal_year INTEGER,

    -- EPS Data
    eps_actual NUMERIC(10,4),
    eps_consensus NUMERIC(10,4),
    eps_whisper NUMERIC(10,4),
    eps_surprise_pct NUMERIC(8,4),
    eps_beat BOOLEAN GENERATED ALWAYS AS (eps_actual > eps_consensus) STORED,

    -- Revenue Data
    revenue_actual NUMERIC(16,2),      -- In millions
    revenue_consensus NUMERIC(16,2),
    revenue_surprise_pct NUMERIC(8,4),
    revenue_beat BOOLEAN GENERATED ALWAYS AS (revenue_actual > revenue_consensus) STORED,

    -- YoY Growth
    eps_yoy_growth_pct NUMERIC(8,2),
    revenue_yoy_growth_pct NUMERIC(8,2),

    -- Guidance
    guidance VARCHAR(20),  -- raised, maintained, lowered, withdrawn
    guidance_details TEXT,
    next_quarter_revenue_guide NUMERIC(16,2),
    next_quarter_eps_guide NUMERIC(10,4),

    -- Key Metrics (company-specific)
    key_metric_name VARCHAR(100),
    key_metric_actual VARCHAR(50),
    key_metric_consensus VARCHAR(50),
    key_metric_surprise_pct NUMERIC(8,4),

    -- Stock Reaction
    price_before NUMERIC(12,4),        -- Close before earnings
    price_after_hours NUMERIC(12,4),   -- After-hours price
    price_open_next_day NUMERIC(12,4), -- Next day open
    price_close_next_day NUMERIC(12,4),-- Next day close
    gap_pct NUMERIC(8,4),              -- Gap % at open
    day1_move_pct NUMERIC(8,4),        -- Full day move %
    week1_move_pct NUMERIC(8,4),       -- Week move %
    gap_direction VARCHAR(10),         -- up, down, flat
    day1_direction VARCHAR(10),        -- up, down, flat
    reaction_notes TEXT,

    -- Metadata
    data_source VARCHAR(50),           -- ib_mcp, brave_web_search, manual
    data_timestamp TIMESTAMPTZ,
    source_analysis_id INTEGER REFERENCES nexus.kb_earnings_analyses(id),
    source_review_id INTEGER REFERENCES nexus.kb_reviews(id),

    -- Standard fields
    yaml_content JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    user_id INTEGER REFERENCES nexus.users(id),

    -- Unique constraint
    CONSTRAINT uq_earnings_results_ticker_date UNIQUE (ticker, earnings_date)
);

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_earnings_results_ticker ON nexus.kb_earnings_results(ticker);
CREATE INDEX IF NOT EXISTS idx_earnings_results_date ON nexus.kb_earnings_results(earnings_date DESC);
CREATE INDEX IF NOT EXISTS idx_earnings_results_eps_beat ON nexus.kb_earnings_results(eps_beat);
CREATE INDEX IF NOT EXISTS idx_earnings_results_revenue_beat ON nexus.kb_earnings_results(revenue_beat);
CREATE INDEX IF NOT EXISTS idx_earnings_results_guidance ON nexus.kb_earnings_results(guidance);
CREATE INDEX IF NOT EXISTS idx_earnings_results_day1_move ON nexus.kb_earnings_results(day1_move_pct);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE nexus.kb_earnings_results IS 'Actual earnings results with EPS, revenue, guidance, and stock reaction';
COMMENT ON COLUMN nexus.kb_earnings_results.eps_beat IS 'Auto-calculated: true if actual > consensus';
COMMENT ON COLUMN nexus.kb_earnings_results.revenue_beat IS 'Auto-calculated: true if actual > consensus';
COMMENT ON COLUMN nexus.kb_earnings_results.gap_pct IS 'Gap percentage at next day open vs previous close';
COMMENT ON COLUMN nexus.kb_earnings_results.day1_move_pct IS 'Full day move percentage (close to close)';

-- ============================================================================
-- Backfill from existing post-earnings reviews
-- ============================================================================

INSERT INTO nexus.kb_earnings_results (
    ticker, earnings_date, earnings_time,
    eps_actual, eps_consensus, eps_whisper, eps_surprise_pct,
    revenue_actual, revenue_consensus, revenue_surprise_pct,
    revenue_yoy_growth_pct, guidance, guidance_details,
    key_metric_name, key_metric_actual, key_metric_consensus, key_metric_surprise_pct,
    day1_move_pct, gap_direction, day1_direction, reaction_notes,
    data_source, data_timestamp, source_review_id, yaml_content
)
SELECT
    r.ticker,
    COALESCE(
        (r.yaml_content->'earnings_date')::text::date,
        (r.yaml_content->>'earnings_date')::date,
        r.created_at::date
    ),
    r.yaml_content->>'earnings_time',
    (r.yaml_content->'actual_results'->'eps'->>'actual')::numeric,
    (r.yaml_content->'actual_results'->'eps'->>'consensus')::numeric,
    (r.yaml_content->'actual_results'->'eps'->>'whisper')::numeric,
    (r.yaml_content->'actual_results'->'eps'->>'surprise_pct')::numeric,
    (r.yaml_content->'actual_results'->'revenue'->>'actual_b')::numeric * 1000, -- Convert B to M
    (r.yaml_content->'actual_results'->'revenue'->>'consensus_b')::numeric * 1000,
    (r.yaml_content->'actual_results'->'revenue'->>'surprise_pct')::numeric,
    (r.yaml_content->'actual_results'->>'yoy_growth_pct')::numeric,
    r.yaml_content->'actual_results'->>'guidance',
    r.yaml_content->'actual_results'->>'guidance_details',
    r.yaml_content->'actual_results'->'key_metric'->>'name',
    r.yaml_content->'actual_results'->'key_metric'->>'actual',
    r.yaml_content->'actual_results'->'key_metric'->>'consensus',
    (r.yaml_content->'actual_results'->'key_metric'->>'surprise_pct')::numeric,
    (r.yaml_content->'actual_results'->'stock_reaction'->>'day1_move_pct')::numeric,
    r.yaml_content->'actual_results'->'stock_reaction'->>'gap_direction',
    r.yaml_content->'actual_results'->'stock_reaction'->>'day1_direction',
    r.yaml_content->'actual_results'->'stock_reaction'->>'reaction_notes',
    r.yaml_content->'actual_results'->>'data_source',
    (r.yaml_content->'actual_results'->>'data_timestamp')::timestamptz,
    r.id,
    r.yaml_content->'actual_results'
FROM nexus.kb_reviews r
WHERE r.review_type = 'post-earnings-review'
  AND r.yaml_content->'actual_results' IS NOT NULL
ON CONFLICT (ticker, earnings_date) DO NOTHING;

-- ============================================================================
-- Views for analysis
-- ============================================================================

-- Earnings surprise analysis
CREATE OR REPLACE VIEW nexus.v_earnings_surprises AS
SELECT
    ticker,
    earnings_date,
    fiscal_quarter,
    eps_actual,
    eps_consensus,
    eps_surprise_pct,
    eps_beat,
    revenue_actual,
    revenue_consensus,
    revenue_surprise_pct,
    revenue_beat,
    guidance,
    day1_move_pct,
    gap_direction,
    -- Classify the reaction
    CASE
        WHEN eps_beat AND revenue_beat AND day1_move_pct > 0 THEN 'beat_up'
        WHEN eps_beat AND revenue_beat AND day1_move_pct < 0 THEN 'beat_down'  -- Sell the news
        WHEN NOT eps_beat AND NOT revenue_beat AND day1_move_pct < 0 THEN 'miss_down'
        WHEN NOT eps_beat AND NOT revenue_beat AND day1_move_pct > 0 THEN 'miss_up'  -- Buy the dip
        ELSE 'mixed'
    END as reaction_type
FROM nexus.kb_earnings_results
ORDER BY earnings_date DESC;

COMMENT ON VIEW nexus.v_earnings_surprises IS 'Earnings surprises with reaction classification';

-- Ticker earnings history
CREATE OR REPLACE VIEW nexus.v_ticker_earnings_history AS
SELECT
    ticker,
    COUNT(*) as total_reports,
    SUM(CASE WHEN eps_beat THEN 1 ELSE 0 END) as eps_beats,
    SUM(CASE WHEN revenue_beat THEN 1 ELSE 0 END) as revenue_beats,
    ROUND(100.0 * SUM(CASE WHEN eps_beat THEN 1 ELSE 0 END) / COUNT(*), 1) as eps_beat_rate,
    ROUND(100.0 * SUM(CASE WHEN revenue_beat THEN 1 ELSE 0 END) / COUNT(*), 1) as revenue_beat_rate,
    ROUND(AVG(eps_surprise_pct), 2) as avg_eps_surprise,
    ROUND(AVG(day1_move_pct), 2) as avg_day1_move,
    SUM(CASE WHEN eps_beat AND day1_move_pct < 0 THEN 1 ELSE 0 END) as sell_the_news_count,
    MAX(earnings_date) as last_earnings_date
FROM nexus.kb_earnings_results
GROUP BY ticker
ORDER BY total_reports DESC;

COMMENT ON VIEW nexus.v_ticker_earnings_history IS 'Aggregated earnings history per ticker';
