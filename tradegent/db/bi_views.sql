-- ═══════════════════════════════════════════════════════════════
-- Tradegent BI Views for Metabase and Dashboard API
-- Run: docker exec -i tradegent-postgres-1 psql -U tradegent -d tradegent < db/bi_views.sql
-- ═══════════════════════════════════════════════════════════════

-- ─── Portfolio Summary (for Dashboard API) ───────────────────────
DROP VIEW IF EXISTS nexus.v_bi_portfolio_summary CASCADE;
CREATE VIEW nexus.v_bi_portfolio_summary AS
SELECT
    -- Total P&L from all closed trades
    COALESCE(SUM(t.pnl_dollars), 0) AS total_pnl,
    -- Total P&L as percentage (weighted average)
    COALESCE(AVG(t.pnl_pct), 0) AS total_pnl_pct,
    -- Open positions count
    (SELECT COUNT(*) FROM nexus.trades WHERE status = 'open') AS open_positions,
    -- Total market value of open positions (entry_price * entry_size)
    COALESCE((
        SELECT SUM(entry_price * entry_size)
        FROM nexus.trades
        WHERE status = 'open'
    ), 0) AS total_market_value
FROM nexus.trades t
WHERE t.status = 'closed';

COMMENT ON VIEW nexus.v_bi_portfolio_summary IS 'Portfolio summary for dashboard stats';


-- ─── Analysis Performance ──────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_analysis_performance CASCADE;
CREATE VIEW nexus.v_bi_analysis_performance AS
SELECT
    ar.id,
    ar.ticker,
    ar.analysis_type::text,
    ar.recommendation,
    ar.confidence,
    ar.expected_value_pct,
    ar.gate_passed,
    ar.entry_price,
    ar.target_price,
    ar.stop_loss,
    ar.created_at AS analysis_date,
    DATE_TRUNC('week', ar.created_at) AS analysis_week,
    DATE_TRUNC('month', ar.created_at) AS analysis_month,
    ar.doc_id
FROM nexus.analysis_results ar;

COMMENT ON VIEW nexus.v_bi_analysis_performance IS 'Analysis results for BI reporting';


-- ─── Trade Performance ─────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_trade_performance CASCADE;
CREATE VIEW nexus.v_bi_trade_performance AS
SELECT
    t.id AS trade_id,
    t.ticker,
    t.entry_type AS trade_type,
    t.status,
    t.entry_date,
    t.entry_price,
    t.entry_size AS position_size,
    t.exit_date,
    t.exit_price,
    t.pnl_dollars,
    t.pnl_pct AS pnl_percent,
    t.exit_reason,
    t.direction,
    -- Calculated fields
    CASE WHEN t.pnl_dollars > 0 THEN 'win'
         WHEN t.pnl_dollars < 0 THEN 'loss'
         ELSE 'breakeven' END AS outcome,
    EXTRACT(DAY FROM COALESCE(t.exit_date, CURRENT_TIMESTAMP) - t.entry_date)::int AS hold_days,
    DATE_TRUNC('week', t.entry_date) AS entry_week,
    DATE_TRUNC('month', t.entry_date) AS entry_month,
    t.source_analysis,
    t.thesis
FROM nexus.trades t;

COMMENT ON VIEW nexus.v_bi_trade_performance IS 'Trade journal with calculated metrics';


-- ─── Daily P&L Summary ─────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_daily_pnl CASCADE;
CREATE VIEW nexus.v_bi_daily_pnl AS
SELECT
    DATE(exit_date) AS date,           -- Dashboard expects 'date'
    COUNT(*) AS trades_closed,
    SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN pnl_dollars < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 1) AS win_rate,
    SUM(pnl_dollars) AS pnl,           -- Dashboard expects 'pnl'
    AVG(pnl_pct) AS pnl_pct,           -- Dashboard expects 'pnl_pct'
    AVG(pnl_dollars) AS avg_pnl,
    MAX(pnl_dollars) AS best_trade,
    MIN(pnl_dollars) AS worst_trade,
    SUM(CASE WHEN pnl_dollars > 0 THEN pnl_dollars ELSE 0 END) AS gross_profit,
    SUM(CASE WHEN pnl_dollars < 0 THEN ABS(pnl_dollars) ELSE 0 END) AS gross_loss,
    -- Cumulative P&L (running total)
    SUM(SUM(pnl_dollars)) OVER (ORDER BY DATE(exit_date)) AS cumulative_pnl
