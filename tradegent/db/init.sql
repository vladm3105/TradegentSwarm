-- ═══════════════════════════════════════════════════════════════
-- Nexus Light Trading Platform - Database Schema
-- Shared PostgreSQL instance with LightRAG (separate schema)
-- ═══════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS nexus;

-- ─── ENUM Types ──────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE nexus.stock_state AS ENUM ('analysis', 'paper', 'live');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE nexus.analysis_type AS ENUM ('earnings', 'stock', 'scan', 'review', 'postmortem');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE nexus.schedule_frequency AS ENUM (
        'once',          -- Run once at next_run_at, then disable
        'daily',         -- Every trading day
        'weekly',        -- Once per week (on day_of_week)
        'pre_earnings',  -- Auto-triggered N days before earnings
        'post_earnings', -- Auto-triggered N days after earnings
        'interval'       -- Every N minutes during market hours
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE nexus.run_status AS ENUM ('pending', 'running', 'completed', 'failed', 'skipped');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE nexus.day_of_week AS ENUM ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── 1. Stocks (Watchlist) ───────────────────────────────────

CREATE TABLE IF NOT EXISTS nexus.stocks (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL UNIQUE,
    name            VARCHAR(100),
    sector          VARCHAR(50),
    is_enabled      BOOLEAN NOT NULL DEFAULT true,
    state           nexus.stock_state NOT NULL DEFAULT 'analysis',
    
    -- Analysis preferences
    default_analysis_type  nexus.analysis_type NOT NULL DEFAULT 'stock',
    priority        INTEGER NOT NULL DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    -- 1=lowest, 10=highest; controls processing order in scheduled runs
    
    -- Earnings tracking
    next_earnings_date  DATE,
    earnings_confirmed  BOOLEAN DEFAULT false,
    beat_history        VARCHAR(20),   -- e.g. "11/12"
    
    -- Position tracking
    has_open_position   BOOLEAN DEFAULT false,
    position_state      VARCHAR(20),   -- 'none', 'pending', 'filled', 'partial'
    
    -- Risk limits per stock
    max_position_pct    NUMERIC(5,2) DEFAULT 6.0,
    
    comments        TEXT,
    tags            TEXT[],            -- e.g. {'mega_cap', 'tech', 'earnings_play'}
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stocks_enabled ON nexus.stocks(is_enabled) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_stocks_state ON nexus.stocks(state);
CREATE INDEX IF NOT EXISTS idx_stocks_earnings ON nexus.stocks(next_earnings_date) WHERE next_earnings_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stocks_tags ON nexus.stocks USING gin(tags);

-- ─── 2. IB Scanners ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nexus.ib_scanners (
    id              SERIAL PRIMARY KEY,
    scanner_code    VARCHAR(100) NOT NULL UNIQUE,
    -- IB scanner codes: TOP_PERC_GAIN, TOP_PERC_LOSE, HIGH_OPT_IMP_VOLAT,
    -- HOT_BY_VOLUME, TOP_TRADE_COUNT, MOST_ACTIVE, HIGH_OPT_VOLUME, etc.
    
    display_name    VARCHAR(200) NOT NULL,
    description     TEXT,
    is_enabled      BOOLEAN NOT NULL DEFAULT true,
    
    -- Scanner parameters
    instrument      VARCHAR(20) DEFAULT 'STK',      -- STK, OPT, FUT
    location        VARCHAR(50) DEFAULT 'STK.US.MAJOR', -- STK.US.MAJOR, STK.US, STK.NASDAQ, etc.
    num_results     INTEGER DEFAULT 20 CHECK (num_results BETWEEN 1 AND 50),
    
    -- Filters (stored as JSONB for flexibility)
    -- e.g. {"priceAbove": 10, "priceBelow": 500, "marketCapAbove": 1e9,
    --        "volumeAbove": 500000, "avgOptVolumeAbove": 1000}
    filters         JSONB DEFAULT '{}',
    
    -- How to process results
    auto_add_to_watchlist  BOOLEAN DEFAULT false,
    auto_analyze           BOOLEAN DEFAULT false,
    analysis_type          nexus.analysis_type DEFAULT 'stock',
    max_candidates         INTEGER DEFAULT 5,       -- Top N results to analyze
    
    comments        TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scanners_enabled ON nexus.ib_scanners(is_enabled) WHERE is_enabled = true;

-- ─── 3. Schedules ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nexus.schedules (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    is_enabled      BOOLEAN NOT NULL DEFAULT true,
    
    -- What to run
    task_type       VARCHAR(50) NOT NULL,
    -- Task types:
    --   'analyze_stock'     - Run analysis on a specific stock
    --   'analyze_watchlist'  - Run analysis on all enabled stocks
    --   'run_scanner'       - Execute an IB scanner
    --   'run_all_scanners'  - Execute all enabled scanners
    --   'pipeline'          - Full analyze+execute pipeline
    --   'portfolio_review'  - Portfolio-wide review
    --   'postmortem'        - Post-earnings review
    --   'custom'            - Custom Claude Code prompt
    
    -- Task target (depends on task_type)
    target_ticker   VARCHAR(10),       -- For stock-specific tasks
    target_scanner_id INTEGER REFERENCES nexus.ib_scanners(id),
    target_tags     TEXT[],            -- Run for stocks matching these tags
    analysis_type   nexus.analysis_type DEFAULT 'stock',
    auto_execute    BOOLEAN DEFAULT false, -- Enable Stage 2 execution
    
    -- Custom prompt (for task_type='custom')
    custom_prompt   TEXT,
    
    -- When to run
    frequency       nexus.schedule_frequency NOT NULL DEFAULT 'daily',
    time_of_day     TIME,                  -- For daily/weekly (ET timezone)
    day_of_week     nexus.day_of_week,     -- For weekly schedules
    interval_minutes INTEGER,              -- For 'interval' frequency
    days_before_earnings INTEGER,          -- For 'pre_earnings' frequency
    days_after_earnings  INTEGER,          -- For 'post_earnings' frequency
    
    -- Market hours awareness
    market_hours_only  BOOLEAN DEFAULT true,  -- Only run during market hours
    trading_days_only  BOOLEAN DEFAULT true,  -- Skip weekends/holidays
    
    -- Execution control
    max_runs_per_day   INTEGER DEFAULT 1,
    timeout_seconds    INTEGER DEFAULT 600,
    priority           INTEGER DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    
    -- State tracking
    last_run_at     TIMESTAMPTZ,
    last_run_status nexus.run_status,
    next_run_at     TIMESTAMPTZ,           -- Calculated by scheduler
    run_count       INTEGER DEFAULT 0,
    fail_count      INTEGER DEFAULT 0,
    consecutive_fails INTEGER DEFAULT 0,
    
    -- Circuit breaker: disable after N consecutive failures
    max_consecutive_fails INTEGER DEFAULT 3,
    
    comments        TEXT,
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON nexus.schedules(is_enabled) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON nexus.schedules(next_run_at) WHERE is_enabled = true;
CREATE INDEX IF NOT EXISTS idx_schedules_task ON nexus.schedules(task_type);

-- ─── 4. Run History (Audit Log) ──────────────────────────────

CREATE TABLE IF NOT EXISTS nexus.run_history (
    id              BIGSERIAL PRIMARY KEY,
    schedule_id     INTEGER REFERENCES nexus.schedules(id),
    
    -- What ran
    task_type       VARCHAR(50) NOT NULL,
    ticker          VARCHAR(10),
    analysis_type   nexus.analysis_type,
    
    -- Result
    status          nexus.run_status NOT NULL DEFAULT 'pending',
    stage           VARCHAR(20),       -- 'analysis', 'execution', 'scan'
    
    -- Analysis results
    gate_passed     BOOLEAN,
    recommendation  VARCHAR(20),
    confidence      INTEGER,
    expected_value  NUMERIC(6,2),
    
    -- Execution results
    order_placed    BOOLEAN,
    order_id        VARCHAR(50),
    order_details   JSONB,
    
    -- Files
    analysis_file   VARCHAR(500),
    trade_file      VARCHAR(500),
    
    -- Timing
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    duration_seconds NUMERIC(8,2),
    
    -- Error tracking
    error_message   TEXT,
    
    -- Full output (compressed for storage efficiency)
    raw_output      TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_history_schedule ON nexus.run_history(schedule_id);
CREATE INDEX IF NOT EXISTS idx_run_history_ticker ON nexus.run_history(ticker);
CREATE INDEX IF NOT EXISTS idx_run_history_status ON nexus.run_history(status);
CREATE INDEX IF NOT EXISTS idx_run_history_started ON nexus.run_history(started_at);

-- ─── 5. Analysis Results (Structured) ────────────────────────

CREATE TABLE IF NOT EXISTS nexus.analysis_results (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT REFERENCES nexus.run_history(id),
    ticker          VARCHAR(10) NOT NULL,
    analysis_type   nexus.analysis_type NOT NULL,
    
    -- Parsed from JSON output
    gate_passed     BOOLEAN,
    recommendation  VARCHAR(20),
    confidence      INTEGER,
    expected_value_pct NUMERIC(6,2),
    entry_price     NUMERIC(10,2),
    stop_loss       NUMERIC(10,2),
    target_price    NUMERIC(10,2),
    position_size_pct NUMERIC(5,2),
    structure       VARCHAR(30),
    expiry_date     DATE,
    strikes         NUMERIC(10,2)[],
    rationale       TEXT,
    
    -- Market snapshot at analysis time
    price_at_analysis NUMERIC(10,2),
    iv_at_analysis    NUMERIC(6,2),
    
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_ticker ON nexus.analysis_results(ticker);
CREATE INDEX IF NOT EXISTS idx_analysis_results_date ON nexus.analysis_results(created_at);

-- ─── Helper Functions ────────────────────────────────────────

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION nexus.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS stocks_updated_at ON nexus.stocks;
CREATE TRIGGER stocks_updated_at BEFORE UPDATE ON nexus.stocks
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS scanners_updated_at ON nexus.ib_scanners;
CREATE TRIGGER scanners_updated_at BEFORE UPDATE ON nexus.ib_scanners
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

DROP TRIGGER IF EXISTS schedules_updated_at ON nexus.schedules;
CREATE TRIGGER schedules_updated_at BEFORE UPDATE ON nexus.schedules
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

-- View: Active schedules due for execution
CREATE OR REPLACE VIEW nexus.v_due_schedules AS
SELECT s.*, 
       CASE WHEN s.next_run_at <= now() THEN true ELSE false END AS is_due,
       COALESCE(s.consecutive_fails, 0) < COALESCE(s.max_consecutive_fails, 3) AS circuit_ok
FROM nexus.schedules s
WHERE s.is_enabled = true
  AND s.next_run_at IS NOT NULL
  AND s.next_run_at <= now()
  AND COALESCE(s.consecutive_fails, 0) < COALESCE(s.max_consecutive_fails, 3)
ORDER BY s.priority DESC, s.next_run_at ASC;

-- View: Stocks approaching earnings
CREATE OR REPLACE VIEW nexus.v_upcoming_earnings AS
SELECT s.*,
       s.next_earnings_date - CURRENT_DATE AS days_until_earnings
FROM nexus.stocks s
WHERE s.is_enabled = true
  AND s.next_earnings_date IS NOT NULL
  AND s.next_earnings_date >= CURRENT_DATE
  AND s.next_earnings_date <= CURRENT_DATE + INTERVAL '21 days'
ORDER BY s.next_earnings_date ASC;

-- ─── Seed Data ───────────────────────────────────────────────

-- Default watchlist
INSERT INTO nexus.stocks (ticker, name, sector, state, default_analysis_type, priority, tags, comments) VALUES
    ('NFLX', 'Netflix', 'Communication Services', 'analysis', 'earnings', 8, '{mega_cap,streaming,earnings_play}', 'Primary earnings candidate - 11/12 beat streak'),
    ('NVDA', 'NVIDIA', 'Technology', 'analysis', 'earnings', 9, '{mega_cap,ai,semiconductors}', 'AI bellwether - data center revenue key metric'),
    ('AAPL', 'Apple', 'Technology', 'analysis', 'stock', 7, '{mega_cap,tech,consumer}', NULL),
    ('AMZN', 'Amazon', 'Consumer Discretionary', 'analysis', 'earnings', 8, '{mega_cap,cloud,retail}', 'AWS growth rate is key metric'),
    ('MSFT', 'Microsoft', 'Technology', 'analysis', 'stock', 7, '{mega_cap,cloud,ai}', NULL),
    ('META', 'Meta Platforms', 'Communication Services', 'analysis', 'stock', 7, '{mega_cap,social,ai}', NULL),
    ('GOOGL', 'Alphabet', 'Communication Services', 'analysis', 'stock', 7, '{mega_cap,search,cloud,ai}', NULL),
    ('TSLA', 'Tesla', 'Consumer Discretionary', 'analysis', 'stock', 6, '{mega_cap,ev,energy}', 'High volatility - careful with position sizing'),
    ('AMD', 'AMD', 'Technology', 'analysis', 'earnings', 7, '{large_cap,semiconductors,ai}', 'Competitor to NVDA - data center GPU ramp'),
    ('CRM', 'Salesforce', 'Technology', 'analysis', 'stock', 5, '{large_cap,saas,ai}', NULL)
ON CONFLICT (ticker) DO NOTHING;

-- Default IB scanners
INSERT INTO nexus.ib_scanners (scanner_code, display_name, description, is_enabled, filters, auto_analyze, max_candidates) VALUES
    ('HIGH_OPT_IMP_VOLAT', 'High Implied Volatility', 'Stocks with highest implied volatility - potential earnings/events', true, 
     '{"priceAbove": 10, "priceBelow": 500, "marketCapAbove": 1000000000, "avgOptVolumeAbove": 1000}', 
     true, 5),
    ('HOT_BY_OPT_VOLUME', 'Hot by Options Volume', 'Unusual options activity - smart money signals', true,
     '{"priceAbove": 10, "priceBelow": 500, "marketCapAbove": 5000000000}',
     false, 10),
    ('TOP_PERC_GAIN', 'Top % Gainers', 'Biggest percentage gainers today', true,
     '{"priceAbove": 10, "marketCapAbove": 1000000000, "volumeAbove": 500000}',
     false, 10),
    ('TOP_PERC_LOSE', 'Top % Losers', 'Biggest percentage losers today - potential bounce candidates', false,
     '{"priceAbove": 10, "marketCapAbove": 1000000000, "volumeAbove": 500000}',
     false, 10),
    ('HIGH_OPT_IMP_VOLAT_OVER_HIST', 'IV Over HV', 'Stocks where IV significantly exceeds HV - premium selling candidates', true,
     '{"priceAbove": 10, "priceBelow": 500, "marketCapAbove": 2000000000, "avgOptVolumeAbove": 500}',
     true, 5),
    ('MOST_ACTIVE', 'Most Active', 'Highest volume stocks today', false,
     '{"priceAbove": 5, "marketCapAbove": 500000000}',
     false, 20)
ON CONFLICT (scanner_code) DO NOTHING;

-- Default schedules
INSERT INTO nexus.schedules (name, task_type, frequency, time_of_day, trading_days_only, market_hours_only, priority, analysis_type, auto_execute, comments) VALUES
    ('Pre-Market Earnings Scan', 'run_all_scanners', 'daily', '06:30', true, false, 9, 'scan', false,
     'Run all enabled IB scanners before market open'),
    ('Morning Watchlist Analysis', 'analyze_watchlist', 'daily', '07:00', true, false, 7, 'stock', false,
     'Quick analysis refresh on enabled watchlist stocks'),
    ('Weekly Portfolio Review', 'portfolio_review', 'weekly', '10:00', false, false, 5, 'review', false,
     'Comprehensive portfolio and framework assessment');

-- Set day_of_week for weekly schedule
UPDATE nexus.schedules SET day_of_week = 'sun' WHERE name = 'Weekly Portfolio Review';

-- Pre-earnings schedules (auto-triggered by earnings dates)
INSERT INTO nexus.schedules (name, task_type, frequency, days_before_earnings, trading_days_only, market_hours_only, priority, analysis_type, auto_execute, comments) VALUES
    ('Pre-Earnings Deep Dive (T-7)', 'pipeline', 'pre_earnings', 7, true, false, 8, 'earnings', false,
     'Full earnings analysis 7 days before. Auto-execute OFF - review first.'),
    ('Pre-Earnings Update (T-2)', 'pipeline', 'pre_earnings', 2, true, false, 9, 'earnings', false,
     'Updated analysis 2 days before earnings with latest data.'),
    ('Post-Earnings Review (T+1)', 'postmortem', 'post_earnings', 1, true, false, 8, 'postmortem', false,
     'Mandatory post-mortem 1 day after earnings.');

-- ─── 6. Settings (Key-Value, hot-reloadable) ─────────────────

CREATE TABLE IF NOT EXISTS nexus.settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           JSONB NOT NULL,
    description     TEXT,
    category        VARCHAR(50) NOT NULL DEFAULT 'general',
    -- Categories: general, rate_limits, claude, ib, lightrag, scheduler, feature_flags
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

DROP TRIGGER IF EXISTS settings_updated_at ON nexus.settings;
CREATE TRIGGER settings_updated_at BEFORE UPDATE ON nexus.settings
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

-- Seed default settings
INSERT INTO nexus.settings (key, value, category, description) VALUES
    -- Rate limits
    ('max_daily_analyses',      '15',           'rate_limits',   'Maximum analysis runs per day'),
    ('max_daily_executions',    '5',            'rate_limits',   'Maximum order executions per day'),
    ('max_concurrent_runs',     '2',            'rate_limits',   'Max Claude Code processes at once'),

    -- Claude Code
    ('claude_cmd',              '"claude"',     'claude',        'Claude Code CLI command'),
    ('claude_timeout_seconds',  '600',          'claude',        'Max seconds per Claude Code call'),
    ('claude_model',            '"claude-sonnet-4-5-20250929"', 'claude', 'Model for Claude Code'),
    ('allowed_tools_analysis',  '"mcp__ib-gateway__*,web_search,mcp__lightrag__*"', 'claude', 'Tools for Stage 1'),
    ('allowed_tools_execution', '"mcp__ib-gateway__*,mcp__lightrag__*"',            'claude', 'Tools for Stage 2'),
    ('allowed_tools_scanner',   '"mcp__ib-gateway__*"',                             'claude', 'Tools for scanners'),

    -- IB
    ('ib_account',              '"DU_PAPER"',   'ib',            'IB account ID for orders'),
    ('ib_trading_mode',         '"paper"',      'ib',            'paper or live'),

    -- LightRAG
    ('lightrag_url',            '"http://localhost:9621"', 'lightrag', 'LightRAG API endpoint'),
    ('lightrag_ingest_enabled', 'true',         'lightrag',      'Ingest analyses into LightRAG'),

    -- Scheduler
    ('scheduler_poll_seconds',  '60',           'scheduler',     'How often daemon checks for due schedules'),
    ('earnings_check_hours',    '[6, 7]',       'scheduler',     'Hours (ET) when earnings triggers are checked'),
    ('earnings_lookback_days',  '21',           'scheduler',     'Days ahead to scan for upcoming earnings'),

    -- Feature flags
    ('auto_execute_enabled',    'false',        'feature_flags', 'Global kill switch for Stage 2 execution'),
    ('scanners_enabled',        'true',         'feature_flags', 'Global enable/disable for IB scanners'),
    ('lightrag_query_enabled',  'true',         'feature_flags', 'Include LightRAG context in prompts'),
    ('dry_run_mode',            'true',         'feature_flags', 'Log what would happen without calling Claude Code'),
    ('four_phase_analysis_enabled', 'true',     'feature_flags', 'Enable 4-phase workflow: fresh analysis → index → retrieve → synthesize'),

    -- Paths
    ('analyses_dir',            '"analyses"',   'general',       'Directory for analysis output files'),
    ('trades_dir',              '"trades"',     'general',       'Directory for trade log files'),
    ('logs_dir',                '"logs"',       'general',       'Directory for log files')
ON CONFLICT (key) DO NOTHING;

-- ─── 7. Service Status (heartbeat + metrics) ─────────────────

CREATE TABLE IF NOT EXISTS nexus.service_status (
    id              INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton row
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_heartbeat  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_tick_duration_ms INTEGER,
    state           VARCHAR(20) NOT NULL DEFAULT 'starting',
    -- states: starting, running, paused, stopping, error
    current_task    VARCHAR(200),
    pid             INTEGER,
    hostname        VARCHAR(100),
    version         VARCHAR(20) DEFAULT '2.1.0',

    -- Cumulative counters (since last restart)
    ticks_total         INTEGER DEFAULT 0,
    analyses_total      INTEGER DEFAULT 0,
    executions_total    INTEGER DEFAULT 0,
    errors_total        INTEGER DEFAULT 0,

    -- Current cycle stats
    today_analyses      INTEGER DEFAULT 0,
    today_executions    INTEGER DEFAULT 0,
    today_errors        INTEGER DEFAULT 0,
    today_date          DATE DEFAULT CURRENT_DATE,

    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO nexus.service_status (id) VALUES (1) ON CONFLICT DO NOTHING;

COMMENT ON TABLE nexus.stocks IS 'Watchlist of stocks to monitor and trade. Controls which tickers the system analyzes.';
COMMENT ON TABLE nexus.ib_scanners IS 'IB market scanners for discovering opportunities. Results can auto-populate watchlist.';
COMMENT ON TABLE nexus.schedules IS 'Cron-like schedule definitions. Drives the orchestrator''s automated execution.';
COMMENT ON TABLE nexus.run_history IS 'Audit log of every orchestrator run. Tracks analysis results and execution outcomes.';
COMMENT ON TABLE nexus.analysis_results IS 'Structured analysis outputs parsed from Claude Code responses. Enables trend analysis.';
COMMENT ON TABLE nexus.settings IS 'Hot-reloadable key-value settings. Changes take effect on next scheduler tick.';
COMMENT ON TABLE nexus.service_status IS 'Singleton row tracking service health. Used for heartbeat and monitoring.';

-- ─── 8. Audit Log (Security Tracking) ──────────────────────────

CREATE TABLE IF NOT EXISTS nexus.audit_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- What happened
    action          VARCHAR(50) NOT NULL,
    -- Actions: stock_add, stock_delete, stock_update, setting_change,
    --          schedule_create, schedule_delete, order_placed, order_cancelled,
    --          login_attempt, api_key_used, cypher_blocked, etc.

    -- Who did it
    actor           VARCHAR(100) NOT NULL DEFAULT 'system',
    -- e.g., 'system', 'orchestrator', 'service', 'cli:user', 'api:token_xxx'

    -- What was affected
    resource_type   VARCHAR(50),
    -- e.g., 'stock', 'schedule', 'setting', 'order', 'analysis'
    resource_id     VARCHAR(100),
    -- e.g., ticker symbol, schedule name, setting key

    -- Result
    result          VARCHAR(20) NOT NULL DEFAULT 'success',
    -- success, failure, blocked, error

    -- Details (JSONB for flexibility)
    details         JSONB DEFAULT '{}',
    -- e.g., {"old_value": "...", "new_value": "...", "reason": "..."}

    -- Context
    ip_address      INET,
    user_agent      VARCHAR(500),
    session_id      VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON nexus.audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON nexus.audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON nexus.audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON nexus.audit_log(resource_type, resource_id);

-- Function to log audit events
CREATE OR REPLACE FUNCTION nexus.audit_log_event(
    p_action VARCHAR(50),
    p_resource_type VARCHAR(50) DEFAULT NULL,
    p_resource_id VARCHAR(100) DEFAULT NULL,
    p_result VARCHAR(20) DEFAULT 'success',
    p_details JSONB DEFAULT '{}',
    p_actor VARCHAR(100) DEFAULT 'system'
) RETURNS BIGINT AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO nexus.audit_log (action, actor, resource_type, resource_id, result, details)
    VALUES (p_action, p_actor, p_resource_type, p_resource_id, p_result, p_details)
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE nexus.audit_log IS 'Security audit log tracking all significant actions. Required for compliance and incident response.';
COMMENT ON FUNCTION nexus.audit_log_event IS 'Helper function to log audit events with consistent structure.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 9. TRADES TABLE (for trade journal and post-trade review)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.trades (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,

    -- Entry
    entry_date      TIMESTAMPTZ NOT NULL,
    entry_price     DECIMAL(12,4) NOT NULL,
    entry_size      DECIMAL(12,4),           -- shares or contracts
    entry_type      VARCHAR(20) DEFAULT 'stock',  -- stock, call, put, spread

    -- Position
    status          VARCHAR(20) DEFAULT 'open',   -- open, closed, partial
    current_size    DECIMAL(12,4),

    -- Exit (when closed)
    exit_date       TIMESTAMPTZ,
    exit_price      DECIMAL(12,4),
    exit_reason     VARCHAR(50),             -- target, stop, manual, expiry

    -- P&L
    pnl_dollars     DECIMAL(12,2),
    pnl_pct         DECIMAL(8,4),

    -- Thesis
    thesis          TEXT,
    source_analysis VARCHAR(200),            -- path to analysis YAML

    -- Review
    review_status   VARCHAR(20) DEFAULT 'pending',  -- pending, completed
    review_path     VARCHAR(200),            -- path to review YAML

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trades_ticker ON nexus.trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_status ON nexus.trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_review ON nexus.trades(review_status) WHERE status = 'closed';

DROP TRIGGER IF EXISTS trades_updated_at ON nexus.trades;
CREATE TRIGGER trades_updated_at BEFORE UPDATE ON nexus.trades
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

COMMENT ON TABLE nexus.trades IS 'Trade journal entries for position tracking and post-trade review.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 10. WATCHLIST TABLE (DB-backed watchlist for persistence)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.watchlist (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(10) NOT NULL,

    -- Entry conditions
    entry_trigger   TEXT NOT NULL,           -- "Price below $150"
    entry_price     DECIMAL(12,4),

    -- Invalidation
    invalidation    TEXT,
    invalidation_price DECIMAL(12,4),

    -- Timing
    expires_at      TIMESTAMPTZ,
    priority        VARCHAR(10) DEFAULT 'medium',  -- high, medium, low

    -- Status
    status          VARCHAR(20) DEFAULT 'active',  -- active, triggered, invalidated, expired

    -- Source
    source          VARCHAR(50),             -- "analysis", "scanner:earnings-momentum"
    source_analysis VARCHAR(200),

    -- Notes
    notes           TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Note: UNIQUE constraint on (ticker, status) not used - allows multiple entries per ticker
CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON nexus.watchlist(ticker);
CREATE INDEX IF NOT EXISTS idx_watchlist_active ON nexus.watchlist(status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_watchlist_expires ON nexus.watchlist(expires_at) WHERE status = 'active';

DROP TRIGGER IF EXISTS watchlist_updated_at ON nexus.watchlist;
CREATE TRIGGER watchlist_updated_at BEFORE UPDATE ON nexus.watchlist
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

COMMENT ON TABLE nexus.watchlist IS 'DB-backed watchlist for entry trigger tracking. Source of truth for watch entries.';

-- ═══════════════════════════════════════════════════════════════════════════
-- 11. TASK QUEUE (for async task processing)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nexus.task_queue (
    id              SERIAL PRIMARY KEY,

    task_type       VARCHAR(50) NOT NULL,    -- analysis, post_trade_review, scan
    ticker          VARCHAR(10),

    -- Task details
    analysis_type   VARCHAR(20),             -- stock, earnings
    prompt          TEXT,
    priority        INTEGER DEFAULT 5,

    -- Status
    status          VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, failed

    -- Cooldown (prevent duplicate runs)
    cooldown_key    VARCHAR(100),            -- "analysis:NVDA:stock"
    cooldown_until  TIMESTAMPTZ,

    -- Execution
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_task_queue_pending ON nexus.task_queue(status, priority DESC) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_task_queue_cooldown ON nexus.task_queue(cooldown_key, cooldown_until);

COMMENT ON TABLE nexus.task_queue IS 'Async task queue for background processing of analyses and reviews.';

-- ═══════════════════════════════════════════════════════════════════════════
-- WORKFLOW AUTOMATION SETTINGS
-- ═══════════════════════════════════════════════════════════════════════════
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('auto_viz_enabled', 'true', 'feature_flags', 'Auto-generate SVG after analysis'),
    ('auto_watchlist_chain', 'true', 'feature_flags', 'Auto-add WATCH recommendations to watchlist'),
    ('scanner_auto_route', 'true', 'feature_flags', 'Auto-route scanner results to analysis/watchlist'),
    ('task_queue_enabled', 'true', 'feature_flags', 'Enable async task queue processing'),
    ('analysis_cooldown_hours', '4', 'rate_limits', 'Hours between re-analyzing same ticker')
ON CONFLICT (key) DO NOTHING;
