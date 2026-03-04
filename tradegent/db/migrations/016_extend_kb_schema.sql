-- Migration 016: Extend knowledge base schema
-- Adds missing columns to kb_stock_analyses and kb_earnings_analyses
-- for consistent field extraction and queryability

-- ============================================================================
-- kb_stock_analyses: Add case strength and catalyst fields
-- ============================================================================

ALTER TABLE nexus.kb_stock_analyses
    ADD COLUMN IF NOT EXISTS bull_case_strength INTEGER,
    ADD COLUMN IF NOT EXISTS bear_case_strength INTEGER,
    ADD COLUMN IF NOT EXISTS catalyst_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS catalyst_date TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS risk_reward_ratio NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS position_size_pct NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS days_to_catalyst INTEGER;

COMMENT ON COLUMN nexus.kb_stock_analyses.bull_case_strength IS 'Bull case strength score (0-100)';
COMMENT ON COLUMN nexus.kb_stock_analyses.bear_case_strength IS 'Bear case strength score (0-100)';
COMMENT ON COLUMN nexus.kb_stock_analyses.catalyst_type IS 'Type of catalyst (earnings, product_launch, fda, etc.)';
COMMENT ON COLUMN nexus.kb_stock_analyses.catalyst_date IS 'Date of upcoming catalyst';
COMMENT ON COLUMN nexus.kb_stock_analyses.risk_reward_ratio IS 'Risk/reward ratio (e.g., 2.5 = 2.5:1)';
COMMENT ON COLUMN nexus.kb_stock_analyses.position_size_pct IS 'Recommended position size as % of portfolio';
COMMENT ON COLUMN nexus.kb_stock_analyses.days_to_catalyst IS 'Days until catalyst event';

-- ============================================================================
-- kb_earnings_analyses: Add price, probability, and score fields
-- ============================================================================

ALTER TABLE nexus.kb_earnings_analyses
    ADD COLUMN IF NOT EXISTS current_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS entry_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS stop_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS target_1_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS target_2_price NUMERIC(12,4),
    ADD COLUMN IF NOT EXISTS bull_probability NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS base_probability NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS bear_probability NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS disaster_probability NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS catalyst_score INTEGER,
    ADD COLUMN IF NOT EXISTS technical_score INTEGER,
    ADD COLUMN IF NOT EXISTS fundamental_score INTEGER,
    ADD COLUMN IF NOT EXISTS sentiment_score INTEGER,
    ADD COLUMN IF NOT EXISTS total_threat_level VARCHAR(20),
    ADD COLUMN IF NOT EXISTS gate_criteria_met INTEGER,
    ADD COLUMN IF NOT EXISTS risk_reward_ratio NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS position_size_pct NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS iv_rank NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS expected_move_pct NUMERIC(5,2);

COMMENT ON COLUMN nexus.kb_earnings_analyses.current_price IS 'Stock price at analysis time';
COMMENT ON COLUMN nexus.kb_earnings_analyses.entry_price IS 'Recommended entry price';
COMMENT ON COLUMN nexus.kb_earnings_analyses.stop_price IS 'Stop loss price';
COMMENT ON COLUMN nexus.kb_earnings_analyses.target_1_price IS 'First price target';
COMMENT ON COLUMN nexus.kb_earnings_analyses.target_2_price IS 'Second price target';
COMMENT ON COLUMN nexus.kb_earnings_analyses.bull_probability IS 'Bull scenario probability (0-100)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.base_probability IS 'Base scenario probability (0-100)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.bear_probability IS 'Bear scenario probability (0-100)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.disaster_probability IS 'Disaster scenario probability (0-100)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.catalyst_score IS 'Catalyst quality score (0-10)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.technical_score IS 'Technical setup score (0-10)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.fundamental_score IS 'Fundamental score (0-10)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.sentiment_score IS 'Sentiment score (0-10)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.total_threat_level IS 'Overall threat level (low/medium/high/critical)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.gate_criteria_met IS 'Number of Do Nothing gate criteria met (0-4)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.risk_reward_ratio IS 'Risk/reward ratio';
COMMENT ON COLUMN nexus.kb_earnings_analyses.position_size_pct IS 'Recommended position size as % of portfolio';
COMMENT ON COLUMN nexus.kb_earnings_analyses.iv_rank IS 'Implied volatility rank (0-100)';
COMMENT ON COLUMN nexus.kb_earnings_analyses.expected_move_pct IS 'Expected move percentage from options pricing';

