-- ============================================================
-- Migration: v1.1.0 - Hybrid Search (BM25 + Vector)
-- ============================================================
-- Adds full-text search capability for hybrid BM25 + vector search
-- using Reciprocal Rank Fusion (RRF) scoring.
--
-- Run: psql -U tradegent -d tradegent -f v1_1_0_hybrid_search.sql
-- ============================================================

-- Add full-text search column (generated from content)
ALTER TABLE nexus.rag_chunks
ADD COLUMN IF NOT EXISTS content_tsv tsvector
GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;

-- Create GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_rag_chunks_fts
    ON nexus.rag_chunks USING gin(content_tsv);

-- Verify migration
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'nexus'
        AND table_name = 'rag_chunks'
        AND column_name = 'content_tsv'
    ) THEN
        RAISE NOTICE 'Migration v1.1.0: content_tsv column added successfully';
    ELSE
        RAISE EXCEPTION 'Migration v1.1.0: Failed to add content_tsv column';
    END IF;
END $$;
