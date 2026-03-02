-- Migration 011: Add user_id Columns for Multi-Tenancy
-- Adds user_id foreign key to all user-specific tables
-- Version: 1.0.0
-- Date: 2026-03-01

BEGIN;

-- ============================================================================
-- CORE TABLES (8 tables)
-- ============================================================================

-- stocks table
ALTER TABLE nexus.stocks
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_stocks_user_id ON nexus.stocks(user_id);

-- trades table
ALTER TABLE nexus.trades
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON nexus.trades(user_id);

-- watchlist table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'watchlist') THEN
        ALTER TABLE nexus.watchlist
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_watchlist_user_id ON nexus.watchlist(user_id);
    END IF;
END $$;

-- schedules table
ALTER TABLE nexus.schedules
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_schedules_user_id ON nexus.schedules(user_id);

-- run_history table
ALTER TABLE nexus.run_history
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_run_history_user_id ON nexus.run_history(user_id);

-- analysis_results table
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'analysis_results') THEN
        ALTER TABLE nexus.analysis_results
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_analysis_results_user_id ON nexus.analysis_results(user_id);
    END IF;
END $$;

-- task_queue table
ALTER TABLE nexus.task_queue
    ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_task_queue_user_id ON nexus.task_queue(user_id);

-- analysis_lineage table (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'analysis_lineage') THEN
        ALTER TABLE nexus.analysis_lineage
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_analysis_lineage_user_id ON nexus.analysis_lineage(user_id);
    END IF;
END $$;

-- ============================================================================
-- KNOWLEDGE BASE TABLES (10 tables from migration 009)
-- ============================================================================

-- kb_stock_analyses
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_stock_analyses') THEN
        ALTER TABLE nexus.kb_stock_analyses
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_stock_analyses_user_id ON nexus.kb_stock_analyses(user_id);
    END IF;
END $$;

-- kb_earnings_analyses
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_earnings_analyses') THEN
        ALTER TABLE nexus.kb_earnings_analyses
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_earnings_analyses_user_id ON nexus.kb_earnings_analyses(user_id);
    END IF;
END $$;

-- kb_research_analyses
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_research_analyses') THEN
        ALTER TABLE nexus.kb_research_analyses
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_research_analyses_user_id ON nexus.kb_research_analyses(user_id);
    END IF;
END $$;

-- kb_ticker_profiles
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_ticker_profiles') THEN
        ALTER TABLE nexus.kb_ticker_profiles
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_ticker_profiles_user_id ON nexus.kb_ticker_profiles(user_id);
    END IF;
END $$;

-- kb_trade_journals
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_trade_journals') THEN
        ALTER TABLE nexus.kb_trade_journals
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_trade_journals_user_id ON nexus.kb_trade_journals(user_id);
    END IF;
END $$;

-- kb_watchlist_entries
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_watchlist_entries') THEN
        ALTER TABLE nexus.kb_watchlist_entries
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_watchlist_entries_user_id ON nexus.kb_watchlist_entries(user_id);
    END IF;
END $$;

-- kb_reviews
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_reviews') THEN
        ALTER TABLE nexus.kb_reviews
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_reviews_user_id ON nexus.kb_reviews(user_id);
    END IF;
END $$;

-- kb_learnings
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_learnings') THEN
        ALTER TABLE nexus.kb_learnings
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_learnings_user_id ON nexus.kb_learnings(user_id);
    END IF;
END $$;

-- kb_strategies
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_strategies') THEN
        ALTER TABLE nexus.kb_strategies
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_strategies_user_id ON nexus.kb_strategies(user_id);
    END IF;
END $$;

-- kb_scanner_configs
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'kb_scanner_configs') THEN
        ALTER TABLE nexus.kb_scanner_configs
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_kb_scanner_configs_user_id ON nexus.kb_scanner_configs(user_id);
    END IF;
END $$;

-- ============================================================================
-- RAG TABLES (for user isolation)
-- ============================================================================

-- rag_documents
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'rag_documents') THEN
        ALTER TABLE nexus.rag_documents
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id ON nexus.rag_documents(user_id);
    END IF;
END $$;

-- rag_chunks
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'rag_chunks') THEN
        ALTER TABLE nexus.rag_chunks
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_rag_chunks_user_id ON nexus.rag_chunks(user_id);
    END IF;
END $$;

-- ============================================================================
-- AGENT UI TABLES (3 tables - if they exist)
-- ============================================================================

-- sessions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'sessions') THEN
        ALTER TABLE nexus.sessions
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON nexus.sessions(user_id);
    END IF;
END $$;

-- messages
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'messages') THEN
        ALTER TABLE nexus.messages
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_messages_user_id ON nexus.messages(user_id);
    END IF;
END $$;

-- tasks
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'tasks') THEN
        ALTER TABLE nexus.tasks
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON nexus.tasks(user_id);
    END IF;
END $$;

-- ============================================================================
-- ADDITIONAL TABLES (skill invocations, confidence calibration, etc.)
-- ============================================================================

-- skill_invocations
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'skill_invocations') THEN
        ALTER TABLE nexus.skill_invocations
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_skill_invocations_user_id ON nexus.skill_invocations(user_id);
    END IF;
END $$;

-- confidence_calibration
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'confidence_calibration') THEN
        ALTER TABLE nexus.confidence_calibration
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_confidence_calibration_user_id ON nexus.confidence_calibration(user_id);
    END IF;
END $$;

-- notification_log
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'notification_log') THEN
        ALTER TABLE nexus.notification_log
            ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS idx_notification_log_user_id ON nexus.notification_log(user_id);
    END IF;
END $$;

COMMIT;
