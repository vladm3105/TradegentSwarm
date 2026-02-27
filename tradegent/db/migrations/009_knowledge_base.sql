-- Migration 009: Knowledge Base Database Tables
-- Stores full YAML content as JSONB with extracted indexed fields
-- Date: 2026-02-27

-- ============================================================================
-- 1. kb_stock_analyses - Full stock analysis storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_stock_analyses (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    ticker              VARCHAR(10) NOT NULL,
    analysis_date       TIMESTAMPTZ NOT NULL,
    schema_version      VARCHAR(10) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Lineage tracking
    lineage_id          INTEGER REFERENCES nexus.analysis_lineage(id),

    -- Key indexed fields (extracted from YAML)
    current_price       DECIMAL(12,4),
    recommendation      VARCHAR(20),
    confidence          INTEGER,
    expected_value_pct  DECIMAL(8,4),
    gate_result         VARCHAR(20),
    gate_criteria_met   INTEGER,

    -- Scenarios
    bull_probability    DECIMAL(5,2),
    base_probability    DECIMAL(5,2),
    bear_probability    DECIMAL(5,2),

    -- Key levels
    entry_price         DECIMAL(12,4),
    stop_price          DECIMAL(12,4),
    target_1_price      DECIMAL(12,4),
    target_2_price      DECIMAL(12,4),

    -- Scores
    catalyst_score      INTEGER,
    technical_score     INTEGER,
    fundamental_score   INTEGER,
    sentiment_score     INTEGER,

    -- Risk assessment
    total_threat_level  VARCHAR(20),

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_stock_ticker ON nexus.kb_stock_analyses(ticker);
CREATE INDEX IF NOT EXISTS idx_kb_stock_date ON nexus.kb_stock_analyses(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_stock_ticker_date ON nexus.kb_stock_analyses(ticker, analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_stock_rec ON nexus.kb_stock_analyses(recommendation);
CREATE INDEX IF NOT EXISTS idx_kb_stock_gate ON nexus.kb_stock_analyses(gate_result);
CREATE INDEX IF NOT EXISTS idx_kb_stock_confidence ON nexus.kb_stock_analyses(confidence);
CREATE INDEX IF NOT EXISTS idx_kb_stock_lineage ON nexus.kb_stock_analyses(lineage_id);
CREATE INDEX IF NOT EXISTS idx_kb_stock_created ON nexus.kb_stock_analyses(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kb_stock_yaml ON nexus.kb_stock_analyses USING gin(yaml_content);

-- ============================================================================
-- 2. kb_earnings_analyses - Full earnings analysis storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_earnings_analyses (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    ticker              VARCHAR(10) NOT NULL,
    analysis_date       TIMESTAMPTZ NOT NULL,
    schema_version      VARCHAR(10) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Lineage tracking
    lineage_id          INTEGER REFERENCES nexus.analysis_lineage(id),

    -- Earnings-specific
    earnings_date       DATE NOT NULL,
    earnings_time       VARCHAR(10),
    days_to_earnings    INTEGER,

    -- Key indexed fields
    recommendation      VARCHAR(20),
    confidence          INTEGER,
    p_beat              DECIMAL(5,2),
    expected_value_pct  DECIMAL(8,4),
    gate_result         VARCHAR(20),

    -- Case analysis
    bull_case_strength  INTEGER,
    bear_case_strength  INTEGER,

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_earnings_ticker ON nexus.kb_earnings_analyses(ticker);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_date ON nexus.kb_earnings_analyses(earnings_date);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_ticker_date ON nexus.kb_earnings_analyses(ticker, analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_lineage ON nexus.kb_earnings_analyses(lineage_id);
CREATE INDEX IF NOT EXISTS idx_kb_earnings_yaml ON nexus.kb_earnings_analyses USING gin(yaml_content);

-- ============================================================================
-- 3. kb_research_analyses - Research/macro/sector analysis storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_research_analyses (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    research_id         VARCHAR(50) NOT NULL UNIQUE,
    research_type       VARCHAR(30) NOT NULL,
    title               VARCHAR(200),
    file_path           VARCHAR(500) NOT NULL UNIQUE,
    schema_version      VARCHAR(10) NOT NULL,
    analysis_date       TIMESTAMPTZ NOT NULL,

    -- Scope
    tickers             TEXT[],
    sectors             TEXT[],
    themes              TEXT[],

    -- Key findings
    outlook             VARCHAR(20),
    confidence          INTEGER,
    time_horizon        VARCHAR(20),

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_research_type ON nexus.kb_research_analyses(research_type);
CREATE INDEX IF NOT EXISTS idx_kb_research_date ON nexus.kb_research_analyses(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_research_tickers ON nexus.kb_research_analyses USING gin(tickers);
CREATE INDEX IF NOT EXISTS idx_kb_research_sectors ON nexus.kb_research_analyses USING gin(sectors);
CREATE INDEX IF NOT EXISTS idx_kb_research_yaml ON nexus.kb_research_analyses USING gin(yaml_content);

-- ============================================================================
-- 4. kb_ticker_profiles - Ticker profile storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_ticker_profiles (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    ticker              VARCHAR(10) NOT NULL UNIQUE,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Company info
    company_name        VARCHAR(200),
    sector              VARCHAR(50),
    industry            VARCHAR(100),
    market_cap_category VARCHAR(20),

    -- Trading characteristics
    typical_iv          DECIMAL(5,2),
    avg_daily_volume    BIGINT,
    options_liquidity   VARCHAR(20),

    -- Historical performance
    total_trades        INTEGER DEFAULT 0,
    win_rate            DECIMAL(5,2),
    avg_return          DECIMAL(8,4),
    total_pnl           DECIMAL(12,2),

    -- Bias history
    common_biases       TEXT[],
    lessons_learned     TEXT[],

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_profile_sector ON nexus.kb_ticker_profiles(sector);
CREATE INDEX IF NOT EXISTS idx_kb_profile_biases ON nexus.kb_ticker_profiles USING gin(common_biases);
CREATE INDEX IF NOT EXISTS idx_kb_profile_yaml ON nexus.kb_ticker_profiles USING gin(yaml_content);

-- ============================================================================
-- 5. kb_trade_journals - Full trade journal storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_trade_journals (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    trade_id            VARCHAR(50) NOT NULL UNIQUE,
    ticker              VARCHAR(10) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Links (polymorphic - can reference stock or earnings analysis)
    source_analysis_id  INTEGER,
    source_analysis_type VARCHAR(20),

    -- Trade details
    direction           VARCHAR(10),
    entry_date          TIMESTAMPTZ,
    entry_price         DECIMAL(12,4),
    exit_date           TIMESTAMPTZ,
    exit_price          DECIMAL(12,4),

    -- Results
    outcome             VARCHAR(20),
    return_pct          DECIMAL(8,4),
    pnl_dollars         DECIMAL(12,2),
    holding_days        INTEGER,

    -- Quality
    entry_grade         VARCHAR(1),
    exit_grade          VARCHAR(1),
    overall_grade       VARCHAR(1),

    -- Bias tracking
    biases_detected     TEXT[],
    primary_lesson      TEXT,

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_trades_ticker ON nexus.kb_trade_journals(ticker);
CREATE INDEX IF NOT EXISTS idx_kb_trades_outcome ON nexus.kb_trade_journals(outcome);
CREATE INDEX IF NOT EXISTS idx_kb_trades_entry ON nexus.kb_trade_journals(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_kb_trades_grade ON nexus.kb_trade_journals(overall_grade);
CREATE INDEX IF NOT EXISTS idx_kb_trades_biases ON nexus.kb_trade_journals USING gin(biases_detected);
CREATE INDEX IF NOT EXISTS idx_kb_trades_yaml ON nexus.kb_trade_journals USING gin(yaml_content);

-- ============================================================================
-- 6. kb_watchlist_entries - Full watchlist entry storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_watchlist_entries (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    watchlist_id        VARCHAR(50) NOT NULL UNIQUE,
    ticker              VARCHAR(10) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Links
    source_analysis_id  INTEGER,
    source_analysis_type VARCHAR(20),

    -- Entry conditions
    entry_trigger       TEXT,
    entry_price         DECIMAL(12,4),

    -- Status
    status              VARCHAR(20) DEFAULT 'active',
    priority            VARCHAR(10),
    conviction_level    INTEGER,

    -- Timing
    expires_at          TIMESTAMPTZ,
    triggered_at        TIMESTAMPTZ,
    invalidated_at      TIMESTAMPTZ,

    -- Source
    source_analysis     VARCHAR(500),
    source_score        DECIMAL(5,2),

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_watchlist_ticker ON nexus.kb_watchlist_entries(ticker);
CREATE INDEX IF NOT EXISTS idx_kb_watchlist_status ON nexus.kb_watchlist_entries(status);
CREATE INDEX IF NOT EXISTS idx_kb_watchlist_active ON nexus.kb_watchlist_entries(status, expires_at)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_kb_watchlist_yaml ON nexus.kb_watchlist_entries USING gin(yaml_content);

-- ============================================================================
-- 7. kb_reviews - Combined table for all review types
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_reviews (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    review_id           VARCHAR(50) NOT NULL UNIQUE,
    review_type         VARCHAR(30) NOT NULL,
    ticker              VARCHAR(10) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Linked documents
    source_analysis_id  INTEGER,
    source_trade_id     INTEGER REFERENCES nexus.kb_trade_journals(id),
    lineage_id          INTEGER REFERENCES nexus.analysis_lineage(id),

    -- Results
    overall_grade       VARCHAR(1),
    return_pct          DECIMAL(8,4),
    outcome             VARCHAR(20),

    -- Validation specific
    validation_result   VARCHAR(20),

    -- Lessons
    primary_lesson      TEXT,
    biases_detected     TEXT[],
    bias_cost_estimate  DECIMAL(12,2),

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_reviews_ticker ON nexus.kb_reviews(ticker);
CREATE INDEX IF NOT EXISTS idx_kb_reviews_type ON nexus.kb_reviews(review_type);
CREATE INDEX IF NOT EXISTS idx_kb_reviews_grade ON nexus.kb_reviews(overall_grade);
CREATE INDEX IF NOT EXISTS idx_kb_reviews_validation ON nexus.kb_reviews(validation_result)
    WHERE review_type = 'validation';
CREATE INDEX IF NOT EXISTS idx_kb_reviews_lineage ON nexus.kb_reviews(lineage_id);
CREATE INDEX IF NOT EXISTS idx_kb_reviews_yaml ON nexus.kb_reviews USING gin(yaml_content);

-- ============================================================================
-- 8. kb_learnings - Extracted learnings (biases, patterns, rules)
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_learnings (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    learning_id         VARCHAR(50) NOT NULL UNIQUE,
    category            VARCHAR(30) NOT NULL,
    subcategory         VARCHAR(50),
    file_path           VARCHAR(500) NOT NULL UNIQUE,

    -- Content
    title               VARCHAR(200),
    description         TEXT,
    rule_statement      TEXT,
    countermeasure      TEXT,

    -- Validation
    confidence          VARCHAR(20),
    validation_status   VARCHAR(20),
    evidence_count      INTEGER,
    estimated_cost      DECIMAL(12,2),

    -- Related
    related_tickers     TEXT[],
    related_trades      TEXT[],

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_learnings_category ON nexus.kb_learnings(category, subcategory);
CREATE INDEX IF NOT EXISTS idx_kb_learnings_status ON nexus.kb_learnings(validation_status);
CREATE INDEX IF NOT EXISTS idx_kb_learnings_tickers ON nexus.kb_learnings USING gin(related_tickers);
CREATE INDEX IF NOT EXISTS idx_kb_learnings_yaml ON nexus.kb_learnings USING gin(yaml_content);

-- ============================================================================
-- 9. kb_strategies - Trading strategy definitions
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_strategies (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    strategy_id         VARCHAR(50) NOT NULL UNIQUE,
    strategy_name       VARCHAR(200) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,
    schema_version      VARCHAR(10),

    -- Strategy classification
    strategy_type       VARCHAR(30),
    asset_class         VARCHAR(20),
    time_horizon        VARCHAR(20),

    -- Performance tracking
    total_trades        INTEGER DEFAULT 0,
    win_rate            DECIMAL(5,2),
    avg_return          DECIMAL(8,4),
    max_drawdown        DECIMAL(8,4),
    sharpe_ratio        DECIMAL(6,3),
    total_pnl           DECIMAL(12,2),

    -- Status
    status              VARCHAR(20) DEFAULT 'active',
    confidence_level    VARCHAR(20),
    last_reviewed       TIMESTAMPTZ,

    -- Entry/Exit rules summary
    entry_conditions    TEXT[],
    exit_conditions     TEXT[],
    known_weaknesses    TEXT[],

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_strategies_type ON nexus.kb_strategies(strategy_type);
CREATE INDEX IF NOT EXISTS idx_kb_strategies_status ON nexus.kb_strategies(status);
CREATE INDEX IF NOT EXISTS idx_kb_strategies_performance ON nexus.kb_strategies(win_rate, total_trades)
    WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_kb_strategies_yaml ON nexus.kb_strategies USING gin(yaml_content);

-- ============================================================================
-- 10. kb_scanner_configs - Scanner configuration storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS nexus.kb_scanner_configs (
    id                  SERIAL PRIMARY KEY,

    -- Identification
    scanner_code        VARCHAR(100) NOT NULL UNIQUE,
    scanner_name        VARCHAR(200) NOT NULL,
    file_path           VARCHAR(500) NOT NULL UNIQUE,
    schema_version      VARCHAR(10),

    -- Classification
    scanner_type        VARCHAR(30) NOT NULL,
    category            VARCHAR(50),

    -- Schedule
    schedule_time       TIME,
    schedule_days       TEXT[],
    is_enabled          BOOLEAN DEFAULT true,

    -- Configuration summary
    data_sources        TEXT[],
    max_candidates      INTEGER,
    min_score           DECIMAL(4,2),
    filters_summary     TEXT,

    -- Scoring weights
    scoring_criteria    JSONB,

    -- Performance tracking
    total_runs          INTEGER DEFAULT 0,
    avg_candidates      DECIMAL(6,2),
    last_run_at         TIMESTAMPTZ,

    -- Full content
    yaml_content        JSONB NOT NULL,

    -- Metadata
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_kb_scanner_type ON nexus.kb_scanner_configs(scanner_type);
CREATE INDEX IF NOT EXISTS idx_kb_scanner_enabled ON nexus.kb_scanner_configs(is_enabled)
    WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_kb_scanner_category ON nexus.kb_scanner_configs(category);
CREATE INDEX IF NOT EXISTS idx_kb_scanner_yaml ON nexus.kb_scanner_configs USING gin(yaml_content);

-- ============================================================================
-- Trigger Function (create if not exists)
-- ============================================================================
CREATE OR REPLACE FUNCTION nexus.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Triggers for updated_at
-- ============================================================================
DROP TRIGGER IF EXISTS kb_stock_analyses_updated_at ON nexus.kb_stock_analyses;
CREATE TRIGGER kb_stock_analyses_updated_at BEFORE UPDATE ON nexus.kb_stock_analyses
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_earnings_analyses_updated_at ON nexus.kb_earnings_analyses;
CREATE TRIGGER kb_earnings_analyses_updated_at BEFORE UPDATE ON nexus.kb_earnings_analyses
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_research_analyses_updated_at ON nexus.kb_research_analyses;
CREATE TRIGGER kb_research_analyses_updated_at BEFORE UPDATE ON nexus.kb_research_analyses
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_ticker_profiles_updated_at ON nexus.kb_ticker_profiles;
CREATE TRIGGER kb_ticker_profiles_updated_at BEFORE UPDATE ON nexus.kb_ticker_profiles
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_trade_journals_updated_at ON nexus.kb_trade_journals;
CREATE TRIGGER kb_trade_journals_updated_at BEFORE UPDATE ON nexus.kb_trade_journals
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_watchlist_entries_updated_at ON nexus.kb_watchlist_entries;
CREATE TRIGGER kb_watchlist_entries_updated_at BEFORE UPDATE ON nexus.kb_watchlist_entries
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_reviews_updated_at ON nexus.kb_reviews;
CREATE TRIGGER kb_reviews_updated_at BEFORE UPDATE ON nexus.kb_reviews
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_learnings_updated_at ON nexus.kb_learnings;
CREATE TRIGGER kb_learnings_updated_at BEFORE UPDATE ON nexus.kb_learnings
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_strategies_updated_at ON nexus.kb_strategies;
CREATE TRIGGER kb_strategies_updated_at BEFORE UPDATE ON nexus.kb_strategies
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS kb_scanner_configs_updated_at ON nexus.kb_scanner_configs;
CREATE TRIGGER kb_scanner_configs_updated_at BEFORE UPDATE ON nexus.kb_scanner_configs
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

-- ============================================================================
-- Views for Common Queries
-- ============================================================================

-- Latest stock analysis per ticker
CREATE OR REPLACE VIEW nexus.v_latest_stock_analyses AS
SELECT DISTINCT ON (ticker) *
FROM nexus.kb_stock_analyses
ORDER BY ticker, analysis_date DESC;

-- Latest earnings analysis per ticker
CREATE OR REPLACE VIEW nexus.v_latest_earnings_analyses AS
SELECT DISTINCT ON (ticker) *
FROM nexus.kb_earnings_analyses
ORDER BY ticker, analysis_date DESC;

-- Active watchlist with full details
CREATE OR REPLACE VIEW nexus.v_kb_active_watchlist AS
SELECT *
FROM nexus.kb_watchlist_entries
WHERE status = 'active'
  AND (expires_at IS NULL OR expires_at > now())
ORDER BY conviction_level DESC, created_at DESC;

-- Trade performance by ticker
CREATE OR REPLACE VIEW nexus.v_trade_performance AS
SELECT
    ticker,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE outcome = 'win') as wins,
    COUNT(*) FILTER (WHERE outcome = 'loss') as losses,
    ROUND(100.0 * COUNT(*) FILTER (WHERE outcome = 'win') / NULLIF(COUNT(*), 0), 2) as win_rate,
    ROUND(AVG(return_pct)::numeric, 4) as avg_return,
    ROUND(SUM(pnl_dollars)::numeric, 2) as total_pnl
FROM nexus.kb_trade_journals
WHERE outcome IS NOT NULL
GROUP BY ticker
ORDER BY total_trades DESC;

-- Bias frequency analysis
CREATE OR REPLACE VIEW nexus.v_bias_frequency AS
SELECT
    unnest(biases_detected) as bias,
    COUNT(*) as occurrences,
    ROUND(AVG(return_pct)::numeric, 4) as avg_return_when_present
FROM nexus.kb_trade_journals
WHERE biases_detected IS NOT NULL AND array_length(biases_detected, 1) > 0
GROUP BY 1
ORDER BY occurrences DESC;

-- High confidence analyses (gate PASS)
CREATE OR REPLACE VIEW nexus.v_high_confidence_analyses AS
SELECT
    'stock' as type, ticker, analysis_date, recommendation, confidence, expected_value_pct, gate_result
FROM nexus.kb_stock_analyses
WHERE gate_result = 'PASS' AND confidence >= 60
UNION ALL
SELECT
    'earnings' as type, ticker, analysis_date, recommendation, confidence, expected_value_pct, gate_result
FROM nexus.kb_earnings_analyses
WHERE gate_result = 'PASS' AND confidence >= 60
ORDER BY analysis_date DESC;

-- Active strategies with performance
CREATE OR REPLACE VIEW nexus.v_active_strategies AS
SELECT
    strategy_id, strategy_name, strategy_type, time_horizon,
    total_trades, win_rate, avg_return, sharpe_ratio, total_pnl,
    confidence_level, last_reviewed
FROM nexus.kb_strategies
WHERE status = 'active'
ORDER BY total_pnl DESC NULLS LAST;

-- Enabled scanners by type
CREATE OR REPLACE VIEW nexus.v_enabled_scanners AS
SELECT
    scanner_code, scanner_name, scanner_type, category,
    schedule_time, total_runs, avg_candidates, last_run_at
FROM nexus.kb_scanner_configs
WHERE is_enabled = true
ORDER BY scanner_type, schedule_time;

-- ============================================================================
-- Migration complete
-- ============================================================================
