-- Tradegent Agent UI Database Schema
-- Run this against the tradegent database

-- Create schema
CREATE SCHEMA IF NOT EXISTS agent_ui;

-- Sessions table - tracks conversation sessions
CREATE TABLE IF NOT EXISTS agent_ui.sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    conversation_state JSONB DEFAULT '{}'::JSONB,
    metadata JSONB DEFAULT '{}'::JSONB
);

-- Messages table - stores conversation history
CREATE TABLE IF NOT EXISTS agent_ui.messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES agent_ui.sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    intent VARCHAR(50),
    tickers TEXT[],
    a2ui_components JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tool calls log - tracks all MCP tool executions
CREATE TABLE IF NOT EXISTS agent_ui.tool_calls (
    call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES agent_ui.sessions(session_id) ON DELETE CASCADE,
    message_id UUID REFERENCES agent_ui.messages(message_id) ON DELETE SET NULL,
    agent_type VARCHAR(50) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    mcp_server VARCHAR(50),
    params JSONB,
    result JSONB,
    error TEXT,
    duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks table - tracks long-running tasks
CREATE TABLE IF NOT EXISTS agent_ui.tasks (
    task_id UUID PRIMARY KEY,
    session_id UUID REFERENCES agent_ui.sessions(session_id) ON DELETE CASCADE,
    intent VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    tickers TEXT[],
    state VARCHAR(20) NOT NULL DEFAULT 'pending',
    progress INT DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    messages TEXT[],
    result JSONB,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Performance metrics - for monitoring and optimization
CREATE TABLE IF NOT EXISTS agent_ui.metrics (
    metric_id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES agent_ui.sessions(session_id) ON DELETE CASCADE,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_sessions_user ON agent_ui.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON agent_ui.sessions(last_activity);
CREATE INDEX IF NOT EXISTS idx_messages_session ON agent_ui.messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_intent ON agent_ui.messages(intent);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON agent_ui.tool_calls(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_tool ON agent_ui.tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON agent_ui.tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_state ON agent_ui.tasks(state);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON agent_ui.metrics(metric_type, created_at);

-- Views for common queries

-- Active sessions (last 24 hours)
CREATE OR REPLACE VIEW agent_ui.v_active_sessions AS
SELECT
    s.session_id,
    s.user_id,
    s.created_at,
    s.last_activity,
    COUNT(DISTINCT m.message_id) AS message_count,
    COUNT(DISTINCT t.call_id) AS tool_call_count
FROM agent_ui.sessions s
LEFT JOIN agent_ui.messages m ON s.session_id = m.session_id
LEFT JOIN agent_ui.tool_calls t ON s.session_id = t.session_id
WHERE s.last_activity > NOW() - INTERVAL '24 hours'
GROUP BY s.session_id;

-- Tool call statistics
CREATE OR REPLACE VIEW agent_ui.v_tool_stats AS
SELECT
    tool_name,
    mcp_server,
    agent_type,
    COUNT(*) AS call_count,
    AVG(duration_ms) AS avg_duration_ms,
    COUNT(*) FILTER (WHERE error IS NOT NULL) AS error_count,
    MAX(created_at) AS last_called
FROM agent_ui.tool_calls
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY tool_name, mcp_server, agent_type
ORDER BY call_count DESC;

-- Intent distribution
CREATE OR REPLACE VIEW agent_ui.v_intent_distribution AS
SELECT
    intent,
    DATE(created_at) AS date,
    COUNT(*) AS count
FROM agent_ui.messages
WHERE role = 'user' AND intent IS NOT NULL
GROUP BY intent, DATE(created_at)
ORDER BY date DESC, count DESC;

-- Task performance
CREATE OR REPLACE VIEW agent_ui.v_task_performance AS
SELECT
    DATE(created_at) AS date,
    state,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) AS avg_duration_seconds
FROM agent_ui.tasks
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at), state
ORDER BY date DESC;

-- Functions

-- Update session last_activity
CREATE OR REPLACE FUNCTION agent_ui.touch_session(p_session_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE agent_ui.sessions
    SET last_activity = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Cleanup old sessions
CREATE OR REPLACE FUNCTION agent_ui.cleanup_old_sessions(p_max_age_hours INT DEFAULT 168)
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM agent_ui.sessions
    WHERE last_activity < NOW() - (p_max_age_hours || ' hours')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Record a metric
CREATE OR REPLACE FUNCTION agent_ui.record_metric(
    p_session_id UUID,
    p_metric_type VARCHAR(50),
    p_metric_name VARCHAR(100),
    p_metric_value NUMERIC,
    p_metadata JSONB DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO agent_ui.metrics (session_id, metric_type, metric_name, metric_value, metadata)
    VALUES (p_session_id, p_metric_type, p_metric_name, p_metric_value, p_metadata);
END;
$$ LANGUAGE plpgsql;

COMMENT ON SCHEMA agent_ui IS 'Tradegent Agent UI session and conversation tracking';
COMMENT ON TABLE agent_ui.sessions IS 'User sessions for the agent UI';
COMMENT ON TABLE agent_ui.messages IS 'Conversation message history';
COMMENT ON TABLE agent_ui.tool_calls IS 'MCP tool execution log';
COMMENT ON TABLE agent_ui.tasks IS 'Long-running task tracking';
COMMENT ON TABLE agent_ui.metrics IS 'Performance and usage metrics';