FROM nexus.trades
WHERE status = 'closed' AND exit_date IS NOT NULL
GROUP BY DATE(exit_date)
ORDER BY date DESC;

COMMENT ON VIEW nexus.v_bi_daily_pnl IS 'Daily P&L aggregation for dashboard';


-- ─── Weekly P&L Summary ────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_weekly_pnl CASCADE;
CREATE VIEW nexus.v_bi_weekly_pnl AS
SELECT
    DATE_TRUNC('week', exit_date)::date AS week,    -- Dashboard expects 'week'
    COUNT(*) AS trades,                              -- Dashboard expects 'trades'
    SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN pnl_dollars < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 1) AS win_rate,  -- Dashboard expects 'win_rate'
    SUM(pnl_dollars) AS pnl,                         -- Dashboard expects 'pnl'
    AVG(pnl_dollars) AS avg_pnl,
    ROUND(
        SUM(CASE WHEN pnl_dollars > 0 THEN pnl_dollars ELSE 0 END) /
        NULLIF(SUM(CASE WHEN pnl_dollars < 0 THEN ABS(pnl_dollars) ELSE 0 END), 0),
        2
    ) AS profit_factor
FROM nexus.trades
WHERE status = 'closed' AND exit_date IS NOT NULL
GROUP BY DATE_TRUNC('week', exit_date)
ORDER BY week DESC;

COMMENT ON VIEW nexus.v_bi_weekly_pnl IS 'Weekly P&L for dashboard';


-- ─── Monthly P&L Summary ───────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_monthly_pnl CASCADE;
CREATE VIEW nexus.v_bi_monthly_pnl AS
SELECT
    DATE_TRUNC('month', exit_date)::date AS month,   -- Dashboard expects 'month'
    TO_CHAR(exit_date, 'YYYY-MM') AS month_label,
    COUNT(*) AS trades,                               -- Dashboard expects 'trades'
    SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN pnl_dollars < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 1) AS win_rate, -- Dashboard expects 'win_rate'
    SUM(pnl_dollars) AS pnl,                         -- Dashboard expects 'pnl'
    AVG(pnl_dollars) AS avg_pnl,
    AVG(pnl_pct) AS avg_pnl_pct,
    SUM(SUM(pnl_dollars)) OVER (ORDER BY DATE_TRUNC('month', exit_date)) AS cumulative_pnl
FROM nexus.trades
WHERE status = 'closed' AND exit_date IS NOT NULL
GROUP BY DATE_TRUNC('month', exit_date), TO_CHAR(exit_date, 'YYYY-MM')
ORDER BY month DESC;

COMMENT ON VIEW nexus.v_bi_monthly_pnl IS 'Monthly P&L for dashboard';


-- ─── Ticker Performance ────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_ticker_performance CASCADE;
CREATE VIEW nexus.v_bi_ticker_performance AS
SELECT
    ticker,
    COUNT(*) AS total_trades,
    SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN pnl_dollars < 0 THEN 1 ELSE 0 END) AS losses,
    ROUND(SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END)::numeric /
          NULLIF(COUNT(*), 0) * 100, 1) AS win_rate,  -- Dashboard expects 'win_rate'
    SUM(pnl_dollars) AS total_pnl,
    AVG(pnl_pct) AS total_pnl_pct,                    -- Dashboard expects 'total_pnl_pct'
    AVG(pnl_dollars) AS avg_pnl,
    AVG(pnl_pct) AS avg_return_pct,
    MAX(pnl_dollars) AS best_trade,
    MIN(pnl_dollars) AS worst_trade,
    AVG(EXTRACT(DAY FROM COALESCE(exit_date, CURRENT_TIMESTAMP) - entry_date)) AS avg_hold_days
FROM nexus.trades
WHERE status = 'closed'
GROUP BY ticker
HAVING COUNT(*) >= 1
ORDER BY total_pnl DESC;

COMMENT ON VIEW nexus.v_bi_ticker_performance IS 'Performance by ticker for dashboard';


-- ─── Recommendation Distribution ───────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_recommendation_distribution CASCADE;
CREATE VIEW nexus.v_bi_recommendation_distribution AS
SELECT
    DATE_TRUNC('week', created_at)::date AS week_start,
    recommendation,
    COUNT(*) AS count,
    AVG(confidence) AS avg_confidence,
    AVG(expected_value_pct) AS avg_expected_value,
    SUM(CASE WHEN gate_passed THEN 1 ELSE 0 END) AS gate_passes
