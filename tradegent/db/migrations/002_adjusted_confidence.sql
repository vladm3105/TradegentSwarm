-- Migration: Add adjusted confidence columns to analysis_results
-- Created: 2026-02-20
-- Purpose: Store Phase 4 synthesis results (confidence adjustments and modifiers)

-- Add adjusted confidence columns to analysis_results
ALTER TABLE nexus.analysis_results
    ADD COLUMN IF NOT EXISTS adjusted_confidence INTEGER,
    ADD COLUMN IF NOT EXISTS confidence_modifiers JSONB,
    ADD COLUMN IF NOT EXISTS doc_id VARCHAR(255);

-- Comments for new columns
COMMENT ON COLUMN nexus.analysis_results.adjusted_confidence IS
    'Confidence after Phase 4 synthesis adjustment (historical comparison)';
COMMENT ON COLUMN nexus.analysis_results.confidence_modifiers IS
    'JSON dict of factors that adjusted confidence: {factor: adjustment_pct}';
COMMENT ON COLUMN nexus.analysis_results.doc_id IS
    'RAG document ID for cross-reference with rag_documents table';

-- Index for doc_id lookups
CREATE INDEX IF NOT EXISTS idx_analysis_results_doc_id
    ON nexus.analysis_results(doc_id);

-- Add phase timeout settings
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('phase2_timeout_seconds', '120', 'timeouts', 'Phase 2 (ingest) timeout in seconds'),
    ('phase3_timeout_seconds', '60', 'timeouts', 'Phase 3 (retrieval) timeout in seconds'),
    ('phase4_timeout_seconds', '30', 'timeouts', 'Phase 4 (synthesis) timeout in seconds')
ON CONFLICT (key) DO NOTHING;
