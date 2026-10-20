-- DWH Analytics: Parishioner sessions and behavioral activity
CREATE TABLE IF NOT EXISTS analytics_user_sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_seconds INT NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    pages_visited TEXT[] NOT NULL DEFAULT '{}',
    total_donated NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total_donated >= 0),
    total_ordered NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (total_ordered >= 0),
    chat_questions_count INT NOT NULL DEFAULT 0 CHECK (chat_questions_count >= 0),
    candles_lit_count INT NOT NULL DEFAULT 0 CHECK (candles_lit_count >= 0),
    language VARCHAR(10) NOT NULL DEFAULT 'ru',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON analytics_user_sessions(started_at);
CREATE INDEX IF NOT EXISTS idx_sessions_duration ON analytics_user_sessions(duration_seconds);