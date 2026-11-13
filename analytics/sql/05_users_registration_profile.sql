-- Registration profile for analytics (docs/registration-analytics.md).
-- Safe to run repeatedly on an existing database: every change is IF NOT EXISTS.
--   docker compose exec -T postgres_dwh psql -U church_admin -d church_dwh < analytics/sql/05_users_registration_profile.sql
-- The backend (User model) must write these columns; the analytics endpoint picks them up automatically.

-- Asked in the registration form (demographics are stored only when analytics_consent is true)
ALTER TABLE users ADD COLUMN IF NOT EXISTS analytics_consent BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_year SMALLINT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS city VARCHAR(80);
ALTER TABLE users ADD COLUMN IF NOT EXISTS acquisition_source VARCHAR(20);
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(2);

-- Collected automatically by the frontend at sign-up (no personal data)
ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_source VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_medium VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS utm_campaign VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS referrer_domain VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS device_type VARCHAR(10);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_birth_year') THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_birth_year
            CHECK (birth_year IS NULL OR birth_year BETWEEN 1900 AND 2100);  -- the minimum age (14) is checked by the backend
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_acquisition_source') THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_acquisition_source
            CHECK (acquisition_source IS NULL
                   OR acquisition_source IN ('friends', 'search', 'social', 'parish', 'other'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_preferred_language') THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_preferred_language
            CHECK (preferred_language IS NULL OR preferred_language IN ('ru', 'en', 'be'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_device_type') THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_device_type
            CHECK (device_type IS NULL OR device_type IN ('mobile', 'tablet', 'desktop'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_demographics_consent') THEN
        ALTER TABLE users ADD CONSTRAINT ck_users_demographics_consent
            CHECK (analytics_consent OR (birth_year IS NULL AND city IS NULL));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at);

-- Also brings an existing database up to the auth schema of BE-001 (PR #10): case-insensitive usernames
-- and login sessions behind the HttpOnly refresh cookie (the backend creates refresh_tokens itself too).
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (lower(username));
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
