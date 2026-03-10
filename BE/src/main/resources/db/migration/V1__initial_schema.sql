CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    age SMALLINT,
    gender VARCHAR(1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_users_user_id UNIQUE (user_id),
    CONSTRAINT chk_users_age CHECK (age IS NULL OR age BETWEEN 0 AND 120),
    CONSTRAINT chk_users_gender CHECK (gender IS NULL OR gender IN ('M', 'F'))
);

CREATE TABLE IF NOT EXISTS hairs (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    category VARCHAR(50) NOT NULL,
    preview_image_url VARCHAR(500),
    description TEXT,
    like_count INTEGER NOT NULL DEFAULT 0,
    view_count INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hair_likes (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    hair_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_hair_likes_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_hair_likes_hair FOREIGN KEY (hair_id) REFERENCES hairs (id) ON DELETE CASCADE,
    CONSTRAINT uq_hair_likes_user_hair UNIQUE (user_id, hair_id)
);

CREATE TABLE IF NOT EXISTS histories (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    hair_id BIGINT NOT NULL,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    view_seconds INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT fk_histories_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_histories_hair FOREIGN KEY (hair_id) REFERENCES hairs (id) ON DELETE CASCADE,
    CONSTRAINT chk_histories_view_seconds CHECK (view_seconds >= 0)
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    user_id BIGINT,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL,
    request_payload JSONB,
    result_payload JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    CONSTRAINT fk_jobs_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ads (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    image_url VARCHAR(500),
    target_url VARCHAR(500),
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_created_at ON users (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_hairs_category_active ON hairs (category, is_active);
CREATE INDEX IF NOT EXISTS idx_histories_user_viewed_at ON histories (user_id, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at ON jobs (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ads_active_order ON ads (is_active, display_order ASC);