FROM nexus.analysis_results
GROUP BY DATE_TRUNC('week', created_at), recommendation
ORDER BY week_start DESC, count DESC;

COMMENT ON VIEW nexus.v_bi_recommendation_distribution IS 'Weekly recommendation patterns';


-- ─── RAG Document Stats ────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_rag_stats CASCADE;
CREATE VIEW nexus.v_bi_rag_stats AS
SELECT
    doc_type,
    COUNT(*) AS document_count,
    SUM(chunk_count) AS total_chunks,
    AVG(chunk_count)::numeric(10,1) AS avg_chunks_per_doc,
    MIN(created_at) AS first_document,
    MAX(created_at) AS last_document,
    COUNT(DISTINCT ticker) AS unique_tickers
FROM nexus.rag_documents
GROUP BY doc_type
ORDER BY document_count DESC;

COMMENT ON VIEW nexus.v_bi_rag_stats IS 'RAG knowledge base statistics';


-- ─── Service Health ────────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_service_health CASCADE;
CREATE VIEW nexus.v_bi_service_health AS
SELECT
    state,
    last_heartbeat,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_heartbeat))::int AS seconds_since_heartbeat,
    ticks_total,
    analyses_total,
    executions_total,
    today_analyses,
    today_executions,
    today_errors,
    CASE
        WHEN last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '5 minutes' THEN 'healthy'
        WHEN last_heartbeat > CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN 'degraded'
        ELSE 'unhealthy'
    END AS health_status
FROM nexus.service_status;

COMMENT ON VIEW nexus.v_bi_service_health IS 'Service health monitoring';


-- ─── Watchlist Summary ─────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_watchlist_summary CASCADE;
CREATE VIEW nexus.v_bi_watchlist_summary AS
SELECT
    status,
    COUNT(*) AS count,
    array_agg(DISTINCT ticker) AS tickers
FROM nexus.watchlist
GROUP BY status
ORDER BY count DESC;

COMMENT ON VIEW nexus.v_bi_watchlist_summary IS 'Watchlist status summary';


-- ─── Stock Watchlist ───────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_stock_watchlist CASCADE;
CREATE VIEW nexus.v_bi_stock_watchlist AS
SELECT
    s.ticker,
    s.state,
    s.is_enabled,
    s.priority,
    s.default_analysis_type::text,
    s.next_earnings_date,
    s.days_to_earnings,
    s.tags,
    s.comment,
    (SELECT COUNT(*) FROM nexus.analysis_results ar WHERE ar.ticker = s.ticker) AS analysis_count,
    (SELECT COUNT(*) FROM nexus.trades t WHERE t.ticker = s.ticker) AS trade_count,
    (SELECT MAX(created_at) FROM nexus.analysis_results ar WHERE ar.ticker = s.ticker) AS last_analysis
FROM nexus.stocks s
ORDER BY s.priority DESC, s.ticker;

COMMENT ON VIEW nexus.v_bi_stock_watchlist IS 'Stock watchlist with activity counts';


-- ─── Analysis by Type ──────────────────────────────────────────
DROP VIEW IF EXISTS nexus.v_bi_analysis_by_type CASCADE;
CREATE VIEW nexus.v_bi_analysis_by_type AS
SELECT
    analysis_type::text,
    DATE_TRUNC('month', created_at)::date AS month,
    COUNT(*) AS analysis_count,
    AVG(confidence) AS avg_confidence,
    AVG(expected_value_pct) AS avg_expected_value,
    SUM(CASE WHEN gate_passed THEN 1 ELSE 0 END) AS gate_passes,
    ROUND(SUM(CASE WHEN gate_passed THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1) AS gate_pass_rate
FROM nexus.analysis_results
GROUP BY analysis_type, DATE_TRUNC('month', created_at)
ORDER BY month DESC, analysis_type;

COMMENT ON VIEW nexus.v_bi_analysis_by_type IS 'Monthly analysis summary by type';


-- ═══════════════════════════════════════════════════════════════
-- Summary: Created BI views
-- ═══════════════════════════════════════════════════════════════
SELECT 'BI Views Created Successfully' AS status;

SELECT viewname FROM pg_views WHERE schemaname = 'nexus' AND viewname LIKE 'v_bi_%' ORDER BY viewname;
