-- Ayaka Sync API — initial schema
-- Non-destructive: only CREATE ... IF NOT EXISTS statements.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- users
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(32)  NOT NULL,
    email           VARCHAR(254) NOT NULL,
    password_hash   TEXT         NOT NULL,
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT users_username_format CHECK (username ~ '^[a-zA-Z0-9_.-]{3,32}$'),
    CONSTRAINT users_email_format CHECK (position('@' in email) > 1)
);
CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_uq ON users (lower(username));
CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_uq ON users (lower(email));

-- -------------------------------------------------------- user_sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      CHAR(64)    NOT NULL,
    user_agent      VARCHAR(300),
    ip_address      VARCHAR(64),
    remember_me     BOOLEAN     NOT NULL DEFAULT FALSE,
    expires_at      TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS user_sessions_token_hash_uq ON user_sessions (token_hash);
CREATE INDEX IF NOT EXISTS user_sessions_user_idx ON user_sessions (user_id, created_at DESC);

-- ------------------------------------------------------------- api_keys
CREATE TABLE IF NOT EXISTS api_keys (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name              VARCHAR(80)  NOT NULL,
    description       VARCHAR(500) NOT NULL DEFAULT '',
    key_prefix        VARCHAR(32)  NOT NULL,
    key_hash          CHAR(64)     NOT NULL,
    environment       VARCHAR(16)  NOT NULL,
    permissions       TEXT[]       NOT NULL DEFAULT ARRAY['read']::TEXT[],
    allowed_endpoints TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    status            VARCHAR(16)  NOT NULL DEFAULT 'active',
    rate_limit        INTEGER      NOT NULL DEFAULT 60,
    expires_at        TIMESTAMPTZ,
    last_used_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    revoked_at        TIMESTAMPTZ,
    CONSTRAINT api_keys_environment_ck CHECK (environment IN ('development', 'production')),
    CONSTRAINT api_keys_status_ck CHECK (status IN ('active', 'disabled', 'revoked')),
    CONSTRAINT api_keys_rate_limit_ck CHECK (rate_limit BETWEEN 1 AND 10000),
    CONSTRAINT api_keys_permissions_ck CHECK (
        permissions <@ ARRAY['read','write','delete','analytics','profile','admin']::TEXT[]
        AND cardinality(permissions) >= 1
    ),
    CONSTRAINT api_keys_revoked_ck CHECK (status <> 'revoked' OR revoked_at IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_hash_uq ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS api_keys_user_idx ON api_keys (user_id, created_at DESC);

-- ------------------------------------------------------------ api_usage
CREATE TABLE IF NOT EXISTS api_usage (
    id               BIGSERIAL PRIMARY KEY,
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key_id       UUID         REFERENCES api_keys(id) ON DELETE SET NULL,
    api_key_name     VARCHAR(80),
    request_id       VARCHAR(40)  NOT NULL,
    endpoint         VARCHAR(255) NOT NULL,
    method           VARCHAR(10)  NOT NULL,
    status_code      SMALLINT     NOT NULL,
    response_time_ms INTEGER      NOT NULL,
    ip_address       VARCHAR(64),
    user_agent       VARCHAR(300),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT api_usage_status_ck CHECK (status_code BETWEEN 100 AND 599),
    CONSTRAINT api_usage_rt_ck CHECK (response_time_ms >= 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS api_usage_request_id_uq ON api_usage (request_id);
CREATE INDEX IF NOT EXISTS api_usage_user_time_idx ON api_usage (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS api_usage_key_time_idx ON api_usage (api_key_id, created_at DESC);

-- -------------------------------------------------------- activity_logs
CREATE TABLE IF NOT EXISTS activity_logs (
    id           BIGSERIAL PRIMARY KEY,
    user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type   VARCHAR(48) NOT NULL,
    description  VARCHAR(500) NOT NULL,
    metadata     JSONB       NOT NULL DEFAULT '{}'::JSONB,
    ip_address   VARCHAR(64),
    user_agent   VARCHAR(300),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS activity_logs_user_time_idx ON activity_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS activity_logs_event_idx ON activity_logs (user_id, event_type);

-- Audit log is append-only: block UPDATE at the database level.
CREATE OR REPLACE FUNCTION activity_logs_block_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'activity_logs is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS activity_logs_no_update ON activity_logs;
CREATE TRIGGER activity_logs_no_update BEFORE UPDATE ON activity_logs
    FOR EACH ROW EXECUTE FUNCTION activity_logs_block_update();

-- -------------------------------------------------------- user_settings
CREATE TABLE IF NOT EXISTS user_settings (
    id             BIGSERIAL PRIMARY KEY,
    user_id        UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    setting_key    VARCHAR(64) NOT NULL,
    setting_value  JSONB       NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT user_settings_user_key_uq UNIQUE (user_id, setting_key)
);

-- --------------------------------------------------- rate_limit_buckets
-- Shared fixed-window counters so limits hold across many serverless instances.
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
    bucket_key    VARCHAR(160) NOT NULL,
    window_start  TIMESTAMPTZ  NOT NULL,
    count         INTEGER      NOT NULL DEFAULT 0,
    expires_at    TIMESTAMPTZ  NOT NULL,
    PRIMARY KEY (bucket_key, window_start)
);
CREATE INDEX IF NOT EXISTS rate_limit_buckets_expires_idx ON rate_limit_buckets (expires_at);

-- --------------------------------------------------------- user_records
-- Small JSON document store exposed through API keys (read/write/delete).
CREATE TABLE IF NOT EXISTS user_records (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    collection  VARCHAR(64)  NOT NULL DEFAULT 'default',
    data        JSONB        NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT user_records_collection_ck CHECK (collection ~ '^[a-z0-9_-]{1,64}$')
);
CREATE INDEX IF NOT EXISTS user_records_user_idx ON user_records (user_id, collection, created_at DESC);