-- ============================================================================
-- Create indexes for common query patterns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_kb_stock_catalyst_type ON nexus.kb_stock_analyses(catalyst_type);
CREATE INDEX IF NOT EXISTS idx_kb_stock_catalyst_date ON nexus.kb_stock_analyses(catalyst_date);
CREATE INDEX IF NOT EXISTS idx_kb_stock_bull_strength ON nexus.kb_stock_analyses(bull_case_strength);
CREATE INDEX IF NOT EXISTS idx_kb_stock_bear_strength ON nexus.kb_stock_analyses(bear_case_strength);

CREATE INDEX IF NOT EXISTS idx_kb_earnings_iv_rank ON nexus.kb_earnings_analyses(iv_rank);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_expected_move ON nexus.kb_earnings_analyses(expected_move_pct);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_threat ON nexus.kb_earnings_analyses(total_threat_level);

-- ============================================================================
-- Backfill existing records from yaml_content
-- ============================================================================

-- Backfill kb_stock_analyses
UPDATE nexus.kb_stock_analyses SET
    bull_case_strength = (yaml_content->'bull_case_analysis'->>'strength')::INTEGER,
    bear_case_strength = (yaml_content->'bear_case_analysis'->>'strength')::INTEGER,
    catalyst_type = yaml_content->'catalyst'->>'type',
    risk_reward_ratio = (yaml_content->'do_nothing_gate'->'criteria'->'risk_reward'->>'value')::NUMERIC
WHERE yaml_content IS NOT NULL
  AND bull_case_strength IS NULL;

-- Backfill kb_earnings_analyses
UPDATE nexus.kb_earnings_analyses SET
    current_price = (yaml_content->>'current_price')::NUMERIC,
    entry_price = (yaml_content->'trade_plan'->'entry'->>'price')::NUMERIC,
    stop_price = (yaml_content->'trade_plan'->'stop'->>'price')::NUMERIC,
    target_1_price = (yaml_content->'trade_plan'->'target_1'->>'price')::NUMERIC,
    bull_probability = (yaml_content->'scenarios'->'bull'->>'probability')::NUMERIC,
    base_probability = (yaml_content->'scenarios'->'base'->>'probability')::NUMERIC,
    bear_probability = (yaml_content->'scenarios'->'bear'->>'probability')::NUMERIC,
    disaster_probability = (yaml_content->'scenarios'->'disaster'->>'probability')::NUMERIC,
    catalyst_score = (yaml_content->'scoring'->>'catalyst')::INTEGER,
    technical_score = (yaml_content->'scoring'->>'technical')::INTEGER,
    fundamental_score = (yaml_content->'scoring'->>'fundamental')::INTEGER,
    sentiment_score = (yaml_content->'scoring'->>'sentiment')::INTEGER,
    total_threat_level = yaml_content->'threat_assessment'->>'total_level',
    iv_rank = (yaml_content->'options_data'->>'iv_rank')::NUMERIC,
    expected_move_pct = (yaml_content->'options_data'->>'expected_move_pct')::NUMERIC
WHERE yaml_content IS NOT NULL
  AND current_price IS NULL;

-- ============================================================================
-- Summary view combining both analysis types
-- ============================================================================

CREATE OR REPLACE VIEW nexus.v_all_analyses AS
SELECT
    'stock' as analysis_type,
    id,
    ticker,
    analysis_date,
    recommendation,
    confidence,
    expected_value_pct,
    gate_result,
    gate_criteria_met,
    current_price,
    entry_price,
    stop_price,
    target_1_price,
    bull_probability,
    bear_probability,
    bull_case_strength,
    bear_case_strength,
    catalyst_type,
    catalyst_date as event_date,
    risk_reward_ratio,
    total_threat_level,
    created_at
FROM nexus.kb_stock_analyses
UNION ALL
SELECT
    'earnings' as analysis_type,
    id,
    ticker,
    analysis_date,
    recommendation,
    confidence,
    expected_value_pct,
    gate_result,
    gate_criteria_met,
    current_price,
    entry_price,
    stop_price,
    target_1_price,
    bull_probability,
    bear_probability,
    bull_case_strength,
    bear_case_strength,
    'earnings' as catalyst_type,
    earnings_date as event_date,
    risk_reward_ratio,
    total_threat_level,
    created_at
FROM nexus.kb_earnings_analyses;

COMMENT ON VIEW nexus.v_all_analyses IS 'Combined view of all stock and earnings analyses for unified querying';
