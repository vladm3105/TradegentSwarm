-- Migration 023: Named watchlists
-- Adds watchlist containers and links existing watchlist entries to them.

CREATE TABLE IF NOT EXISTS nexus.watchlists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    source_type VARCHAR(20) NOT NULL DEFAULT 'manual',
    source_ref VARCHAR(100),
    color VARCHAR(7) DEFAULT '#3b82f6',
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_pinned BOOLEAN NOT NULL DEFAULT false,
    user_id INTEGER REFERENCES nexus.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_watchlists_source_type CHECK (source_type IN ('manual', 'scanner', 'auto')),
    CONSTRAINT chk_watchlists_color CHECK (color IS NULL OR color ~ '^#[0-9A-Fa-f]{6}$')
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_name_unique ON nexus.watchlists(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_default_unique ON nexus.watchlists(is_default) WHERE is_default = true;
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlists_source_unique ON nexus.watchlists(source_type, source_ref) WHERE source_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_watchlists_source_type ON nexus.watchlists(source_type);

DROP TRIGGER IF EXISTS watchlists_updated_at ON nexus.watchlists;
CREATE TRIGGER watchlists_updated_at BEFORE UPDATE ON nexus.watchlists
    FOR EACH ROW EXECUTE FUNCTION nexus.update_timestamp();

COMMENT ON TABLE nexus.watchlists IS 'Named watchlist containers for manual, scanner, and automatic watch entries.';

ALTER TABLE nexus.watchlist
    ADD COLUMN IF NOT EXISTS watchlist_id INTEGER REFERENCES nexus.watchlists(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_watchlist_watchlist_id ON nexus.watchlist(watchlist_id);

INSERT INTO nexus.watchlists (name, description, source_type, source_ref, color, is_default, is_pinned)
SELECT
    'Analysis Signals',
    'Automatic watchlist entries created from WATCH recommendations in completed analyses.',
    'auto',
    'analysis-watch',
    '#3b82f6',
    true,
    true
WHERE NOT EXISTS (
    SELECT 1 FROM nexus.watchlists WHERE source_type = 'auto' AND source_ref = 'analysis-watch'
);

UPDATE nexus.watchlist
SET watchlist_id = (
    SELECT id FROM nexus.watchlists WHERE source_type = 'auto' AND source_ref = 'analysis-watch'
)
WHERE watchlist_id IS NULL AND source = 'analysis';
