-- Migration: 020_safety_features.sql
-- Description: Add tables for alerts, notifications, and circuit breaker logging
-- Date: 2026-03-04

-- Trading mode and circuit breaker settings
ALTER TABLE nexus.settings ADD COLUMN IF NOT EXISTS
  value_type TEXT DEFAULT 'string';

-- Insert safety settings if not exist (values are JSONB - strings must be quoted)
INSERT INTO nexus.settings (section, key, value, value_type) VALUES
  ('safety', 'max_daily_loss', '"1000"', 'decimal'),
  ('safety', 'max_daily_loss_pct', '"5"', 'decimal'),
  ('safety', 'circuit_breaker_enabled', '"true"', 'boolean'),
  ('safety', 'circuit_breaker_triggered', '"false"', 'boolean'),
  ('safety', 'circuit_breaker_triggered_at', 'null', 'timestamp'),
  ('trading', 'trading_mode', '"dry_run"', 'string'),
  ('trading', 'auto_execute_enabled', '"false"', 'boolean'),
  ('trading', 'trading_paused', '"false"', 'boolean'),
  ('trading', 'trading_paused_at', 'null', 'timestamp')
ON CONFLICT (section, key) DO NOTHING;

-- Alerts table
CREATE TABLE IF NOT EXISTS nexus.alerts (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  alert_type TEXT NOT NULL CHECK (alert_type IN ('price', 'pnl', 'stop', 'target', 'expiration', 'system')),
  ticker TEXT,
  condition JSONB NOT NULL,
  is_active BOOLEAN DEFAULT true,
  is_triggered BOOLEAN DEFAULT false,
  triggered_at TIMESTAMPTZ,
  trigger_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_user_active ON nexus.alerts(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker ON nexus.alerts(ticker) WHERE ticker IS NOT NULL;

-- Notifications table
CREATE TABLE IF NOT EXISTS nexus.notifications (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('alert', 'trade', 'system', 'analysis', 'info')),
  severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
  title TEXT NOT NULL,
  message TEXT,
  data JSONB,
  is_read BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON nexus.notifications(user_id, is_read) WHERE NOT is_read;
CREATE INDEX IF NOT EXISTS idx_notifications_created ON nexus.notifications(created_at);

-- Circuit breaker log
CREATE TABLE IF NOT EXISTS nexus.circuit_breaker_log (
  id SERIAL PRIMARY KEY,
  triggered_at TIMESTAMPTZ DEFAULT NOW(),
  reason TEXT NOT NULL,
  daily_pnl DECIMAL(12,2),
  threshold DECIMAL(12,2),
  reset_at TIMESTAMPTZ,
  reset_by TEXT
);

-- Notification cleanup function (retention policy)
CREATE OR REPLACE FUNCTION nexus.cleanup_old_notifications(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM nexus.notifications
    WHERE created_at < NOW() - (retention_days || ' days')::INTERVAL
      AND is_read = true;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
