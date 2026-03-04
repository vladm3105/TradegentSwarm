-- Migration 019: Complete Skill-Database Mapping
-- Addresses gaps in skill output to database storage
-- Date: 2026-03-02

-- ============================================================================
-- 1. Create kb_scanner_runs for scanner execution results
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.kb_scanner_runs (
    id SERIAL PRIMARY KEY,

    -- Identification
    run_id VARCHAR(100) NOT NULL,
    scanner_name VARCHAR(100) NOT NULL,
    scanner_config_id INTEGER REFERENCES nexus.kb_scanner_configs(id),
    file_path VARCHAR(500) UNIQUE,

    -- Timing
    run_timestamp TIMESTAMPTZ NOT NULL,
    schedule_type VARCHAR(20),  -- daily, intraday, weekly
    market_phase VARCHAR(20),   -- premarket, open, mid_day, close, after_hours

    -- Market Context
    market_regime VARCHAR(20),  -- bull, bear, neutral, high_volatility
    vix_level NUMERIC(6,2),
    spy_change_pct NUMERIC(6,2),

    -- Results Summary
    universe_size INTEGER,
    passed_quality_filters INTEGER,
    passed_liquidity_filters INTEGER,
    scored_candidates INTEGER,
    high_score_count INTEGER,      -- >= 7.5 (full analysis)
    watchlist_count INTEGER,       -- 5.5-7.4
    skipped_count INTEGER,         -- < 5.5

    -- Top Candidates (denormalized for quick access)
    top_candidate_ticker VARCHAR(10),
    top_candidate_score NUMERIC(4,2),
    top_candidate_action VARCHAR(20),

    -- Full content
    yaml_content JSONB NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT now(),

    CONSTRAINT uq_scanner_run UNIQUE (scanner_name, run_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_scanner_runs_name ON nexus.kb_scanner_runs(scanner_name);
CREATE INDEX IF NOT EXISTS idx_scanner_runs_timestamp ON nexus.kb_scanner_runs(run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_scanner_runs_regime ON nexus.kb_scanner_runs(market_regime);
CREATE INDEX IF NOT EXISTS idx_scanner_runs_yaml ON nexus.kb_scanner_runs USING gin(yaml_content);

COMMENT ON TABLE nexus.kb_scanner_runs IS 'Scanner execution results with candidates';

-- ============================================================================
-- 2. Add functions for alert extraction from analyses
-- ============================================================================

-- Function to extract alerts from stock analysis
CREATE OR REPLACE FUNCTION nexus.extract_alerts_from_stock_analysis(
    p_analysis_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_ticker VARCHAR(20);
    v_alert JSONB;
    v_alert_count INTEGER := 0;
    v_expires_at TIMESTAMPTZ;
BEGIN
    -- Get ticker and forecast expiration
    SELECT ticker,
           (yaml_content->>'forecast_valid_until')::DATE + INTERVAL '1 day'
    INTO v_ticker, v_expires_at
    FROM nexus.kb_stock_analyses
    WHERE id = p_analysis_id;

    IF v_ticker IS NULL THEN
        RETURN 0;
    END IF;

    -- Extract price alerts
    FOR v_alert IN
        SELECT jsonb_array_elements(yaml_content->'alert_levels'->'price_alerts')
        FROM nexus.kb_stock_analyses
        WHERE id = p_analysis_id
    LOOP
        INSERT INTO nexus.kb_alert_tracking (
            ticker, source_stock_analysis_id,
            alert_type, alert_level, alert_tag, direction, significance,
            status, expires_at
        ) VALUES (
            v_ticker, p_analysis_id,
            CASE WHEN (v_alert->>'direction') = 'above' THEN 'price_above' ELSE 'price_below' END,
            (v_alert->>'price')::NUMERIC,
            v_alert->>'tag',
            v_alert->>'direction',
            v_alert->>'significance',
            'active',
            v_expires_at
        )
        ON CONFLICT DO NOTHING;

        v_alert_count := v_alert_count + 1;
    END LOOP;

    RETURN v_alert_count;
END;
$$ LANGUAGE plpgsql;

-- Function to extract alerts from earnings analysis
CREATE OR REPLACE FUNCTION nexus.extract_alerts_from_earnings_analysis(
    p_analysis_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_ticker VARCHAR(20);
    v_alert JSONB;
    v_alert_count INTEGER := 0;
    v_expires_at TIMESTAMPTZ;
BEGIN
    -- Get ticker and earnings date (alerts expire day after earnings)
    SELECT ticker, earnings_date + INTERVAL '1 day'
    INTO v_ticker, v_expires_at
    FROM nexus.kb_earnings_analyses
    WHERE id = p_analysis_id;

    IF v_ticker IS NULL THEN
        RETURN 0;
    END IF;

    -- Extract price alerts
    FOR v_alert IN
        SELECT jsonb_array_elements(yaml_content->'alert_levels'->'price_alerts')
        FROM nexus.kb_earnings_analyses
        WHERE id = p_analysis_id
    LOOP
        INSERT INTO nexus.kb_alert_tracking (
            ticker, source_earnings_analysis_id,
            alert_type, alert_level, alert_tag, direction, significance,
            status, expires_at
        ) VALUES (
            v_ticker, p_analysis_id,
            CASE WHEN (v_alert->>'direction') = 'above' THEN 'price_above' ELSE 'price_below' END,
            (v_alert->>'price')::NUMERIC,
            v_alert->>'tag',
            v_alert->>'direction',
            v_alert->>'significance',
            'active',
            v_expires_at
        )
        ON CONFLICT DO NOTHING;

        v_alert_count := v_alert_count + 1;
    END LOOP;

    RETURN v_alert_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 3. Add function for target tracking creation
-- ============================================================================

CREATE OR REPLACE FUNCTION nexus.create_target_tracking_from_stock_analysis(
    p_analysis_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_tracking_id INTEGER;
    v_analysis RECORD;
BEGIN
    SELECT
        ticker, analysis_date, current_price,
        entry_price, stop_price, target_1_price, target_2_price,
        recommendation, gate_result
    INTO v_analysis
    FROM nexus.kb_stock_analyses
    WHERE id = p_analysis_id;

    IF v_analysis.ticker IS NULL THEN
        RETURN NULL;
    END IF;

    -- Only track analyses with PASS or MARGINAL gate result
    IF v_analysis.gate_result NOT IN ('PASS', 'MARGINAL') THEN
        RETURN NULL;
    END IF;

    INSERT INTO nexus.kb_target_tracking (
        ticker, source_stock_analysis_id, analysis_date,
        price_at_analysis, entry_price, stop_price, target_1_price, target_2_price,
        recommendation, gate_result,
        tracking_start_date, status
    ) VALUES (
        v_analysis.ticker, p_analysis_id, v_analysis.analysis_date,
        v_analysis.current_price, v_analysis.entry_price, v_analysis.stop_price,
        v_analysis.target_1_price, v_analysis.target_2_price,
        v_analysis.recommendation, v_analysis.gate_result,
        CURRENT_DATE, 'tracking'
    )
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_tracking_id;

    RETURN v_tracking_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nexus.create_target_tracking_from_earnings_analysis(
    p_analysis_id INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_tracking_id INTEGER;
    v_analysis RECORD;
BEGIN
    SELECT
        ticker, analysis_date, current_price,
        entry_price, stop_price, target_1_price, target_2_price,
        recommendation, gate_result
    INTO v_analysis
    FROM nexus.kb_earnings_analyses
    WHERE id = p_analysis_id;

    IF v_analysis.ticker IS NULL THEN
        RETURN NULL;
    END IF;

    -- Only track analyses with PASS gate result
    IF v_analysis.gate_result != 'PASS' THEN
        RETURN NULL;
    END IF;

    INSERT INTO nexus.kb_target_tracking (
        ticker, source_earnings_analysis_id, analysis_date,
        price_at_analysis, entry_price, stop_price, target_1_price, target_2_price,
        recommendation, gate_result,
        tracking_start_date, status
    ) VALUES (
        v_analysis.ticker, p_analysis_id, v_analysis.analysis_date,
        v_analysis.current_price, v_analysis.entry_price, v_analysis.stop_price,
        v_analysis.target_1_price, v_analysis.target_2_price,
        v_analysis.recommendation, v_analysis.gate_result,
        CURRENT_DATE, 'tracking'
    )
    ON CONFLICT DO NOTHING
    RETURNING id INTO v_tracking_id;

    RETURN v_tracking_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. Add trigger to auto-extract alerts and create target tracking
-- ============================================================================

CREATE OR REPLACE FUNCTION nexus.after_stock_analysis_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Extract alerts
    PERFORM nexus.extract_alerts_from_stock_analysis(NEW.id);
    -- Create target tracking
    PERFORM nexus.create_target_tracking_from_stock_analysis(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION nexus.after_earnings_analysis_insert()
RETURNS TRIGGER AS $$
BEGIN
    -- Extract alerts
    PERFORM nexus.extract_alerts_from_earnings_analysis(NEW.id);
    -- Create target tracking
    PERFORM nexus.create_target_tracking_from_earnings_analysis(NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_stock_analysis_post_insert ON nexus.kb_stock_analyses;
CREATE TRIGGER trg_stock_analysis_post_insert
    AFTER INSERT ON nexus.kb_stock_analyses
    FOR EACH ROW
    EXECUTE FUNCTION nexus.after_stock_analysis_insert();

DROP TRIGGER IF EXISTS trg_earnings_analysis_post_insert ON nexus.kb_earnings_analyses;
CREATE TRIGGER trg_earnings_analysis_post_insert
    AFTER INSERT ON nexus.kb_earnings_analyses
    FOR EACH ROW
    EXECUTE FUNCTION nexus.after_earnings_analysis_insert();

-- ============================================================================
-- 5. View for scanner performance tracking
-- ============================================================================

CREATE OR REPLACE VIEW nexus.v_scanner_performance AS
SELECT
    scanner_name,
    COUNT(*) as total_runs,
    AVG(high_score_count) as avg_high_score_candidates,
    AVG(watchlist_count) as avg_watchlist_candidates,
    AVG(scored_candidates) as avg_total_candidates,
    MAX(run_timestamp) as last_run,
    MODE() WITHIN GROUP (ORDER BY market_regime) as typical_regime
FROM nexus.kb_scanner_runs
GROUP BY scanner_name
ORDER BY total_runs DESC;

COMMENT ON VIEW nexus.v_scanner_performance IS 'Scanner execution statistics';

-- ============================================================================
-- 6. View for pending target checks
-- ============================================================================

CREATE OR REPLACE VIEW nexus.v_pending_target_checks AS
SELECT
    tt.id,
    tt.ticker,
    tt.analysis_date,
    tt.price_at_analysis,
    tt.entry_price,
    tt.stop_price,
    tt.target_1_price,
    tt.target_2_price,
    tt.entry_hit,
    tt.target_1_hit,
    tt.stop_hit,
    tt.days_tracked,
    CASE
        WHEN sa.id IS NOT NULL THEN 'stock'
        ELSE 'earnings'
    END as analysis_type,
    COALESCE(sa.recommendation, ea.recommendation) as recommendation
FROM nexus.kb_target_tracking tt
LEFT JOIN nexus.kb_stock_analyses sa ON tt.source_stock_analysis_id = sa.id
LEFT JOIN nexus.kb_earnings_analyses ea ON tt.source_earnings_analysis_id = ea.id
WHERE tt.status = 'tracking'
ORDER BY tt.analysis_date DESC;

COMMENT ON VIEW nexus.v_pending_target_checks IS 'Active target tracking records that need price updates';

-- ============================================================================
-- Migration complete
-- ============================================================================
