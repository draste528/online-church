-- Create DWH Schemas
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;

-- =======================================================
-- 1. STAGING LAYER (Raw ingested payloads)
-- =======================================================
CREATE TABLE IF NOT EXISTS staging.stg_donations (
    raw_id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(100),
    user_id VARCHAR(100),
    amount NUMERIC(12, 2),
    currency VARCHAR(10),
    fund_type VARCHAR(50),
    payment_method VARCHAR(50),
    raw_created_at VARCHAR(50),
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging.stg_stream_logs (
    raw_id BIGSERIAL PRIMARY KEY,
    stream_id VARCHAR(100),
    service_name VARCHAR(150),
    peak_viewers INT,
    avg_watch_time_seconds INT,
    chat_messages_count INT,
    donations_during_stream NUMERIC(12, 2),
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =======================================================
-- 2. CORE LAYER (Normalized facts and dimensions)
-- =======================================================
CREATE TABLE IF NOT EXISTS core.dim_funds (
    fund_key SERIAL PRIMARY KEY,
    fund_type VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS core.fact_donations (
    fact_id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID,
    fund_key INT REFERENCES core.dim_funds(fund_key),
    amount_base_currency NUMERIC(12, 2) NOT NULL,
    original_currency VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE IF NOT EXISTS core.fact_stream_attendance (
    fact_id BIGSERIAL PRIMARY KEY,
    stream_id VARCHAR(100) NOT NULL,
    service_name VARCHAR(150) NOT NULL,
    peak_viewers INT NOT NULL,
    avg_watch_time_seconds INT NOT NULL,
    chat_messages_count INT NOT NULL,
    donations_collected NUMERIC(12, 2) NOT NULL,
    stream_date DATE NOT NULL
);

-- =======================================================
-- 3. MARTS LAYER (Aggregated business views for reporting)
-- =======================================================
CREATE TABLE IF NOT EXISTS marts.mart_daily_finances (
    report_date DATE NOT NULL,
    fund_type VARCHAR(50) NOT NULL,
    total_amount NUMERIC(14, 2) NOT NULL,
    transaction_count INT NOT NULL,
    avg_donation NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (report_date, fund_type)
);

CREATE TABLE IF NOT EXISTS marts.mart_parishioner_activity (
    report_date DATE NOT NULL,
    active_donors_count INT NOT NULL,
    total_prayer_requests INT NOT NULL,
    total_stream_viewers INT NOT NULL,
    PRIMARY KEY (report_date)
);
