-- Migration 014: Add section column to settings table
-- Supports Auth0 and other config sections
-- Version: 1.0.0
-- Date: 2026-03-01

BEGIN;

-- ============================================================================
-- UPDATE SETTINGS TABLE
-- ============================================================================

-- Drop the existing primary key constraint
ALTER TABLE nexus.settings DROP CONSTRAINT IF EXISTS settings_pkey;

-- Add section column
ALTER TABLE nexus.settings ADD COLUMN IF NOT EXISTS section VARCHAR(50) DEFAULT 'general';

-- Update existing keys to use section from category
UPDATE nexus.settings SET section = COALESCE(category, 'general') WHERE section IS NULL OR section = 'general';

-- Create a composite unique constraint
ALTER TABLE nexus.settings ADD CONSTRAINT settings_section_key_unique UNIQUE (section, key);

-- Add index for lookups by section
CREATE INDEX IF NOT EXISTS idx_settings_section ON nexus.settings(section);

-- ============================================================================
-- HELPER FUNCTION TO GET/SET SETTINGS
-- ============================================================================

-- Get a setting value
CREATE OR REPLACE FUNCTION nexus.get_setting(p_section VARCHAR, p_key VARCHAR)
RETURNS TEXT AS $$
DECLARE
    v_value JSONB;
BEGIN
    SELECT value INTO v_value
    FROM nexus.settings
    WHERE section = p_section AND key = p_key;

    -- Return as text (remove quotes for strings)
    IF jsonb_typeof(v_value) = 'string' THEN
        RETURN v_value #>> '{}';
    ELSE
        RETURN v_value::text;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

-- Set a setting value
CREATE OR REPLACE FUNCTION nexus.set_setting(p_section VARCHAR, p_key VARCHAR, p_value TEXT)
RETURNS VOID AS $$
BEGIN
    INSERT INTO nexus.settings (section, key, value, category)
    VALUES (p_section, p_key, to_jsonb(p_value), p_section)
    ON CONFLICT (section, key) DO UPDATE SET
        value = to_jsonb(p_value),
        updated_at = now();
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- SEED AUTH0 PLACEHOLDER SETTINGS
-- ============================================================================

INSERT INTO nexus.settings (section, key, value, category, description) VALUES
    ('auth0', 'domain', '""', 'auth0', 'Auth0 tenant domain'),
    ('auth0', 'client_id', '""', 'auth0', 'Auth0 application client ID'),
    ('auth0', 'client_secret', '""', 'auth0', 'Auth0 application client secret (encrypted)'),
    ('auth0', 'audience', '"https://tradegent-api.local"', 'auth0', 'Auth0 API audience identifier')
ON CONFLICT (section, key) DO NOTHING;

COMMIT;
