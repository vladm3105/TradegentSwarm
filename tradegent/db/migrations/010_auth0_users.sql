-- Migration 010: Auth0 Users and RBAC System
-- Creates users, roles, permissions, API keys, and sessions tables for multi-user support
-- Version: 1.0.0
-- Date: 2026-03-01

BEGIN;

-- ============================================================================
-- USERS TABLE (synced from Auth0)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.users (
    id SERIAL PRIMARY KEY,
    auth0_sub VARCHAR(255) UNIQUE NOT NULL,  -- Auth0 subject identifier
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    picture TEXT,  -- Avatar URL from Auth0

    -- Account status
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    email_verified BOOLEAN DEFAULT false,

    -- IB Account configuration (per-user)
    ib_account_id VARCHAR(50),
    ib_trading_mode VARCHAR(10) DEFAULT 'paper' CHECK (ib_trading_mode IN ('paper', 'live')),
    ib_gateway_port INTEGER,

    -- User preferences (JSON)
    preferences JSONB DEFAULT '{
        "theme": "system",
        "timezone": "America/New_York",
        "notifications_enabled": true,
        "default_analysis_type": "stock",
        "onboarding_completed": false
    }'::jsonb,

    -- Timestamps
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Create system admin user (placeholder for existing data migration)
INSERT INTO nexus.users (id, auth0_sub, email, name, is_active, is_admin, email_verified)
VALUES (1, 'system|admin', 'admin@tradegent.local', 'System Admin', true, true, true)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to start after system admin
SELECT setval('nexus.users_id_seq', GREATEST(1, (SELECT MAX(id) FROM nexus.users)));

CREATE INDEX idx_users_auth0_sub ON nexus.users(auth0_sub);
CREATE INDEX idx_users_email ON nexus.users(email);
CREATE INDEX idx_users_is_active ON nexus.users(is_active) WHERE is_active = true;

-- ============================================================================
-- ROLES TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,  -- admin, trader, analyst, viewer
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT false,  -- System roles cannot be deleted
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed default roles
INSERT INTO nexus.roles (name, display_name, description, is_system) VALUES
    ('admin', 'Administrator', 'Full system access including user management', true),
    ('trader', 'Trader', 'Can execute trades and manage portfolio', true),
    ('analyst', 'Analyst', 'Can create and manage analyses, no trading', true),
    ('viewer', 'Viewer', 'Read-only access to dashboards and analyses', true)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PERMISSIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,  -- read:portfolio, write:trades, etc.
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    resource_type VARCHAR(50),  -- portfolio, trades, analyses, watchlist, users, system
    action VARCHAR(20),  -- read, write, delete, admin
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Seed permissions
INSERT INTO nexus.permissions (code, display_name, resource_type, action, description) VALUES
    -- Portfolio permissions
    ('read:portfolio', 'View Portfolio', 'portfolio', 'read', 'View portfolio positions and P&L'),
    ('write:portfolio', 'Manage Portfolio', 'portfolio', 'write', 'Execute trades and manage positions'),

    -- Trade permissions
    ('read:trades', 'View Trades', 'trades', 'read', 'View trade history and journal'),
    ('write:trades', 'Create Trades', 'trades', 'write', 'Create trade journal entries'),

    -- Analysis permissions
    ('read:analyses', 'View Analyses', 'analyses', 'read', 'View stock and earnings analyses'),
    ('write:analyses', 'Create Analyses', 'analyses', 'write', 'Create and manage analyses'),

    -- Watchlist permissions
    ('read:watchlist', 'View Watchlist', 'watchlist', 'read', 'View watchlist entries'),
    ('write:watchlist', 'Manage Watchlist', 'watchlist', 'write', 'Add and remove watchlist entries'),

    -- Knowledge permissions
    ('read:knowledge', 'View Knowledge', 'knowledge', 'read', 'Search and view knowledge base'),
    ('write:knowledge', 'Manage Knowledge', 'knowledge', 'write', 'Create and update knowledge entries'),

    -- Admin permissions
    ('admin:users', 'Manage Users', 'users', 'admin', 'Create, update, and deactivate users'),
    ('admin:system', 'System Administration', 'system', 'admin', 'Access system settings and configuration')
ON CONFLICT (code) DO NOTHING;

