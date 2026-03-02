-- Migration 013: Audit Log Table
-- Creates audit logging for user actions and GDPR compliance
-- Version: 1.0.0
-- Date: 2026-03-01

BEGIN;

-- ============================================================================
-- AUDIT LOG TABLE (update existing or create new)
-- ============================================================================

-- Add user_id column if it doesn't exist
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'nexus' AND table_name = 'audit_log') THEN
        -- Add user_id to existing table
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nexus' AND table_name = 'audit_log' AND column_name = 'user_id') THEN
            ALTER TABLE nexus.audit_log ADD COLUMN user_id INTEGER REFERENCES nexus.users(id) ON DELETE SET NULL;
        END IF;
        -- Add created_at if timestamp column exists but created_at doesn't
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nexus' AND table_name = 'audit_log' AND column_name = 'created_at') THEN
            IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'nexus' AND table_name = 'audit_log' AND column_name = 'timestamp') THEN
                ALTER TABLE nexus.audit_log RENAME COLUMN timestamp TO created_at;
            ELSE
                ALTER TABLE nexus.audit_log ADD COLUMN created_at TIMESTAMPTZ DEFAULT now();
            END IF;
        END IF;
    ELSE
        -- Create new table
        CREATE TABLE nexus.audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES nexus.users(id) ON DELETE SET NULL,
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50),
            resource_id VARCHAR(100),
            details JSONB,
            ip_address INET,
            user_agent TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        );
    END IF;
END $$;

-- Indexes for common query patterns (create if not exists)
CREATE INDEX IF NOT EXISTS idx_audit_log_user_time ON nexus.audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON nexus.audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON nexus.audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON nexus.audit_log(created_at DESC);

-- Partition by month for better performance (optional, for large deployments)
-- For now, using a single table with indexes

-- ============================================================================
-- AUDIT LOG ACTIONS REFERENCE
-- ============================================================================

COMMENT ON TABLE nexus.audit_log IS 'Tracks all user actions for auditing and GDPR compliance';

COMMENT ON COLUMN nexus.audit_log.action IS '
Common actions:
- auth.login, auth.logout, auth.failed_login
- user.create, user.update, user.deactivate, user.delete_data
- analysis.create, analysis.update, analysis.delete
- trade.execute, trade.journal_create, trade.journal_update
- watchlist.add, watchlist.remove, watchlist.trigger
- portfolio.view, portfolio.export
- api_key.create, api_key.revoke, api_key.use
- admin.user_role_change, admin.user_deactivate
';

-- ============================================================================
-- AUDIT LOG HELPER FUNCTIONS
-- ============================================================================

-- Function to log an action
CREATE OR REPLACE FUNCTION nexus.log_audit(
    p_user_id INTEGER,
    p_action VARCHAR(100),
    p_resource_type VARCHAR(50) DEFAULT NULL,
    p_resource_id VARCHAR(100) DEFAULT NULL,
    p_details JSONB DEFAULT NULL,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_id BIGINT;
BEGIN
    INSERT INTO nexus.audit_log (
        user_id, action, resource_type, resource_id, details, ip_address, user_agent
    ) VALUES (
        p_user_id, p_action, p_resource_type, p_resource_id, p_details, p_ip_address, p_user_agent
    ) RETURNING id INTO v_id;

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get user audit history
CREATE OR REPLACE FUNCTION nexus.get_user_audit_history(
    p_user_id INTEGER,
    p_limit INTEGER DEFAULT 100,
    p_offset INTEGER DEFAULT 0
) RETURNS TABLE (
    id BIGINT,
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT al.id, al.action, al.resource_type, al.resource_id, al.details, al.ip_address, al.created_at
    FROM nexus.audit_log al
    WHERE al.user_id = p_user_id
    ORDER BY al.created_at DESC
    LIMIT p_limit OFFSET p_offset;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- GDPR DATA DELETION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.gdpr_deletion_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,  -- No FK since user will be deleted
    user_email VARCHAR(255) NOT NULL,
    requested_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,
    processed_by INTEGER REFERENCES nexus.users(id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    tables_cleared TEXT[],  -- List of tables that were cleared
    error_message TEXT
);

CREATE INDEX idx_gdpr_deletion_status ON nexus.gdpr_deletion_requests(status);

-- ============================================================================
-- LOGIN HISTORY (for security)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    success BOOLEAN NOT NULL,
    ip_address INET,
    user_agent TEXT,
    location JSONB,  -- GeoIP data if available
    failure_reason VARCHAR(100),  -- invalid_password, account_locked, etc.
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_login_history_user ON nexus.login_history(user_id, created_at DESC);
CREATE INDEX idx_login_history_ip ON nexus.login_history(ip_address);
CREATE INDEX idx_login_history_failed ON nexus.login_history(ip_address, created_at DESC)
    WHERE success = false;

-- Function to check for brute force attempts
CREATE OR REPLACE FUNCTION nexus.check_brute_force(
    p_ip_address INET,
    p_window_minutes INTEGER DEFAULT 15,
    p_max_attempts INTEGER DEFAULT 5
) RETURNS BOOLEAN AS $$
DECLARE
    v_failed_attempts INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_failed_attempts
    FROM nexus.login_history
    WHERE ip_address = p_ip_address
      AND success = false
      AND created_at > (now() - (p_window_minutes || ' minutes')::INTERVAL);

    RETURN v_failed_attempts >= p_max_attempts;
END;
$$ LANGUAGE plpgsql STABLE;

-- ============================================================================
-- VIEWS
-- ============================================================================

-- Recent audit activity
CREATE OR REPLACE VIEW nexus.v_recent_audit_activity AS
SELECT
    al.id,
    al.user_id,
    u.email as user_email,
    u.name as user_name,
    al.action,
    al.resource_type,
    al.resource_id,
    al.details,
    al.ip_address,
    al.created_at
FROM nexus.audit_log al
LEFT JOIN nexus.users u ON al.user_id = u.id
ORDER BY al.created_at DESC
LIMIT 1000;

-- Failed login attempts summary
CREATE OR REPLACE VIEW nexus.v_failed_login_summary AS
SELECT
    ip_address,
    COUNT(*) as failed_attempts,
    MAX(created_at) as last_attempt,
    MIN(created_at) as first_attempt
FROM nexus.login_history
WHERE success = false
  AND created_at > (now() - INTERVAL '24 hours')
GROUP BY ip_address
HAVING COUNT(*) >= 3
ORDER BY failed_attempts DESC;

COMMIT;
