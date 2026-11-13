CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- DROP EXISTING TABLES
DROP TABLE IF EXISTS shop_order_lines CASCADE;
DROP TABLE IF EXISTS shop_orders CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS chats CASCADE;
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS donations CASCADE;
DROP TABLE IF EXISTS treby_orders CASCADE;
DROP TABLE IF EXISTS items CASCADE;
DROP TABLE IF EXISTS refresh_tokens CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- (users) Parishioners, clergy, and administrative staff
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone_number VARCHAR(20) UNIQUE,
    role VARCHAR(20) NOT NULL DEFAULT 'parishioner' CHECK(role IN ('parishioner', 'priest', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE,
    -- Registration profile for analytics (docs/registration-analytics.md). Demographics need consent.
    analytics_consent BOOLEAN NOT NULL DEFAULT FALSE,
    birth_year SMALLINT CHECK (birth_year >= 1900),
    city VARCHAR(80),
    acquisition_source VARCHAR(20) CHECK (acquisition_source IN ('friends', 'search', 'social', 'parish', 'other')),
    preferred_language VARCHAR(2) CHECK (preferred_language IN ('ru', 'en', 'be')),
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    referrer_domain VARCHAR(255),
    device_type VARCHAR(10) CHECK (device_type IN ('mobile', 'tablet', 'desktop')),
    CONSTRAINT ck_users_demographics_consent CHECK (analytics_consent OR (birth_year IS NULL AND city IS NULL))
);
-- Username keeps its case but is unique ignoring it (two concurrent sign-ups as "Olga" and "olga").
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username_lower ON users (lower(username));

-- (refresh_tokens) Login sessions behind the HttpOnly refresh cookie; only a SHA-256 of the token is stored
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);

-- (items) Orthodox church store products (candles, icons, prosphora)
CREATE TABLE IF NOT EXISTS items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(150) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL CHECK(category IN ('candle', 'icon', 'prosphora', 'incense', 'cross', 'literature')),
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
    image_url VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_available BOOLEAN DEFAULT TRUE
);

-- (shop_orders, shop_order_lines) Checked-out shop carts; stock is decreased in the same transaction
CREATE TABLE IF NOT EXISTS shop_orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_name VARCHAR(80),
    status VARCHAR(20) NOT NULL DEFAULT 'accepted',
    total NUMERIC(12, 2) NOT NULL CHECK (total >= 0),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shop_order_lines (
    line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES shop_orders(order_id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES items(item_id),
    title VARCHAR(150) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(12, 2) NOT NULL CHECK (line_total >= 0)
);

-- (treby_orders) Orthodox prayer notes (for health, repose, sorokoust)
CREATE TABLE IF NOT EXISTS treby_orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    treba_type VARCHAR(50) NOT NULL CHECK(treba_type IN ('health', 'repose', 'sorokoust', 'moleben', 'blessing')),
    commemoration_names TEXT[] NOT NULL,
    donation_amount NUMERIC(10, 2) NOT NULL DEFAULT 0.00 CHECK (donation_amount >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'submitted' CHECK(status IN ('submitted', 'accepted', 'completed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- (donations) Direct donations and targeted fundraising
CREATE TABLE IF NOT EXISTS donations (
    donation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    target_fund VARCHAR(50) NOT NULL CHECK(target_fund IN ('general', 'temple_restoration', 'choir', 'charity', 'minecraft_church')),
    payment_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(payment_status IN ('pending', 'completed', 'failed')),
    minecraft_blocks_awarded INT NOT NULL DEFAULT 0,
    transaction_reference VARCHAR(100) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- (appointments) Pastoral counseling and confession bookings
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parishioner_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    priest_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    appointment_type VARCHAR(30) NOT NULL CHECK(appointment_type IN ('confession', 'pastoral_talk', 'baptism_counseling')),
    status VARCHAR(20) NOT NULL DEFAULT 'requested' CHECK(status IN ('requested', 'approved', 'rejected', 'completed')),
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- (chats) Communication channels with a priest or AI assistant
CREATE TABLE IF NOT EXISTS chats (
    chat_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parishioner_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    priest_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    topic VARCHAR(100),
    is_ai_assistant BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_closed BOOLEAN DEFAULT FALSE
);

-- (messages) Spiritual consultation message history
CREATE TABLE IF NOT EXISTS messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
    sender_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
    text_content TEXT NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_read BOOLEAN DEFAULT FALSE
);

-- INDEXES FOR PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_treby_user_status ON treby_orders(user_id, status);
CREATE INDEX IF NOT EXISTS idx_donations_target_fund ON donations(target_fund);
CREATE INDEX IF NOT EXISTS idx_appointments_priest_date ON appointments(priest_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_order_lines_order ON shop_order_lines(order_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_sent_at ON messages(chat_id, sent_at);
