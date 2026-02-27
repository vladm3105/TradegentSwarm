-- Rollback migration 009: Knowledge Base Tables
-- WARNING: This will delete all data in kb_* tables!
-- Date: 2026-02-27

-- ============================================================================
-- Drop views first
-- ============================================================================
DROP VIEW IF EXISTS nexus.v_latest_stock_analyses CASCADE;
DROP VIEW IF EXISTS nexus.v_latest_earnings_analyses CASCADE;
DROP VIEW IF EXISTS nexus.v_kb_active_watchlist CASCADE;
DROP VIEW IF EXISTS nexus.v_trade_performance CASCADE;
DROP VIEW IF EXISTS nexus.v_bias_frequency CASCADE;
DROP VIEW IF EXISTS nexus.v_high_confidence_analyses CASCADE;
DROP VIEW IF EXISTS nexus.v_active_strategies CASCADE;
DROP VIEW IF EXISTS nexus.v_enabled_scanners CASCADE;

-- ============================================================================
-- Drop tables (order matters due to FK constraints)
-- ============================================================================
DROP TABLE IF EXISTS nexus.kb_reviews CASCADE;
DROP TABLE IF EXISTS nexus.kb_watchlist_entries CASCADE;
DROP TABLE IF EXISTS nexus.kb_trade_journals CASCADE;
DROP TABLE IF EXISTS nexus.kb_learnings CASCADE;
DROP TABLE IF EXISTS nexus.kb_strategies CASCADE;
DROP TABLE IF EXISTS nexus.kb_scanner_configs CASCADE;
DROP TABLE IF EXISTS nexus.kb_ticker_profiles CASCADE;
DROP TABLE IF EXISTS nexus.kb_research_analyses CASCADE;
DROP TABLE IF EXISTS nexus.kb_earnings_analyses CASCADE;
DROP TABLE IF EXISTS nexus.kb_stock_analyses CASCADE;

-- ============================================================================
-- Verify cleanup (tables)
-- ============================================================================
SELECT 'Remaining kb_* tables:' as check_type, table_name
FROM information_schema.tables
WHERE table_schema = 'nexus' AND table_name LIKE 'kb_%';

-- ============================================================================
-- Verify cleanup (views)
-- ============================================================================
SELECT 'Remaining v_* views:' as check_type, table_name
FROM information_schema.views
WHERE table_schema = 'nexus' AND table_name IN (
    'v_latest_stock_analyses',
    'v_latest_earnings_analyses',
    'v_kb_active_watchlist',
    'v_trade_performance',
    'v_bias_frequency',
    'v_high_confidence_analyses',
    'v_active_strategies',
    'v_enabled_scanners'
);
