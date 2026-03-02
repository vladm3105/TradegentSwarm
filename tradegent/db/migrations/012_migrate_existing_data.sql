-- Migration 012: Migrate Existing Data to Admin User
-- Backfills all existing data to user_id = 1 (system admin)
-- Version: 1.0.0
-- Date: 2026-03-01

BEGIN;

-- ============================================================================
-- BACKFILL EXISTING DATA TO ADMIN USER (user_id = 1)
-- ============================================================================

-- Core tables
UPDATE nexus.stocks SET user_id = 1 WHERE user_id IS NULL;
UPDATE nexus.trades SET user_id = 1 WHERE user_id IS NULL;
UPDATE nexus.schedules SET user_id = 1 WHERE user_id IS NULL;
UPDATE nexus.run_history SET user_id = 1 WHERE user_id IS NULL;
UPDATE nexus.task_queue SET user_id = 1 WHERE user_id IS NULL;

-- Watchlist (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'watchlist') THEN
        EXECUTE 'UPDATE nexus.watchlist SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- Analysis results (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'analysis_results') THEN
        EXECUTE 'UPDATE nexus.analysis_results SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- Analysis lineage (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'analysis_lineage') THEN
        EXECUTE 'UPDATE nexus.analysis_lineage SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- Knowledge Base tables
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_stock_analyses') THEN
        EXECUTE 'UPDATE nexus.kb_stock_analyses SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_earnings_analyses') THEN
        EXECUTE 'UPDATE nexus.kb_earnings_analyses SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_research_analyses') THEN
        EXECUTE 'UPDATE nexus.kb_research_analyses SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_ticker_profiles') THEN
        EXECUTE 'UPDATE nexus.kb_ticker_profiles SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_trade_journals') THEN
        EXECUTE 'UPDATE nexus.kb_trade_journals SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_watchlist_entries') THEN
        EXECUTE 'UPDATE nexus.kb_watchlist_entries SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_reviews') THEN
        EXECUTE 'UPDATE nexus.kb_reviews SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_learnings') THEN
        EXECUTE 'UPDATE nexus.kb_learnings SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_strategies') THEN
        EXECUTE 'UPDATE nexus.kb_strategies SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_scanner_configs') THEN
        EXECUTE 'UPDATE nexus.kb_scanner_configs SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- RAG tables
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'rag_documents') THEN
        EXECUTE 'UPDATE nexus.rag_documents SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'rag_chunks') THEN
        EXECUTE 'UPDATE nexus.rag_chunks SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- Agent UI tables
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'sessions') THEN
        EXECUTE 'UPDATE nexus.sessions SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'messages') THEN
        EXECUTE 'UPDATE nexus.messages SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'tasks') THEN
        EXECUTE 'UPDATE nexus.tasks SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- Additional tables
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'skill_invocations') THEN
        EXECUTE 'UPDATE nexus.skill_invocations SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'confidence_calibration') THEN
        EXECUTE 'UPDATE nexus.confidence_calibration SET user_id = 1 WHERE user_id IS NULL';
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'notification_log') THEN
        EXECUTE 'UPDATE nexus.notification_log SET user_id = 1 WHERE user_id IS NULL';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================

-- Create a verification view to check migration status
CREATE OR REPLACE VIEW nexus.v_user_data_migration_status AS
SELECT 'stocks' as table_name, COUNT(*) as total, COUNT(user_id) as with_user_id FROM nexus.stocks
UNION ALL
SELECT 'trades', COUNT(*), COUNT(user_id) FROM nexus.trades
UNION ALL
SELECT 'schedules', COUNT(*), COUNT(user_id) FROM nexus.schedules
UNION ALL
SELECT 'run_history', COUNT(*), COUNT(user_id) FROM nexus.run_history
UNION ALL
SELECT 'task_queue', COUNT(*), COUNT(user_id) FROM nexus.task_queue;

-- Log migration completion
DO $$
DECLARE
    v_total_records INTEGER;
    v_migrated_records INTEGER;
BEGIN
    SELECT SUM(total), SUM(with_user_id)
    INTO v_total_records, v_migrated_records
    FROM nexus.v_user_data_migration_status;

    RAISE NOTICE 'Migration complete: % of % records now have user_id', v_migrated_records, v_total_records;
END $$;

COMMIT;