-- ============================================================================
-- ROLE_PERMISSIONS (Many-to-Many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.role_permissions (
    role_id INTEGER REFERENCES nexus.roles(id) ON DELETE CASCADE,
    permission_id INTEGER REFERENCES nexus.permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

-- Assign permissions to roles
-- Admin: All permissions
INSERT INTO nexus.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM nexus.roles r, nexus.permissions p WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

-- Trader: Portfolio, trades, analyses, watchlist, knowledge (read + write)
INSERT INTO nexus.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM nexus.roles r, nexus.permissions p
WHERE r.name = 'trader' AND p.code IN (
    'read:portfolio', 'write:portfolio',
    'read:trades', 'write:trades',
    'read:analyses', 'write:analyses',
    'read:watchlist', 'write:watchlist',
    'read:knowledge', 'write:knowledge'
)
ON CONFLICT DO NOTHING;

-- Analyst: Analyses, watchlist, knowledge (read + write), portfolio/trades (read only)
INSERT INTO nexus.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM nexus.roles r, nexus.permissions p
WHERE r.name = 'analyst' AND p.code IN (
    'read:portfolio', 'read:trades',
    'read:analyses', 'write:analyses',
    'read:watchlist', 'write:watchlist',
    'read:knowledge', 'write:knowledge'
)
ON CONFLICT DO NOTHING;

-- Viewer: Read-only access to everything except admin
INSERT INTO nexus.role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM nexus.roles r, nexus.permissions p
WHERE r.name = 'viewer' AND p.code LIKE 'read:%'
ON CONFLICT DO NOTHING;

-- ============================================================================
-- USER_ROLES (Many-to-Many)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.user_roles (
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    role_id INTEGER REFERENCES nexus.roles(id) ON DELETE CASCADE,
    assigned_by INTEGER REFERENCES nexus.users(id),
    assigned_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- Assign admin role to system admin
INSERT INTO nexus.user_roles (user_id, role_id)
SELECT 1, r.id FROM nexus.roles r WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

CREATE INDEX idx_user_roles_user_id ON nexus.user_roles(user_id);

-- ============================================================================
-- API KEYS TABLE (for CLI/automation access)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL,  -- SHA-256 of the actual key
    key_prefix VARCHAR(8) NOT NULL,  -- First 8 chars for identification (tg_xxxx)
    name VARCHAR(100),  -- User-provided name for the key
    permissions TEXT[],  -- Subset of user's permissions
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_api_keys_user_id ON nexus.api_keys(user_id);
CREATE INDEX idx_api_keys_prefix ON nexus.api_keys(key_prefix);
CREATE INDEX idx_api_keys_hash ON nexus.api_keys(key_hash);

-- ============================================================================
-- USER SESSIONS TABLE (for session management)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    session_token_hash VARCHAR(64),  -- SHA-256 of session token
    device_info JSONB,  -- Browser, OS, device type
    ip_address INET,
    last_active_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_sessions_user_id ON nexus.user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires ON nexus.user_sessions(expires_at);

-- ============================================================================
-- INVITES TABLE (for invite-only registration)
-- ============================================================================

CREATE TABLE IF NOT EXISTS nexus.invites (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    email VARCHAR(255),  -- Optional: restrict to specific email
    created_by INTEGER REFERENCES nexus.users(id),
    used_by INTEGER REFERENCES nexus.users(id),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_invites_code ON nexus.invites(code);
CREATE INDEX idx_invites_email ON nexus.invites(email) WHERE email IS NOT NULL;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get user permissions
CREATE OR REPLACE FUNCTION nexus.get_user_permissions(p_user_id INTEGER)
RETURNS TEXT[] AS $$
    SELECT ARRAY_AGG(DISTINCT p.code)
    FROM nexus.user_roles ur
    JOIN nexus.role_permissions rp ON ur.role_id = rp.role_id
    JOIN nexus.permissions p ON rp.permission_id = p.id
    WHERE ur.user_id = p_user_id;
$$ LANGUAGE SQL STABLE;

-- Function to check if user has permission
CREATE OR REPLACE FUNCTION nexus.user_has_permission(p_user_id INTEGER, p_permission TEXT)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1
        FROM nexus.user_roles ur
        JOIN nexus.role_permissions rp ON ur.role_id = rp.role_id
        JOIN nexus.permissions p ON rp.permission_id = p.id
        WHERE ur.user_id = p_user_id AND p.code = p_permission
    );
$$ LANGUAGE SQL STABLE;

-- Function to get user roles
CREATE OR REPLACE FUNCTION nexus.get_user_roles(p_user_id INTEGER)
RETURNS TEXT[] AS $$
    SELECT ARRAY_AGG(r.name)
    FROM nexus.user_roles ur
    JOIN nexus.roles r ON ur.role_id = r.id
    WHERE ur.user_id = p_user_id;
$$ LANGUAGE SQL STABLE;

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION nexus.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON nexus.users
    FOR EACH ROW
    EXECUTE FUNCTION nexus.update_updated_at();

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View for user with roles and permissions
CREATE OR REPLACE VIEW nexus.v_users_with_roles AS
SELECT
    u.id,
    u.auth0_sub,
    u.email,
    u.name,
    u.picture,
    u.is_active,
    u.is_admin,
    u.email_verified,
    u.ib_account_id,
    u.ib_trading_mode,
    u.preferences,
    u.last_login_at,
    u.created_at,
    nexus.get_user_roles(u.id) as roles,
    nexus.get_user_permissions(u.id) as permissions
FROM nexus.users u;

COMMIT;
