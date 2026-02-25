-- Migration 007: Notification Log Table
-- Tracks sent notifications for debugging, audit, and analytics

-- Notification log table
CREATE TABLE IF NOT EXISTS nexus.notification_log (
    id SERIAL PRIMARY KEY,
    notification_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    priority VARCHAR(20),
    ticker VARCHAR(10),
    channel VARCHAR(50) NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    success BOOLEAN NOT NULL
);

-- Index for querying by ticker and time
CREATE INDEX IF NOT EXISTS idx_notification_log_ticker
ON nexus.notification_log(ticker, sent_at DESC);

-- Index for querying by event type
CREATE INDEX IF NOT EXISTS idx_notification_log_event_type
ON nexus.notification_log(event_type, sent_at DESC);

-- Index for querying failures
CREATE INDEX IF NOT EXISTS idx_notification_log_failed
ON nexus.notification_log(success) WHERE success = false;

-- Index for deduplication checks
CREATE INDEX IF NOT EXISTS idx_notification_log_notification_id
ON nexus.notification_log(notification_id);

-- Add comment
COMMENT ON TABLE nexus.notification_log IS 'Log of sent notifications for audit and debugging';

-- Default settings for notifications (inserted if not exists)
INSERT INTO nexus.settings (category, key, value, description)
VALUES
    ('feature_flags', 'notifications_enabled', 'false', 'Master enable/disable for notifications'),
    ('feature_flags', 'notification_min_priority', 'MEDIUM', 'Minimum priority to send (LOW, MEDIUM, HIGH, CRITICAL)'),
    ('feature_flags', 'notification_rate_limit', '1.0', 'Notifications per second'),
    ('feature_flags', 'notification_rate_burst', '5', 'Burst capacity for rate limiter'),
    ('feature_flags', 'webhook_url', '', 'Generic webhook URL for notifications'),
    ('feature_flags', 'webhook_headers', '{}', 'JSON string of auth headers for webhook')
ON CONFLICT (category, key) DO NOTHING;

-- Retention policy: Delete logs older than 30 days
-- Run this periodically via cron or pg_cron:
-- DELETE FROM nexus.notification_log WHERE sent_at < now() - interval '30 days';
