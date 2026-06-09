-- 04_audit.sql
-- Audit schema: agent sessions, decisions, query history, LLM calls

CREATE TABLE IF NOT EXISTS audit.agent_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    llm_provider VARCHAR(50),
    llm_model   VARCHAR(100),
    status      VARCHAR(20) DEFAULT 'running',
    error_text  TEXT
);

CREATE TABLE IF NOT EXISTS audit.agent_decisions (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID REFERENCES audit.agent_sessions(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    step_name       VARCHAR(100),
    tool_name       VARCHAR(100),
    input_summary   TEXT,
    output_summary  TEXT,
    duration_ms     INTEGER,
    success         BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS audit.query_history (
    id               BIGSERIAL PRIMARY KEY,
    session_id       UUID REFERENCES audit.agent_sessions(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    query_text       TEXT NOT NULL,
    query_hash       VARCHAR(64),
    execution_time_ms INTEGER,
    blocked          BOOLEAN DEFAULT FALSE,
    block_reason     TEXT,
    db_user          VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS audit.llm_calls (
    id               BIGSERIAL PRIMARY KEY,
    session_id       UUID REFERENCES audit.agent_sessions(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    prompt_name      VARCHAR(100),
    prompt_file      VARCHAR(200),
    prompt_hash      VARCHAR(64),
    response_summary TEXT,
    tokens_input     INTEGER,
    tokens_output    INTEGER,
    duration_ms      INTEGER
);

-- Indexes for common query patterns
CREATE INDEX idx_agent_sessions_created_at ON audit.agent_sessions (created_at DESC);
CREATE INDEX idx_agent_decisions_session_created ON audit.agent_decisions (session_id, created_at);
CREATE INDEX idx_query_history_session ON audit.query_history (session_id);
CREATE INDEX idx_query_history_hash ON audit.query_history (query_hash);
CREATE INDEX idx_llm_calls_session ON audit.llm_calls (session_id);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA audit TO srag_app;
GRANT USAGE ON SCHEMA audit TO srag_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT, INSERT, UPDATE ON TABLES TO srag_app;