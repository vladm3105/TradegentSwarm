-- Migration 004: Add retry support to task_queue
-- Run: python scripts/apply_migration.py 004

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM nexus.migrations WHERE id = '004') THEN
        RAISE EXCEPTION 'Migration 004 already applied';
    END IF;
END $$;

-- Add retry columns
ALTER TABLE nexus.task_queue
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_retries INTEGER DEFAULT 3,
ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ;

-- Index for retry queries
CREATE INDEX IF NOT EXISTS idx_task_queue_retry
ON nexus.task_queue(next_retry_at)
WHERE status = 'failed' AND next_retry_at IS NOT NULL;

-- Add task timeout and retry settings
INSERT INTO nexus.settings (key, value, category, description) VALUES
    ('task_timeout_minutes', '30', 'scheduler', 'Minutes before stuck running task is reset'),
    ('task_retry_delay_minutes', '15', 'scheduler', 'Base delay between task retries'),
    ('max_tasks_per_tick', '3', 'scheduler', 'Max tasks to process per service tick')
ON CONFLICT (key) DO NOTHING;

INSERT INTO nexus.migrations (id, description) VALUES ('004', 'Add retry support to task_queue');
