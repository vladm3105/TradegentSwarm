-- Migration: 015_agent_sessions
-- Description: Create tables for Agent UI chat sessions and messages
-- Date: 2026-03-02

BEGIN;

-- Record migration
INSERT INTO nexus.migrations (id, description)
VALUES ('015_agent_sessions', 'Agent UI chat sessions and messages')
ON CONFLICT (id) DO NOTHING;

-- Agent chat sessions
CREATE TABLE IF NOT EXISTS nexus.agent_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL UNIQUE,
    user_id INTEGER REFERENCES nexus.users(id) ON DELETE CASCADE,
    title VARCHAR(255),                        -- Auto-generated or user-defined
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_archived BOOLEAN NOT NULL DEFAULT false,
    message_count INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb         -- Extra session data
);

CREATE INDEX idx_agent_sessions_user ON nexus.agent_sessions(user_id, created_at DESC);
CREATE INDEX idx_agent_sessions_archived ON nexus.agent_sessions(user_id, is_archived, updated_at DESC);

-- Agent chat messages
CREATE TABLE IF NOT EXISTS nexus.agent_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES nexus.agent_sessions(id) ON DELETE CASCADE,
    message_id VARCHAR(100) NOT NULL,          -- Client-generated ID
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'complete' CHECK (status IN ('pending', 'streaming', 'complete', 'error')),
    error TEXT,
    a2ui JSONB,                                -- A2UI response data
    task_id VARCHAR(100),                      -- Associated task ID
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX idx_agent_messages_session ON nexus.agent_messages(session_id, created_at);
CREATE INDEX idx_agent_messages_message_id ON nexus.agent_messages(message_id);

-- Update session updated_at and message_count on message insert
CREATE OR REPLACE FUNCTION nexus.update_session_on_message()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE nexus.agent_sessions
    SET updated_at = now(),
        message_count = message_count + 1
    WHERE id = NEW.session_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_session_on_message
    AFTER INSERT ON nexus.agent_messages
    FOR EACH ROW
    EXECUTE FUNCTION nexus.update_session_on_message();

-- Auto-generate session title from first user message
CREATE OR REPLACE FUNCTION nexus.auto_title_session()
RETURNS TRIGGER AS $$
BEGIN
    -- Only set title if it's the first user message and title is empty
    IF NEW.role = 'user' THEN
        UPDATE nexus.agent_sessions
        SET title = COALESCE(
            NULLIF(title, ''),
            LEFT(NEW.content, 100)
        )
        WHERE id = NEW.session_id AND (title IS NULL OR title = '');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auto_title_session
    AFTER INSERT ON nexus.agent_messages
    FOR EACH ROW
    EXECUTE FUNCTION nexus.auto_title_session();

COMMIT;
