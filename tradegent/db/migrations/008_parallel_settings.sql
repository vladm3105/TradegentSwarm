-- Migration 008: Parallel execution settings
-- Applied: IPLAN-003 Parallel Analysis Execution
-- Date: 2026-02-27

-- Add parallel execution settings
INSERT INTO nexus.settings (key, value, category, description)
VALUES
    ('parallel_execution_enabled', 'true', 'feature_flags', 'Enable parallel analysis execution'),
    ('parallel_fallback_to_sequential', 'true', 'feature_flags', 'Fall back to sequential on parallel failure')
ON CONFLICT (key) DO NOTHING;

-- Log migration
DO $$
BEGIN
    RAISE NOTICE 'Migration 008: Parallel execution settings applied';
END $$;
